"""
Hybrid Retriever — fuses BM25 + ChromaDB results using Reciprocal Rank Fusion.

RRF Formula (Cormack et al., 2009):
  RRF(doc) = Σ  1 / (k + rank_in_list_i)
  where k=60 is a stability constant

Why RRF?
  - Parameter-free combination (no learned weights needed)
  - Robust when BM25 and embedding scores are on different scales
  - Consistently outperforms weighted score combination in practice
  - Works even when one retriever returns 0 results
"""
from __future__ import annotations
from typing import List, Optional, Dict

from . import bm25_index as bm25_mod
from .. import chroma_db

RRF_K = 60   # RRF stability constant


def _rrf_score(rank: int) -> float:
    return 1.0 / (RRF_K + rank + 1)


def _deduplicate(chunks: List[dict]) -> List[dict]:
    """Remove duplicate chunk_ids, keep highest scored."""
    seen: Dict[str, dict] = {}
    for c in chunks:
        cid = c["chunk_id"]
        if cid not in seen or c["rrf_score"] > seen[cid]["rrf_score"]:
            seen[cid] = c
    return list(seen.values())


async def retrieve(
    query: str,
    top_k: int = 20,
    doc_ids: Optional[List[str]] = None,
) -> List[dict]:
    """
    Hybrid retrieval: BM25 + ChromaDB, fused with RRF.

    Returns up to `top_k` chunks, each with:
      { chunk_id, doc_id, filename, text, rrf_score, bm25_rank, vec_rank }
    """
    # ── 1. BM25 retrieval ──────────────────────────────────────────────
    bm25_results = bm25_mod.get_index().search(query, top_k=top_k, doc_ids=doc_ids)

    # ── 2. Vector retrieval (ChromaDB) ─────────────────────────────────
    raw_vec = chroma_db.search_documents_with_ids(query, document_ids=doc_ids, top_k=top_k)

    # ── 3. Build candidate maps ───────────────────────────────────────
    # Map chunk_id → { chunk_id, doc_id, filename, text }
    candidates: Dict[str, dict] = {}

    for rank, item in enumerate(bm25_results):
        cid = item["chunk_id"]
        candidates[cid] = {
            "chunk_id":  cid,
            "doc_id":    item["doc_id"],
            "filename":  item["filename"],
            "text":      item["text"],
            "bm25_rank": rank,
            "vec_rank":  9999,
            "rrf_score": _rrf_score(rank),
        }

    for rank, (cid, text, meta) in enumerate(raw_vec):
        if cid in candidates:
            # Already in BM25 results — add vector RRF contribution
            candidates[cid]["vec_rank"]   = rank
            candidates[cid]["rrf_score"] += _rrf_score(rank)
        else:
            candidates[cid] = {
                "chunk_id":  cid,
                "doc_id":    meta.get("document_id", ""),
                "filename":  meta.get("filename", ""),
                "text":      text,
                "bm25_rank": 9999,
                "vec_rank":  rank,
                "rrf_score": _rrf_score(rank),
            }

    # ── 4. Sort by RRF score, return top_k ────────────────────────────
    ranked = sorted(candidates.values(), key=lambda x: x["rrf_score"], reverse=True)
    return ranked[:top_k]
