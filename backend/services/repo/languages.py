"""
Language detection and per-language parsing strategies.

Why separate language handling?
  Different languages have different structure conventions.
  Python has clean AST. JS uses braces. Go has package declarations.
  A language-aware chunker extracts meaningful units (functions/classes)
  instead of arbitrary line blocks.

Supported languages and their strategies:
  python     → ast module (100% precise)
  javascript → regex (function/class/arrow detection)
  typescript → regex (same as JS + type annotations)
  go         → regex (func declarations)
  rust       → regex (fn/impl/struct)
  java       → regex (class/method)
  cpp/c      → regex (function patterns)
  generic    → line-based fallback
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


# File extension → language name
EXTENSION_MAP = {
    ".py":    "python",
    ".pyw":   "python",
    ".js":    "javascript",
    ".jsx":   "javascript",
    ".ts":    "typescript",
    ".tsx":   "typescript",
    ".mjs":   "javascript",
    ".cjs":   "javascript",
    ".go":    "go",
    ".rs":    "rust",
    ".java":  "java",
    ".kt":    "kotlin",
    ".cpp":   "cpp",
    ".cc":    "cpp",
    ".cxx":   "cpp",
    ".c":     "c",
    ".h":     "c",
    ".hpp":   "cpp",
    ".cs":    "csharp",
    ".rb":    "ruby",
    ".php":   "php",
    ".swift": "swift",
    ".sh":    "bash",
    ".bash":  "bash",
    ".zsh":   "bash",
    ".md":    "markdown",
    ".txt":   "text",
    ".json":  "json",
    ".yaml":  "yaml",
    ".yml":   "yaml",
    ".toml":  "toml",
    ".sql":   "sql",
    ".html":  "html",
    ".css":   "css",
}

# Directories to always skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".env", "dist", "build", "target", ".idea", ".vscode", "coverage",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "site-packages",
    ".tox", "eggs", ".eggs", "htmlcov", ".cache",
}

# Files to skip
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp3", ".mp4", ".wav", ".ogg", ".avi",
    ".zip", ".tar", ".gz", ".bz2", ".7z",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".lock",  # package-lock.json, poetry.lock → too noisy
    ".min.js", ".min.css",
}

MAX_FILE_SIZE = 500_000   # 500KB — skip huge generated files


@dataclass
class FileInfo:
    path:      Path
    language:  str
    rel_path:  str   # relative to repo root
    size:      int


def detect_language(file_path: Path) -> Optional[str]:
    """Return language name for a file, or None if it should be skipped."""
    name = file_path.name.lower()
    suffix = file_path.suffix.lower()

    # Skip by extension
    if suffix in SKIP_EXTENSIONS:
        return None
    if name.endswith(".min.js") or name.endswith(".min.css"):
        return None

    return EXTENSION_MAP.get(suffix, "text")


def walk_repo(repo_path: str | Path, max_files: int = 5000) -> List[FileInfo]:
    """
    Walk a repository directory and return indexable files.

    Skips:
    - Binary files
    - node_modules / __pycache__ / .git / etc.
    - Files larger than MAX_FILE_SIZE
    - Generated / minified files

    Returns FileInfo list ordered: code files first, config/docs last.
    """
    root = Path(repo_path).resolve()
    if not root.exists():
        raise ValueError(f"Repository path does not exist: {root}")

    code_langs   = {"python","javascript","typescript","go","rust","java","kotlin","cpp","c","csharp","ruby","php","swift"}
    config_langs = {"json","yaml","toml","sql","bash","html","css","markdown","text"}

    code_files:   List[FileInfo] = []
    config_files: List[FileInfo] = []

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue

        # Skip ignored directories
        parts = file_path.parts
        if any(part in SKIP_DIRS for part in parts):
            continue

        # Check file size
        try:
            size = file_path.stat().st_size
        except OSError:
            continue
        if size > MAX_FILE_SIZE or size == 0:
            continue

        lang = detect_language(file_path)
        if lang is None:
            continue

        rel = str(file_path.relative_to(root)).replace("\\", "/")
        info = FileInfo(path=file_path, language=lang, rel_path=rel, size=size)

        if lang in code_langs:
            code_files.append(info)
        else:
            config_files.append(info)

    # Code files first
    all_files = code_files + config_files
    return all_files[:max_files]
