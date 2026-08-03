"""
Incremental Indexer — tracks chunk hashes to skip unchanged content.

Why?
  Re-uploading a 500-page PDF re-indexes all 1,000 chunks even if
  only 3 paragraphs changed. This wastes 30+ seconds.

  Incremental indexing stores a hash of each chunk's content.
  On re-upload, only changed/new chunks are re-embedded. Unchanged
  chunks are skipped entirely.

Storage: SQLite table 'chunk_hashes' (lightweight, no extra dependency)
"""
from __future__ import annotations
import hashlib
from typing import List, Tuple

import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "offlinegpt.db"


async def init_table():
    """Create chunk_hashes table if not exists."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chunk_hashes (
                chunk_id   TEXT PRIMARY KEY,
                doc_id     TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunk_hashes_doc ON chunk_hashes(doc_id)"
        )
        await db.commit()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


async def filter_changed_chunks(
    doc_id: str,
    chunks: List[str],
    chunk_ids: List[str],
) -> Tuple[List[str], List[str]]:
    """
    Compare chunks against stored hashes.

    Returns (new_chunks, new_ids) — only chunks that are new or changed.
    Unchanged chunks are skipped.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT chunk_id, content_hash FROM chunk_hashes WHERE doc_id = ?",
                (doc_id,)
            ) as cur:
                existing = {r["chunk_id"]: r["content_hash"] for r in await cur.fetchall()}

        new_chunks, new_ids = [], []
        for cid, text in zip(chunk_ids, chunks):
            h = _hash(text)
            if existing.get(cid) != h:
                new_chunks.append(text)
                new_ids.append(cid)

        return new_chunks, new_ids

    except Exception as e:
        print(f"[Incremental] filter error: {e} — indexing all chunks")
        return chunks, chunk_ids


async def save_hashes(doc_id: str, chunks: List[str], chunk_ids: List[str]):
    """Persist chunk hashes after successful indexing."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            for cid, text in zip(chunk_ids, chunks):
                await db.execute(
                    "INSERT OR REPLACE INTO chunk_hashes (chunk_id, doc_id, content_hash)"
                    " VALUES (?, ?, ?)",
                    (cid, doc_id, _hash(text)),
                )
            await db.commit()
    except Exception as e:
        print(f"[Incremental] save_hashes error: {e}")


async def delete_document_hashes(doc_id: str):
    """Remove stored hashes when a document is deleted."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM chunk_hashes WHERE doc_id = ?", (doc_id,))
            await db.commit()
    except Exception as e:
        print(f"[Incremental] delete error: {e}")
