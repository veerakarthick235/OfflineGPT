"""
Code Execute Agent Tool — runs code snippets requested by the user or AI.

Registered triggers:
  "run this code", "execute this", "test this function",
  "what does this output", "run the script", etc.

The tool:
1. Extracts code from the user message (or uses provided code)
2. Runs it in the secure sandbox
3. Returns stdout/stderr as tool context
4. The AI then narrates the result

Auto-run mode (future): if the AI's own response contains runnable code,
we can auto-execute it and inject the result before the next prompt.
"""
from __future__ import annotations
from ..agent.tool_registry import registry, ToolResult
from .sandbox import run_code
from .code_extractor import extract_first_runnable, normalize_language


@registry.tool(
    name        = "code_execute",
    description = "Execute Python, JavaScript, or SQL code locally in a secure sandbox and return the output",
    fast_triggers = [
        r"\brun\s+(this|the|my)\s+(code|script|function|program|snippet)\b",
        r"\bexecute\s+(this|the|my)?\s*(code|script|function|snippet)\b",
        r"\btest\s+(this|the|my)\s+(function|code|script)\b",
        r"\bwhat\s+(does|would|will)\s+this\s+(code|script|function)\s+(output|print|return|do)\b",
        r"\bwhat\s+is\s+the\s+output\s+of\b",
        r"\bcan\s+you\s+run\s+(this|the|my)?\b",
        r"\brun\s+it\b",
        r"\btry\s+(running|executing)\s+(this|the|it)\b",
    ],
)
async def code_execute_tool(
    code:      str = "",
    language:  str = "python",
    message:   str = "",    # original user message (for extraction)
    timeout:   float = 10.0,
    **kwargs,
) -> ToolResult:
    """Execute code in a secure sandbox and return the result."""
    # If no code provided, try to extract from the user message
    if not code.strip() and message:
        block = extract_first_runnable(message)
        if block:
            code     = block.code
            language = block.language

    if not code.strip():
        return ToolResult(
            tool    = "code_execute",
            success = False,
            error   = "No code found to execute. Please provide a code block using ```python ... ``` syntax.",
            label   = "No code found",
        )

    language = normalize_language(language)
    result   = await run_code(code, language=language, timeout=timeout)

    # Build context string for LLM
    parts = [f"[Code Execution — {language}]"]
    if result["success"]:
        if result["stdout"]:
            parts.append(f"Output:\n```\n{result['stdout'].strip()}\n```")
        else:
            parts.append("Code ran successfully with no output.")
    else:
        if result.get("error"):
            parts.append(f"Error: {result['error']}")
        if result["stderr"]:
            parts.append(f"stderr:\n```\n{result['stderr'].strip()}\n```")
        if result["stdout"]:
            parts.append(f"stdout (before error):\n```\n{result['stdout'].strip()}\n```")

    parts.append(f"Exit code: {result['exit_code']} | Duration: {result['duration_ms']}ms")
    if result.get("truncated"):
        parts.append("⚠️ Output was truncated (>50KB)")

    context = "\n".join(parts)

    status_icon = "✅" if result["success"] else "❌"
    label = (
        f"{status_icon} Ran {language} ({result['duration_ms']}ms) — "
        + ("OK" if result["success"] else "Error")
    )

    return ToolResult(
        tool    = "code_execute",
        success = result["success"],
        context = context,
        label   = label,
        data    = result,
        error   = result.get("error") if not result["success"] else None,
    )
