"""
Working Memory — smart context window management.

The problem:
  Ollama has a finite context window (typically 4096–8192 tokens).
  Sending ALL messages from a long conversation will:
  - Exceed the context window and get truncated silently
  - Slow down inference dramatically

The solution:
  A token-budget-aware trimmer that:
  1. Always includes the SYSTEM prompt
  2. Always includes the LAST N turns (recency bias)
  3. Fits as many earlier turns as possible within the budget
  4. Adds a "[Memory: X turns summarized]" note when trimming

Token estimation: ~4 chars per token (fast, no model needed)
"""
from __future__ import annotations
from typing import List, Dict

# Conservative token budget (leave room for response + memory injection)
DEFAULT_TOKEN_BUDGET = 3500
CHARS_PER_TOKEN      = 4
RECENT_TURNS_ALWAYS  = 3   # always keep last N user+assistant pairs


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _msg_tokens(msg: dict) -> int:
    return _estimate_tokens(msg.get("content", "")) + 4  # +4 for role overhead


def trim(
    messages:     List[Dict],
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> tuple[List[Dict], dict]:
    """
    Trim a message list to fit within token_budget.

    Returns:
      (trimmed_messages, stats)
      stats: { original_count, kept_count, trimmed_count, estimated_tokens }
    """
    if not messages:
        return [], {"original_count": 0, "kept_count": 0, "trimmed_count": 0, "estimated_tokens": 0}

    # Separate system messages (always keep)
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system  = [m for m in messages if m.get("role") != "system"]

    system_tokens = sum(_msg_tokens(m) for m in system_msgs)
    budget = token_budget - system_tokens

    # Always keep the most recent RECENT_TURNS_ALWAYS * 2 messages
    recent_n = min(RECENT_TURNS_ALWAYS * 2, len(non_system))
    recent   = non_system[-recent_n:]
    older    = non_system[:-recent_n] if recent_n < len(non_system) else []

    recent_tokens = sum(_msg_tokens(m) for m in recent)
    remaining_budget = budget - recent_tokens

    # Greedily add older messages from most-recent to least-recent
    included_older = []
    for msg in reversed(older):
        t = _msg_tokens(msg)
        if remaining_budget - t >= 0:
            included_older.insert(0, msg)
            remaining_budget -= t
        else:
            break  # can't fit any more (older messages are larger risk)

    trimmed_count = len(older) - len(included_older)
    kept = system_msgs + included_older + recent

    # If we trimmed anything, add a context note
    if trimmed_count > 0:
        note = {
            "role": "system",
            "content": f"[Note: {trimmed_count} earlier turn(s) were summarized to save context. "
                       "Key facts are preserved in the memory block above.]",
        }
        # Insert after system messages
        insert_pos = len(system_msgs)
        kept.insert(insert_pos, note)

    total_tokens = sum(_msg_tokens(m) for m in kept)

    return kept, {
        "original_count":  len(messages),
        "kept_count":      len(kept),
        "trimmed_count":   trimmed_count,
        "estimated_tokens": total_tokens,
    }
