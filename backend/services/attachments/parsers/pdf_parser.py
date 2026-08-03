"""
PDF Parser — extracts text from PDF files using PyMuPDF (fitz).

Strategy:
1. Open with fitz.open()
2. Extract text per page
3. If page is empty (scanned), try pytesseract OCR (optional)
4. Return combined text + page count
"""
from __future__ import annotations
from pathlib import Path
from typing import Tuple


def parse_pdf(file_path: str) -> Tuple[str, int]:
    """
    Extract text from PDF.
    Returns (full_text, page_count).
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return f"[PDF Parser Error: PyMuPDF not installed. Run: pip install pymupdf]", 0

    pages = []
    page_count = 0
    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if not text:
                # Scanned page — try OCR if available
                text = _try_ocr(page, i + 1)
            if text:
                pages.append(f"--- Page {i + 1} ---\n{text}")
        doc.close()
    except Exception as e:
        return f"[PDF Parse Error: {e}]", 0

    return "\n\n".join(pages), page_count


def _try_ocr(page, page_num: int) -> str:
    """Attempt OCR on a scanned page. Gracefully returns empty if not available."""
    try:
        import pytesseract
        from PIL import Image
        import io
        # Render page to image at 2x resolution for better OCR
        mat  = page.get_pixmap(matrix=page.IDENTITY.prescale(2, 2))
        data = mat.tobytes("png")
        img  = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception:
        return ""  # OCR not available or failed — just skip


def extract_pdf_metadata(file_path: str) -> dict:
    """Extract PDF metadata (author, title, creation date)."""
    try:
        import fitz
        doc  = fitz.open(file_path)
        meta = doc.metadata or {}
        doc.close()
        return {
            "title":    meta.get("title", ""),
            "author":   meta.get("author", ""),
            "subject":  meta.get("subject", ""),
            "keywords": meta.get("keywords", ""),
            "creator":  meta.get("creator", ""),
        }
    except Exception:
        return {}
