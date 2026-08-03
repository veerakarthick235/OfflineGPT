"""
Query Rewriter — improves retrieval by generating better search queries.

Why?
  Users write conversational queries: "tell me about it", "how does that work?"
  Search engines work better with specific, information-dense queries.

  This module uses Ollama (offline) to:
  1. Expand ambiguous pronouns ("it" → "Python's GIL")
  2. Generate 2-3 search query variants covering different angles
  3. Add technical synonyms

Research basis: HyDE (Hypothetical Document Embeddings), RAG-Fusion, FLARE
"""
from __future__ import annotations
import json
from typing import List

import httpx

OLLAMA_URL  = "http://localhost:11434/api/generate"
REWRITE_MODEL = "llama3.2"   # use the user's chat model

REWRITE_PROMPT = """\
You are a search query optimizer for a document retrieval system.

Given the user's question, generate 3 specific, keyword-rich search queries
that will help find the most relevant document passages.

Rules:
- Each query should approach the question from a different angle
- Be specific and information-dense
- Include technical terms and synonyms
- Do NOT include conversational filler words
- Output ONLY a JSON array of strings, no explanation

User question: {question}

Output format: ["query1", "query2", "query3"]
"""


async def rewrite(query: str, model: str = REWRITE_MODEL) -> List[str]:
    """
    Rewrite a user query into multiple search-optimized variants.
    Falls back to [original_query] if Ollama is unavailable.
    """
    if len(query.strip()) < 10:
        # Too short to benefit from rewriting
        return [query]

    prompt = REWRITE_PROMPT.format(question=query.strip())

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(OLLAMA_URL, json={
                "model":  model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 150},
            })
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()

        # Extract JSON array from response
        start = text.find("[")
        end   = text.rfind("]") + 1
        if start >= 0 and end > start:
            queries = json.loads(text[start:end])
            if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
                # Always include the original too
                all_queries = [query] + [q for q in queries if q.strip()]
                return list(dict.fromkeys(all_queries))[:4]  # deduplicate, max 4

    except Exception as e:
        print(f"[QueryRewriter] fallback (original query): {e}")

    return [query]
