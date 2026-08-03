"""
WhisperService — singleton wrapper around faster-whisper.
Loads the model once, transcribes audio on demand.
"""
from __future__ import annotations
import asyncio
import tempfile
import os
from pathlib import Path
from typing import Optional

from .model_manager import model_path, is_downloaded, MODELS

# Active model state
_model      = None
_model_id   = None
_model_lock = asyncio.Lock()

DEFAULT_MODEL = "base"


def get_active_model_id() -> str:
    return _model_id or DEFAULT_MODEL


async def load_model(model_id: str = DEFAULT_MODEL) -> None:
    """Load (or reload) a faster-whisper model into memory."""
    global _model, _model_id

    if not is_downloaded(model_id):
        raise RuntimeError(
            f"Whisper model '{model_id}' is not downloaded. "
            "Go to Models → STT Models to download it first."
        )

    async with _model_lock:
        if _model_id == model_id and _model is not None:
            return  # already loaded

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Run: pip install faster-whisper"
            )

        path = str(model_path(model_id))
        loop = asyncio.get_event_loop()

        def _load():
            return WhisperModel(
                path,
                device          = "cpu",   # use "cuda" if GPU available
                compute_type    = "int8",  # fastest on CPU
                num_workers     = 2,
            )

        _model    = await loop.run_in_executor(None, _load)
        _model_id = model_id
        print(f"[STT] Loaded faster-whisper model: {model_id}")


async def ensure_model_loaded(model_id: Optional[str] = None) -> None:
    """Load default model on first use if none is loaded."""
    target = model_id or _model_id or DEFAULT_MODEL
    if _model is None or _model_id != target:
        await load_model(target)


async def transcribe(audio_bytes: bytes, audio_format: str = "webm") -> dict:
    """
    Transcribe raw audio bytes.
    Returns: { text, segments, language, model_id }
    """
    await ensure_model_loaded()

    if _model is None:
        raise RuntimeError("No STT model loaded")

    # Write to a temp file (faster-whisper needs a file path)
    suffix = f".{audio_format}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        loop = asyncio.get_event_loop()

        def _run():
            segments, info = _model.transcribe(
                tmp_path,
                language         = None,   # auto-detect
                beam_size        = 5,
                vad_filter       = True,   # skip silence
                vad_parameters   = dict(min_silence_duration_ms=500),
            )
            text_parts = []
            seg_list   = []
            for seg in segments:
                text_parts.append(seg.text.strip())
                seg_list.append({
                    "start": round(seg.start, 2),
                    "end":   round(seg.end,   2),
                    "text":  seg.text.strip(),
                })
            return {
                "text":     " ".join(text_parts).strip(),
                "segments": seg_list,
                "language": info.language,
                "model_id": _model_id,
            }

        return await loop.run_in_executor(None, _run)

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


async def unload_model() -> None:
    """Free GPU/CPU memory by unloading the model."""
    global _model, _model_id
    _model    = None
    _model_id = None
