"""
Agent Planner — top-level entry point for Phase 3 agentic routing.

Usage in chat.py:
    from ..services.agent import planner

    plan = await planner.plan(user_message, model=model, doc_count=doc_count)
    # plan.tool_name is None → direct chat
    # plan.tool_name is set  → execute tool first

The planner:
1. Ensures all tools are loaded (lazy import)
2. Calls the intent classifier
3. Returns a ToolPlan
"""
from __future__ import annotations
from typing import Optional

from .intent_classifier import classify, ToolPlan
from . import executor as _executor   # noqa: F401 — import for re-export


_tools_loaded = False


def _ensure_tools():
    """Lazy-load all tool modules so they register with the registry."""
    global _tools_loaded
    if _tools_loaded:
        return
    # Import triggers @registry.tool(...) decorators
    from .tools import rag_tool        # noqa: F401
    from .tools import image_tool      # noqa: F401
    from .tools import calculator_tool # noqa: F401
    from .tools import datetime_tool   # noqa: F401
    # Phase 4: repo search
    try:
        from ..repo import repo_tool   # noqa: F401
    except Exception as e:
        print(f"[Agent] repo_tool not loaded: {e}")
    # Phase 5: code execution
    try:
        from ..sandbox import code_tool  # noqa: F401
    except Exception as e:
        print(f"[Agent] code_tool not loaded: {e}")
    _tools_loaded = True






async def plan(
    user_message: str,
    model:        str = "llama3.2",
    doc_count:    int = 0,
) -> ToolPlan:
    """
    Classify user message and return a ToolPlan.
    Always returns a ToolPlan — tool_name=None means direct chat.
    """
    _ensure_tools()
    return await classify(user_message, model=model, doc_count=doc_count)


def list_tools() -> list:
    """Return tool registry as list of dicts (for API endpoint)."""
    _ensure_tools()
    from .tool_registry import registry
    return [
        {
            "name":        t.name,
            "description": t.description,
            "trigger_count": len(t.fast_triggers),
        }
        for t in registry.all()
    ]
