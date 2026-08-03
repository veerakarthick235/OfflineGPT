"""
ImageManager — application-level singleton.

Responsibilities:
  - Select the best available provider at startup (priority: A1111 > ComfyUI > Diffusers)
  - Manage the Diffusers model lifecycle (download, load, unload)
  - Expose a single generate() entry point for the rest of the app
  - Expose model catalogue info (downloaded status, disk size, etc.)
"""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, AsyncIterator

from .base import ImageProvider, ImageResult
from .diffusers_provider import DiffusersProvider
from .a1111_provider import A1111Provider
from .comfyui_provider import ComfyUIProvider
from .models_catalog import CATALOG, ModelEntry, get_model

IMAGES_DIR = Path(__file__).parent.parent.parent / "data" / "images"
MODELS_DIR = Path(__file__).parent.parent.parent / "data" / "models"


class ImageManager:
    def __init__(self):
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)

        # Initialise providers
        self._diffusers  = DiffusersProvider(MODELS_DIR)
        self._a1111      = A1111Provider()
        self._comfyui    = ComfyUIProvider()
        self._active:  Optional[ImageProvider] = None
        self._download_progress: Dict[str, float] = {}  # model_id → 0-100

    # ── Provider selection ────────────────────────────────────────────

    async def _resolve_provider(self) -> ImageProvider:
        """Pick the best available provider. Prefer external tools if running."""
        if await self._a1111.is_available():
            return self._a1111
        if await self._comfyui.is_available():
            return self._comfyui
        return self._diffusers

    async def get_active_provider(self) -> ImageProvider:
        if self._active is None:
            self._active = await self._resolve_provider()
        return self._active

    async def refresh_provider(self) -> str:
        self._active = await self._resolve_provider()
        return self._active.name

    # ── Status ────────────────────────────────────────────────────────

    async def status(self) -> Dict[str, Any]:
        provider  = await self.get_active_provider()
        available = await provider.is_available()

        diffusers_ok = await self._diffusers.is_available()
        loaded_model = (
            self._diffusers.loaded_model_id
            if provider.name == "diffusers" else ""
        )

        return {
            "provider":         provider.name,
            "available":        available,
            "diffusers_ready":  diffusers_ok,
            "loaded_model":     loaded_model,
            "a1111_available":  await self._a1111.is_available(),
            "comfyui_available": await self._comfyui.is_available(),
        }

    # ── Model catalogue ───────────────────────────────────────────────

    def catalogue(self) -> List[Dict[str, Any]]:
        result = []
        for m in CATALOG:
            downloaded = self._diffusers.is_model_downloaded(m.id)
            disk_bytes = self._diffusers.model_disk_size(m.id) if downloaded else 0
            result.append({
                "id":          m.id,
                "name":        m.name,
                "description": m.description,
                "hf_repo":     m.hf_repo,
                "size_gb":     m.size_gb,
                "size_label":  m.size_label,
                "steps_default": m.steps_default,
                "pipeline_type": m.pipeline_type,
                "tags":        m.tags,
                "downloaded":  downloaded,
                "disk_bytes":  disk_bytes,
                "disk_label":  _fmt_bytes(disk_bytes),
                "loaded":      self._diffusers.loaded_model_id == m.id,
                "downloading": self._download_progress.get(m.id, None),
            })
        return result

    # ── Download ──────────────────────────────────────────────────────

    async def download_model_stream(
        self, model_id: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """SSE-friendly async generator — yields progress events."""
        if get_model(model_id) is None:
            yield {"type": "error", "message": f"Unknown model: {model_id}"}
            return

        if self._diffusers.is_model_downloaded(model_id):
            yield {"type": "done", "message": "Already downloaded"}
            return

        self._download_progress[model_id] = 0
        yield {"type": "start", "model_id": model_id, "progress": 0}

        # huggingface_hub doesn't have async streaming progress,
        # so we run in a thread and poll disk size for progress.
        entry = get_model(model_id)
        expected_bytes = int(entry.size_gb * 1_000_000_000)

        done_event = asyncio.Event()
        error_holder = []

        def _do_download():
            try:
                asyncio.get_event_loop()
            except RuntimeError:
                pass
            try:
                from huggingface_hub import snapshot_download
                dest = str(MODELS_DIR / model_id)
                snapshot_download(
                    repo_id=entry.hf_repo,
                    local_dir=dest,
                    ignore_patterns=["*.ckpt", "flax_model*", "tf_model*", "*.msgpack", "onnx*"],
                )
            except Exception as e:
                error_holder.append(str(e))
            finally:
                done_event.set()

        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _do_download)

        # Poll progress by checking disk size
        while not done_event.is_set():
            await asyncio.sleep(2)
            current = self._diffusers.model_disk_size(model_id)
            pct = min(99, int(current / max(expected_bytes, 1) * 100))
            self._download_progress[model_id] = pct
            yield {"type": "progress", "model_id": model_id, "progress": pct,
                   "downloaded_bytes": current, "total_bytes": expected_bytes}

        self._download_progress.pop(model_id, None)

        if error_holder:
            yield {"type": "error", "model_id": model_id, "message": error_holder[0]}
        else:
            disk = self._diffusers.model_disk_size(model_id)
            yield {"type": "done", "model_id": model_id, "progress": 100,
                   "disk_bytes": disk, "disk_label": _fmt_bytes(disk)}

    async def delete_model(self, model_id: str) -> None:
        self._diffusers.delete_model(model_id)

    # ── Load / Unload ─────────────────────────────────────────────────

    async def load_model(self, model_id: str) -> None:
        await self._diffusers.load_model(model_id)
        # Refresh provider selection after loading
        self._active = self._diffusers

    async def unload_model(self) -> None:
        self._diffusers.unload_model()

    # ── Generate ──────────────────────────────────────────────────────

    async def generate(
        self,
        prompt:          str,
        negative_prompt: str   = "low quality, blurry, nsfw, watermark, text",
        width:           int   = 512,
        height:          int   = 512,
        steps:           int   = -1,    # -1 = model default
        cfg_scale:       float = 7.0,
        seed:            int   = -1,
        model_id:        str   = "",
    ) -> ImageResult:
        provider = await self.get_active_provider()

        # For diffusers: ensure a model is loaded
        if provider.name == "diffusers":
            if not self._diffusers._pipeline:
                # Auto-load the first downloaded model
                for entry in CATALOG:
                    if self._diffusers.is_model_downloaded(entry.id):
                        await self._diffusers.load_model(entry.id)
                        break
                if not self._diffusers._pipeline:
                    raise RuntimeError(
                        "No model loaded. Please download a model via the Model Manager."
                    )

            # Use model's default steps if not specified
            if steps < 0:
                loaded_id = self._diffusers.loaded_model_id
                entry = get_model(loaded_id)
                steps = entry.steps_default if entry else 20

        return await provider.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            seed=seed,
            model_id=model_id or (self._diffusers.loaded_model_id if provider.name == "diffusers" else ""),
            output_path=IMAGES_DIR,
        )


def _fmt_bytes(n: int) -> str:
    if n < 1024:       return f"{n} B"
    if n < 1024**2:    return f"{n/1024:.1f} KB"
    if n < 1024**3:    return f"{n/1024**2:.1f} MB"
    return f"{n/1024**3:.2f} GB"


# ── Singleton ─────────────────────────────────────────────────────────
_manager: Optional[ImageManager] = None


def get_manager() -> ImageManager:
    global _manager
    if _manager is None:
        _manager = ImageManager()
    return _manager
