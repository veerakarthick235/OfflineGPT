"""
BM25 index — keyword frequency based retrieval.

Uses rank-bm25 (Okapi BM25). Index is persisted to disk as a pickle
so it survives backend restarts without re-indexing.

BM25 Formula (simplified):
  score(doc, query) = Σ IDF(term) × TF(term, doc) / (TF + k1*(1 - b + b*|doc|/avgdl))

Why BM25?
  - Exact keyword matching — great for code, variable names, IDs, acronyms
  - Complements embedding search which handles synonyms/paraphrasing
  - Pure Python, 100% offline, no model required
"""
from __future__ import annotations
import pickle
import re
import threading
from pathlib import Path
from typing import List, Optional

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    print("[RAG] rank-bm25 not installed — BM25 retrieval disabled")

INDEX_PATH = Path(__file__).parent.parent.parent / "data" / "bm25_index.pkl"
INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + punctuation tokenizer, lowercased."""
    text = text.lower()
    # Keep alphanumeric tokens and underscores (for code)
    tokens = re.findall(r"[a-z0-9_]+", text)
    return [t for t in tokens if len(t) > 1]


class BM25Index:
    """
    Thread-safe BM25 index over document chunks.

    Each entry stores:
      - chunk_id  : unique string identifier
      - doc_id    : parent document ID
      - filename  : source filename
      - text      : raw chunk text
      - tokens    : tokenized form for BM25
    """

    def __init__(self):
        self._lock   = threading.Lock()
        self._chunks : List[dict] = []   # [{chunk_id, doc_id, filename, text}]
        self._bm25   : Optional[object] = None
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────
    def _load(self):
        if INDEX_PATH.exists():
            try:
                with open(INDEX_PATH, "rb") as f:
                    state = pickle.load(f)
                self._chunks = state.get("chunks", [])
                self._rebuild_bm25()
                print(f"[BM25] Loaded {len(self._chunks)} chunks from disk")
            except Exception as e:
                print(f"[BM25] Failed to load index: {e} — starting fresh")
                self._chunks = []

    def _save(self):
        try:
            with open(INDEX_PATH, "wb") as f:
                pickle.dump({"chunks": self._chunks}, f)
        except Exception as e:
            print(f"[BM25] Failed to save index: {e}")

    def _rebuild_bm25(self):
        if not BM25_AVAILABLE or not self._chunks:
            self._bm25 = None
            return
        corpus = [c["tokens"] for c in self._chunks]
        self._bm25 = BM25Okapi(corpus)

    # ── Mutators ─────────────────────────────────────────────────────────
    def add_chunks(self, doc_id: str, filename: str, chunks: List[str],
                   chunk_ids: List[str]) -> None:
        """Add or update chunks for a document."""
        with self._lock:
            # Remove existing chunks for this document (re-index support)
            self._chunks = [c for c in self._chunks if c["doc_id"] != doc_id]
            for cid, text in zip(chunk_ids, chunks):
                if text.strip():
                    self._chunks.append({
                        "chunk_id": cid,
                        "doc_id":   doc_id,
                        "filename": filename,
                        "text":     text,
                        "tokens":   _tokenize(text),
                    })
            self._rebuild_bm25()
            self._save()

    def remove_document(self, doc_id: str) -> None:
        """Remove all chunks for a document."""
        with self._lock:
            before = len(self._chunks)
            self._chunks = [c for c in self._chunks if c["doc_id"] != doc_id]
            if len(self._chunks) != before:
                self._rebuild_bm25()
                self._save()

    # ── Query ─────────────────────────────────────────────────────────────
    def search(self, query: str, top_k: int = 20,
               doc_ids: Optional[List[str]] = None) -> List[dict]:
        """
        Return top-k chunks scored by BM25.
        Returns: [{ chunk_id, doc_id, filename, text, score }]
        """
        with self._lock:
            if not self._bm25 or not self._chunks:
                return []

            tokens = _tokenize(query)
            if not tokens:
                return []

            scores = self._bm25.get_scores(tokens)

            results = []
            for i, chunk in enumerate(self._chunks):
                if doc_ids and chunk["doc_id"] not in doc_ids:
                    continue
                if scores[i] > 0:
                    results.append({**chunk, "score": float(scores[i])})

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)


# ── Singleton ─────────────────────────────────────────────────────────────
_index: Optional[BM25Index] = None

def get_index() -> BM25Index:
    global _index
    if _index is None:
        _index = BM25Index()
    return _index
