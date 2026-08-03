"""
Intent Classifier — decides which tool (if any) to call.

Two-stage pipeline for speed + accuracy:

Stage 1 — Fast (< 1ms):
  Regex pattern matching against each tool's fast_triggers.
  If one tool matches with high confidence → done (no LLM needed).

Stage 2 — LLM (50-200ms, only when Stage 1 is ambiguous):
  Send user message + tool descriptions to Ollama.
  Ask it to output a single tool name or "none".
  Structured output makes this reliable.

Result: ToolPlan
  { tool_name, params, confidence, reasoning, stage }
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from .tool_registry import registry, ToolDefinition

OLLAMA_URL = "http://localhost:11434/api/generate"


@dataclass
class ToolPlan:
    """The agent's decision about what tool to use for a user request."""
    tool_name:  Optional[str]    # None = direct chat (no tool)
    params:     Dict[str, Any]   = field(default_factory=dict)
    confidence: float            = 0.0
    reasoning:  str              = ""
    stage:      str              = "fast"   # "fast" | "llm" | "none"


# ── LLM Classification Prompt ─────────────────────────────────────────

_CLASSIFY_PROMPT = """\
You are a tool router for an AI assistant.
Decide which ONE tool to use (or none) for this user message.

Available tools:
{tool_descriptions}

User message: "{user_message}"

Rules:
- Choose "none" if the message is a general question, conversation, or coding help
- Choose "rag_search" if the user wants to search documents they uploaded
- Choose "image_generate" if they want to create/draw/generate an image
- Choose "calculator" if there is a math calculation to compute
- Choose "datetime" if they ask about current time or date
- Choose "memory_search" if they ask about past conversations or what they said before

Respond with ONLY valid JSON, no explanation:
{{"tool": "<tool_name_or_none>", "params": {{}}, "confidence": <0.0-1.0>, "reason": "<one sentence>"}}
"""


async def classify(
    user_message: str,
    model:        str = "llama3.2",
    doc_count:    int = 0,   # number of uploaded docs (context)
) -> ToolPlan:
    """
    Classify user intent and return a ToolPlan.

    doc_count > 0 boosts confidence for rag_search.
    """
    text = user_message.strip()
    if not text:
        return ToolPlan(tool_name=None, stage="none")

    # ── Stage 1: Fast regex ───────────────────────────────────────────
    fast_result = registry.fast_detect(text)
    if fast_result:
        tool_name, conf = fast_result
        params = _extract_params(tool_name, text, doc_count)
        return ToolPlan(
            tool_name  = tool_name,
            params     = params,
            confidence = conf,
            reasoning  = "fast pattern match",
            stage      = "fast",
        )

    # ── Stage 2: LLM classification (only for ambiguous cases) ────────
    try:
        tool_descriptions = registry.descriptions_for_llm()
        prompt = _CLASSIFY_PROMPT.format(
            tool_descriptions = tool_descriptions,
            user_message      = text[:400],   # truncate very long messages
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(OLLAMA_URL, json={
                "model":  model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 120},
            })
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()

        # Parse JSON from response
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            parsed    = json.loads(json_match.group())
            tool_name = parsed.get("tool", "none")
            if tool_name == "none" or not registry.get(tool_name):
                return ToolPlan(tool_name=None, stage="llm",
                                confidence=1.0, reasoning=parsed.get("reason",""))
            params = parsed.get("params", {})
            params = _extract_params(tool_name, text, doc_count, base_params=params)
            return ToolPlan(
                tool_name  = tool_name,
                params     = params,
                confidence = float(parsed.get("confidence", 0.8)),
                reasoning  = parsed.get("reason", ""),
                stage      = "llm",
            )

    except Exception as e:
        print(f"[IntentClassifier] LLM error: {e} — defaulting to no-tool")

    return ToolPlan(tool_name=None, stage="none", confidence=1.0,
                   reasoning="fallback: no pattern matched")


def _extract_params(
    tool_name:   str,
    text:        str,
    doc_count:   int = 0,
    base_params: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Extract tool-specific parameters from the user message."""
    params = dict(base_params or {})

    if tool_name == "rag_search":
        params.setdefault("query", text)
        params["doc_count"] = doc_count

    elif tool_name == "image_generate":
        # Strip image command words to get the pure visual prompt
        clean = re.sub(
            r"^(generate|create|make|draw|paint|render|produce|design|illustrate|show me|visualize)\s+"
            r"(an?\s+)?(image|picture|photo|illustration|artwork|painting|drawing|sketch|portrait|wallpaper|poster)?\s*"
            r"(of|showing|that shows|that depicts)?\s*",
            "", text, flags=re.IGNORECASE
        ).strip()
        params.setdefault("prompt", clean or text)

    elif tool_name == "calculator":
        # Extract math expression
        math_match = re.search(
            r'[\d\s\+\-\*\/\(\)\^\.\%]+(?:\s*[\+\-\*\/\^]\s*[\d\s\(\)\.]+)+',
            text
        )
        params.setdefault("expression", math_match.group().strip() if math_match else text)

    elif tool_name == "memory_search":
        params.setdefault("query", text)

    return params
