"""
Repo RAG — hybrid code search: exact symbol match + semantic vector search.

Why hybrid?
  - Exact search: "find function named 'authenticate'" → SQLite LIKE
  - Semantic search: "how does user login work?" → ChromaDB vectors
  
  RRF fusion combines both for best results.

Returns code chunks formatted for context injection.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any

from . import symbol_store
from ..chroma_db import search_code_chunks


async def search(
    query:   str,
    repo_id: Optional[str] = None,
    top_k:   int = 6,
) -> Dict[str, Any]:
    """
    Hybrid code search combining exact symbol matching + semantic search.

    Returns:
      {
        "context":  str,   # formatted code for LLM injection
        "symbols":  list,  # exact symbol matches
        "semantic": list,  # semantic matches
        "total":    int,
      }
    """
    # ── Stage 1: Exact symbol name search ────────────────────────────
    symbol_results: List[dict] = []
    if repo_id:
        # Extract potential symbol names from query (CamelCase, snake_case, anything)
        import re
        tokens = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\b", query)
        seen_ids = set()
        for token in tokens[:5]:
            hits = await symbol_store.search_symbols_by_name(repo_id, token, limit=3)
            for h in hits:
                if h["id"] not in seen_ids:
                    symbol_results.append(h)
                    seen_ids.add(h["id"])

    # ── Stage 2: Semantic vector search ──────────────────────────────
    semantic_results: List[dict] = []
    try:
        semantic_results = search_code_chunks(query, repo_id=repo_id, top_k=top_k)
    except Exception as e:
        print(f"[RepoRAG] semantic search error: {e}")

    # ── Stage 3: Merge + deduplicate (prefer exact matches first) ─────
    seen = set()
    merged = []

    # Exact matches first
    for s in symbol_results[:3]:
        cid = s.get("id") or s.get("chunk_id", "")
        if cid not in seen:
            merged.append({**s, "match_type": "exact"})
            seen.add(cid)

    # Semantic matches
    for s in semantic_results:
        cid = s.get("chunk_id", s.get("id", ""))
        if cid not in seen:
            merged.append({**s, "match_type": "semantic"})
            seen.add(cid)

    merged = merged[:top_k]

    # ── Stage 4: Format context ───────────────────────────────────────
    context_parts = []
    for chunk in merged:
        file_path   = chunk.get("file_path", "unknown")
        symbol_name = chunk.get("symbol_name", "")
        sym_type    = chunk.get("symbol_type", "")
        language    = chunk.get("language", "")
        start_line  = chunk.get("start_line", 1)
        code        = chunk.get("code", chunk.get("text", ""))

        header = f"[{file_path}:{start_line}]"
        if symbol_name:
            header += f" {sym_type}: {symbol_name}"

        context_parts.append(
            f"{header}\n```{language}\n{code[:1500]}\n```"
        )

    context = "\n\n---\n\n".join(context_parts)

    return {
        "context":  context,
        "symbols":  symbol_results,
        "semantic": semantic_results,
        "merged":   merged,
        "total":    len(merged),
    }


async def get_file_context(repo_id: str, file_path: str) -> str:
    """Get all symbols and dependencies for a specific file."""
    symbols = await symbol_store.get_file_symbols(repo_id, file_path)
    deps    = await symbol_store.get_file_dependencies(repo_id, file_path)

    parts = [f"# File: {file_path}"]

    if deps:
        parts.append("\n## Dependencies")
        for d in deps[:10]:
            parts.append(f"  → {d['imported_module']}")

    if symbols:
        parts.append("\n## Symbols")
        for s in symbols:
            sig = s.get("signature") or s.get("symbol_name", "")
            parts.append(f"  {s['symbol_type']}: {sig} (L{s['start_line']})")

    return "\n".join(parts)
