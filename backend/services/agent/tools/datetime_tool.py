"""
DateTime Tool — provides current date, time, and timezone info.

100% offline — uses system clock only.

Registered triggers:
  "what time is it", "what is today's date", "current date", etc.
"""
from __future__ import annotations
from datetime import datetime, timezone
from ..tool_registry import registry, ToolResult


@registry.tool(
    name        = "datetime",
    description = "Get the current date, time, day of week, or timezone information",
    fast_triggers = [
        r"\bwhat\s+(time|day|date)\s+is\s+it\b",
        r"\bwhat\s+is\s+(today|the\s+date|the\s+time|current\s+time)\b",
        r"\bcurrent\s+(date|time|day)\b",
        r"\btoday'?s?\s+date\b",
        r"\bwhat\s+day\s+(of\s+the\s+week\s+)?is\s+(it|today)\b",
        r"\bwhat\s+year\s+is\s+it\b",
        r"\bwhat\s+month\s+is\s+(it|this)\b",
        r"\btell\s+me\s+the\s+(time|date)\b",
    ],
)
async def datetime_tool(**kwargs) -> ToolResult:
    """Return current local date and time information."""
    now_local = datetime.now()
    now_utc   = datetime.now(timezone.utc)

    day_name  = now_local.strftime("%A")       # Monday
    date_str  = now_local.strftime("%B %d, %Y") # July 31, 2026
    time_str  = now_local.strftime("%I:%M %p")  # 03:40 PM
    time_24   = now_local.strftime("%H:%M")     # 15:40
    week_num  = now_local.isocalendar()[1]

    context_text = (
        f"[DateTime]\n"
        f"Today is {day_name}, {date_str}.\n"
        f"Current time: {time_str} (local) / {time_24} (24h)\n"
        f"UTC: {now_utc.strftime('%Y-%m-%d %H:%M')} UTC\n"
        f"Week number: {week_num}"
    )

    return ToolResult(
        tool    = "datetime",
        success = True,
        context = context_text,
        label   = f"Today: {day_name}, {date_str} — {time_str}",
        data    = {
            "date":     date_str,
            "time":     time_str,
            "day":      day_name,
            "utc":      now_utc.isoformat(),
            "iso":      now_local.isoformat(),
            "week_num": week_num,
        },
    )


@registry.tool(
    name        = "memory_search",
    description = "Search past conversations and long-term memory for relevant information",
    fast_triggers = [
        r"\bwhat\s+(did\s+we|did\s+I|have\s+we)\s+(discuss|talk|say|mention)\b",
        r"\bdo\s+you\s+remember\b",
        r"\bwhat\s+(is|was)\s+my\s+(name|preference|project|goal)\b",
        r"\bremember\s+(when|that|what)\b",
        r"\bour\s+previous\s+(conversation|discussion|chat|session)\b",
        r"\blast\s+time\s+(we|I)\b",
        r"\b(recall|remember)\s+(my|our|the)\b",
    ],
)
async def memory_search_tool(query: str = "", **kwargs) -> ToolResult:
    """Search long-term memory and past conversation summaries."""
    from ...memory import long_term, conversation as conv_memory

    facts     = await long_term.retrieve_relevant(query, top_k=5)
    past_convs = await conv_memory.retrieve_relevant(query)

    parts = []
    if facts:
        parts.append("Long-term facts about you:")
        for f in facts:
            parts.append(f"  • {f['fact']}")

    if past_convs:
        parts.append("\nRelevant past conversations:")
        for pc in past_convs:
            topic   = pc.get("topic", "Past conversation")
            summary = pc.get("summary", "")[:300]
            parts.append(f"  [{topic}] {summary}")

    if not parts:
        return ToolResult(
            tool    = "memory_search",
            success = True,
            context = "[Memory] No relevant memories found for this query.",
            label   = "No memories found",
            data    = {"facts": [], "past_convs": []},
        )

    context = "[Memory Search Results]\n" + "\n".join(parts)
    return ToolResult(
        tool    = "memory_search",
        success = True,
        context = context,
        label   = f"Found {len(facts)} facts, {len(past_convs)} past conversations",
        data    = {"facts": facts, "past_convs": past_convs},
    )
