"""
Optional ComfyUI provider wrapper — only used if ComfyUI is already running.
"""
from __future__ import annotations
import asyncio, base64, uuid, random, json
from pathlib import Path
import httpx
from .base import ImageProvider, ImageResult

COMFYUI_URL = "http://localhost:8188"
_TIMEOUT    = httpx.Timeout(5.0, read=180.0)


class ComfyUIProvider(ImageProvider):
    name = "comfyui"

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                r = await c.get(COMFYUI_URL)
                return r.status_code < 500
        except Exception:
            return False

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
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt or "bad quality", "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "offlinegpt"}},
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            pid = (await c.post(f"{COMFYUI_URL}/prompt", json={"prompt": workflow})).json()["prompt_id"]
            for _ in range(120):
                await asyncio.sleep(1)
                hist = (await c.get(f"{COMFYUI_URL}/history/{pid}")).json()
                if pid in hist:
                    for node_out in hist[pid]["outputs"].values():
                        if "images" in node_out:
                            img_info = node_out["images"][0]
                            img_resp = await c.get(f"{COMFYUI_URL}/view", params={
                                "filename": img_info["filename"],
                                "subfolder": img_info.get("subfolder", ""),
                                "type": img_info.get("type", "output"),
                            })
                            filename = f"{uuid.uuid4().hex}.png"
                            out_file  = output_path / filename
                            out_file.write_bytes(img_resp.content)
                            return ImageResult(
                                filename=filename, path=str(out_file),
                                url=f"/api/images/file/{filename}",
                                prompt=prompt, width=width, height=height,
                                steps=steps, seed=actual_seed,
                                provider="comfyui", model_id=model_id,
                            )
        raise TimeoutError("ComfyUI generation timed out")
