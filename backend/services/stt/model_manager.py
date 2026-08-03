"""
Whisper model manager — download and manage faster-whisper models locally.
Models are stored in backend/models/whisper/<model_id>/
"""
from __future__ import annotations
import asyncio
import os
import shutil
from pathlib import Path
from typing import AsyncIterator

# ---------------------------------------------------------------------------
# Model catalogue
# ---------------------------------------------------------------------------
MODELS = {
    "tiny": {
        "id":          "tiny",
        "name":        "Whisper Tiny",
        "size_mb":     75,
        "hf_repo":     "Systran/faster-whisper-tiny",
        "description": "Fastest · ~75 MB · basic accuracy",
    },
    "base": {
        "id":          "base",
        "name":        "Whisper Base",
        "size_mb":     145,
        "hf_repo":     "Systran/faster-whisper-base",
        "description": "Fast · ~145 MB · good accuracy (recommended)",
    },
    "small": {
        "id":          "small",
        "name":        "Whisper Small",
        "size_mb":     461,
        "hf_repo":     "Systran/faster-whisper-small",
        "description": "Balanced · ~461 MB · better accuracy",
    },
    "medium": {
        "id":          "medium",
        "name":        "Whisper Medium",
        "size_mb":     1500,
        "hf_repo":     "Systran/faster-whisper-medium",
        "description": "Slower · ~1.5 GB · high accuracy",
    },
}

MODELS_DIR = Path(__file__).parent.parent.parent / "models" / "whisper"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def model_path(model_id: str) -> Path:
    return MODELS_DIR / model_id


def is_downloaded(model_id: str) -> bool:
    p = model_path(model_id)
    return p.exists() and any(p.iterdir())


def list_models() -> list[dict]:
    result = []
    for mid, info in MODELS.items():
        entry = dict(info)
        entry["downloaded"] = is_downloaded(mid)
        entry["path"]       = str(model_path(mid)) if is_downloaded(mid) else None
        result.append(entry)
    return result


async def download_model(model_id: str) -> AsyncIterator[dict]:
    """
    Download a faster-whisper model from Hugging Face Hub.
    Yields progress dicts: { status, progress, message }
    """
    if model_id not in MODELS:
        yield {"status": "error", "message": f"Unknown model: {model_id}"}
        return

    info   = MODELS[model_id]
    target = model_path(model_id)

    if is_downloaded(model_id):
        yield {"status": "done", "progress": 100, "message": "Already downloaded"}
        return

    yield {"status": "downloading", "progress": 0, "message": f"Downloading {info['name']}…"}

    try:
        from huggingface_hub import snapshot_download
        import functools

        loop = asyncio.get_event_loop()
        downloaded_path = await loop.run_in_executor(
            None,
            functools.partial(
                snapshot_download,
                repo_id      = info["hf_repo"],
                local_dir    = str(target),
                local_dir_use_symlinks = False,
                ignore_patterns = ["*.msgpack", "*.h5", "flax_model*", "tf_model*"],
            )
        )
        yield {"status": "done", "progress": 100,
               "message": f"{info['name']} ready", "path": downloaded_path}

    except Exception as e:
        # Clean up partial download
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        yield {"status": "error", "progress": 0, "message": str(e)}


def delete_model(model_id: str) -> dict:
    target = model_path(model_id)
    if not target.exists():
        return {"ok": False, "message": "Not downloaded"}
    shutil.rmtree(target, ignore_errors=True)
    return {"ok": True, "message": f"Deleted {model_id}"}
