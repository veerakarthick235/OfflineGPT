"""
Memory Summarizer — offline Ollama-based text summarization.

Used by:
  - conversation.py : summarize long conversations
  - long_term.py    : extract facts from conversations
  
100% offline — all calls go to localhost:11434
"""
from __future__ import annotations
import httpx
from typing import List

OLLAMA_URL = "http://localhost:11434/api/generate"


async def _call(prompt: str, model: str, max_tokens: int = 400) -> str:
    """Generic Ollama call, returns response text or empty string on error."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(OLLAMA_URL, json={
                "model":  model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": max_tokens},
            })
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"[Summarizer] Ollama error: {e}")
        return ""


async def summarize_conversation(
    messages: List[dict],
    model:    str = "llama3.2",
) -> dict:
    """
    Summarize a conversation into a compact summary + key points.
    
    Returns:
      { summary: str, key_points: List[str], topic: str }
    """
    # Build transcript
    lines = []
    for m in messages:
        role = m.get("role", "?")
        content = m.get("content", "")[:800]  # truncate very long messages
        if role in ("user", "assistant"):
            lines.append(f"{role.upper()}: {content}")

    if not lines:
        return {"summary": "", "key_points": [], "topic": ""}

    transcript = "\n".join(lines[-30:])  # last 30 turns max

    prompt = f"""Summarize this AI conversation concisely.

CONVERSATION:
{transcript}

Respond in this exact format:
TOPIC: (one-line topic, e.g. "Python debugging help")
SUMMARY: (2-4 sentences summarizing what was discussed and decided)
KEY_POINTS:
- (key fact or decision 1)
- (key fact or decision 2)
- (key fact or decision 3)

Be factual. Focus on information the AI should remember for future conversations."""

    text = await _call(prompt, model, max_tokens=300)
    if not text:
        # Fallback: first user message as summary
        first_user = next((m["content"][:200] for m in messages if m.get("role") == "user"), "")
        return {"summary": first_user, "key_points": [], "topic": "Conversation"}

    # Parse response
    topic     = ""
    summary   = ""
    key_points: List[str] = []
    section = None

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("TOPIC:"):
            topic = line[6:].strip()
        elif line.startswith("SUMMARY:"):
            summary = line[8:].strip()
            section = "summary"
        elif line.startswith("KEY_POINTS:"):
            section = "key_points"
        elif section == "summary" and line and not line.startswith("-"):
            summary = (summary + " " + line).strip()
        elif section == "key_points" and line.startswith("-"):
            kp = line[1:].strip()
            if kp:
                key_points.append(kp)

    return {
        "summary":    summary or text[:300],
        "key_points": key_points,
        "topic":      topic or "Conversation",
    }


async def extract_user_facts(
    messages: List[dict],
    model:    str = "llama3.2",
) -> List[dict]:
    """
    Extract persistent facts about the user from a conversation.
    
    Returns list of { fact, category } dicts.
    Categories: name, skill, preference, project, location, other
    """
    lines = []
    for m in messages:
        if m.get("role") == "user":
            lines.append(m.get("content", "")[:400])

    if not lines:
        return []

    user_text = "\n".join(lines[-15:])

    prompt = f"""Extract persistent facts about the USER from these messages.
Only include facts that would be useful in future conversations.
Ignore greetings, questions, and temporary requests.

USER MESSAGES:
{user_text}

Respond ONLY with facts in this exact format (one per line):
FACT: (fact text) | CATEGORY: (name/skill/preference/project/location/other)

If no persistent facts found, respond with: NONE

Examples:
FACT: User's name is Veera | CATEGORY: name
FACT: User prefers Python over JavaScript | CATEGORY: preference
FACT: User is building an Offline AI Assistant | CATEGORY: project
FACT: User works on Windows | CATEGORY: preference"""

    text = await _call(prompt, model, max_tokens=200)
    if not text or text.strip() == "NONE":
        return []

    facts = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("FACT:") and "| CATEGORY:" in line:
            parts    = line.split("| CATEGORY:")
            fact_text = parts[0].replace("FACT:", "").strip()
            category  = parts[1].strip().lower() if len(parts) > 1 else "other"
            if fact_text and len(fact_text) > 5:
                facts.append({"fact": fact_text, "category": category})

    return facts
