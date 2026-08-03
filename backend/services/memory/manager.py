"""
Memory Manager — orchestrates all memory layers and builds context for chat.

Called from chat.py before every Ollama inference call.

Output: a structured memory block injected into the system prompt:

  ═══ MEMORY ═══════════════════════════════════════
  About you (long-term facts):
  • User's name is Veera
  • User prefers Python, works on Windows

  Relevant past conversations:
  • [Python debugging session] We debugged a FastAPI import error...

  [Working memory: 18 messages, ~1,240 tokens]
  ══════════════════════════════════════════════════

The AI sees this block and uses it naturally.
"""
from __future__ import annotations
import asyncio
from typing import List, Dict, Optional, Any

from . import working, conversation as conv_memory, long_term


async def build_context(
    query:           str,
    conversation_id: str,
    messages:        List[Dict],
    model:           str = "llama3.2",
) -> Dict[str, Any]:
    """
    Build a complete memory context for the current turn.

    Returns:
      {
        "memory_block":   str,   # inject into system prompt
        "trimmed_messages": list, # token-trimmed message list
        "stats": dict,
      }
    """
    # Run retrieval in parallel for speed
    facts_task    = asyncio.create_task(long_term.retrieve_relevant(query))
    past_conv_task = asyncio.create_task(conv_memory.retrieve_relevant(query, exclude_conv_id=conversation_id))

    facts, past_convs = await asyncio.gather(facts_task, past_conv_task)

    # Trim working memory to fit context window
    trimmed, trim_stats = working.trim(messages)

    # Build memory block text
    lines = []

    if facts:
        lines.append("About the user (long-term memory):")
        for f in facts:
            lines.append(f"  • {f['fact']}")
        lines.append("")

    if past_convs:
        lines.append("Relevant past conversations:")
        for pc in past_convs:
            topic   = pc.get("topic",   "Previous conversation")
            summary = pc.get("summary", "")[:200]
            lines.append(f"  • [{topic}] {summary}")
        lines.append("")

    if trim_stats["trimmed_count"] > 0:
        lines.append(
            f"[Context note: {trim_stats['trimmed_count']} older turn(s) were compressed. "
            f"Est. tokens in window: ~{trim_stats['estimated_tokens']}]"
        )

    memory_block = "\n".join(lines) if lines else ""

    return {
        "memory_block":     memory_block,
        "trimmed_messages": trimmed,
        "facts":            facts,
        "past_convs":       past_convs,
        "stats": {
            "facts_count":     len(facts),
            "past_convs_count": len(past_convs),
            **trim_stats,
        },
    }


async def post_turn_tasks(
    conversation_id: str,
    messages:        List[Dict],
    model:           str = "llama3.2",
):
    """
    Background tasks to run after each AI response:
    1. Extract new user facts from the conversation
    2. Summarize conversation if it's grown long enough

    These run in the background — they don't block the response.
    """
    try:
        await asyncio.gather(
            long_term.extract_and_store(messages, conversation_id, model),
            conv_memory.maybe_summarize(conversation_id, messages, model),
            return_exceptions=True,
        )
    except Exception as e:
        print(f"[MemoryManager] post_turn_tasks error: {e}")
