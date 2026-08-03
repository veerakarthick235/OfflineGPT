"""
Memory Router — /api/memory/*

Expose memory management to the frontend:

  GET  /api/memory/facts          — list all long-term user facts
  POST /api/memory/facts          — manually add a fact
  DELETE /api/memory/facts/{id}   — delete a fact
  DELETE /api/memory/facts        — clear all facts

  GET  /api/memory/summaries      — list all conversation summaries
  POST /api/memory/summaries/{conv_id} — manually trigger summarization

  GET  /api/memory/status         — memory system health
"""
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..services.memory import long_term, conversation as conv_memory
from ..services        import sqlite_db

router = APIRouter(prefix="/api/memory", tags=["memory"])


# ── Schemas ────────────────────────────────────────────────────────────

class AddFactRequest(BaseModel):
    fact:     str
    category: Optional[str] = "other"


# ── Long-term Facts ────────────────────────────────────────────────────

@router.get("/facts")
async def get_facts():
    """List all stored long-term user facts."""
    facts = await long_term.list_all()
    return {"facts": facts, "count": len(facts)}


@router.post("/facts", status_code=201)
async def add_fact(req: AddFactRequest):
    """Manually add a long-term fact about the user."""
    import uuid
    from datetime import datetime, timezone
    from ..services import chroma_db

    fact_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    import aiosqlite
    from pathlib import Path
    DB_PATH = Path(__file__).parent.parent / "data" / "offlinegpt.db"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_facts (id, fact, category, confidence, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (fact_id, req.fact, req.category, 1.0, now, now),
        )
        await db.commit()

    try:
        chroma_db.upsert_user_fact(fact_id, req.fact, req.category or "other")
    except Exception:
        pass

    return {"id": fact_id, "fact": req.fact, "category": req.category, "created_at": now}


@router.delete("/facts/{fact_id}", status_code=204)
async def delete_fact(fact_id: str):
    """Delete a specific long-term fact."""
    await long_term.delete_fact(fact_id)


@router.delete("/facts", status_code=204)
async def clear_facts():
    """Clear all long-term user facts."""
    await long_term.clear_all()


# ── Conversation Summaries ─────────────────────────────────────────────

@router.get("/summaries")
async def get_summaries():
    """List all conversation summaries."""
    summaries = await conv_memory.list_all()
    return {"summaries": summaries, "count": len(summaries)}


@router.post("/summaries/{conversation_id}")
async def summarize_conversation(conversation_id: str, model: str = "llama3.2"):
    """Manually trigger summarization for a conversation."""
    conv = await sqlite_db.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    messages = [{"role": m["role"], "content": m["content"]} for m in conv["messages"]]
    if len(messages) < 2:
        raise HTTPException(400, "Conversation too short to summarize (need ≥2 messages)")

    result = await conv_memory.maybe_summarize(conversation_id, messages, model=model)
    if not result:
        return {"message": "Already summarized or too short", "summary": None}
    return result


# ── Status ─────────────────────────────────────────────────────────────

@router.get("/status")
async def memory_status():
    """Memory system health and counts."""
    facts     = await long_term.list_all()
    summaries = await conv_memory.list_all()
    return {
        "layers": {
            "working":      {"description": "Context window trimmer", "active": True},
            "conversation": {"description": "Auto-summarized past conversations",
                             "count": len(summaries)},
            "long_term":    {"description": "Persistent user facts",
                             "count": len(facts),
                             "categories": _count_categories(facts)},
        },
        "total_memories": len(facts) + len(summaries),
    }


def _count_categories(facts: list) -> dict:
    cats: dict = {}
    for f in facts:
        c = f.get("category", "other")
        cats[c] = cats.get(c, 0) + 1
    return cats
