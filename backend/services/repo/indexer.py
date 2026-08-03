"""
Repository Indexer — orchestrates full repo indexing.

Pipeline:
  1. Walk repo directory (languages.walk_repo)
  2. For each file:
     a. Read source
     b. Extract code chunks (code_chunker.chunk_file)
     c. Extract dependencies (dependency_graph.extract_dependencies)
  3. Bulk save symbols to SQLite (symbol_store.save_symbols)
  4. Bulk save deps to SQLite (symbol_store.save_dependencies)
  5. Embed all chunks in ChromaDB for semantic search
  6. Update repo stats

Designed for async streaming progress — yields progress events
so the API endpoint can stream them back to the frontend.
"""
from __future__ import annotations
import asyncio
from collections import Counter
from pathlib import Path
from typing import AsyncIterator, Optional

from .languages import walk_repo, FileInfo
from .code_chunker import chunk_file, CodeChunk
from .dependency_graph import extract_dependencies
from . import symbol_store


async def index_repo(
    repo_path:  str,
    repo_name:  Optional[str] = None,
    max_files:  int = 2000,
) -> AsyncIterator[dict]:
    """
    Index a repository. Yields progress dicts:
      { status, file, progress, total, phase }

    Usage:
      async for event in index_repo("/path/to/repo"):
          print(event)
    """
    root = Path(repo_path).resolve()
    name = repo_name or root.name

    yield {"phase": "init", "status": "Starting indexing", "file": name}

    # ── 1. Create / update repo record ───────────────────────────────
    repo = await symbol_store.create_repo(name, str(root))
    repo_id = repo["id"]

    yield {"phase": "walk", "status": "Walking directory tree…", "repo_id": repo_id}

    # ── 2. Walk directory ─────────────────────────────────────────────
    files = walk_repo(root, max_files=max_files)
    total = len(files)

    yield {"phase": "walk", "status": f"Found {total} files to index", "total": total}

    if total == 0:
        yield {"phase": "done", "status": "No files found", "repo_id": repo_id}
        return

    # ── 3. Extract chunks + deps ──────────────────────────────────────
    all_chunks: list[CodeChunk] = []
    all_deps:   list[dict]      = []
    lang_counter: Counter       = Counter()
    errors = 0

    for i, file_info in enumerate(files):
        try:
            source = file_info.path.read_text(encoding="utf-8", errors="replace")
            if not source.strip():
                continue

            # Code chunking
            chunks = chunk_file(source, file_info.rel_path, repo_id, file_info.language)
            all_chunks.extend(chunks)

            # Dependency extraction
            deps = extract_dependencies(file_info, source)
            all_deps.extend(deps)

            lang_counter[file_info.language] += 1

        except Exception as e:
            errors += 1
            continue

        # Yield progress every 20 files (don't flood the stream)
        if (i + 1) % 20 == 0 or i == total - 1:
            yield {
                "phase":    "indexing",
                "status":   f"Indexed {i+1}/{total} files",
                "progress": i + 1,
                "total":    total,
                "chunks":   len(all_chunks),
                "errors":   errors,
            }
            await asyncio.sleep(0)  # yield control

    yield {"phase": "saving", "status": f"Saving {len(all_chunks)} symbols to database…"}

    # ── 4. Save to SQLite ─────────────────────────────────────────────
    saved_symbols = await symbol_store.save_symbols(repo_id, all_chunks)
    saved_deps    = await symbol_store.save_dependencies(repo_id, all_deps)

    # ── 5. Embed in ChromaDB ──────────────────────────────────────────
    yield {"phase": "embedding", "status": f"Embedding {saved_symbols} symbols in ChromaDB…"}

    embedded = await _embed_chunks(repo_id, all_chunks)

    # ── 6. Update stats ───────────────────────────────────────────────
    primary_lang = lang_counter.most_common(1)[0][0] if lang_counter else "unknown"
    await symbol_store.update_repo_stats(
        repo_id      = repo_id,
        file_count   = total,
        symbol_count = saved_symbols,
        language     = primary_lang,
    )

    yield {
        "phase":        "done",
        "status":       "Indexing complete",
        "repo_id":      repo_id,
        "repo_name":    name,
        "file_count":   total,
        "symbol_count": saved_symbols,
        "dep_count":    saved_deps,
        "embedded":     embedded,
        "language":     primary_lang,
        "lang_breakdown": dict(lang_counter.most_common(10)),
        "errors":       errors,
    }


async def _embed_chunks(repo_id: str, chunks: list[CodeChunk]) -> int:
    """
    Embed code chunks in ChromaDB for semantic search.
    Batches to avoid overwhelming Ollama.
    """
    if not chunks:
        return 0

    from ...services import chroma_db

    batch_size = 50
    embedded   = 0

    # Clear old embeddings for this repo
    try:
        chroma_db.delete_repo_chunks(repo_id)
    except Exception:
        pass

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i: i + batch_size]
        try:
            texts = []
            ids   = []
            metas = []

            for c in batch:
                # Build a rich text for embedding:
                # include symbol name, signature, and code
                parts = []
                if c.symbol_name:
                    parts.append(f"# {c.symbol_name}")
                if c.signature:
                    parts.append(c.signature)
                if c.docstring:
                    parts.append(c.docstring)
                parts.append(c.code[:1500])

                texts.append("\n".join(parts))
                ids.append(c.chunk_id)
                metas.append({
                    "repo_id":     repo_id,
                    "file_path":   c.file_path,
                    "symbol_name": c.symbol_name or "",
                    "symbol_type": c.symbol_type,
                    "language":    c.language,
                    "start_line":  c.start_line,
                })

            chroma_db.upsert_code_chunks(ids, texts, metas)
            embedded += len(batch)

        except Exception as e:
            print(f"[RepoIndexer] embed batch error: {e}")

        await asyncio.sleep(0)

    return embedded
