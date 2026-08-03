"""
Image generation API — fully self-contained, no external tools required.

Routes:
  GET  /api/images/status
  GET  /api/images/models
  POST /api/images/models/{id}/download   (SSE progress stream)
  DELETE /api/images/models/{id}
  POST /api/images/models/{id}/load
  POST /api/images/models/unload
  POST /api/images/generate
  GET  /api/images/gallery
  GET  /api/images/file/{filename}
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field

from ..services.image.manager import get_manager, IMAGES_DIR
from ..services import image_library as lib

router = APIRouter(prefix="/api/images", tags=["images"])


# ── Status ────────────────────────────────────────────────────────────

@router.get("/status")
async def image_status():
    return await get_manager().status()


# ── Model catalogue ───────────────────────────────────────────────────

@router.get("/models")
async def list_models():
    return get_manager().catalogue()


@router.get("/models/{model_id}/download")
async def download_model(model_id: str):
    """Stream download progress as Server-Sent Events (GET required for EventSource)."""
    async def _event_stream():
        async for event in get_manager().download_model_stream(model_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(model_id: str):
    await get_manager().delete_model(model_id)


@router.post("/models/{model_id}/load")
async def load_model(model_id: str):
    try:
        await get_manager().load_model(model_id)
        return {"status": "loaded", "model_id": model_id}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/models/unload")
async def unload_model():
    await get_manager().unload_model()
    return {"status": "unloaded"}


# ── Generate ──────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt:          str
    negative_prompt: str   = "low quality, blurry, nsfw, watermark"
    width:           int   = Field(512, ge=64, le=1536, multiple_of=64)
    height:          int   = Field(512, ge=64, le=1536, multiple_of=64)
    steps:           int   = Field(-1, ge=-1, le=150)
    cfg_scale:       float = Field(7.0, ge=1.0, le=30.0)
    seed:            int   = -1


@router.post("/generate")
async def generate(req: GenerateRequest):
    try:
        result = await get_manager().generate(
            prompt          = req.prompt,
            negative_prompt = req.negative_prompt,
            width           = req.width,
            height          = req.height,
            steps           = req.steps,
            cfg_scale       = req.cfg_scale,
            seed            = req.seed,
        )
        # Save metadata to library
        from pathlib import Path
        file_bytes = Path(result.path).stat().st_size if Path(result.path).exists() else 0
        await lib.add_image(
            filename   = result.filename,
            prompt     = result.prompt,
            model_id   = result.model_id,
            provider   = result.provider,
            width      = result.width,
            height     = result.height,
            steps      = result.steps,
            seed       = result.seed,
            file_bytes = file_bytes,
        )
        return {
            "filename":  result.filename,
            "url":       result.url,
            "prompt":    result.prompt,
            "width":     result.width,
            "height":    result.height,
            "steps":     result.steps,
            "seed":      result.seed,
            "provider":  result.provider,
            "model_id":  result.model_id,
        }
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


# ── Gallery ───────────────────────────────────────────────────────────

@router.get("/gallery")
async def gallery():
    if not IMAGES_DIR.exists():
        return []
    files = sorted(IMAGES_DIR.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [
        {"filename": f.name, "url": f"/api/images/file/{f.name}", "size": f.stat().st_size}
        for f in files[:100]
    ]


@router.get("/file/{filename}")
async def serve_image(filename: str):
    path = IMAGES_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(path, media_type="image/png")
