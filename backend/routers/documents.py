"""
Documents router — /api/documents/*

Upgraded with:
- Smart sentence-aware chunking (no mid-sentence cuts)
- BM25 index update on upload
- Incremental indexing (skip unchanged chunks)
- Cleans up BM25 + ChromaDB + hash table on delete
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List, Optional

from ..services import sqlite_db, chroma_db
from ..services.rag import bm25_index as bm25_mod
from ..services.rag import incremental
from ..services.rag.pipeline import smart_chunk
from ..schemas import RAGQueryRequest

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
async def list_documents():
    return await sqlite_db.list_documents()


@router.post("", status_code=201)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document and index it for RAG retrieval.

    Process:
    1. Parse text
    2. Smart chunking (sentence-aware)
    3. Incremental check — skip unchanged chunks
    4. Index new/changed chunks in ChromaDB (embeddings) + BM25 (keywords)
    5. Persist hash fingerprints
    """
    raw  = await file.read()
    text = raw.decode("utf-8", errors="ignore")
    if not text.strip():
        raise HTTPException(400, "File is empty or not readable as text")

    filename = file.filename or "upload.txt"

    # Save document record (get stable doc_id)
    doc = await sqlite_db.add_document(filename, text)
    doc_id = doc["id"]

    # Smart chunking
    chunks    = smart_chunk(text)
    chunk_ids = [f"{doc_id}__chunk_{i}" for i in range(len(chunks))]

    # Incremental indexing — only process changed chunks
    new_chunks, new_ids = await incremental.filter_changed_chunks(doc_id, chunks, chunk_ids)
    skipped = len(chunks) - len(new_chunks)

    if new_chunks:
        # ChromaDB (vector embeddings)
        chroma_db.add_document_chunks(doc_id, filename, new_chunks)

        # BM25 (keyword index) — always re-index all chunks for this doc
        # so BM25 stays consistent with ChromaDB
        bm25_mod.get_index().add_chunks(doc_id, filename, chunks, chunk_ids)

        # Save hashes for future incremental checks
        await incremental.save_hashes(doc_id, chunks, chunk_ids)

    return {
        **doc,
        "chunk_count":    len(chunks),
        "indexed_chunks": len(new_chunks),
        "skipped_chunks": skipped,
    }


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str):
    """Delete document from SQLite, ChromaDB, BM25 index, and hash table."""
    chroma_db.delete_document(doc_id)
    bm25_mod.get_index().remove_document(doc_id)
    await incremental.delete_document_hashes(doc_id)
    await sqlite_db.delete_document_record(doc_id)


@router.post("/rag-query")
async def rag_query_legacy(req: RAGQueryRequest):
    """
    Legacy endpoint — kept for backwards compatibility.
    For new code, use POST /api/rag/query (full Hybrid RAG pipeline).
    """
    chunks = chroma_db.search_documents(req.query, req.document_ids, req.top_k)
    context = "\n\n---\n\n".join(chunks)
    return {"query": req.query, "context": context, "chunks": chunks}
