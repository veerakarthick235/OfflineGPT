from pydantic import BaseModel
from typing import Optional, List


# ── Conversations ──────────────────────────────────
class ConversationCreate(BaseModel):
    title: str = "New Chat"
    model: str = "llama3.2"
    system_prompt: str = ""


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None


# ── Chat ───────────────────────────────────────────
class ChatRequest(BaseModel):
    conversation_id: str
    content: str
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    attachment_ids: List[str] = []   # Phase 6: Universal Attachment Intelligence


# ── RAG ────────────────────────────────────────────
class RAGQueryRequest(BaseModel):
    query: str
    document_ids: Optional[List[str]] = None
    top_k: int = 3
