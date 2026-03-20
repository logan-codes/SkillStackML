@echo off
title CertVerify — Multi-Platform Certificate Verifier
color 0A
cls

echo.
echo  =========================================================
echo    CertVerify -- Certificate Verification
echo    NPTEL  /  CodeTantra  /  Coursera  /  Udemy
echo  =========================================================
echo.

REM ── Change to the project root (same folder as this .bat file)
cd /d "%~dp0"

REM ── Check Python ────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo          Download from https://python.org and add it to PATH.
    pause & exit /b 1
)
echo  [OK] Python found.

REM ── Check / install uv (fast package manager) ───────────────
uv --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Installing uv package manager...
    pip install uv -q
    if errorlevel 1 (
        echo  [ERROR] Failed to install uv. Check your internet connection.
        pause & exit /b 1
    )
)
echo  [OK] uv ready.
echo.

REM ── Create virtual environment if it doesn't exist ──────────
if not exist "backend\.venv" (
    echo  [1/3] Creating virtual environment...
    cd backend
    uv venv .venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause & exit /b 1
    )
    cd ..
    echo        Done.
) else (
    echo  [1/3] Virtual environment already exists — skipping.
)

REM ── Check for .env file ──────────────────────────────────────
if not exist "backend\.env" (
    echo.
    echo  [WARN] No .env file found in backend\.
    echo         Copying .env.example to .env ...
    copy "backend\.env.example" "backend\.env" >nul
    echo.
    echo  ---------------------------------------------------------
    echo    ACTION REQUIRED:
    echo    Open backend\.env and set your GROQ_API_KEY
    echo    Get a free key at: https://console.groq.com
    echo    (Required for Coursera and Udemy verification)
    echo  ---------------------------------------------------------
    echo.
    pause
)

REM ── Install / sync dependencies ──────────────────────────────
echo  [2/3] Installing dependencies (this may take a moment on first run)...
cd backend
uv pip install -r requirements.txt --python .venv\Scripts\python.exe -q
if errorlevel 1 (
    echo  [ERROR] Dependency installation failed.
    echo         Check your internet connection and try again.
    cd ..
    pause & exit /b 1
)
cd ..
echo        Done.
echo.

REM ── Launch frontend in browser ───────────────────────────────
echo  [3/3] Opening frontend and starting backend...
start "" "%~dp0frontend\index.html"
echo        Frontend opened in browser.
echo.

REM ── Print info ───────────────────────────────────────────────
echo  =========================================================
echo    Backend API  :  http://localhost:8000
echo    API Docs     :  http://localhost:8000/docs
echo    Frontend     :  frontend/index.html (opened)
echo.
echo    Supported providers:
echo      POST /api/v1/verify/nptel
echo      POST /api/v1/verify/codetantra
echo      POST /api/v1/verify/coursera
echo      POST /api/v1/verify/udemy
echo.
echo    Press Ctrl+C to stop the server.
echo  =========================================================
echo.

REM ── Start backend server ─────────────────────────────────────
cd backend
.venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8000 --reload

echo.
echo  Server stopped. Press any key to exit.
cd ..
pause