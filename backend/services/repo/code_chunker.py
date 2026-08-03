"""
Code Chunker — extracts meaningful code units (functions, classes, methods).

Why NOT arbitrary line-splitting?
  Splitting at line 50 might cut a function in half:
  the docstring is in chunk 1, the body is in chunk 2.
  Neither chunk is useful on its own.

  Code-aware chunking keeps each function/class WHOLE in one chunk,
  preserving the semantic unit that answers "how does X work?"

Strategy per language:
  Python:     ast module → exact AST node boundaries (perfect)
  JS/TS:      regex function/class/arrow detection
  Go:         regex func declarations
  Rust:       regex fn/impl/struct
  Java/Kotlin:regex class/method
  Generic:    sliding window with overlap (fallback)
"""
from __future__ import annotations
import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class CodeChunk:
    """A meaningful code unit extracted from a file."""
    chunk_id:    str         # "{repo_id}__{rel_path}__L{start}"
    repo_id:     str
    file_path:   str         # relative path
    language:    str
    symbol_name: Optional[str]   # function/class name, None for file-level
    symbol_type: str             # "function" | "class" | "method" | "block" | "file"
    start_line:  int
    end_line:    int
    code:        str         # the actual source code
    docstring:   Optional[str]
    signature:   Optional[str]   # first line (def ..., class ...)


# ── Python: AST-based extraction ─────────────────────────────────────

def _python_chunks(source: str, rel_path: str, repo_id: str) -> List[CodeChunk]:
    """Extract functions and classes using Python's built-in ast module."""
    chunks: List[CodeChunk] = []
    lines  = source.splitlines(keepends=True)

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Fall back to line-based chunking
        return _generic_chunks(source, rel_path, repo_id, "python")

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        start = node.lineno - 1        # 0-indexed
        end   = node.end_lineno        # exclusive
        code  = "".join(lines[start:end])

        if len(code.strip()) < 10:
            continue

        # Determine type
        if isinstance(node, ast.ClassDef):
            sym_type = "class"
        elif isinstance(node, ast.AsyncFunctionDef):
            sym_type = "async_function"
        else:
            # Check if it's a method (inside a class)
            sym_type = "function"

        # Extract docstring
        docstring = None
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            docstring = node.body[0].value.value[:400]

        # Signature: first line
        signature = lines[start].rstrip() if lines else None

        cid = f"{repo_id}__{rel_path}__L{node.lineno}"
        chunks.append(CodeChunk(
            chunk_id    = cid,
            repo_id     = repo_id,
            file_path   = rel_path,
            language    = "python",
            symbol_name = node.name,
            symbol_type = sym_type,
            start_line  = node.lineno,
            end_line    = end,
            code        = code[:3000],   # cap very long functions
            docstring   = docstring,
            signature   = signature,
        ))

    # Also add a file-level summary chunk if no top-level functions found
    if not chunks or len(lines) < 30:
        chunks.append(_file_chunk(source, rel_path, repo_id, "python", lines))

    return chunks


# ── Regex-based: JS/TS/Go/Rust/Java/Generic ──────────────────────────

# Patterns per language family
_JS_PATTERNS = [
    # named function declarations: function foo(...) {
    re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(", re.M),
    # arrow functions assigned to const: const foo = (...) =>
    re.compile(r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(.*\)\s*=>", re.M),
    # class declarations
    re.compile(r"^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", re.M),
    # class methods: methodName(...) {
    re.compile(r"^\s{2,}(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{", re.M),
]

_GO_PATTERNS = [
    re.compile(r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(", re.M),
    re.compile(r"^type\s+(\w+)\s+(?:struct|interface)\b", re.M),
]

_RUST_PATTERNS = [
    re.compile(r"^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*[\(<]", re.M),
    re.compile(r"^(?:pub\s+)?(?:struct|enum|impl|trait)\s+(\w+)", re.M),
]

_JAVA_PATTERNS = [
    re.compile(r"^(?:\s*)(?:public|private|protected|static|final|abstract|\s)+\s+\w[\w<>,\[\]\s]*\s+(\w+)\s*\(", re.M),
    re.compile(r"^(?:public\s+)?(?:abstract\s+)?class\s+(\w+)", re.M),
]

_LANG_PATTERNS = {
    "javascript": _JS_PATTERNS,
    "typescript": _JS_PATTERNS,
    "go":         _GO_PATTERNS,
    "rust":       _RUST_PATTERNS,
    "java":       _JAVA_PATTERNS,
    "kotlin":     _JAVA_PATTERNS,
    "csharp":     _JAVA_PATTERNS,
}


def _regex_chunks(source: str, rel_path: str, repo_id: str, language: str) -> List[CodeChunk]:
    """Extract code chunks using regex patterns for the given language."""
    patterns = _LANG_PATTERNS.get(language, [])
    if not patterns:
        return _generic_chunks(source, rel_path, repo_id, language)

    lines  = source.splitlines()
    n      = len(lines)
    chunks = []

    # Collect all match positions
    positions = []
    for pat in patterns:
        for m in pat.finditer(source):
            line_no = source[:m.start()].count("\n") + 1
            name    = m.group(1) if m.lastindex else "anonymous"
            positions.append((line_no, name, m.group()))

    positions.sort()

    for i, (start_line, name, match_text) in enumerate(positions):
        # End = next match or EOF
        end_line = positions[i + 1][0] - 1 if i + 1 < len(positions) else n
        end_line = min(end_line, start_line + 100)  # cap at 100 lines

        code = "\n".join(lines[start_line - 1: end_line])
        if len(code.strip()) < 10:
            continue

        # Guess type
        sym_type = "class" if re.search(r"\bclass\b|\bstruct\b|\binterface\b|\btrait\b|\benum\b", match_text) else "function"

        cid = f"{repo_id}__{rel_path}__L{start_line}"
        chunks.append(CodeChunk(
            chunk_id    = cid,
            repo_id     = repo_id,
            file_path   = rel_path,
            language    = language,
            symbol_name = name,
            symbol_type = sym_type,
            start_line  = start_line,
            end_line    = end_line,
            code        = code[:3000],
            docstring   = None,
            signature   = match_text.strip()[:200],
        ))

    if not chunks:
        chunks.append(_file_chunk(source, rel_path, repo_id, language, lines))

    return chunks


def _generic_chunks(source: str, rel_path: str, repo_id: str, language: str) -> List[CodeChunk]:
    """Sliding window chunking for unsupported languages."""
    lines      = source.splitlines()
    chunk_size = 40
    overlap    = 8
    chunks     = []

    for start in range(0, len(lines), chunk_size - overlap):
        end     = min(start + chunk_size, len(lines))
        code    = "\n".join(lines[start:end])
        if not code.strip():
            continue
        cid = f"{repo_id}__{rel_path}__L{start+1}"
        chunks.append(CodeChunk(
            chunk_id    = cid,
            repo_id     = repo_id,
            file_path   = rel_path,
            language    = language,
            symbol_name = None,
            symbol_type = "block",
            start_line  = start + 1,
            end_line    = end,
            code        = code[:3000],
            docstring   = None,
            signature   = None,
        ))

    return chunks


def _file_chunk(source: str, rel_path: str, repo_id: str, language: str, lines) -> CodeChunk:
    """Create a file-level chunk for very short files."""
    return CodeChunk(
        chunk_id    = f"{repo_id}__{rel_path}__file",
        repo_id     = repo_id,
        file_path   = rel_path,
        language    = language,
        symbol_name = rel_path.split("/")[-1],
        symbol_type = "file",
        start_line  = 1,
        end_line    = len(lines) if lines else 1,
        code        = source[:3000],
        docstring   = None,
        signature   = None,
    )


# ── Main entry point ──────────────────────────────────────────────────

def chunk_file(
    source:   str,
    rel_path: str,
    repo_id:  str,
    language: str,
) -> List[CodeChunk]:
    """
    Extract code chunks from a source file.
    Dispatches to the best available strategy for the language.
    """
    if not source.strip():
        return []

    if language == "python":
        return _python_chunks(source, rel_path, repo_id)
    elif language in _LANG_PATTERNS:
        return _regex_chunks(source, rel_path, repo_id, language)
    else:
        return _generic_chunks(source, rel_path, repo_id, language)
