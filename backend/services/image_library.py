"""
Image library: SQLite metadata for every generated image.
Lets the Library view show prompt, model, size, date, etc.
"""
import uuid
import aiosqlite
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

DB_PATH = Path(__file__).parent.parent / "data" / "offlinegpt.db"

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS image_library (
    id          TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    prompt      TEXT NOT NULL DEFAULT '',
    model_id    TEXT NOT NULL DEFAULT '',
    provider    TEXT NOT NULL DEFAULT 'diffusers',
    width       INTEGER NOT NULL DEFAULT 512,
    height      INTEGER NOT NULL DEFAULT 512,
    steps       INTEGER NOT NULL DEFAULT 20,
    seed        INTEGER NOT NULL DEFAULT -1,
    file_bytes  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
"""


async def init_table():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(CREATE_SQL)
        await db.commit()


async def add_image(
    filename:   str,
    prompt:     str,
    model_id:   str,
    provider:   str,
    width:      int,
    height:     int,
    steps:      int,
    seed:       int,
    file_bytes: int,
) -> dict:
    img_id = uuid.uuid4().hex
    now    = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Ensure table exists (self-healing — no reliance on startup init_table)
        await db.execute(CREATE_SQL)
        await db.commit()
        await db.execute(
            """INSERT INTO image_library
               (id, filename, prompt, model_id, provider, width, height, steps, seed, file_bytes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (img_id, filename, prompt, model_id, provider, width, height, steps, seed, file_bytes, now),
        )
        await db.commit()
        async with db.execute("SELECT * FROM image_library WHERE id=?", (img_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else {}


async def list_images(limit: int = 200, offset: int = 0) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM image_library ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def delete_image(img_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT filename FROM image_library WHERE id=?", (img_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            return False
        # Remove physical file
        from .image.manager import IMAGES_DIR
        path = IMAGES_DIR / row["filename"]
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass
        await db.execute("DELETE FROM image_library WHERE id=?", (img_id,))
        await db.commit()
        return True


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*), SUM(file_bytes) FROM image_library") as cur:
            row = await cur.fetchone()
            count      = row[0] or 0
            total_bytes = row[1] or 0
            return {"count": count, "total_bytes": total_bytes,
                    "total_label": _fmt(total_bytes)}


def _fmt(n: int) -> str:
    if n < 1024: return f"{n} B"
    if n < 1024**2: return f"{n/1024:.1f} KB"
    if n < 1024**3: return f"{n/1024**2:.1f} MB"
    return f"{n/1024**3:.2f} GB"
