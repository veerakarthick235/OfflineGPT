"""
Repository Router — /api/repo/*

Endpoints:
  GET  /api/repo                    — list all indexed repos
  POST /api/repo/index              — start indexing (SSE streaming progress)
  GET  /api/repo/{id}               — repo details + stats
  DELETE /api/repo/{id}             — delete a repo index
  GET  /api/repo/{id}/symbols       — list all symbols
  GET  /api/repo/{id}/search        — search symbols
  GET  /api/repo/{id}/files/{path}  — get file context
  POST /api/repo/search             — search across all repos
"""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from ..services.repo import symbol_store, repo_rag
from ..services.repo.indexer import index_repo

router = APIRouter(prefix="/api/repo", tags=["repo"])


# ── Schemas ────────────────────────────────────────────────────────────

class IndexRequest(BaseModel):
    path:      str
    name:      Optional[str] = None
    max_files: int            = 2000


class SearchRequest(BaseModel):
    query:   str
    repo_id: Optional[str] = None
    top_k:   int           = 6


# ── List + Index ───────────────────────────────────────────────────────

@router.get("")
async def list_repos():
    repos = await symbol_store.list_repos()
    return {"repos": repos, "count": len(repos)}


@router.post("/index")
async def start_indexing(req: IndexRequest):
    """
    Stream indexing progress via SSE.
    Frontend receives JSON events while indexing runs.
    """
    path = Path(req.path)
    if not path.exists():
        raise HTTPException(400, f"Path does not exist: {req.path}")
    if not path.is_dir():
        raise HTTPException(400, f"Path is not a directory: {req.path}")

    async def generate():
        async for event in index_repo(
            repo_path = str(path),
            repo_name = req.name or path.name,
            max_files = req.max_files,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "Connection":        "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Repo Details ───────────────────────────────────────────────────────

@router.get("/{repo_id}")
async def get_repo(repo_id: str):
    repo = await symbol_store.get_repo(repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    return repo


@router.delete("/{repo_id}", status_code=204)
async def delete_repo(repo_id: str):
    """Delete repo index from SQLite and ChromaDB."""
    from ..services.chroma_db import delete_repo_chunks
    try:
        delete_repo_chunks(repo_id)
    except Exception:
        pass
    await symbol_store.delete_repo(repo_id)


# ── Symbol Search ──────────────────────────────────────────────────────

@router.get("/{repo_id}/symbols")
async def list_symbols(
    repo_id:     str,
    symbol_type: Optional[str] = None,
    limit:       int = 100,
):
    """List all symbols in a repo (optionally filter by type)."""
    symbols = await symbol_store.list_symbols(repo_id, symbol_type, limit)
    return {"symbols": symbols, "count": len(symbols)}


@router.get("/{repo_id}/search")
async def search_repo(repo_id: str, q: str, top_k: int = 6):
    """Search a specific repo's code."""
    result = await repo_rag.search(query=q, repo_id=repo_id, top_k=top_k)
    return result


@router.post("/search")
async def search_all_repos(req: SearchRequest):
    """Search across all repos (or a specific one)."""
    if not req.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    result = await repo_rag.search(
        query   = req.query,
        repo_id = req.repo_id,
        top_k   = req.top_k,
    )
    return result


# ── File Context ───────────────────────────────────────────────────────

@router.get("/{repo_id}/files")
async def get_file_context(repo_id: str, path: str):
    """Get symbols and dependencies for a specific file."""
    context = await repo_rag.get_file_context(repo_id, path)
    symbols = await symbol_store.get_file_symbols(repo_id, path)
    deps    = await symbol_store.get_file_dependencies(repo_id, path)
    return {
        "file":     path,
        "context":  context,
        "symbols":  symbols,
        "dependencies": deps,
    }
