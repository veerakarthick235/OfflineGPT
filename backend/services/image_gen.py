"""
Image generation service.

Supports two backends (auto-detected):
  1. AUTOMATIC1111 / SD WebUI  — http://localhost:7860
  2. ComfyUI                   — http://localhost:8188
  3. Ollama (future)           — placeholder

Install one of:
  - https://github.com/AUTOMATIC1111/stable-diffusion-webui
  - https://github.com/comfyanonymous/ComfyUI
"""
import httpx
import base64
import json
import uuid
from pathlib import Path
from typing import Optional

SD_WEBUI  = "http://localhost:7860"
COMFYUI   = "http://localhost:8188"
IMG_DIR   = Path(__file__).parent.parent / "data" / "images"
_TIMEOUT  = httpx.Timeout(5.0, read=120.0)


IMG_DIR.mkdir(parents=True, exist_ok=True)


# ── Backend detection ─────────────────────────────────────────────────

async def detect_backend() -> Optional[str]:
    """Return 'sdwebui', 'comfyui', or None."""
    for url, name in [(SD_WEBUI, "sdwebui"), (COMFYUI, "comfyui")]:
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                r = await c.get(url)
                if r.status_code < 500:
                    return name
        except Exception:
            continue
    return None


async def backend_status() -> dict:
    backend = await detect_backend()
    return {
        "available": backend is not None,
        "backend":   backend,
        "sdwebui_url": SD_WEBUI,
        "comfyui_url": COMFYUI,
    }


# ── SD WebUI (AUTOMATIC1111) ─────────────────────────────────────────

async def _generate_sdwebui(
    prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg_scale: float = 7.0,
    seed: int = -1,
) -> str:
    payload = {
        "prompt":           prompt,
        "negative_prompt":  negative_prompt,
        "width":            width,
        "height":           height,
        "steps":            steps,
        "cfg_scale":        cfg_scale,
        "seed":             seed,
        "sampler_name":     "DPM++ 2M Karras",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(f"{SD_WEBUI}/sdapi/v1/txt2img", json=payload)
        r.raise_for_status()
        data = r.json()
        b64 = data["images"][0]
        return b64


# ── ComfyUI ──────────────────────────────────────────────────────────

async def _generate_comfyui(
    prompt: str,
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg_scale: float = 7.0,
    seed: int = -1,
) -> str:
    """Simple ComfyUI workflow for txt2img."""
    import random
    actual_seed = seed if seed >= 0 else random.randint(0, 2**32 - 1)

    workflow = {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": actual_seed, "steps": steps, "cfg": cfg_scale,
            "sampler_name": "dpmpp_2m", "scheduler": "karras",
            "denoise": 1, "model": ["4", 0],
            "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0],
        }},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "bad quality, blurry", "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode",    "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",    "inputs": {"images": ["8", 0], "filename_prefix": "offlinegpt"}},
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        prompt_id = (await c.post(f"{COMFYUI}/prompt", json={"prompt": workflow})).json()["prompt_id"]
        # Poll until done
        import asyncio
        for _ in range(120):
            await asyncio.sleep(1)
            hist = (await c.get(f"{COMFYUI}/history/{prompt_id}")).json()
            if prompt_id in hist:
                outputs = hist[prompt_id]["outputs"]
                for node_out in outputs.values():
                    if "images" in node_out:
                        img_info = node_out["images"][0]
                        img_resp = await c.get(
                            f"{COMFYUI}/view",
                            params={"filename": img_info["filename"], "subfolder": img_info.get("subfolder",""), "type": img_info.get("type","output")},
                        )
                        return base64.b64encode(img_resp.content).decode()
        raise TimeoutError("ComfyUI timed out")


# ── Public interface ─────────────────────────────────────────────────

async def generate_image(
    prompt: str,
    negative_prompt: str = "low quality, blurry, nsfw",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg_scale: float = 7.0,
    seed: int = -1,
) -> dict:
    """
    Generate image. Returns:
      { "b64": <base64 PNG>, "path": <saved file path>, "backend": "sdwebui"|"comfyui" }
    """
    backend = await detect_backend()
    if not backend:
        raise RuntimeError(
            "No image generation backend found. "
            "Install AUTOMATIC1111 (port 7860) or ComfyUI (port 8188)."
        )

    if backend == "sdwebui":
        b64 = await _generate_sdwebui(prompt, negative_prompt, width, height, steps, cfg_scale, seed)
    else:
        b64 = await _generate_comfyui(prompt, width, height, steps, cfg_scale, seed)

    # Save to disk
    img_bytes = base64.b64decode(b64)
    filename  = f"{uuid.uuid4().hex}.png"
    img_path  = IMG_DIR / filename
    img_path.write_bytes(img_bytes)

    return {
        "b64":     b64,
        "path":    str(img_path),
        "filename": filename,
        "backend":  backend,
        "prompt":   prompt,
        "width":    width,
        "height":   height,
    }
