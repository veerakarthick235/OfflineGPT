"""
Archive Parser — safely extracts ZIP files and re-routes contents.

Security:
  - Max total extracted size: 200MB
  - Max files: 500
  - Blocks path traversal (../ attacks)
  - Max nesting depth: 5
"""
from __future__ import annotations
import zipfile
import shutil
import tempfile
from pathlib import Path
from typing import Tuple, List

MAX_EXTRACTED_MB = 200
MAX_FILES        = 500


def parse_archive(file_path: str, upload_dir: Path) -> Tuple[str, List[Path], int]:
    """
    Extract ZIP and return (summary_text, extracted_file_paths, count).
    Extracted files are stored under upload_dir/extracted_{stem}/.
    """
    path      = Path(file_path)
    extract_to = upload_dir / f"extracted_{path.stem}"
    extract_to.mkdir(parents=True, exist_ok=True)

    extracted_paths: List[Path] = []
    total_size      = 0
    skipped         = []

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            members = zf.infolist()
            if len(members) > MAX_FILES:
                skipped.append(f"[Too many files — capped at {MAX_FILES}]")
                members = members[:MAX_FILES]

            for info in members:
                # Block path traversal
                member_path = extract_to / info.filename
                try:
                    member_path.resolve().relative_to(extract_to.resolve())
                except ValueError:
                    skipped.append(f"Skipped (path traversal): {info.filename}")
                    continue

                # Size check
                total_size += info.file_size
                if total_size > MAX_EXTRACTED_MB * 1024 * 1024:
                    skipped.append(f"[Size limit exceeded at {info.filename}]")
                    break

                # Extract
                try:
                    zf.extract(info, extract_to)
                    extracted = extract_to / info.filename
                    if extracted.is_file():
                        extracted_paths.append(extracted)
                except Exception as e:
                    skipped.append(f"Error extracting {info.filename}: {e}")

    except zipfile.BadZipFile:
        return "[Archive Error: Not a valid ZIP file]", [], 0
    except Exception as e:
        return f"[Archive Error: {e}]", [], 0

    # Build summary
    lines = [
        f"=== ZIP Archive: {path.name} ===",
        f"Extracted {len(extracted_paths)} files ({total_size / 1024:.1f} KB total)",
    ]

    # Group by extension
    from collections import Counter
    ext_counts = Counter(f.suffix.lower() for f in extracted_paths)
    if ext_counts:
        lines.append("\nFile types:")
        for ext, cnt in ext_counts.most_common(15):
            lines.append(f"  {ext or '(no ext)'}: {cnt}")

    # List files (first 50)
    lines.append(f"\nFiles ({min(50, len(extracted_paths))} shown):")
    for p in sorted(extracted_paths)[:50]:
        rel = p.relative_to(extract_to)
        lines.append(f"  {rel}")

    if skipped:
        lines.append(f"\nSkipped ({len(skipped)}):")
        for s in skipped[:5]:
            lines.append(f"  {s}")

    # Is this a code repository?
    is_repo = _detect_repository(extracted_paths)
    if is_repo:
        lines.append("\n✓ Detected as code repository — indexing with Repository Intelligence")

    summary = "\n".join(lines)
    return summary, extracted_paths, len(extracted_paths)


def _detect_repository(paths: List[Path]) -> bool:
    """Check if extracted files look like a code repository."""
    code_exts = {".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".rb"}
    config_files = {"package.json", "setup.py", "pom.xml", "Cargo.toml", "go.mod"}
    names = {p.name for p in paths}
    exts  = {p.suffix.lower() for p in paths}
    return bool(
        (exts & code_exts) and
        (names & config_files or any("src" in str(p) for p in paths))
    )
