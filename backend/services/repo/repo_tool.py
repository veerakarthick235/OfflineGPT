"""
Repo Search Tool — search indexed code repositories.

Registered triggers:
  "how does X work", "find function", "show me the class",
  "what does file X do", "explain the code for", etc.
"""
from __future__ import annotations
from ..agent.tool_registry import registry, ToolResult
from . import symbol_store
from .repo_rag import search as repo_search


@registry.tool(
    name        = "repo_search",
    description = "Search indexed code repositories — find functions, classes, and understand how code works",
    fast_triggers = [
        r"\bhow\s+does\s+(?:the\s+)?(\w+)\s+(work|function|method|class)\b",
        r"\bfind\s+(function|class|method|def)\s+\w+\b",
        r"\bshow\s+me\s+(?:the\s+)?(function|class|method|code\s+for)\b",
        r"\bexplain\s+(?:the\s+)?(code|function|class|method|implementation)\b",
        r"\bwhat\s+does\s+(?:the\s+)?\w+\.(py|js|ts|go|rs|java)\s+(do|contain)\b",
        r"\bwhere\s+is\s+(?:the\s+)?(\w+)\s+(defined|implemented|called)\b",
        r"\bsearch\s+(?:the\s+)?(?:code|codebase|repository|repo)\b",
        r"\bwhat\s+imports?\s+(?:does|from)\b",
        r"\bdependency\s+graph\b",
        r"\bshow\s+me\s+(?:all\s+)?(functions?|classes?|methods?)\s+(?:in|that|for)\b",
        r"\bcode\s+(for|of|in|that|to)\b",
        r"\bimplementation\s+of\b",
    ],
)
async def repo_search_tool(query: str = "", **kwargs) -> ToolResult:
    """Search code repositories using hybrid exact + semantic search."""
    # Get active repos
    repos = await symbol_store.list_repos()
    if not repos:
        return ToolResult(
            tool    = "repo_search",
            success = False,
            error   = "No repositories indexed. Use the Repository panel to index a codebase.",
            label   = "No repositories indexed",
        )

    # Search across all repos (or first repo if multiple)
    repo_id = repos[0]["id"] if len(repos) == 1 else None
    result  = await repo_search(query=query, repo_id=repo_id, top_k=6)

    if not result["context"]:
        return ToolResult(
            tool    = "repo_search",
            success = True,
            context = f"[Code Search] No relevant code found for: {query}",
            label   = "No matching code found",
            data    = {"repos_searched": len(repos)},
        )

    total = result["total"]
    exact = len(result["symbols"])
    sem   = len(result["semantic"])

    return ToolResult(
        tool    = "repo_search",
        success = True,
        context = f"[Code Repository Search Results]\n{result['context']}",
        label   = f"Found {total} code chunks ({exact} exact, {sem} semantic)",
        data    = {
            "total":   total,
            "exact":   exact,
            "semantic": sem,
            "repos":   [r["name"] for r in repos],
        },
        metadata = {"inject_as": "context"},
    )
