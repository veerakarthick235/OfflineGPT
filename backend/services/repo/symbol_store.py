"""
Symbol Store — persists extracted code symbols to SQLite + ChromaDB.

SQLite tables:
  repos          — indexed repo metadata
  repo_symbols   — every function/class/method with code snippet
  repo_dependencies — import relationships between files

ChromaDB collection:
  code_chunks — semantic search over code (using nomic-embed-text)

This enables two search modes:
  1. Exact: "find function named 'login'" → SQLite symbol lookup
  2. Semantic: "how does authentication work?" → ChromaDB vector search
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "offlinegpt.db"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# ── Schema ────────────────────────────────────────────────────────────

async def init_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS repos (
                id           TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                path         TEXT NOT NULL UNIQUE,
                language     TEXT DEFAULT 'mixed',
                file_count   INTEGER DEFAULT 0,
                symbol_count INTEGER DEFAULT 0,
                indexed_at   TEXT DEFAULT (datetime('now')),
                updated_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS repo_symbols (
                id           TEXT PRIMARY KEY,
                repo_id      TEXT NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
                file_path    TEXT NOT NULL,
                symbol_name  TEXT,
                symbol_type  TEXT NOT NULL,
                start_line   INTEGER DEFAULT 1,
                end_line     INTEGER DEFAULT 1,
                code         TEXT NOT NULL,
                docstring    TEXT,
                signature    TEXT,
                language     TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_symbols_repo
                ON repo_symbols(repo_id);
            CREATE INDEX IF NOT EXISTS idx_symbols_name
                ON repo_symbols(symbol_name COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_symbols_file
                ON repo_symbols(file_path);
            CREATE INDEX IF NOT EXISTS idx_symbols_type
                ON repo_symbols(symbol_type);

            CREATE TABLE IF NOT EXISTS repo_dependencies (
                id              TEXT PRIMARY KEY,
                repo_id         TEXT NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
                source_file     TEXT NOT NULL,
                imported_module TEXT NOT NULL,
                import_type     TEXT DEFAULT 'import',
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_deps_repo
                ON repo_dependencies(repo_id);
            CREATE INDEX IF NOT EXISTS idx_deps_source
                ON repo_dependencies(source_file);
        """)
        await db.commit()


# ── Repo CRUD ─────────────────────────────────────────────────────────

async def create_repo(name: str, path: str) -> dict:
    rid = str(uuid.uuid4())
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Upsert by path
        await db.execute("""
            INSERT INTO repos (id, name, path, indexed_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                name       = excluded.name,
                updated_at = excluded.updated_at
        """, (rid, name, path, now, now))
        await db.commit()
        async with db.execute("SELECT * FROM repos WHERE path = ?", (path,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else {"id": rid, "name": name, "path": path}


async def update_repo_stats(repo_id: str, file_count: int, symbol_count: int, language: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE repos
            SET file_count=?, symbol_count=?, language=?, updated_at=?
            WHERE id=?
        """, (file_count, symbol_count, language, _now(), repo_id))
        await db.commit()


async def list_repos() -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM repos ORDER BY updated_at DESC") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_repo(repo_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM repos WHERE id=?", (repo_id,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def get_repo_by_path(path: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM repos WHERE path=?", (path,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def delete_repo(repo_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM repos WHERE id=?", (repo_id,))
        await db.commit()


# ── Symbol CRUD ───────────────────────────────────────────────────────

async def save_symbols(repo_id: str, chunks: list) -> int:
    """Bulk insert symbols. Returns count inserted."""
    if not chunks:
        return 0
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        # Clear old symbols for this repo
        await db.execute("DELETE FROM repo_symbols WHERE repo_id=?", (repo_id,))
        for c in chunks:
            await db.execute("""
                INSERT OR REPLACE INTO repo_symbols
                (id, repo_id, file_path, symbol_name, symbol_type,
                 start_line, end_line, code, docstring, signature, language, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                c.chunk_id, repo_id, c.file_path, c.symbol_name, c.symbol_type,
                c.start_line, c.end_line, c.code[:4000],
                c.docstring, c.signature, c.language, now,
            ))
        await db.commit()
    return len(chunks)


async def search_symbols_by_name(repo_id: str, name: str, limit: int = 10) -> List[dict]:
    """Exact and prefix symbol name search (case-insensitive)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM repo_symbols
            WHERE repo_id=? AND symbol_name LIKE ?
            ORDER BY
                CASE WHEN symbol_name = ? THEN 0 ELSE 1 END,
                symbol_type, file_path
            LIMIT ?
        """, (repo_id, f"%{name}%", name, limit)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_file_symbols(repo_id: str, file_path: str) -> List[dict]:
    """All symbols from a specific file."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM repo_symbols
            WHERE repo_id=? AND file_path=?
            ORDER BY start_line
        """, (repo_id, file_path)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def list_symbols(repo_id: str, symbol_type: Optional[str] = None, limit: int = 100) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if symbol_type:
            async with db.execute("""
                SELECT id, repo_id, file_path, symbol_name, symbol_type,
                       start_line, end_line, signature, language
                FROM repo_symbols WHERE repo_id=? AND symbol_type=?
                ORDER BY file_path, start_line LIMIT ?
            """, (repo_id, symbol_type, limit)) as cur:
                return [dict(r) for r in await cur.fetchall()]
        else:
            async with db.execute("""
                SELECT id, repo_id, file_path, symbol_name, symbol_type,
                       start_line, end_line, signature, language
                FROM repo_symbols WHERE repo_id=?
                ORDER BY file_path, start_line LIMIT ?
            """, (repo_id, limit)) as cur:
                return [dict(r) for r in await cur.fetchall()]


# ── Dependencies CRUD ─────────────────────────────────────────────────

async def save_dependencies(repo_id: str, deps: List[Dict[str, str]]) -> int:
    if not deps:
        return 0
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM repo_dependencies WHERE repo_id=?", (repo_id,))
        for d in deps:
            await db.execute("""
                INSERT INTO repo_dependencies
                (id, repo_id, source_file, imported_module, import_type, created_at)
                VALUES (?,?,?,?,?,?)
            """, (str(uuid.uuid4()), repo_id, d["source_file"],
                  d["imported_module"], d.get("import_type","import"), _now()))
        await db.commit()
    return len(deps)


async def get_file_dependencies(repo_id: str, file_path: str) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM repo_dependencies
            WHERE repo_id=? AND source_file=?
            ORDER BY imported_module
        """, (repo_id, file_path)) as cur:
            return [dict(r) for r in await cur.fetchall()]
