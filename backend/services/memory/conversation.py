"""
Conversation Memory — stores and retrieves summaries of past conversations.

Lifecycle:
  1. On every CHAT response, check if the conversation has grown long
  2. If message_count >= SUMMARIZE_THRESHOLD: summarize with Ollama
  3. Store summary in SQLite + embed in ChromaDB for semantic search
  4. On new chat turns, retrieve the 2 most relevant past conversation summaries
     and inject them as context: "Previous relevant conversations: ..."

This gives the AI continuity across sessions without loading all history.

Table: memory_summaries
  id, conversation_id, topic, summary, key_points (JSON), message_count, created_at
"""
from __future__ import annotations
import json
import uuid
from typing import List, Optional

import aiosqlite
from pathlib import Path

from . import summarizer
from .. import chroma_db

DB_PATH = Path(__file__).parent.parent.parent / "data" / "offlinegpt.db"

SUMMARIZE_THRESHOLD = 10   # summarize after this many messages
RETRIEVE_TOP_K      = 2    # inject this many past conversation summaries


async def init_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS memory_summaries (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL UNIQUE,
                topic           TEXT DEFAULT '',
                summary         TEXT NOT NULL,
                key_points      TEXT DEFAULT '[]',
                message_count   INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_memory_summaries_conv
                ON memory_summaries(conversation_id);
        """)
        await db.commit()


async def maybe_summarize(
    conversation_id: str,
    messages:        List[dict],
    model:           str = "llama3.2",
) -> Optional[dict]:
    """
    Summarize a conversation if it's long enough.
    Idempotent — re-summarizes if message count has grown significantly.
    
    Returns the summary dict if created/updated, else None.
    """
    if len(messages) < SUMMARIZE_THRESHOLD:
        return None

    # Check if we already have a recent summary
    existing = await get_summary(conversation_id)
    if existing and existing["message_count"] >= len(messages) - 2:
        return existing  # still fresh

    # Summarize
    result = await summarizer.summarize_conversation(messages, model=model)
    if not result["summary"]:
        return None

    sid = str(uuid.uuid4())
    now = _now()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO memory_summaries
                (id, conversation_id, topic, summary, key_points, message_count,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                topic         = excluded.topic,
                summary       = excluded.summary,
                key_points    = excluded.key_points,
                message_count = excluded.message_count,
                updated_at    = excluded.updated_at
        """, (
            sid, conversation_id,
            result["topic"], result["summary"],
            json.dumps(result["key_points"]),
            len(messages), now, now,
        ))
        await db.commit()

    # Embed in ChromaDB for semantic retrieval
    embed_text = f"{result['topic']}\n{result['summary']}"
    try:
        chroma_db.upsert_memory_summary(
            summary_id      = conversation_id,  # use conv_id for stable upsert
            text            = embed_text,
            conversation_id = conversation_id,
            topic           = result["topic"],
        )
    except Exception as e:
        print(f"[ConvMemory] ChromaDB upsert error: {e}")

    return {**result, "conversation_id": conversation_id, "message_count": len(messages)}


async def get_summary(conversation_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM memory_summaries WHERE conversation_id = ?",
            (conversation_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["key_points"] = json.loads(d.get("key_points", "[]"))
    return d


async def retrieve_relevant(query: str, exclude_conv_id: Optional[str] = None) -> List[dict]:
    """
    Find past conversation summaries relevant to the current query.
    Uses ChromaDB semantic search.
    """
    try:
        results = chroma_db.search_memory_summaries(query, top_k=RETRIEVE_TOP_K + 2)
    except Exception:
        results = []

    # Filter out current conversation
    filtered = [r for r in results if r.get("conversation_id") != exclude_conv_id]
    return filtered[:RETRIEVE_TOP_K]


async def list_all() -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM memory_summaries ORDER BY updated_at DESC"
        ) as cur:
            rows = await cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["key_points"] = json.loads(d.get("key_points", "[]"))
        result.append(d)
    return result


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
