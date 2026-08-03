@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title OfflineGPT v2

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║           OfflineGPT  v2  Launcher               ║
echo  ║   React + FastAPI + SQLite + ChromaDB + Ollama   ║
echo  ╚══════════════════════════════════════════════════╝
echo.

set ROOT=%~dp0
set BACKEND=%ROOT%backend
set FRONTEND=%ROOT%frontend

:: ── 1. Check Python ─────────────────────────────────────
where python > nul 2>&1
if %errorlevel% neq 0 (
    echo [!!] Python not found. Install from https://python.org
    pause & exit /b 1
)

:: ── 2. Check Node ────────────────────────────────────────
where node > nul 2>&1
if %errorlevel% neq 0 (
    echo [!!] Node.js not found. Install from https://nodejs.org
    pause & exit /b 1
)

:: ── 3. Install backend packages (first run only) ─────────
if not exist "%BACKEND%\venv\Scripts\activate.bat" (
    echo [..] Creating Python virtual environment...
    python -m venv "%BACKEND%\venv"
)

if not exist "%BACKEND%\venv\Lib\site-packages\fastapi" (
    echo [..] Installing Python packages (this takes ~2 minutes first time)...
    call "%BACKEND%\venv\Scripts\activate.bat"
    pip install -r "%BACKEND%\requirements.txt" --quiet
    echo [OK] Python packages installed.
) else (
    echo [OK] Python packages already installed.
)

:: ── 4. Install frontend packages (first run only) ────────
if not exist "%FRONTEND%\node_modules" (
    echo [..] Installing npm packages...
    cd /d "%FRONTEND%"
    call npm install --silent
    echo [OK] npm packages installed.
) else (
    echo [OK] npm packages already installed.
)

:: ── 5. Start Ollama (if not running) ─────────────────────
set OLLAMA_ORIGINS=*
set OLLAMA_HOST=127.0.0.1:11434

curl -s --max-time 2 http://localhost:11434 > nul 2>&1
if %errorlevel% neq 0 (
    where ollama > nul 2>&1
    if %errorlevel% == 0 (
        echo [..] Starting Ollama...
        start "Ollama" /min cmd /c "set OLLAMA_ORIGINS=* && ollama serve"
        timeout /t 3 /nobreak > nul
    ) else (
        echo [!!] Ollama not found. Download from https://ollama.com
    )
) else (
    echo [OK] Ollama is already running.
)

:: ── 6. Start FastAPI backend ─────────────────────────────
echo [..] Starting FastAPI backend on :8000...
start "OfflineGPT Backend" /min cmd /c "call \"%BACKEND%\venv\Scripts\activate.bat\" && cd /d \"%ROOT%\" && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

:: Wait for backend to be ready
echo [..] Waiting for backend...
set /a tries=0
:wait_backend
timeout /t 2 /nobreak > nul
curl -s --max-time 1 http://localhost:8000/api/health > nul 2>&1
if %errorlevel% == 0 goto backend_ready
set /a tries+=1
if !tries! GEQ 15 (
    echo [!!] Backend did not start in time. Check "OfflineGPT Backend" window.
    goto start_frontend
)
echo     Still waiting... (!tries!/15)
goto wait_backend

:backend_ready
echo [OK] Backend ready!

:start_frontend
:: ── 7. Start Vite dev server ─────────────────────────────
echo [..] Starting React frontend on :5173...
start "OfflineGPT Frontend" cmd /c "cd /d \"%FRONTEND%\" && npm run dev"

:: Wait for frontend
timeout /t 4 /nobreak > nul

:: ── 8. Open browser ──────────────────────────────────────
echo [..] Opening browser...
start "" "http://localhost:5173"

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║  OfflineGPT is running!                          ║
echo  ║                                                  ║
echo  ║  Frontend  → http://localhost:5173               ║
echo  ║  Backend   → http://localhost:8000               ║
echo  ║  API docs  → http://localhost:8000/docs          ║
echo  ║                                                  ║
echo  ║  Shortcuts:                                      ║
echo  ║  Ctrl+/  → New chat                              ║
echo  ║  Ctrl+K  → Semantic search                       ║
echo  ║  Enter   → Send message                          ║
echo  ║  Shift+Enter → New line                          ║
echo  ╚══════════════════════════════════════════════════╝
echo.
echo  Keep this window open. Press Ctrl+C to stop.
echo.

:alive
timeout /t 60 /nobreak > nul
goto alive
