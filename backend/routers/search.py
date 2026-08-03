from fastapi import APIRouter, Query
from typing import Optional
from ..services import chroma_db

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def semantic_search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    conversation_id: Optional[str] = None,
):
    raw = chroma_db.search_messages(q, limit=limit, conversation_id=conversation_id)

    docs      = raw.get("documents", [[]])[0]
    metas     = raw.get("metadatas", [[]])[0]
    distances = raw.get("distances", [[]])[0]

    results = [
        {
            "content":            doc,
            "conversation_id":    m.get("conversation_id"),
            "conversation_title": m.get("conversation_title"),
            "role":               m.get("role"),
            "created_at":         m.get("created_at"),
            "score":              round(1 - dist, 4),
        }
        for doc, m, dist in zip(docs, metas, distances)
    ]

    return {"query": q, "results": results}
