"""
Attachment Store — SQLite persistence for uploaded files.

Table: attachments
  id              TEXT PK
  filename        TEXT
  original_name   TEXT
  file_type       TEXT    (pdf|image|document|data|code|archive)
  mime_type       TEXT
  file_path       TEXT    (absolute path on disk)
  file_size       INTEGER (bytes)
  status          TEXT    (uploading|processing|ready|error)
  text_preview    TEXT    (first 500 chars of extracted text)
  page_count      INTEGER
  conversation_id TEXT    (nullable — can be shared across convs)
  error_msg       TEXT
  created_at      TEXT

Index: by conversation_id
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import aiosqlite

DB_PATH = Path(__file__).parent.parent.parent / "data" / "offlinegpt.db"
UPLOAD_DIR = Path(__file__).parent.parent.parent / "data" / "uploads"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


async def init_table():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS attachments (
                id              TEXT PRIMARY KEY,
                filename        TEXT NOT NULL,
                original_name   TEXT NOT NULL,
                file_type       TEXT NOT NULL DEFAULT 'document',
                mime_type       TEXT DEFAULT '',
                file_path       TEXT NOT NULL,
                file_size       INTEGER DEFAULT 0,
                status          TEXT DEFAULT 'uploading',
                text_preview    TEXT DEFAULT '',
                full_text       TEXT DEFAULT '',
                page_count      INTEGER DEFAULT 1,
                conversation_id TEXT,
                error_msg       TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_attach_conv
                ON attachments(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_attach_status
                ON attachments(status);
        """)
        await db.commit()


async def create_attachment(
    filename:        str,
    original_name:   str,
    file_type:       str,
    mime_type:       str,
    file_path:       str,
    file_size:       int,
    conversation_id: Optional[str] = None,
) -> dict:
    aid = str(uuid.uuid4())
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("""
            INSERT INTO attachments
            (id, filename, original_name, file_type, mime_type,
             file_path, file_size, status, conversation_id, created_at)
            VALUES (?,?,?,?,?,?,?,'uploading',?,?)
        """, (aid, filename, original_name, file_type, mime_type,
               file_path, file_size, conversation_id, now))
        await db.commit()
        async with db.execute("SELECT * FROM attachments WHERE id=?", (aid,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else {"id": aid}


async def update_attachment(
    aid:          str,
    status:       Optional[str] = None,
    text_preview: Optional[str] = None,
    full_text:    Optional[str] = None,
    page_count:   Optional[int] = None,
    error_msg:    Optional[str] = None,
):
    sets = []
    vals = []
    if status       is not None: sets.append("status=?");       vals.append(status)
    if text_preview is not None: sets.append("text_preview=?"); vals.append(text_preview[:1000])
    if full_text    is not None: sets.append("full_text=?");    vals.append(full_text[:200_000])
    if page_count   is not None: sets.append("page_count=?");   vals.append(page_count)
    if error_msg    is not None: sets.append("error_msg=?");    vals.append(error_msg)
    if not sets:
        return
    vals.append(aid)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE attachments SET {','.join(sets)} WHERE id=?", vals)
        await db.commit()


async def get_attachment(aid: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM attachments WHERE id=?", (aid,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def list_attachments(conversation_id: Optional[str] = None, limit: int = 50) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if conversation_id:
            async with db.execute("""
                SELECT id,filename,original_name,file_type,mime_type,file_size,
                       status,text_preview,page_count,conversation_id,created_at
                FROM attachments WHERE conversation_id=?
                ORDER BY created_at DESC LIMIT ?
            """, (conversation_id, limit)) as cur:
                return [dict(r) for r in await cur.fetchall()]
        else:
            async with db.execute("""
                SELECT id,filename,original_name,file_type,mime_type,file_size,
                       status,text_preview,page_count,conversation_id,created_at
                FROM attachments ORDER BY created_at DESC LIMIT ?
            """, (limit,)) as cur:
                return [dict(r) for r in await cur.fetchall()]


async def delete_attachment(aid: str) -> Optional[str]:
    """Delete DB record. Returns file_path for caller to delete from disk."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT file_path FROM attachments WHERE id=?", (aid,)) as cur:
            row = await cur.fetchone()
        if row:
            await db.execute("DELETE FROM attachments WHERE id=?", (aid,))
            await db.commit()
            return dict(row)["file_path"]
    return None


async def get_full_text(aid: str) -> str:
    """Retrieve full extracted text for context injection."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT full_text FROM attachments WHERE id=?", (aid,)) as cur:
            row = await cur.fetchone()
    return row[0] if row else ""
