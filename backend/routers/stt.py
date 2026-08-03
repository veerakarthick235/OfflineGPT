"""
STT Router — /api/stt/*
Endpoints:
  POST /api/stt/transcribe          — transcribe audio blob → text
  GET  /api/stt/models              — list all Whisper models
  GET  /api/stt/models/active       — currently loaded model
  POST /api/stt/models/{id}/load    — load a model into memory
  GET  /api/stt/models/{id}/download — SSE stream download progress
  DELETE /api/stt/models/{id}       — delete downloaded model
"""
import asyncio
import json
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from ..services.stt import whisper_service as stt
from ..services.stt import model_manager   as mm

router = APIRouter(prefix="/api/stt", tags=["stt"])


# ── Transcribe ───────────────────────────────────────────────────
@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """
    Accept an audio file (WebM, WAV, MP3, OGG, etc.) and return the transcript.
    The frontend sends the MediaRecorder blob directly.
    """
    # Check a model is available
    if not any(mm.is_downloaded(mid) for mid in mm.MODELS):
        raise HTTPException(
            status_code=503,
            detail="No Whisper model downloaded. Go to Models → STT to download one."
        )

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Determine format from MIME type
    ct  = (audio.content_type or "audio/webm").split("/")[-1].split(";")[0]
    fmt = ct if ct in ("wav", "mp3", "ogg", "flac", "m4a") else "webm"

    try:
        result = await stt.transcribe(audio_bytes, audio_format=fmt)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")


# ── Model listing ────────────────────────────────────────────────
@router.get("/models")
async def list_models():
    return mm.list_models()


@router.get("/models/active")
async def active_model():
    return {
        "model_id":  stt.get_active_model_id(),
        "loaded":    stt._model is not None,
    }


# ── Load model into memory ────────────────────────────────────────
@router.post("/models/{model_id}/load")
async def load_model(model_id: str):
    if model_id not in mm.MODELS:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_id}")
    if not mm.is_downloaded(model_id):
        raise HTTPException(status_code=409, detail="Model not downloaded yet")
    try:
        await stt.load_model(model_id)
        return {"ok": True, "model_id": model_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Download model (SSE stream) ───────────────────────────────────
@router.get("/models/{model_id}/download")
async def download_model(model_id: str):
    """SSE stream — yields JSON progress events."""
    if model_id not in mm.MODELS:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_id}")

    async def event_gen():
        async for event in mm.download_model(model_id):
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0)
        # After download succeeds, auto-load model
        if mm.is_downloaded(model_id):
            try:
                await stt.load_model(model_id)
            except Exception:
                pass

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Delete model ──────────────────────────────────────────────────
@router.delete("/models/{model_id}")
async def delete_model(model_id: str):
    result = mm.delete_model(model_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["message"])
    # Unload if it was active
    if stt._model_id == model_id:
        await stt.unload_model()
    return result
