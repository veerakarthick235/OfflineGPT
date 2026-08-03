"""
Cross-encoder Reranker — re-scores retrieved chunks against the query.

Why reranking?
  Retrieval (BM25 + vectors) is optimized for RECALL (get many relevant docs).
  Reranking is optimized for PRECISION (pick the BEST ones).

  Cross-encoders read BOTH the query and each candidate together, unlike
  bi-encoders (embeddings) which encode them separately. This gives them
  much better understanding of relevance — but they're too slow to use
  on the full corpus (hence: retrieve 20, rerank to 5).

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
  - 22M parameters, runs on CPU in ~50ms per batch
  - Downloaded once to backend/models/reranker/, fully offline thereafter
  - SOTA on MS MARCO passage ranking benchmark

If sentence-transformers is not installed, falls back to identity reranking
(returns chunks in original RRF order).
"""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import List, Optional

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
MODEL_DIR  = Path(__file__).parent.parent.parent / "models" / "reranker"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

_reranker = None
_load_lock = asyncio.Lock()


async def _get_reranker():
    global _reranker
    if _reranker is not None:
        return _reranker

    async with _load_lock:
        if _reranker is not None:
            return _reranker
        try:
            from sentence_transformers import CrossEncoder
            loop = asyncio.get_event_loop()

            local_path = MODEL_DIR / "ms-marco-MiniLM-L-6-v2"

            def _load():
                # Use local path if downloaded, else download on first use
                path = str(local_path) if local_path.exists() else MODEL_NAME
                return CrossEncoder(path, max_length=512, device="cpu")

            _reranker = await loop.run_in_executor(None, _load)
            print(f"[Reranker] Loaded cross-encoder model")
        except ImportError:
            print("[Reranker] sentence-transformers not available — using identity ranking")
            _reranker = None
        except Exception as e:
            print(f"[Reranker] Failed to load: {e} — using identity ranking")
            _reranker = None

    return _reranker


async def rerank(
    query: str,
    candidates: List[dict],
    top_k: int = 5,
) -> List[dict]:
    """
    Re-score and re-order candidates using cross-encoder.

    Input candidates: [{ chunk_id, text, rrf_score, ... }]
    Returns top_k candidates with added 'rerank_score' field.
    """
    if not candidates:
        return []

    reranker = await _get_reranker()

    if reranker is None:
        # Fallback: identity (use RRF score order)
        for i, c in enumerate(candidates):
            c["rerank_score"] = candidates[i].get("rrf_score", 0)
        return candidates[:top_k]

    # Build query-passage pairs
    pairs = [(query, c["text"]) for c in candidates]

    try:
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None,
            lambda: reranker.predict(pairs, show_progress_bar=False)
        )

        for chunk, score in zip(candidates, scores):
            chunk["rerank_score"] = float(score)

        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]

    except Exception as e:
        print(f"[Reranker] inference error: {e} — using RRF order")
        for c in candidates:
            c["rerank_score"] = c.get("rrf_score", 0)
        return candidates[:top_k]


async def download_model() -> dict:
    """Download the reranker model for offline use."""
    try:
        from sentence_transformers import CrossEncoder
        import asyncio

        local_path = MODEL_DIR / "ms-marco-MiniLM-L-6-v2"
        if local_path.exists():
            return {"ok": True, "message": "Already downloaded"}

        loop = asyncio.get_event_loop()
        def _dl():
            model = CrossEncoder(MODEL_NAME, device="cpu")
            model.save(str(local_path))
            return True

        await loop.run_in_executor(None, _dl)
        return {"ok": True, "message": f"Downloaded to {local_path}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
