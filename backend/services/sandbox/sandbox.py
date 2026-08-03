"""
Secure Code Sandbox — runs user/AI code in isolated subprocesses.

Security model:
  ✅ Each run gets its own temp directory (deleted after)
  ✅ Hard timeout (default 10s) via asyncio.wait_for
  ✅ Captured stdout + stderr (no terminal passthrough)
  ✅ Restricted environment variables (no proxies, no tokens)
  ✅ Maximum output size cap (50KB)
  ⚠️ No OS-level sandboxing (no seccomp/chroot on Windows)
     → Rely on the dangerous-import check as a first guard
  ⚠️ JavaScript requires Node.js installed locally

Supported languages:
  python      → uses the project venv interpreter
  javascript  → uses node (if found on PATH)
  typescript  → transpiles with ts-node (if found)
  bash/shell  → DISABLED (too risky)
  sql         → parsed + executed against in-memory SQLite

Result schema:
  {
    "success":   bool,
    "stdout":    str,
    "stderr":    str,
    "exit_code": int,
    "duration_ms": float,
    "language":  str,
    "truncated": bool,
    "error":     str | None,
  }
"""
from __future__ import annotations
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

# ── Configuration ─────────────────────────────────────────────────────
DEFAULT_TIMEOUT   = 10.0          # seconds
MAX_OUTPUT_BYTES  = 50_000        # 50 KB
PYTHON_EXEC       = Path(sys.executable)   # current venv python

# Environment for sandboxed subprocess — minimal, no secrets
_SAFE_ENV = {
    "PATH":         os.environ.get("PATH", ""),
    "TEMP":         tempfile.gettempdir(),
    "TMP":          tempfile.gettempdir(),
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8":   "1",
}


# ── Dangerous pattern check ────────────────────────────────────────────
_PYTHON_BLOCKED = [
    "import subprocess", "from subprocess",
    "import socket", "from socket",
    "import ctypes", "from ctypes",
    "__import__('os').system",
    "exec(", "compile(",
    "open('/etc", "open('C:\\\\Windows",
]

_JS_BLOCKED = [
    "require('child_process')", "require(\"child_process\")",
    "require('fs').rmSync", "require('fs').unlinkSync",
    "process.exit(0)", "eval(",
]


def _check_safety(code: str, language: str) -> Optional[str]:
    """Return an error message if the code contains dangerous patterns."""
    blocked = _PYTHON_BLOCKED if language == "python" else _JS_BLOCKED
    for pattern in blocked:
        if pattern in code:
            return f"Blocked: code contains restricted pattern `{pattern}`"
    return None


# ── Result builder ─────────────────────────────────────────────────────
def _result(
    success:  bool,
    stdout:   str  = "",
    stderr:   str  = "",
    exit_code:int  = 0,
    duration: float = 0.0,
    language: str   = "",
    truncated:bool  = False,
    error:    Optional[str] = None,
) -> dict:
    return {
        "success":     success,
        "stdout":      stdout,
        "stderr":      stderr,
        "exit_code":   exit_code,
        "duration_ms": round(duration * 1000, 1),
        "language":    language,
        "truncated":   truncated,
        "error":       error,
    }


# ── Core runner ────────────────────────────────────────────────────────

async def run_code(
    code:       str,
    language:   str    = "python",
    timeout:    float  = DEFAULT_TIMEOUT,
    extra_files: dict  = None,   # {"filename.txt": "content"} written to tmpdir
) -> dict:
    """
    Execute code in an isolated subprocess.

    Args:
        code:        Source code to run
        language:    "python" | "javascript" | "sql"
        timeout:     Max execution time in seconds
        extra_files: Additional files to write to the temp directory

    Returns:
        Result dict (see module docstring)
    """
    language = language.lower().strip()
    if language in ("js", "node"):
        language = "javascript"
    if language in ("py",):
        language = "python"

    # Safety check
    err = _check_safety(code, language)
    if err:
        return _result(False, error=err, language=language)

    # Dispatch
    if language == "python":
        return await _run_python(code, timeout, extra_files)
    elif language == "javascript":
        return await _run_javascript(code, timeout, extra_files)
    elif language == "sql":
        return await _run_sql(code, timeout)
    else:
        return _result(False, error=f"Unsupported language: {language}", language=language)


# ── Python runner ──────────────────────────────────────────────────────

async def _run_python(code: str, timeout: float, extra_files: dict = None) -> dict:
    tmpdir = tempfile.mkdtemp(prefix="ogpt_sandbox_")
    try:
        # Write extra files
        if extra_files:
            for fname, content in extra_files.items():
                (Path(tmpdir) / fname).write_text(content, encoding="utf-8")

        # Write the code file
        code_file = Path(tmpdir) / "run.py"
        code_file.write_text(code, encoding="utf-8")

        start = time.perf_counter()
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    str(PYTHON_EXEC), str(code_file),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmpdir,
                    env=_SAFE_ENV,
                ),
                timeout=2.0,   # process creation timeout
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            duration = time.perf_counter() - start

        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return _result(False, error=f"Execution timed out after {timeout}s",
                           language="python", duration=timeout)

        stdout = _decode_cap(stdout_b)
        stderr = _decode_cap(stderr_b)
        truncated = (len(stdout_b) + len(stderr_b)) > MAX_OUTPUT_BYTES

        return _result(
            success   = proc.returncode == 0,
            stdout    = stdout,
            stderr    = stderr,
            exit_code = proc.returncode,
            duration  = duration,
            language  = "python",
            truncated = truncated,
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── JavaScript runner ──────────────────────────────────────────────────

async def _run_javascript(code: str, timeout: float, extra_files: dict = None) -> dict:
    node_exe = shutil.which("node")
    if not node_exe:
        return _result(False, language="javascript",
                       error="Node.js not found. Install Node.js to run JavaScript.")

    tmpdir = tempfile.mkdtemp(prefix="ogpt_sandbox_")
    try:
        if extra_files:
            for fname, content in extra_files.items():
                (Path(tmpdir) / fname).write_text(content, encoding="utf-8")

        code_file = Path(tmpdir) / "run.js"
        code_file.write_text(code, encoding="utf-8")

        start = time.perf_counter()
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    node_exe, str(code_file),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmpdir,
                    env=_SAFE_ENV,
                ),
                timeout=2.0,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            duration = time.perf_counter() - start

        except asyncio.TimeoutError:
            try: proc.kill()
            except Exception: pass
            return _result(False, error=f"Execution timed out after {timeout}s",
                           language="javascript", duration=timeout)

        stdout = _decode_cap(stdout_b)
        stderr = _decode_cap(stderr_b)
        return _result(
            success   = proc.returncode == 0,
            stdout    = stdout,
            stderr    = stderr,
            exit_code = proc.returncode,
            duration  = duration,
            language  = "javascript",
            truncated = (len(stdout_b) + len(stderr_b)) > MAX_OUTPUT_BYTES,
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── SQL runner (in-memory SQLite) ──────────────────────────────────────

async def _run_sql(code: str, timeout: float) -> dict:
    """Execute SQL against an in-memory SQLite database."""
    import sqlite3
    import io

    output = io.StringIO()
    start  = time.perf_counter()
    try:
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        # Execute each statement
        statements = [s.strip() for s in code.split(";") if s.strip()]
        for stmt in statements:
            cur.execute(stmt)
            rows = cur.fetchall()
            if rows:
                # Header
                cols = [d[0] for d in cur.description]
                output.write(" | ".join(cols) + "\n")
                output.write("-" * (sum(len(c) for c in cols) + 3 * len(cols)) + "\n")
                for row in rows:
                    output.write(" | ".join(str(v) for v in row) + "\n")
                output.write(f"\n({len(rows)} rows)\n")

        con.close()
        duration = time.perf_counter() - start
        return _result(True, stdout=output.getvalue(), duration=duration, language="sql")

    except Exception as e:
        duration = time.perf_counter() - start
        return _result(False, stderr=str(e), exit_code=1, duration=duration, language="sql", error=str(e))


# ── Helpers ────────────────────────────────────────────────────────────

def _decode_cap(raw: bytes) -> str:
    """Decode bytes, cap at MAX_OUTPUT_BYTES, ensure valid text."""
    if len(raw) > MAX_OUTPUT_BYTES:
        raw = raw[:MAX_OUTPUT_BYTES]
    return raw.decode("utf-8", errors="replace")
