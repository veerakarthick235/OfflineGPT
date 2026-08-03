"""
Attachments Router — /api/attachments/*

POST  /api/attachments/upload       — upload file(s), start processing
GET   /api/attachments              — list (by conversation_id)
GET   /api/attachments/{id}         — get single attachment
GET   /api/attachments/{id}/status  — poll processing status
GET   /api/attachments/{id}/text    — get extracted text
DELETE /api/attachments/{id}        — delete file + DB record
"""
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..services.attachments import attachment_store as store
from ..services.attachments.pipeline import process_attachment

router = APIRouter(prefix="/api/attachments", tags=["attachments"])

MAX_FILE_MB = 50


@router.post("/upload")
async def upload_attachment(
    files:           List[UploadFile] = File(...),
    conversation_id: Optional[str]    = Form(None),
):
    """Upload one or more files. Processing happens in background."""
    results = []
    for upload in files:
        if upload.size and upload.size > MAX_FILE_MB * 1024 * 1024:
            raise HTTPException(413, f"File '{upload.filename}' exceeds {MAX_FILE_MB}MB limit")

        file_bytes = await upload.read()
        if len(file_bytes) > MAX_FILE_MB * 1024 * 1024:
            raise HTTPException(413, f"File '{upload.filename}' exceeds {MAX_FILE_MB}MB limit")

        att = await process_attachment(
            file_bytes       = file_bytes,
            original_name    = upload.filename or "upload",
            conversation_id  = conversation_id,
        )
        results.append(att)

    return {"attachments": results, "count": len(results)}


@router.get("")
async def list_attachments(
    conversation_id: Optional[str] = None,
    limit:           int            = 50,
):
    """List attachments, optionally filtered by conversation."""
    atts = await store.list_attachments(conversation_id, limit)
    return {"attachments": atts, "count": len(atts)}


@router.get("/{attachment_id}/status")
async def get_attachment_status(attachment_id: str):
    """Poll status for a processing attachment."""
    att = await store.get_attachment(attachment_id)
    if not att:
        raise HTTPException(404, "Attachment not found")
    return {
        "id":     att["id"],
        "status": att["status"],
        "error":  att.get("error_msg"),
    }


@router.get("/{attachment_id}/text")
async def get_attachment_text(attachment_id: str):
    """Get full extracted text."""
    att = await store.get_attachment(attachment_id)
    if not att:
        raise HTTPException(404, "Attachment not found")
    text = att.get("full_text") or await store.get_full_text(attachment_id)
    return {
        "id":       attachment_id,
        "filename": att.get("original_name"),
        "text":     text,
        "length":   len(text),
    }


@router.get("/{attachment_id}")
async def get_attachment(attachment_id: str):
    """Get attachment metadata."""
    att = await store.get_attachment(attachment_id)
    if not att:
        raise HTTPException(404, "Attachment not found")
    return att


@router.delete("/{attachment_id}")
async def delete_attachment(attachment_id: str):
    """Delete attachment from DB and disk."""
    file_path = await store.delete_attachment(attachment_id)
    if file_path is None:
        raise HTTPException(404, "Attachment not found")

    # Delete file from disk (and parent uuid dir if empty)
    try:
        p = Path(file_path)
        if p.exists():
            p.unlink()
        parent = p.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
    except Exception as e:
        print(f"[Attachments] Disk delete warning: {e}")

    return {"deleted": True, "id": attachment_id}
