"""
Data Parser — analyzes CSV, XLSX, JSON, XML files using pandas.

Generates a rich statistical summary that becomes the LLM's context:
  - Shape (rows × columns)
  - Column names + dtypes
  - First 5 rows preview (table)
  - Numeric describe() summary
  - Value counts for categoricals
  - Missing values report
  - Correlation insights (top pairs)
"""
from __future__ import annotations
from pathlib import Path
from typing import Tuple


def parse_data(file_path: str) -> Tuple[str, int]:
    """
    Returns (analysis_text, 1).
    """
    ext = Path(file_path).suffix.lower()
    try:
        import pandas as pd
        import numpy as np

        df = _load_dataframe(file_path, ext)
        if df is None:
            return "[Data Parse Error: Could not load file as DataFrame]", 0

        lines = []
        fname = Path(file_path).name

        lines.append(f"=== Data File: {fname} ===")
        lines.append(f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
        lines.append(f"Columns: {list(df.columns)}")
        lines.append("")

        # Data types
        lines.append("--- Column Types ---")
        for col in df.columns:
            lines.append(f"  {col}: {df[col].dtype}")
        lines.append("")

        # Preview (first 5 rows)
        lines.append("--- Data Preview (first 5 rows) ---")
        lines.append(df.head(5).to_string(index=False))
        lines.append("")

        # Numeric stats
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if num_cols:
            lines.append("--- Numeric Statistics ---")
            lines.append(df[num_cols].describe().round(4).to_string())
            lines.append("")

        # Missing values
        missing = df.isnull().sum()
        missing = missing[missing > 0]
        if not missing.empty:
            lines.append("--- Missing Values ---")
            for col, cnt in missing.items():
                pct = cnt / len(df) * 100
                lines.append(f"  {col}: {cnt} ({pct:.1f}%)")
            lines.append("")

        # Categorical value counts
        cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        for col in cat_cols[:5]:  # max 5 categorical columns
            vc = df[col].value_counts().head(10)
            lines.append(f"--- Top Values: {col} ---")
            for val, cnt in vc.items():
                lines.append(f"  {val}: {cnt}")
            lines.append("")

        # Correlation (numeric only, top pairs)
        if len(num_cols) >= 2:
            try:
                corr = df[num_cols].corr().abs()
                # Get upper triangle
                pairs = []
                for i, c1 in enumerate(num_cols):
                    for c2 in num_cols[i+1:]:
                        pairs.append((corr.loc[c1, c2], c1, c2))
                pairs.sort(reverse=True)
                if pairs:
                    lines.append("--- Top Correlations ---")
                    for val, c1, c2 in pairs[:5]:
                        lines.append(f"  {c1} ↔ {c2}: {val:.3f}")
                    lines.append("")
            except Exception:
                pass

        return "\n".join(lines), 1

    except ImportError:
        return "[Data Error: pandas not installed]", 0
    except Exception as e:
        return f"[Data Parse Error: {e}]", 0


def _load_dataframe(file_path: str, ext: str):
    """Load file into a pandas DataFrame."""
    import pandas as pd
    try:
        if ext == ".csv":
            # Try to detect separator
            import chardet
            raw = Path(file_path).read_bytes()[:4096]
            enc = chardet.detect(raw).get("encoding", "utf-8")
            # Detect separator
            sep = ","
            try:
                head = raw.decode(enc, errors="replace").split("\n")[0]
                for s in [";", "\t", "|"]:
                    if s in head and head.count(s) > head.count(","):
                        sep = s
                        break
            except Exception:
                pass
            return pd.read_csv(file_path, encoding=enc, sep=sep,
                               on_bad_lines="skip", nrows=50_000)

        elif ext in (".xlsx", ".xls"):
            return pd.read_excel(file_path, nrows=50_000)

        elif ext == ".json":
            import json
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            if isinstance(data, list):
                return pd.DataFrame(data)
            elif isinstance(data, dict):
                return pd.DataFrame([data])
            return None

        elif ext == ".xml":
            return pd.read_xml(file_path)

        return None
    except Exception:
        return None
