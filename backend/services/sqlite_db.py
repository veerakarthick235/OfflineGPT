import aiosqlite
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

DB_PATH = Path(__file__).parent.parent / "data" / "offlinegpt.db"


async def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id            TEXT PRIMARY KEY,
                title         TEXT NOT NULL DEFAULT 'New Chat',
                model         TEXT NOT NULL DEFAULT 'llama3.2',
                system_prompt TEXT DEFAULT '',
                created_at    TEXT DEFAULT (datetime('now')),
                updated_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL
                                     REFERENCES conversations(id) ON DELETE CASCADE,
                role            TEXT NOT NULL
                                     CHECK(role IN ('user','assistant','system')),
                content         TEXT NOT NULL,
                tokens          INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS documents (
                id         TEXT PRIMARY KEY,
                filename   TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conv
                ON messages(conversation_id);
        """)
        await db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# ══════════════════════════════════════════════════
# CONVERSATIONS
# ══════════════════════════════════════════════════

async def create_conversation(
    title: str = "New Chat",
    model: str = "llama3.2",
    system_prompt: str = "",
) -> dict:
    cid = str(uuid.uuid4())
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (id,title,model,system_prompt,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (cid, title, model, system_prompt, now, now),
        )
        await db.commit()
    return {
        "id": cid, "title": title, "model": model,
        "system_prompt": system_prompt,
        "created_at": now, "updated_at": now,
        "messages": [], "message_count": 0,
    }


async def list_conversations() -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = """
            SELECT c.*,
                   COUNT(m.id) AS message_count,
                   (SELECT content FROM messages
                    WHERE conversation_id = c.id
                    ORDER BY created_at DESC LIMIT 1) AS last_message
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.updated_at DESC
        """
        async with db.execute(sql) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_conversation(cid: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM conversations WHERE id = ?", (cid,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        conv = dict(row)

        async with db.execute(
            "SELECT * FROM messages WHERE conversation_id = ?"
            " ORDER BY created_at ASC",
            (cid,),
        ) as cur:
            conv["messages"] = [dict(r) for r in await cur.fetchall()]

    return conv


async def update_conversation(cid: str, **kwargs) -> Optional[dict]:
    updates = {k: v for k, v in kwargs.items() if v is not None}
    if not updates:
        return await get_conversation(cid)
    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [cid]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE conversations SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
    return await get_conversation(cid)


async def delete_conversation(cid: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM conversations WHERE id = ?", (cid,))
        await db.commit()
    return True


# ══════════════════════════════════════════════════
# MESSAGES
# ══════════════════════════════════════════════════

async def add_message(
    conv_id: str, role: str, content: str, tokens: int = 0
) -> dict:
    mid = str(uuid.uuid4())
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (id,conversation_id,role,content,tokens,created_at)"
            " VALUES (?,?,?,?,?,?)",
            (mid, conv_id, role, content, tokens, now),
        )
        await db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conv_id),
        )
        await db.commit()
    return {
        "id": mid, "conversation_id": conv_id, "role": role,
        "content": content, "tokens": tokens, "created_at": now,
    }


async def get_messages(conv_id: str) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM messages WHERE conversation_id = ?"
            " ORDER BY created_at ASC",
            (conv_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ══════════════════════════════════════════════════
# DOCUMENTS
# ══════════════════════════════════════════════════

async def add_document(filename: str, content: str) -> dict:
    did = str(uuid.uuid4())
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO documents (id,filename,content,created_at) VALUES (?,?,?,?)",
            (did, filename, content, now),
        )
        await db.commit()
    return {"id": did, "filename": filename, "created_at": now}


async def list_documents() -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id,filename,created_at FROM documents ORDER BY created_at DESC"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_document(did: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM documents WHERE id = ?", (did,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def delete_document_record(did: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM documents WHERE id = ?", (did,))
        await db.commit()
