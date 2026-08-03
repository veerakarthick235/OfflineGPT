from fastapi import APIRouter, HTTPException
from typing import Optional
from ..services import sqlite_db, chroma_db
from ..schemas import ConversationCreate, ConversationUpdate

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
async def list_conversations():
    return await sqlite_db.list_conversations()


@router.post("", status_code=201)
async def create_conversation(body: ConversationCreate):
    return await sqlite_db.create_conversation(
        title=body.title,
        model=body.model,
        system_prompt=body.system_prompt,
    )


@router.get("/{cid}")
async def get_conversation(cid: str):
    conv = await sqlite_db.get_conversation(cid)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.patch("/{cid}")
async def update_conversation(cid: str, body: ConversationUpdate):
    conv = await sqlite_db.update_conversation(
        cid,
        title=body.title,
        model=body.model,
        system_prompt=body.system_prompt,
    )
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.delete("/{cid}", status_code=204)
async def delete_conversation(cid: str):
    chroma_db.delete_conversation_messages(cid)
    await sqlite_db.delete_conversation(cid)
