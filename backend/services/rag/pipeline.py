"""
RAG Pipeline — orchestrates all Phase 1 components into one call.

Pipeline stages:
  1. Query Rewriting      (Ollama, offline)
  2. Hybrid Retrieval     (BM25 + ChromaDB → RRF fusion)
  3. Cross-encoder Rerank (sentence-transformers, CPU)
  4. Context Compression  (extractive, pure Python)

Usage:
    result = await pipeline.run(query, doc_ids=["..."], model="llama3.2")
    context = result["context"]        # inject into system prompt
    trace   = result["pipeline_trace"] # for debugging
"""
from __future__ import annotations
import time
from typing import List, Optional, Dict, Any

from . import query_rewriter, hybrid_retriever, reranker, compressor

# Chunker for documents (smart sentence-aware chunker)
import re


def smart_chunk(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """
    Sentence-aware chunker — never cuts in the middle of a sentence.

    1. Split into sentences
    2. Group sentences into chunks of ~chunk_size words
    3. Overlap by carrying last `overlap` words into next chunk
    """
    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks: List[str] = []
    current_words: List[str] = []

    for sent in sentences:
        sent_words = sent.split()
        if len(current_words) + len(sent_words) > chunk_size and current_words:
            chunk = " ".join(current_words)
            if chunk.strip():
                chunks.append(chunk)
            # Keep overlap
            current_words = current_words[-overlap:]
        current_words.extend(sent_words)

    if current_words:
        chunk = " ".join(current_words)
        if chunk.strip():
            chunks.append(chunk)

    return chunks if chunks else [text[:2000]]


async def run(
    query: str,
    doc_ids:   Optional[List[str]] = None,
    model:     str = "llama3.2",
    top_k_retrieve: int = 20,
    top_k_rerank:   int = 5,
    rewrite:        bool = True,
    do_rerank:      bool = True,
    do_compress:    bool = True,
) -> Dict[str, Any]:
    """
    Full RAG pipeline. Returns:
    {
      "context":        str,   # ready-to-inject context string
      "chunks":         list,  # compressed chunk objects
      "queries_used":   list,  # rewritten queries (for transparency)
      "pipeline_trace": dict,  # timing & counts for each stage
    }
    """
    trace: Dict[str, Any] = {}
    t0 = time.perf_counter()

    # ── Stage 1: Query Rewriting ──────────────────────────────────────
    if rewrite:
        t = time.perf_counter()
        queries = await query_rewriter.rewrite(query, model=model)
        trace["rewrite_ms"] = round((time.perf_counter() - t) * 1000)
        trace["rewritten_queries"] = queries
    else:
        queries = [query]
        trace["rewrite_ms"] = 0

    # ── Stage 2: Hybrid Retrieval (for each rewritten query, then merge) ──
    t = time.perf_counter()
    all_candidates: Dict[str, dict] = {}

    for q in queries:
        retrieved = await hybrid_retriever.retrieve(q, top_k=top_k_retrieve, doc_ids=doc_ids)
        for item in retrieved:
            cid = item["chunk_id"]
            if cid not in all_candidates:
                all_candidates[cid] = item
            else:
                # Accumulate RRF scores across query variants
                all_candidates[cid]["rrf_score"] = max(
                    all_candidates[cid]["rrf_score"],
                    item["rrf_score"]
                )

    candidates = sorted(all_candidates.values(), key=lambda x: x["rrf_score"], reverse=True)
    candidates = candidates[:top_k_retrieve]

    trace["retrieve_ms"]    = round((time.perf_counter() - t) * 1000)
    trace["candidates_count"] = len(candidates)

    if not candidates:
        return {
            "context":        "",
            "chunks":         [],
            "queries_used":   queries,
            "pipeline_trace": {**trace, "total_ms": round((time.perf_counter() - t0) * 1000)},
        }

    # ── Stage 3: Reranking ────────────────────────────────────────────
    if do_rerank:
        t = time.perf_counter()
        reranked = await reranker.rerank(query, candidates, top_k=top_k_rerank)
        trace["rerank_ms"]     = round((time.perf_counter() - t) * 1000)
        trace["reranked_count"] = len(reranked)
    else:
        reranked = candidates[:top_k_rerank]
        trace["rerank_ms"] = 0

    # ── Stage 4: Context Compression ─────────────────────────────────
    if do_compress:
        t = time.perf_counter()
        compressed = compressor.compress(query, reranked)
        trace["compress_ms"] = round((time.perf_counter() - t) * 1000)

        # Build context string from compressed text
        context_parts = []
        for c in compressed:
            src  = c.get("filename", "unknown")
            text = c.get("compressed_text") or c.get("text", "")
            context_parts.append(f"[Source: {src}]\n{text}")
    else:
        compressed = reranked
        context_parts = []
        for c in reranked:
            src  = c.get("filename", "unknown")
            text = c.get("text", "")
            context_parts.append(f"[Source: {src}]\n{text}")
        trace["compress_ms"] = 0

    context = "\n\n---\n\n".join(context_parts)

    trace["total_ms"]         = round((time.perf_counter() - t0) * 1000)
    trace["final_chunks"]     = len(compressed)
    trace["context_chars"]    = len(context)

    return {
        "context":        context,
        "chunks":         compressed,
        "queries_used":   queries,
        "pipeline_trace": trace,
    }
