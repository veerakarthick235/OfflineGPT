"""
Run this file from EITHER the project root OR the backend/ directory.

From project root:
    python backend/run.py

From backend/ directory:
    python run.py

Or use the start.bat in the project root.
"""
import sys
import os

# Ensure project root is on sys.path so `backend.*` imports resolve
_here       = os.path.dirname(os.path.abspath(__file__))   # backend/
_proj_root  = os.path.dirname(_here)                        # offlinegpt-v2/
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host        = "127.0.0.1",
        port        = 8000,
        reload      = True,
        reload_dirs = [_here],          # watch backend/ only
    )
