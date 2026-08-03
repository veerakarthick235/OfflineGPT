"""
HuggingFace Diffusers provider — runs entirely in-process.
No external servers required.

Lazy-loads the pipeline on first use; can be unloaded to free memory.
Supports both CPU (float32) and CUDA (float16).
"""
from __future__ import annotations
import asyncio
import random
import uuid
from pathlib import Path
from typing import Optional

from .base import ImageProvider, ImageResult
from .models_catalog import CATALOG_MAP, ModelEntry

# Lazy imports — avoids crashing if torch/diffusers aren't installed yet
_diffusers_ok: Optional[bool] = None


def _check_diffusers() -> bool:
    global _diffusers_ok
    if _diffusers_ok is not None:
        return _diffusers_ok
    try:
        import diffusers  # noqa
        import torch      # noqa
        _diffusers_ok = True
    except ImportError:
        _diffusers_ok = False
    return _diffusers_ok


def _get_torch_device():
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda", "float16"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps", "float16"
    except ImportError:
        pass
    return "cpu", "float32"


class DiffusersProvider(ImageProvider):
    name = "diffusers"

    def __init__(self, models_dir: Path):
        self.models_dir = models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._pipeline = None       # loaded pipeline object
        self._loaded_model_id = ""  # which model is loaded

    # ── availability ────────────────────────────────────────────────

    async def is_available(self) -> bool:
        return _check_diffusers()

    @property
    def loaded_model_id(self) -> str:
        return self._loaded_model_id

    def is_model_downloaded(self, model_id: str) -> bool:
        model_path = self.models_dir / model_id
        # Check for any safetensors / bin file inside the directory
        if model_path.exists():
            for ext in ("*.safetensors", "*.bin"):
                if any(model_path.rglob(ext)):
                    return True
        return False

    def model_disk_size(self, model_id: str) -> int:
        """Return total bytes used on disk by a model, or 0 if not downloaded."""
        model_path = self.models_dir / model_id
        if not model_path.exists():
            return 0
        return sum(f.stat().st_size for f in model_path.rglob("*") if f.is_file())

    # ── load / unload ────────────────────────────────────────────────

    async def load_model(self, model_id: str) -> None:
        """Load pipeline into memory (blocking; run in thread pool)."""
        if self._loaded_model_id == model_id and self._pipeline is not None:
            return
        await asyncio.get_event_loop().run_in_executor(None, self._load_sync, model_id)

    def _load_sync(self, model_id: str) -> None:
        import torch

        entry: ModelEntry | None = CATALOG_MAP.get(model_id)
        if entry is None:
            raise ValueError(f"Unknown model id: {model_id}")

        model_path = self.models_dir / model_id
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model '{model_id}' not found at {model_path}. "
                "Please download it first via the Model Manager."
            )

        device, dtype_str = _get_torch_device()
        torch_dtype = torch.float16 if dtype_str == "float16" else torch.float32

        print(f"[ImageGen] Loading '{model_id}' on {device} ({dtype_str})…")

        # Unload previous
        self._unload_sync()

        # Build pipeline
        pipeline_cls_name = entry.pipeline_type
        if pipeline_cls_name == "AutoPipelineForText2Image":
            from diffusers import AutoPipelineForText2Image as PipelineCls
        elif pipeline_cls_name == "StableDiffusionXLPipeline":
            from diffusers import StableDiffusionXLPipeline as PipelineCls
        else:
            from diffusers import StableDiffusionPipeline as PipelineCls

        pipe = PipelineCls.from_pretrained(
            str(model_path),
            torch_dtype=torch_dtype,
            safety_checker=None,         # saves ~1.2 GB for SD 1.5
            requires_safety_checker=False,
            local_files_only=True,
        )
        pipe = pipe.to(device)

        # Memory optimisations
        try:
            pipe.enable_attention_slicing()
        except Exception:
            pass
        if device == "cuda":
            try:
                pipe.enable_model_cpu_offload()
            except Exception:
                pass

        self._pipeline = pipe
        self._loaded_model_id = model_id
        print(f"[ImageGen] '{model_id}' loaded successfully.")

    def unload_model(self) -> None:
        self._unload_sync()

    def _unload_sync(self) -> None:
        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None
            self._loaded_model_id = ""
            try:
                import torch, gc
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
            print("[ImageGen] Pipeline unloaded.")

    # ── download ─────────────────────────────────────────────────────

    async def download_model(self, model_id: str, progress_cb=None) -> None:
        """Download model from HuggingFace Hub into models_dir/model_id."""
        entry = CATALOG_MAP.get(model_id)
        if entry is None:
            raise ValueError(f"Unknown model id: {model_id}")
        await asyncio.get_event_loop().run_in_executor(
            None, self._download_sync, entry, progress_cb
        )

    def _download_sync(self, entry: ModelEntry, progress_cb=None) -> None:
        from huggingface_hub import snapshot_download
        import os

        dest = str(self.models_dir / entry.id)
        print(f"[ImageGen] Downloading {entry.hf_repo} → {dest}")

        ignore = [
            "*.ckpt",           # skip legacy checkpoints — use safetensors
            "flax_model*",
            "tf_model*",
            "*.msgpack",
            "onnx*",
        ]

        snapshot_download(
            repo_id      = entry.hf_repo,
            local_dir    = dest,
            ignore_patterns = ignore,
        )
        print(f"[ImageGen] Download complete: {entry.id}")
        if progress_cb:
            progress_cb(100)

    def delete_model(self, model_id: str) -> None:
        """Remove model files from disk."""
        import shutil
        model_path = self.models_dir / model_id
        if model_path.exists():
            if self._loaded_model_id == model_id:
                self._unload_sync()
            shutil.rmtree(model_path)
            print(f"[ImageGen] Deleted model: {model_id}")

    # ── generate ─────────────────────────────────────────────────────

    async def generate(
        self,
        prompt:          str,
        negative_prompt: str   = "",
        width:           int   = 512,
        height:          int   = 512,
        steps:           int   = 20,
        cfg_scale:       float = 7.0,
        seed:            int   = -1,
        model_id:        str   = "",
        output_path:     Path  = Path("."),
    ) -> ImageResult:
        if not self._pipeline:
            raise RuntimeError(
                "No model loaded. Download and load a model via the Model Manager first."
            )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._generate_sync,
            prompt, negative_prompt, width, height,
            steps, cfg_scale, seed, output_path,
        )
        return result

    def _generate_sync(
        self, prompt, negative_prompt, width, height,
        steps, cfg_scale, seed, output_path: Path,
    ) -> ImageResult:
        import torch

        actual_seed = seed if seed >= 0 else random.randint(0, 2**32 - 1)
        generator = torch.Generator().manual_seed(actual_seed)

        filename = f"{uuid.uuid4().hex}.png"
        out_file = output_path / filename

        # SDXL Turbo uses guidance_scale=0 and steps=4 by default
        is_turbo = "turbo" in self._loaded_model_id.lower()
        kwargs = dict(
            prompt            = prompt,
            negative_prompt   = negative_prompt if not is_turbo else None,
            width             = width,
            height            = height,
            num_inference_steps = steps,
            generator         = generator,
        )
        if not is_turbo:
            kwargs["guidance_scale"] = cfg_scale

        print(f"[ImageGen] Generating: '{prompt[:60]}…'")
        result = self._pipeline(**{k: v for k, v in kwargs.items() if v is not None})
        image = result.images[0]
        image.save(str(out_file), format="PNG")
        print(f"[ImageGen] Saved: {out_file}")

        return ImageResult(
            filename  = filename,
            path      = str(out_file),
            url       = f"/api/images/file/{filename}",
            prompt    = prompt,
            width     = width,
            height    = height,
            steps     = steps,
            seed      = actual_seed,
            provider  = "diffusers",
            model_id  = self._loaded_model_id,
        )
