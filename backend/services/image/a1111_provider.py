"""
Optional AUTOMATIC1111 SD WebUI provider.
Used only if the server is already running on port 7860.
Does NOT start A1111 — it simply wraps its API if detected.
"""
from __future__ import annotations
import uuid, random
from pathlib import Path
import httpx
from .base import ImageProvider, ImageResult

A1111_URL = "http://localhost:7860"
_TIMEOUT  = httpx.Timeout(5.0, read=180.0)


class A1111Provider(ImageProvider):
    name = "a1111"

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                r = await c.get(A1111_URL)
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
        import base64
        payload = {
            "prompt": prompt, "negative_prompt": negative_prompt,
            "width": width, "height": height,
            "steps": steps, "cfg_scale": cfg_scale,
            "seed": seed, "sampler_name": "DPM++ 2M Karras",
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(f"{A1111_URL}/sdapi/v1/txt2img", json=payload)
            r.raise_for_status()

        data = r.json()
        b64  = data["images"][0]
        filename = f"{uuid.uuid4().hex}.png"
        out_file  = output_path / filename
        out_file.write_bytes(base64.b64decode(b64))

        info  = data.get("info", "{}")
        import json
        info_d = json.loads(info) if isinstance(info, str) else info
        actual_seed = info_d.get("seed", seed)

        return ImageResult(
            filename=filename, path=str(out_file),
            url=f"/api/images/file/{filename}",
            prompt=prompt, width=width, height=height,
            steps=steps, seed=actual_seed,
            provider="a1111", model_id=model_id,
        )
