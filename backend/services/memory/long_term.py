"""
Long-term Memory — stores persistent facts about the user.

Examples of stored facts:
  - "User's name is Veera"              (category: name)
  - "User is building an AI assistant"  (category: project)
  - "User prefers Python"               (category: preference)
  - "User works on Windows"             (category: preference)
  - "User is a freelancer"              (category: other)

These facts are extracted after EVERY conversation turn using Ollama.
They survive indefinitely across sessions.
On each chat turn, the top-5 relevant facts are injected into the prompt.

Table: user_facts
  id, fact, category, confidence, source_conv_id, created_at, updated_at
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import aiosqlite
from pathlib import Path

from . import summarizer
from .. import chroma_db

DB_PATH = Path(__file__).parent.parent.parent / "data" / "offlinegpt.db"
FACT_TOP_K = 5   # inject this many relevant facts per turn


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


async def init_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS user_facts (
                id             TEXT PRIMARY KEY,
                fact           TEXT NOT NULL,
                category       TEXT DEFAULT 'other',
                confidence     REAL DEFAULT 1.0,
                source_conv_id TEXT,
                created_at     TEXT DEFAULT (datetime('now')),
                updated_at     TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_user_facts_category
                ON user_facts(category);
        """)
        await db.commit()


async def extract_and_store(
    messages:        List[dict],
    conversation_id: str,
    model:           str = "llama3.2",
) -> List[dict]:
    """
    Extract user facts from a conversation and persist new ones.
    Duplicate detection: skip facts that are too similar to existing ones.
    Returns list of newly stored facts.
    """
    new_facts = await summarizer.extract_user_facts(messages, model=model)
    if not new_facts:
        return []

    # Load existing facts to deduplicate
    existing = await list_all()
    existing_texts = {f["fact"].lower() for f in existing}

    stored = []
    async with aiosqlite.connect(DB_PATH) as db:
        for item in new_facts:
            fact_text = item["fact"]
            # Simple dedup: skip if very similar text already stored
            if any(fact_text.lower() in e or e in fact_text.lower()
                   for e in existing_texts):
                continue

            fid = str(uuid.uuid4())
            now = _now()
            await db.execute(
                """INSERT INTO user_facts
                   (id, fact, category, confidence, source_conv_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (fid, fact_text, item["category"], 1.0, conversation_id, now, now),
            )
            stored.append({"id": fid, **item})
            existing_texts.add(fact_text.lower())

        await db.commit()

    # Embed new facts in ChromaDB
    for f in stored:
        try:
            chroma_db.upsert_user_fact(
                fact_id  = f["id"],
                text     = f["fact"],
                category = f["category"],
            )
        except Exception as e:
            print(f"[LongTermMemory] ChromaDB embed error: {e}")

    if stored:
        print(f"[LongTermMemory] Stored {len(stored)} new facts from conv {conversation_id[:8]}")

    return stored


async def retrieve_relevant(query: str, top_k: int = FACT_TOP_K) -> List[dict]:
    """
    Find facts relevant to the current query (semantic search).
    Falls back to returning recent facts if ChromaDB fails.
    """
    try:
        results = chroma_db.search_user_facts(query, top_k=top_k)
        if results:
            return results
    except Exception as e:
        print(f"[LongTermMemory] ChromaDB search error: {e}")

    # Fallback: return most recent facts
    return (await list_all())[:top_k]


async def list_all() -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_facts ORDER BY updated_at DESC"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def delete_fact(fact_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_facts WHERE id = ?", (fact_id,))
        await db.commit()
    try:
        chroma_db.delete_user_fact(fact_id)
    except Exception:
        pass


async def clear_all():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_facts")
        await db.commit()
