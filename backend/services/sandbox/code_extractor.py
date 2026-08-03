"""
Code Extractor — pulls code blocks from AI response text.

Used by the code_execute agent tool to:
1. Detect when the AI has written runnable code
2. Extract the language and code content
3. Optionally auto-run it

Handles:
  ```python
  print("hello")
  ```

  ```javascript
  console.log("hi")
  ```
  
  Also detects inline code mentions like:
  "Run: `python sort.py`"
"""
from __future__ import annotations
import re
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class CodeBlock:
    language:  str
    code:      str
    is_runnable: bool   # python, javascript, sql only


# Fenced code blocks: ```language\n...\n```
_FENCE_RE = re.compile(
    r"```(\w*)\n(.*?)```",
    re.DOTALL,
)

RUNNABLE_LANGS = {"python", "py", "javascript", "js", "node", "sql", "sqlite"}


def extract_code_blocks(text: str) -> List[CodeBlock]:
    """Extract all fenced code blocks from a text string."""
    blocks = []
    for m in _FENCE_RE.finditer(text):
        lang = m.group(1).strip().lower() or "text"
        code = m.group(2).strip()
        if not code:
            continue
        blocks.append(CodeBlock(
            language    = lang,
            code        = code,
            is_runnable = lang in RUNNABLE_LANGS,
        ))
    return blocks


def extract_first_runnable(text: str) -> Optional[CodeBlock]:
    """Return the first runnable code block found in text."""
    for block in extract_code_blocks(text):
        if block.is_runnable:
            return block
    return None


def normalize_language(lang: str) -> str:
    """Normalize language aliases to canonical form."""
    aliases = {
        "py":     "python",
        "js":     "javascript",
        "node":   "javascript",
        "ts":     "typescript",
        "sqlite": "sql",
        "mysql":  "sql",
        "psql":   "sql",
    }
    return aliases.get(lang.lower(), lang.lower())
