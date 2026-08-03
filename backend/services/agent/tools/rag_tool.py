"""
RAG Search Tool — search uploaded documents with Hybrid RAG.

Registered triggers:
  "search documents", "find in", "according to the document", 
  "what does the PDF say", "look up in", "document says", etc.
"""
from __future__ import annotations
from ..tool_registry import registry, ToolResult
from ...rag import pipeline as rag_pipeline
from ... import sqlite_db


@registry.tool(
    name        = "rag_search",
    description = "Search documents/PDFs/files the user uploaded using Hybrid RAG (BM25 + vectors)",
    fast_triggers = [
        r"\bsearch\s+(my\s+)?(documents?|files?|pdf|uploaded)\b",
        r"\bfind\s+(in|from)\s+(my\s+)?(documents?|files?|pdf)\b",
        r"\baccording\s+to\s+(my\s+)?(documents?|files?|pdf|the)\b",
        r"\bwhat\s+does\s+(my\s+)?(document|pdf|file|report)\s+say\b",
        r"\blook\s+up\s+(in|from)\b",
        r"\b(document|pdf|file|report)\s+(says?|mentions?|contains?|shows?)\b",
        r"\bsummarize\s+(my\s+)?(document|pdf|file|report|uploaded)\b",
        r"\bsummarize\s+this\s+(pdf|document|file)\b",
        r"\bfrom\s+the\s+(document|pdf|file|report)\b",
    ],
)
async def rag_search_tool(
    query:     str,
    doc_ids:   list  = None,
    doc_count: int   = 0,
    model:     str   = "llama3.2",
) -> ToolResult:
    """Run full Hybrid RAG pipeline and return compressed context."""
    if doc_count == 0:
        # Check if any documents exist
        docs = await sqlite_db.list_documents()
        if not docs:
            return ToolResult(
                tool    = "rag_search",
                success = False,
                error   = "No documents uploaded. Please upload a document first.",
                label   = "No documents found",
            )
        doc_count = len(docs)

    result = await rag_pipeline.run(
        query      = query,
        doc_ids    = doc_ids,
        model      = model,
        top_k_retrieve = 20,
        top_k_rerank   = 5,
        rewrite    = True,
        do_rerank  = True,
        do_compress= True,
    )

    chunks = result.get("chunks", [])
    context = result.get("context", "")
    trace   = result.get("pipeline_trace", {})

    if not context:
        return ToolResult(
            tool    = "rag_search",
            success = False,
            error   = "No relevant passages found in documents.",
            label   = "Nothing relevant found",
            data    = {"doc_count": doc_count},
        )

    sources = list({c.get("filename","?") for c in chunks})
    return ToolResult(
        tool    = "rag_search",
        success = True,
        context = f"[Document Search Results]\n{context}",
        label   = f"Found {len(chunks)} relevant passages from {len(sources)} source(s)",
        data    = {
            "chunk_count":     len(chunks),
            "sources":         sources,
            "pipeline_trace":  trace,
            "queries_used":    result.get("queries_used", []),
        },
        metadata = {"inject_as": "context"},
    )
