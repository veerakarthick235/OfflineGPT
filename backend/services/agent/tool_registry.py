"""
Tool Registry — declarative registration of all available tools.

Design:
  Each tool is an async callable registered with:
  - name          : unique string identifier
  - description   : natural language description (used in LLM prompts)
  - fast_triggers : regex patterns for instant detection (no LLM needed)
  - parameters    : JSON-schema-like parameter definitions

Usage:
  registry = ToolRegistry()

  @registry.tool(name="rag_search", description="...", fast_triggers=[...])
  async def rag_search(query: str) -> ToolResult:
      ...
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Awaitable


@dataclass
class ToolResult:
    """Unified result object returned by all tools."""
    tool:         str
    success:      bool
    data:         Dict[str, Any]          = field(default_factory=dict)
    context:      str                     = ""   # text to inject into prompt
    error:        Optional[str]           = None
    label:        str                     = ""   # human-readable status
    metadata:     Dict[str, Any]          = field(default_factory=dict)


@dataclass
class ToolDefinition:
    name:          str
    description:   str
    fast_triggers: List[str]              # regex patterns
    handler:       Callable[..., Awaitable[ToolResult]]
    parameters:    Dict[str, Any]         = field(default_factory=dict)
    # pre-compiled patterns
    _patterns:     List[re.Pattern]       = field(default_factory=list, repr=False)

    def __post_init__(self):
        self._patterns = [
            re.compile(p, re.IGNORECASE) for p in self.fast_triggers
        ]

    def matches(self, text: str) -> float:
        """Return confidence [0,1] based on pattern matching."""
        for pat in self._patterns:
            if pat.search(text):
                return 0.9   # strong match
        return 0.0


class ToolRegistry:
    """Singleton registry of all available tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def tool(
        self,
        name:          str,
        description:   str,
        fast_triggers: List[str],
        parameters:    Optional[Dict] = None,
    ):
        """Decorator to register a tool handler."""
        def decorator(func: Callable):
            defn = ToolDefinition(
                name          = name,
                description   = description,
                fast_triggers = fast_triggers,
                handler       = func,
                parameters    = parameters or {},
            )
            self._tools[name] = defn
            return func
        return decorator

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def all(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def descriptions_for_llm(self) -> str:
        """Return tool descriptions formatted for an LLM prompt."""
        lines = []
        for t in self._tools.values():
            lines.append(f'  "{t.name}": {t.description}')
        return "\n".join(lines)

    def fast_detect(self, text: str) -> Optional[tuple[str, float]]:
        """
        Try to detect which tool to use purely from regex patterns.
        Returns (tool_name, confidence) or None if ambiguous.
        """
        matches = []
        for defn in self._tools.values():
            conf = defn.matches(text)
            if conf > 0:
                matches.append((defn.name, conf))

        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]

        # Multiple matches — pick highest confidence
        matches.sort(key=lambda x: x[1], reverse=True)
        # If top match is uniquely confident, return it
        if matches[0][1] > matches[1][1]:
            return matches[0]

        return None   # ambiguous — needs LLM


# ── Singleton ─────────────────────────────────────────────────────────
registry = ToolRegistry()
