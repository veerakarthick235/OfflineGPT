"""
Code Execution Router — /api/exec/*

Endpoints:
  POST /api/exec/run            — execute code directly
  GET  /api/exec/history        — list past executions
  GET  /api/exec/{id}           — get a specific execution result
  GET  /api/exec/languages      — list supported languages
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..services.sandbox.sandbox import run_code
from ..services.sandbox import execution_store

router = APIRouter(prefix="/api/exec", tags=["code-execution"])


class RunRequest(BaseModel):
    code:            str
    language:        str           = "python"
    timeout:         float         = 10.0
    conversation_id: Optional[str] = None


@router.post("/run")
async def run_code_endpoint(req: RunRequest):
    """Execute code in the sandbox and return the result."""
    if not req.code.strip():
        raise HTTPException(400, "Code cannot be empty")
    if req.timeout > 30:
        raise HTTPException(400, "Timeout cannot exceed 30 seconds")

    result = await run_code(req.code, language=req.language, timeout=req.timeout)

    # Persist to history
    saved = await execution_store.save_execution(
        language        = req.language,
        code            = req.code,
        result          = result,
        conversation_id = req.conversation_id,
    )

    return {**result, "id": saved["id"]}


@router.get("/history")
async def get_history(conversation_id: Optional[str] = None, limit: int = 20):
    """List recent code executions."""
    execs = await execution_store.list_executions(conversation_id, limit)
    return {"executions": execs, "count": len(execs)}


@router.get("/languages")
async def get_languages():
    """List supported languages and their availability."""
    import shutil
    return {
        "languages": [
            {"name": "python",     "available": True,                      "icon": "🐍"},
            {"name": "javascript", "available": bool(shutil.which("node")), "icon": "🟨"},
            {"name": "sql",        "available": True,                      "icon": "🗄️"},
        ]
    }


@router.get("/{exec_id}")
async def get_execution(exec_id: str):
    """Get a specific execution result by ID."""
    result = await execution_store.get_execution(exec_id)
    if not result:
        raise HTTPException(404, "Execution not found")
    return result
