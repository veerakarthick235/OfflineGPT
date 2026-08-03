"""
Agent Executor — runs a ToolPlan and yields SSE events.

Flow for each tool call:
  1. yield tool_start   → frontend shows "🔍 Searching documents..."
  2. execute tool       → calls tool handler
  3. yield tool_result  → frontend shows "✅ Found 3 passages"
  4. return ToolResult  → caller injects context into prompt

For image_generate (special case):
  The executor yields the full image SSE flow and returns a special flag
  that tells chat.py to skip Ollama inference.

SSE event schema:
  {"type": "tool_start",  "tool": "rag_search",  "label": "Searching..."}
  {"type": "tool_result", "tool": "rag_search",  "label": "Found 3 passages",
   "success": true, "data": {...}}
  {"type": "tool_error",  "tool": "rag_search",  "message": "No docs found"}
"""
from __future__ import annotations
import asyncio
import json
from typing import AsyncIterator, Optional

from .tool_registry import registry, ToolResult
from .intent_classifier import ToolPlan

TOOL_ICONS = {
    "rag_search":     "🔍",
    "image_generate": "🎨",
    "calculator":     "🧮",
    "datetime":       "🕐",
    "memory_search":  "🧠",
    "repo_search":    "💻",
    "code_execute":   "▶️",
}

TOOL_START_LABELS = {
    "rag_search":     "Searching documents with Hybrid RAG…",
    "image_generate": "Generating image…",
    "calculator":     "Calculating…",
    "datetime":       "Checking date and time…",
    "memory_search":  "Searching memory…",
    "repo_search":    "Searching codebase…",
    "code_execute":   "Running code in sandbox…",
}


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def execute(
    plan:         ToolPlan,
    model:        str         = "llama3.2",
    doc_ids:      Optional[list] = None,
) -> AsyncIterator[tuple[str, Optional[ToolResult]]]:
    """
    Execute a tool plan, yielding (sse_event_str, result) tuples.
    
    Yields:
      (sse_str, None)         for streaming events (tool_start, tool_result)
      (sse_str, ToolResult)   for the final result (caller inspects this)

    The caller should yield the sse_str to the client,
    and use the ToolResult to inject context into the LLM prompt.
    """
    if not plan.tool_name:
        return   # no tool — caller proceeds with direct chat

    icon  = TOOL_ICONS.get(plan.tool_name, "⚡")
    start = TOOL_START_LABELS.get(plan.tool_name, f"Running {plan.tool_name}…")

    # ── 1. Announce tool start ─────────────────────────────────────
    yield _sse({
        "type":  "tool_start",
        "tool":  plan.tool_name,
        "icon":  icon,
        "label": start,
    }), None

    # ── 2. Execute tool ────────────────────────────────────────────
    tool_def = registry.get(plan.tool_name)
    if not tool_def:
        result = ToolResult(
            tool    = plan.tool_name,
            success = False,
            error   = f"Tool '{plan.tool_name}' not found in registry",
        )
    else:
        try:
            # Inject model + doc_ids for tools that need them
            params = dict(plan.params)
            if plan.tool_name == "rag_search":
                params["model"]    = model
                params["doc_ids"]  = doc_ids
            elif plan.tool_name == "code_execute":
                # Pass original user message so tool can extract code blocks
                params.setdefault("message", plan.params.get("query", ""))
            elif plan.tool_name == "image_generate":
                # image_generate is handled specially by chat.py
                # Just return the ToolResult with metadata flag
                result = await tool_def.handler(**params)
                yield _sse({
                    "type":    "tool_result",
                    "tool":    plan.tool_name,
                    "success": result.success,
                    "label":   result.label or "Image ready",
                }), result
                return

            result = await tool_def.handler(**params)

        except Exception as e:
            result = ToolResult(
                tool    = plan.tool_name,
                success = False,
                error   = str(e),
            )

    # ── 3. Emit result event ───────────────────────────────────────
    if result.success:
        yield _sse({
            "type":    "tool_result",
            "tool":    plan.tool_name,
            "icon":    icon,
            "success": True,
            "label":   result.label or "Done",
            "data":    result.data,
        }), result
    else:
        yield _sse({
            "type":    "tool_error",
            "tool":    plan.tool_name,
            "icon":    "⚠️",
            "message": result.error or "Tool failed",
        }), result
