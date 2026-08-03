"""
Dependency Graph — extracts import relationships from source files.

Why?
  Understanding what imports what lets us answer:
  - "What files does auth.py depend on?"
  - "Which files use the database service?"
  - "Show me the call graph for the API layer"

  This is the foundation for future multi-hop code reasoning.

Supported import styles:
  Python:     import X, from X import Y, from . import Z
  JS/TS:      import X from 'Y', const X = require('Y')
  Go:         import "package"
  Rust:       use crate::module
  Java:       import com.example.Class
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import List, Dict

from .languages import FileInfo


# ── Import extractors per language ───────────────────────────────────

# Python: import X | from X import Y | from .X import Y
# One import keyword per line (ast-parse style)
_PY_IMPORT_RE = re.compile(
    r"^(?:from\s+([\w\.]+)\s+import\s+[^\n]+|import\s+([\w\.]+(?:\s*,\s*[\w\.]+)*))",
    re.MULTILINE
)

# JS/TS: import X from 'Y' | const X = require('Y')
_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
    re.MULTILINE
)

# Go: import "pkg" | import ( "pkg" )
_GO_IMPORT_RE = re.compile(r'"([\w/\.]+)"')

# Rust: use crate::X; use std::X;
_RUST_IMPORT_RE = re.compile(r"^use\s+([\w:]+)", re.MULTILINE)

# Java/Kotlin: import com.example.Class;
_JAVA_IMPORT_RE = re.compile(r"^import\s+([\w\.]+);", re.MULTILINE)


def extract_dependencies(file_info: FileInfo, source: str) -> List[Dict[str, str]]:
    """
    Extract all imports from a source file.
    Returns list of { source_file, imported_module, import_type }.
    """
    deps: List[Dict[str, str]] = []
    lang = file_info.language

    if lang == "python":
        for m in _PY_IMPORT_RE.finditer(source):
            mod = m.group(1) or m.group(2)
            if mod:
                for part in mod.split(","):
                    part = part.strip()
                    if part:
                        import_type = "relative" if part.startswith(".") else "absolute"
                        deps.append({
                            "source_file":     file_info.rel_path,
                            "imported_module":  part,
                            "import_type":      import_type,
                        })

    elif lang in ("javascript", "typescript"):
        for m in _JS_IMPORT_RE.finditer(source):
            mod = m.group(1) or m.group(2)
            if mod:
                import_type = "relative" if mod.startswith(".") else "npm"
                deps.append({
                    "source_file":     file_info.rel_path,
                    "imported_module":  mod,
                    "import_type":      import_type,
                })

    elif lang == "go":
        # Find import blocks
        import_block = re.search(r"import\s+\(([^)]+)\)", source, re.DOTALL)
        if import_block:
            for m in _GO_IMPORT_RE.finditer(import_block.group(1)):
                deps.append({
                    "source_file":     file_info.rel_path,
                    "imported_module":  m.group(1),
                    "import_type":      "go",
                })

    elif lang == "rust":
        for m in _RUST_IMPORT_RE.finditer(source):
            deps.append({
                "source_file":     file_info.rel_path,
                "imported_module":  m.group(1),
                "import_type":      "use",
            })

    elif lang in ("java", "kotlin", "csharp"):
        for m in _JAVA_IMPORT_RE.finditer(source):
            deps.append({
                "source_file":     file_info.rel_path,
                "imported_module":  m.group(1),
                "import_type":      "import",
            })

    return deps


def build_dependency_summary(dependencies: List[Dict]) -> str:
    """
    Build a human-readable dependency summary for context injection.
    Groups by source file.
    """
    by_file: Dict[str, List[str]] = {}
    for d in dependencies:
        src = d["source_file"]
        if src not in by_file:
            by_file[src] = []
        by_file[src].append(d["imported_module"])

    lines = []
    for src, mods in sorted(by_file.items()):
        lines.append(f"{src}:")
        # De-duplicate and sort
        unique = sorted(set(mods))[:10]  # cap at 10 per file
        for m in unique:
            lines.append(f"  → {m}")

    return "\n".join(lines)
