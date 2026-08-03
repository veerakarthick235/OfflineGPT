"""
Execution Store — persists code execution history to SQLite.

Schema:
  executions
    id, language, code, stdout, stderr, exit_code,
    duration_ms, success, error, created_at, conversation_id

Useful for:
  - Showing execution history in the UI
  - Letting the AI reference previous run outputs
  - Debugging failed executions
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import aiosqlite

DB_PATH = Path(__file__).parent.parent.parent / "data" / "offlinegpt.db"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


async def init_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS executions (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT,
                language        TEXT NOT NULL,
                code            TEXT NOT NULL,
                stdout          TEXT DEFAULT '',
                stderr          TEXT DEFAULT '',
                exit_code       INTEGER DEFAULT 0,
                duration_ms     REAL DEFAULT 0,
                success         INTEGER DEFAULT 1,
                error           TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_exec_conv
                ON executions(conversation_id);
        """)
        await db.commit()


async def save_execution(
    language:        str,
    code:            str,
    result:          dict,
    conversation_id: Optional[str] = None,
) -> dict:
    eid = str(uuid.uuid4())
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO executions
            (id, conversation_id, language, code, stdout, stderr,
             exit_code, duration_ms, success, error, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            eid, conversation_id, language, code[:8000],
            result.get("stdout", "")[:4000],
            result.get("stderr", "")[:2000],
            result.get("exit_code", 0),
            result.get("duration_ms", 0),
            1 if result.get("success") else 0,
            result.get("error"),
            now,
        ))
        await db.commit()
    return {"id": eid, "created_at": now, **result}


async def list_executions(conversation_id: Optional[str] = None, limit: int = 20) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if conversation_id:
            async with db.execute("""
                SELECT id, language, exit_code, duration_ms, success, created_at,
                       substr(code,1,100) as code_preview
                FROM executions WHERE conversation_id=?
                ORDER BY created_at DESC LIMIT ?
            """, (conversation_id, limit)) as cur:
                return [dict(r) for r in await cur.fetchall()]
        else:
            async with db.execute("""
                SELECT id, language, exit_code, duration_ms, success, created_at,
                       substr(code,1,100) as code_preview
                FROM executions ORDER BY created_at DESC LIMIT ?
            """, (limit,)) as cur:
                return [dict(r) for r in await cur.fetchall()]


async def get_execution(exec_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM executions WHERE id=?", (exec_id,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None
