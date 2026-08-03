"""
Attachment Pipeline — orchestrates file upload, parsing, and RAG indexing.

Flow:
  1. Save file to disk  (uploader)
  2. Detect file type   (file_detector)
  3. Parse → extract text  (appropriate parser)
  4. Update attachment record in SQLite
  5. Index text into ChromaDB attachments collection
  6. Update BM25 index

This is the single entry point for all attachment processing.
"""
from __future__ import annotations
import asyncio
import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

from . import attachment_store as store
from .file_detector import detect_file_type, get_mime_type

UPLOAD_DIR = Path(__file__).parent.parent.parent / "data" / "uploads"

# ── ChromaDB collection for attachments ─────────────────────────
_collection = None

def _get_collection():
    global _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb
        client = chromadb.PersistentClient(
            path=str(Path(__file__).parent.parent.parent / "data" / "chroma_db")
        )
        _collection = client.get_or_create_collection(
            name="attachments",
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        print(f"[Attachments] ChromaDB not available: {e}")
        _collection = None
    return _collection


def _get_embedder():
    """Get the same sentence-transformer used by the main RAG system."""
    try:
        from ...rag.embeddings import get_embedder as rag_embedder
        return rag_embedder()
    except Exception:
        pass
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Simple sliding-window chunker."""
    words  = text.split()
    chunks = []
    i      = 0
    while i < len(words):
        chunk = " ".join(words[i: i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return [c for c in chunks if c.strip()]


def _index_text(attachment_id: str, filename: str, file_type: str, text: str):
    """Index text chunks into ChromaDB attachments collection."""
    col = _get_collection()
    if col is None or not text.strip():
        return
    try:
        embedder = _get_embedder()
        chunks   = _chunk_text(text)
        if not chunks:
            return

        ids       = [f"{attachment_id}_chunk_{i}" for i in range(len(chunks))]
        metas     = [{
            "attachment_id": attachment_id,
            "filename":      filename,
            "file_type":     file_type,
            "chunk_index":   i,
        } for i in range(len(chunks))]

        if embedder:
            embeddings = embedder.encode(chunks, show_progress_bar=False).tolist()
            col.add(ids=ids, documents=chunks, metadatas=metas, embeddings=embeddings)
        else:
            col.add(ids=ids, documents=chunks, metadatas=metas)
    except Exception as e:
        print(f"[Attachments] ChromaDB index error: {e}")


async def process_attachment(
    file_bytes:      bytes,
    original_name:   str,
    conversation_id: Optional[str] = None,
) -> dict:
    """
    Full pipeline: save → detect → parse → index.
    Returns the attachment dict from SQLite.
    """
    # ── 1. Save file ──────────────────────────────────────────────
    aid      = str(uuid.uuid4())
    safe_ext = Path(original_name).suffix.lower()
    safe_name = f"{aid}{safe_ext}"

    dest_dir = UPLOAD_DIR / aid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name

    dest_path.write_bytes(file_bytes)

    # ── 2. Detect type ────────────────────────────────────────────
    cat, label, icon = detect_file_type(original_name)
    mime             = get_mime_type(original_name)
    file_size        = len(file_bytes)

    # ── 3. Create DB record (status=uploading) ────────────────────
    att = await store.create_attachment(
        filename        = safe_name,
        original_name   = original_name,
        file_type       = cat,
        mime_type       = mime,
        file_path       = str(dest_path),
        file_size       = file_size,
        conversation_id = conversation_id,
    )
    att_id = att["id"] if isinstance(att, dict) else aid

    # ── 4. Parse (in background, do not block upload response) ────
    asyncio.create_task(_parse_and_index(att_id, str(dest_path), original_name, cat, dest_dir))

    return {
        **att,
        "icon": icon,
        "label": label,
        "status": "processing",
    }


async def _parse_and_index(
    att_id:       str,
    file_path:    str,
    original_name: str,
    cat:          str,
    dest_dir:     Path,
):
    """Background task: parse file, update SQLite, index into ChromaDB."""
    await store.update_attachment(att_id, status="processing")
    try:
        text, pages = await _run_parser(file_path, original_name, cat, dest_dir)

        # Update DB
        preview = _clean_text(text)[:500]
        await store.update_attachment(
            att_id,
            status       = "ready",
            text_preview = preview,
            full_text    = _clean_text(text),
            page_count   = pages,
        )

        # Index into ChromaDB (sync call in thread)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, _index_text, att_id, original_name, cat, text
        )

    except Exception as e:
        print(f"[Attachments] Parse error for {att_id}: {e}")
        await store.update_attachment(att_id, status="error", error_msg=str(e)[:500])


async def _run_parser(file_path: str, original_name: str, cat: str, dest_dir: Path):
    """Dispatch to correct parser based on category."""
    loop = asyncio.get_event_loop()

    if cat == "pdf":
        from .parsers.pdf_parser import parse_pdf
        return await loop.run_in_executor(None, parse_pdf, file_path)

    elif cat == "document":
        from .parsers.document_parser import parse_document
        return await loop.run_in_executor(None, parse_document, file_path, cat)

    elif cat == "slides":
        from .parsers.slide_parser import parse_slides
        return await loop.run_in_executor(None, parse_slides, file_path)

    elif cat == "data":
        from .parsers.data_parser import parse_data
        return await loop.run_in_executor(None, parse_data, file_path)

    elif cat == "image":
        from .parsers.image_parser import parse_image
        return await parse_image(file_path)

    elif cat == "code":
        from .parsers.code_parser import parse_code
        return await loop.run_in_executor(None, parse_code, file_path)

    elif cat == "archive":
        from .parsers.archive_parser import parse_archive, _detect_repository
        summary, extracted_paths, count = await loop.run_in_executor(
            None, parse_archive, file_path, dest_dir
        )
        # If repo detected, index each code file
        if extracted_paths and _detect_repository(extracted_paths):
            asyncio.create_task(_index_repo_files(extracted_paths))
        return summary, count

    else:
        # Unknown: try plain text
        from .parsers.document_parser import _parse_plaintext
        return await loop.run_in_executor(None, _parse_plaintext, file_path)


async def _index_repo_files(paths):
    """Index extracted code files using existing repo indexer."""
    try:
        from ..repo.code_chunker import chunk_file
        loop = asyncio.get_event_loop()
        for p in paths[:200]:  # max 200 files from ZIP
            if p.suffix.lower() in {".py", ".js", ".ts", ".java", ".cpp", ".go", ".rs"}:
                try:
                    code = p.read_text(encoding="utf-8", errors="replace")
                    await loop.run_in_executor(None, chunk_file, str(p), code)
                except Exception:
                    pass
    except Exception as e:
        print(f"[Attachments] Repo indexing error: {e}")


def _clean_text(text: str) -> str:
    """Remove excessive whitespace."""
    return re.sub(r"\n{3,}", "\n\n", text).strip()


async def build_attachment_context(attachment_ids: list[str], query: str = "") -> str:
    """
    Build context block for LLM from attachment_ids.
    Combines full_text (for small files) + semantic search hits (for large files).
    """
    if not attachment_ids:
        return ""

    parts = []

    for aid in attachment_ids:
        att = await store.get_attachment(aid)
        if not att:
            continue

        fname    = att.get("original_name", att.get("filename", "file"))
        file_type = att.get("file_type", "document")
        status   = att.get("status", "")
        icon     = {"pdf": "📄", "image": "🖼️", "data": "📊",
                    "code": "💻", "document": "📝", "slides": "📊",
                    "archive": "📦"}.get(file_type, "📎")

        if status == "processing":
            parts.append(f"{icon} [{fname}] — Still processing, please wait.")
            continue
        if status == "error":
            err = att.get("error_msg", "unknown error")
            parts.append(f"{icon} [{fname}] — Processing failed: {err}")
            continue

        full_text = att.get("full_text", "") or await store.get_full_text(aid)

        if full_text:
            # For short texts include all, for long ones do semantic search
            if len(full_text) <= 6000:
                parts.append(
                    f"{icon} [{fname}] ({file_type.upper()}):\n{full_text}"
                )
            else:
                # Semantic search in ChromaDB for most relevant chunks
                relevant = _semantic_search(aid, query, top_k=5)
                if relevant:
                    parts.append(
                        f"{icon} [{fname}] ({file_type.upper()}) — Relevant sections:\n"
                        + "\n---\n".join(relevant)
                    )
                else:
                    # Fallback to text preview
                    preview = full_text[:4000]
                    parts.append(
                        f"{icon} [{fname}] ({file_type.upper()}) — Preview:\n{preview}\n"
                        f"[File has {len(full_text):,} characters total]"
                    )
        else:
            preview = att.get("text_preview", "")
            parts.append(
                f"{icon} [{fname}] ({file_type.upper()}) — Preview:\n{preview}"
            )

    if not parts:
        return ""

    return (
        "The user has attached the following file(s):\n\n"
        + "\n\n" + "═" * 50 + "\n\n".join(parts)
        + "\n\n"
        + "Answer the user's question using the content from these attached files."
    )


def _semantic_search(attachment_id: str, query: str, top_k: int = 5) -> list[str]:
    """Search ChromaDB for relevant chunks from a specific attachment."""
    if not query.strip():
        return []
    try:
        col      = _get_collection()
        embedder = _get_embedder()
        if col is None or embedder is None:
            return []
        q_emb = embedder.encode([query]).tolist()
        results = col.query(
            query_embeddings = q_emb,
            n_results        = top_k,
            where            = {"attachment_id": attachment_id},
        )
        docs = results.get("documents", [[]])[0]
        return [d for d in docs if d]
    except Exception:
        return []
