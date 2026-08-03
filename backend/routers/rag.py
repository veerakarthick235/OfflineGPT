"""
RAG Router — /api/rag/*

Replaces the old /api/documents/rag-query with a full Hybrid RAG pipeline.

Endpoints:
  POST /api/rag/query          — run full pipeline, return context
  GET  /api/rag/status         — pipeline health & chunk counts
  POST /api/rag/reranker/download — download cross-encoder model
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from ..services.rag import pipeline
from ..services.rag import bm25_index as bm25_mod
from ..services.rag import reranker
from ..services   import chroma_db

router = APIRouter(prefix="/api/rag", tags=["rag"])


# ── Request / Response schemas ─────────────────────────────────────────

class RAGQueryRequest(BaseModel):
    query:       str
    doc_ids:     Optional[List[str]] = None
    model:       str                 = "llama3.2"
    top_k:       int                 = Field(5,  ge=1, le=20)
    rewrite:     bool                = True
    rerank:      bool                = True
    compress:    bool                = True


# ── Endpoints ──────────────────────────────────────────────────────────

@router.post("/query")
async def rag_query(req: RAGQueryRequest):
    """
    Full Hybrid RAG pipeline:
    Query Rewriting → BM25+Vector Retrieval → Reranking → Compression

    Returns ready-to-inject context + pipeline trace for transparency.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    result = await pipeline.run(
        query          = req.query,
        doc_ids        = req.doc_ids,
        model          = req.model,
        top_k_retrieve = req.top_k * 4,   # retrieve 4× then rerank down
        top_k_rerank   = req.top_k,
        rewrite        = req.rewrite,
        do_rerank      = req.rerank,
        do_compress    = req.compress,
    )
    return result


@router.get("/status")
async def rag_status():
    """Return health metrics for the RAG pipeline components."""
    bm25_idx = bm25_mod.get_index()

    # ChromaDB chunk count
    try:
        chroma_count = chroma_db._documents_col().count()
    except Exception:
        chroma_count = -1

    return {
        "bm25": {
            "available":   bm25_mod.BM25_AVAILABLE,
            "chunk_count": bm25_idx.chunk_count,
        },
        "chroma": {
            "chunk_count": chroma_count,
        },
        "reranker": {
            "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "loaded": reranker._reranker is not None,
        },
        "pipeline_stages": ["query_rewriting", "hybrid_retrieval", "reranking", "compression"],
    }


@router.post("/reranker/download")
async def download_reranker():
    """Download the cross-encoder reranker model for offline use (~90 MB)."""
    result = await reranker.download_model()
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result
