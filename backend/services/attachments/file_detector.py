"""
File Detector — maps any uploaded file to a category and routes
it to the correct parser.

Categories:
  pdf       → pdf_parser
  image     → image_parser
  document  → document_parser  (docx, txt, md, rtf)
  slides    → slide_parser     (pptx)
  data      → data_parser      (csv, xlsx, json, xml)
  code      → code_parser      (py, js, ts, java, c, cpp, go, rs, …)
  archive   → archive_parser   (zip)
  unknown   → raw text read attempt
"""
from __future__ import annotations
import mimetypes
from pathlib import Path
from typing import Tuple

# Extension → (category, label)
_EXT_MAP: dict[str, Tuple[str, str]] = {
    # Documents
    ".pdf":  ("pdf",      "PDF"),
    ".docx": ("document", "Word Document"),
    ".doc":  ("document", "Word Document"),
    ".txt":  ("document", "Text File"),
    ".md":   ("document", "Markdown"),
    ".rtf":  ("document", "Rich Text"),
    # Slides
    ".pptx": ("slides",   "PowerPoint"),
    ".ppt":  ("slides",   "PowerPoint"),
    # Data
    ".csv":  ("data",     "CSV Spreadsheet"),
    ".xlsx": ("data",     "Excel Spreadsheet"),
    ".xls":  ("data",     "Excel Spreadsheet"),
    ".json": ("data",     "JSON Data"),
    ".xml":  ("data",     "XML Data"),
    # Images
    ".png":  ("image",    "PNG Image"),
    ".jpg":  ("image",    "JPEG Image"),
    ".jpeg": ("image",    "JPEG Image"),
    ".webp": ("image",    "WebP Image"),
    ".bmp":  ("image",    "BMP Image"),
    ".gif":  ("image",    "GIF Image"),
    # Code
    ".py":   ("code",     "Python"),
    ".js":   ("code",     "JavaScript"),
    ".ts":   ("code",     "TypeScript"),
    ".jsx":  ("code",     "React JSX"),
    ".tsx":  ("code",     "React TSX"),
    ".java": ("code",     "Java"),
    ".c":    ("code",     "C"),
    ".cpp":  ("code",     "C++"),
    ".cc":   ("code",     "C++"),
    ".cxx":  ("code",     "C++"),
    ".h":    ("code",     "C Header"),
    ".hpp":  ("code",     "C++ Header"),
    ".cs":   ("code",     "C#"),
    ".go":   ("code",     "Go"),
    ".rs":   ("code",     "Rust"),
    ".rb":   ("code",     "Ruby"),
    ".php":  ("code",     "PHP"),
    ".swift":("code",     "Swift"),
    ".kt":   ("code",     "Kotlin"),
    ".scala":("code",     "Scala"),
    ".r":    ("code",     "R"),
    ".sh":   ("code",     "Shell"),
    ".bash": ("code",     "Bash"),
    ".sql":  ("code",     "SQL"),
    ".html": ("code",     "HTML"),
    ".css":  ("code",     "CSS"),
    ".scss": ("code",     "SCSS"),
    ".yaml": ("code",     "YAML"),
    ".yml":  ("code",     "YAML"),
    ".toml": ("code",     "TOML"),
    ".ini":  ("code",     "Config"),
    ".env":  ("code",     "Env Config"),
    # Archives
    ".zip":  ("archive",  "ZIP Archive"),
    ".tar":  ("archive",  "TAR Archive"),
    ".gz":   ("archive",  "GZip Archive"),
}

# Category → icon (for UI)
CATEGORY_ICONS = {
    "pdf":      "📄",
    "document": "📝",
    "slides":   "📊",
    "data":     "📊",
    "image":    "🖼️",
    "code":     "💻",
    "archive":  "📦",
    "unknown":  "📎",
}


def detect_file_type(filename: str) -> Tuple[str, str, str]:
    """
    Returns (category, label, icon) for a given filename.
    E.g. "report.pdf" → ("pdf", "PDF", "📄")
    """
    ext   = Path(filename).suffix.lower()
    entry = _EXT_MAP.get(ext)
    if entry:
        cat, label = entry
    else:
        # Fallback: use mimetypes
        mime, _ = mimetypes.guess_type(filename)
        if mime:
            if mime.startswith("image/"):
                cat, label = "image", "Image"
            elif mime.startswith("text/"):
                cat, label = "document", "Text File"
            elif "zip" in mime or "archive" in mime or "compressed" in mime:
                cat, label = "archive", "Archive"
            else:
                cat, label = "unknown", "File"
        else:
            cat, label = "unknown", "File"
    return cat, label, CATEGORY_ICONS.get(cat, "📎")


def get_mime_type(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"
