"""
ChromaDB wrapper — uses Ollama for embeddings (100% offline).
Requires: ollama pull nomic-embed-text
"""
import chromadb
from chromadb import EmbeddingFunction, Documents, Embeddings
from pathlib import Path
from typing import List, Optional
import httpx

CHROMA_PATH = Path(__file__).parent.parent / "data" / "chroma"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"
EMBED_DIM   = 768  # nomic-embed-text output dimension

_client: Optional[chromadb.ClientAPI] = None


# ── Offline embedding function via Ollama ────────────────────────────

class OllamaEmbedding(EmbeddingFunction):
    """Calls Ollama /api/embeddings — no internet required."""

    def __init__(self, model: str = EMBED_MODEL):
        self.model = model

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: Embeddings = []
        for text in input:
            try:
                r = httpx.post(
                    OLLAMA_EMBED_URL,
                    json={"model": self.model, "prompt": text or " "},
                    timeout=20,
                )
                r.raise_for_status()
                embeddings.append(r.json()["embedding"])
            except Exception as exc:
                print(f"[ChromaDB] embed error: {exc}")
                # Fallback: zero vector so the rest of the flow doesn't crash
                embeddings.append([0.0] * EMBED_DIM)
        return embeddings


_embed_fn = OllamaEmbedding()


# ── ChromaDB client ──────────────────────────────────────────────────

def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return _client


def _messages_col():
    return _get_client().get_or_create_collection(
        name="messages",
        embedding_function=_embed_fn,
        metadata={"hnsw:space": "cosine"},
    )


def _documents_col():
    return _get_client().get_or_create_collection(
        name="documents",
        embedding_function=_embed_fn,
        metadata={"hnsw:space": "cosine"},
    )


def _summaries_col():
    """ChromaDB collection for conversation summaries (memory layer 2)."""
    return _get_client().get_or_create_collection(
        name="memory_summaries",
        embedding_function=_embed_fn,
        metadata={"hnsw:space": "cosine"},
    )


def _facts_col():
    """ChromaDB collection for long-term user facts (memory layer 3)."""
    return _get_client().get_or_create_collection(
        name="user_facts",
        embedding_function=_embed_fn,
        metadata={"hnsw:space": "cosine"},
    )


# ── Memory: Conversation Summaries ───────────────────────────────────

def upsert_memory_summary(
    summary_id: str, text: str,
    conversation_id: str, topic: str,
):
    try:
        _summaries_col().upsert(
            documents=[text],
            ids=[summary_id],
            metadatas=[{"conversation_id": conversation_id, "topic": topic}],
        )
    except Exception as e:
        print(f"[ChromaDB] upsert_memory_summary error: {e}")


def search_memory_summaries(query: str, top_k: int = 3) -> list:
    try:
        col = _summaries_col()
        if col.count() == 0:
            return []
        n = min(top_k, col.count())
        results = col.query(query_texts=[query], n_results=n)
        docs   = results.get("documents", [[]])[0]
        metas  = results.get("metadatas", [[]])[0]
        return [{"summary": d, **m} for d, m in zip(docs, metas)]
    except Exception as e:
        print(f"[ChromaDB] search_memory_summaries error: {e}")
        return []


# ── Memory: Long-term User Facts ─────────────────────────────────────

def upsert_user_fact(fact_id: str, text: str, category: str):
    try:
        _facts_col().upsert(
            documents=[text],
            ids=[fact_id],
            metadatas=[{"category": category}],
        )
    except Exception as e:
        print(f"[ChromaDB] upsert_user_fact error: {e}")


def search_user_facts(query: str, top_k: int = 5) -> list:
    try:
        col = _facts_col()
        if col.count() == 0:
            return []
        n = min(top_k, col.count())
        results = col.query(query_texts=[query], n_results=n)
        docs  = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        return [{"fact": d, **m} for d, m in zip(docs, metas)]
    except Exception as e:
        print(f"[ChromaDB] search_user_facts error: {e}")
        return []


def delete_user_fact(fact_id: str):
    try:
        col = _facts_col()
        col.delete(ids=[fact_id])
    except Exception as e:
        print(f"[ChromaDB] delete_user_fact error: {e}")


# ── Phase 4: Repository Intelligence — Code Chunks ────────────────────

def _code_chunks_col():
    """ChromaDB collection for indexed repository code chunks."""
    return _get_client().get_or_create_collection(
        name="code_chunks",
        embedding_function=_embed_fn,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_code_chunks(ids: list, texts: list, metadatas: list):
    """Upsert a batch of code chunks into ChromaDB."""
    try:
        _code_chunks_col().upsert(
            documents=texts,
            ids=ids,
            metadatas=metadatas,
        )
    except Exception as e:
        print(f"[ChromaDB] upsert_code_chunks error: {e}")


def search_code_chunks(
    query:   str,
    repo_id: Optional[str] = None,
    top_k:   int = 6,
) -> List[dict]:
    """Semantic search over code chunks."""
    try:
        col = _code_chunks_col()
        if col.count() == 0:
            return []
        n      = min(top_k, col.count())
        kwargs = {"query_texts": [query], "n_results": n,
                  "include": ["documents", "metadatas"]}
        if repo_id:
            kwargs["where"] = {"repo_id": repo_id}
        results = col.query(**kwargs)
        docs  = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        out = []
        for doc, meta in zip(docs, metas):
            out.append({"text": doc, "code": doc, **meta})
        return out
    except Exception as e:
        print(f"[ChromaDB] search_code_chunks error: {e}")
        return []


def delete_repo_chunks(repo_id: str):
    """Delete all code chunks for a repo (called before re-indexing)."""
    try:
        col = _code_chunks_col()
        results = col.get(where={"repo_id": repo_id})
        if results["ids"]:
            col.delete(ids=results["ids"])
    except Exception as e:
        print(f"[ChromaDB] delete_repo_chunks error: {e}")


def add_message(
    message_id: str,
    content: str,
    conversation_id: str,
    conversation_title: str,
    role: str,
    created_at: str,
):
    if not content.strip():
        return
    try:
        col = _messages_col()
        col.upsert(
            documents=[content],
            ids=[message_id],
            metadatas=[{
                "conversation_id":    conversation_id,
                "conversation_title": conversation_title,
                "role":               role,
                "created_at":         created_at,
            }],
        )
    except Exception as exc:
        print(f"[ChromaDB] add_message error: {exc}")


def search_messages(
    query: str,
    limit: int = 10,
    conversation_id: Optional[str] = None,
) -> dict:
    try:
        col = _messages_col()
        count = col.count()
        if count == 0:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

        n = min(limit, count)
        kwargs: dict = {"query_texts": [query], "n_results": n}
        if conversation_id:
            kwargs["where"] = {"conversation_id": conversation_id}

        return col.query(**kwargs)
    except Exception as exc:
        print(f"[ChromaDB] search_messages error: {exc}")
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}


def delete_conversation_messages(conversation_id: str):
    try:
        col = _messages_col()
        results = col.get(where={"conversation_id": conversation_id})
        if results["ids"]:
            col.delete(ids=results["ids"])
    except Exception as exc:
        print(f"[ChromaDB] delete_conversation_messages error: {exc}")


# ── Document / RAG embeddings ────────────────────────────────────────

def add_document_chunks(doc_id: str, filename: str, chunks: List[str]):
    if not chunks:
        return
    try:
        col = _documents_col()
        ids   = [f"{doc_id}__chunk_{i}" for i in range(len(chunks))]
        metas = [
            {"document_id": doc_id, "filename": filename, "chunk_index": i}
            for i in range(len(chunks))
        ]
        col.upsert(documents=chunks, ids=ids, metadatas=metas)
    except Exception as exc:
        print(f"[ChromaDB] add_document_chunks error: {exc}")


def search_documents(
    query: str,
    document_ids: Optional[List[str]] = None,
    top_k: int = 3,
) -> List[str]:
    try:
        col = _documents_col()
        count = col.count()
        if count == 0:
            return []

        n = min(top_k, count)
        kwargs: dict = {"query_texts": [query], "n_results": n}
        if document_ids:
            kwargs["where"] = {"document_id": {"$in": document_ids}}

        results = col.query(**kwargs)
        return results.get("documents", [[]])[0]
    except Exception as exc:
        print(f"[ChromaDB] search_documents error: {exc}")
        return []


def delete_document(doc_id: str):
    try:
        col = _documents_col()
        results = col.get(where={"document_id": doc_id})
        if results["ids"]:
            col.delete(ids=results["ids"])
    except Exception as exc:
        print(f"[ChromaDB] delete_document error: {exc}")


def search_documents_with_ids(
    query: str,
    document_ids: Optional[List[str]] = None,
    top_k: int = 20,
) -> List[tuple]:
    """
    Like search_documents but returns (chunk_id, text, metadata) tuples.
    Used by the hybrid retriever for RRF fusion with BM25.
    """
    try:
        col = _documents_col()
        count = col.count()
        if count == 0:
            return []

        n = min(top_k, count)
        kwargs: dict = {"query_texts": [query], "n_results": n, "include": ["documents", "metadatas"]}
        if document_ids:
            kwargs["where"] = {"document_id": {"$in": document_ids}}

        results = col.query(**kwargs)
        ids   = results.get("ids",       [[]])[0]
        docs  = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        return list(zip(ids, docs, metas))
    except Exception as exc:
        print(f"[ChromaDB] search_documents_with_ids error: {exc}")
        return []

