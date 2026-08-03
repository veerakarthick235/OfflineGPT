"""
Detect image generation intent from a chat message.

Uses a layered approach:
  1. High-confidence explicit keywords   → INTENT_IMAGE
  2. Medium-confidence contextual phrases → INTENT_IMAGE
  3. Everything else                      → INTENT_CHAT

Returns a namedtuple: (is_image, cleaned_prompt, confidence)
"""
from __future__ import annotations
import re
from dataclasses import dataclass

@dataclass
class IntentResult:
    is_image:   bool
    prompt:     str    # cleaned prompt (command words stripped)
    confidence: float  # 0.0–1.0


# ── High-confidence patterns ─────────────────────────────────────────
# These strongly signal an image request.
_HIGH_PATTERNS = [
    r"(generate|create|make|draw|paint|render|produce|design|illustrate)\s+(an?\s+)?(image|picture|photo|illustration|artwork|painting|drawing|sketch|portrait|wallpaper|poster)\s+of\b",
    r"\b(image|picture|photo|illustration|artwork|painting|drawing|sketch)\s+of\s+",
    r"\bshow\s+me\s+(an?\s+)?(image|picture|photo|illustration|painting|drawing)\s+(of\b|showing\b)",
    r"\b(visualize|visualise)\s+",
    r"\bi\s+want\s+(an?\s+)?(image|picture|photo|illustration|painting)\s+(of\b|showing\b|that\b)",
    r"\b(generate|create|make|produce)\s+(an?\s+)?(AI\s+)?(art|image|picture|photo|illustration)",
    r"\bdraw\s+(me\s+)?(an?\s+)?",
    r"\bpaint\s+(me\s+)?(an?\s+)?",
]

# ── Medium-confidence patterns ────────────────────────────────────────
_MED_PATTERNS = [
    r"\bshow\s+me\s+(a\s+)?(picture|photo|illustration|painting)\b",
    r"\b(portrait|landscape|wallpaper|poster|thumbnail)\s+of\b",
    r"\b(cute|realistic|fantasy|cyberpunk|anime)\s+(character|robot|cat|dog|person|scene)\b",
    r"\bimage\s+(prompt|of|showing)\b",
    r"\btext.?to.?image\b",
]

_HIGH_RX = [re.compile(p, re.IGNORECASE) for p in _HIGH_PATTERNS]
_MED_RX  = [re.compile(p, re.IGNORECASE) for p in _MED_PATTERNS]

# ── Prefix removal ────────────────────────────────────────────────────
# Remove command words at the start to extract the pure visual prompt.
_PREFIX_RX = re.compile(
    r"^(generate|create|make|draw|paint|render|produce|design|illustrate|show me|visualize|visualise)\s+"
    r"(an?\s+)?"
    r"(image|picture|photo|illustration|artwork|painting|drawing|sketch|portrait|wallpaper|poster)?\s*"
    r"(of|showing|that shows|that depicts)?\s*",
    re.IGNORECASE,
)


def detect(text: str) -> IntentResult:
    stripped = text.strip()

    # High confidence
    for rx in _HIGH_RX:
        if rx.search(stripped):
            prompt = _PREFIX_RX.sub("", stripped, count=1).strip()
            prompt = prompt or stripped
            return IntentResult(is_image=True, prompt=prompt, confidence=0.95)

    # Medium confidence
    for rx in _MED_RX:
        if rx.search(stripped):
            prompt = _PREFIX_RX.sub("", stripped, count=1).strip()
            prompt = prompt or stripped
            return IntentResult(is_image=True, prompt=prompt, confidence=0.70)

    return IntentResult(is_image=False, prompt=stripped, confidence=0.0)
