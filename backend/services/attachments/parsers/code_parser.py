"""
Code Parser — reads source code files as plain text.
Leverages existing repo intelligence for symbol/dependency extraction.
For single files: reads raw text with syntax info.
"""
from __future__ import annotations
from pathlib import Path
from typing import Tuple


def parse_code(file_path: str) -> Tuple[str, int]:
    """
    Returns (code_text_with_header, 1).
    """
    path = Path(file_path)
    ext  = path.suffix.lower().lstrip(".")

    try:
        import chardet
        raw = path.read_bytes()
        enc = chardet.detect(raw).get("encoding", "utf-8") or "utf-8"
        text = raw.decode(enc, errors="replace")
    except Exception:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[Code Read Error: {e}]", 0

    # Try to extract symbols using existing chunker
    symbols_summary = _extract_symbols(file_path, ext, text)

    lines      = text.count("\n") + 1
    char_count = len(text)
    header = (
        f"=== Code File: {path.name} ===\n"
        f"Language: {ext}\n"
        f"Lines: {lines:,} | Characters: {char_count:,}\n"
    )
    if symbols_summary:
        header += f"\n--- Symbols ---\n{symbols_summary}\n"

    header += "\n--- Source Code ---\n"

    # For very long files, include first 5000 chars + summary
    MAX_CODE_CHARS = 12_000
    if len(text) > MAX_CODE_CHARS:
        snippet = text[:MAX_CODE_CHARS]
        full    = header + snippet + f"\n... [truncated — {lines} total lines]"
    else:
        full = header + text

    return full, 1


def _extract_symbols(file_path: str, ext: str, code: str) -> str:
    """Try to use existing code_chunker for symbol extraction."""
    try:
        from ...repo.code_chunker import chunk_file
        chunks = chunk_file(file_path, code)
        funcs  = [c.symbol_name for c in chunks if c.symbol_type in ("function", "method", "class")]
        if funcs:
            return ", ".join(funcs[:30])  # first 30 symbols
    except Exception:
        pass
    return ""
