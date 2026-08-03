"""
Image Parser — sends image to Ollama vision model for analysis.

Flow:
1. Load image with PIL
2. Convert to base64
3. Call Ollama /api/chat with llava (or any vision model)
4. Return the vision model's description as "extracted text"

Fallback: if no vision model available, return EXIF metadata + file info.
"""
from __future__ import annotations
import base64
import io
from pathlib import Path
from typing import Tuple

import httpx

OLLAMA_BASE = "http://localhost:11434"
# Vision models to try in order of preference
VISION_MODELS = ["llava", "llava:latest", "llava:7b", "moondream", "llava-llama3"]


def _load_image_base64(file_path: str) -> Tuple[str, str]:
    """Load image, return (base64_string, format)."""
    try:
        from PIL import Image
        img = Image.open(file_path)
        # Resize large images to max 1024x1024 to save tokens
        if max(img.size) > 1024:
            img.thumbnail((1024, 1024), Image.LANCZOS)
        buf = io.BytesIO()
        fmt = img.format or "PNG"
        img.save(buf, format=fmt)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return b64, fmt.lower()
    except Exception as e:
        raise ValueError(f"Cannot load image: {e}")


async def _get_vision_model() -> str:
    """Find the first available vision model in Ollama."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                for vm in VISION_MODELS:
                    if any(vm in m for m in models):
                        return next(m for m in models if vm in m)
    except Exception:
        pass
    return ""


async def parse_image(file_path: str, custom_prompt: str = "") -> Tuple[str, int]:
    """
    Analyze image using Ollama vision model.
    Returns (description_text, 1).
    """
    try:
        b64, fmt = _load_image_base64(file_path)
    except ValueError as e:
        return str(e), 0

    # Try vision model
    vision_model = await _get_vision_model()

    if vision_model:
        prompt = custom_prompt or (
            "Please provide a detailed description of this image. Include:\n"
            "1. Main subjects and objects\n"
            "2. Any text visible in the image (transcribe it exactly)\n"
            "3. Colors, layout, and visual structure\n"
            "4. Any charts, graphs, tables, or diagrams (describe data if visible)\n"
            "5. Overall context and what this image likely represents"
        )
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                payload = {
                    "model": vision_model,
                    "messages": [{
                        "role": "user",
                        "content": prompt,
                        "images": [b64],
                    }],
                    "stream": False,
                }
                resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
                if resp.status_code == 200:
                    data    = resp.json()
                    content = data.get("message", {}).get("content", "")
                    if content.strip():
                        full = f"[Image Analysis by {vision_model}]\n\n{content.strip()}"
                        return full, 1
        except Exception as e:
            print(f"[Image Parser] Vision model error: {e}")

    # Fallback: extract EXIF metadata
    return _extract_image_metadata(file_path), 1


def _extract_image_metadata(file_path: str) -> str:
    """Extract basic image info as fallback."""
    parts = [f"[Image File: {Path(file_path).name}]"]
    try:
        from PIL import Image, ExifTags
        img = Image.open(file_path)
        parts.append(f"Format: {img.format}")
        parts.append(f"Size: {img.size[0]}x{img.size[1]} pixels")
        parts.append(f"Mode: {img.mode}")

        # EXIF data
        exif_data = img.getexif() if hasattr(img, "getexif") else {}
        if exif_data:
            for tag_id, val in list(exif_data.items())[:10]:
                tag = ExifTags.TAGS.get(tag_id, str(tag_id))
                parts.append(f"EXIF {tag}: {val}")
    except Exception as e:
        parts.append(f"[Metadata error: {e}]")

    parts.append("\n[Note: No vision model available. Install llava via `ollama pull llava` for image analysis.]")
    return "\n".join(parts)
