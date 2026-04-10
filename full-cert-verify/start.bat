@echo off
title CertVerify
color 0A
cls

echo.
echo  =========================================================
echo    CertVerify -- Certificate Verification
echo    NPTEL  /  CodeTantra  /  Coursera  /  Udemy
echo  =========================================================
echo.

cd /d "%~dp0"

REM ── Python check ─────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Download from https://python.org
    pause & exit /b 1
)
echo  [OK] Python found.

REM ── Delete broken venv if pip missing ────────────────────────
if exist "backend\.venv" (
    backend\.venv\Scripts\python.exe -m pip --version >nul 2>&1
    if errorlevel 1 (
        echo  [INFO] Fixing broken virtual environment...
        rmdir /s /q "backend\.venv"
    )
)

REM ── Create venv if missing ───────────────────────────────────
if not exist "backend\.venv" (
    echo  [1/3] Creating virtual environment...
    python -m venv backend\.venv --clear
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause & exit /b 1
    )
    REM ── Ensure pip is installed inside venv
    backend\.venv\Scripts\python.exe -m ensurepip --upgrade >nul 2>&1
    echo        Done.
) else (
    echo  [1/3] Virtual environment ready.
)

REM ── Upgrade pip silently ─────────────────────────────────────
backend\.venv\Scripts\python.exe -m pip install --upgrade pip -q >nul 2>&1

REM ── Check .env ───────────────────────────────────────────────
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        copy "backend\.env.example" "backend\.env" >nul
    )
)

REM ── Install dependencies ─────────────────────────────────────
echo  [2/3] Installing dependencies...
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -q
if errorlevel 1 (
    echo  [ERROR] Dependency installation failed.
    pause & exit /b 1
)
echo        Done.
echo.

REM ── Open frontend ────────────────────────────────────────────
echo  [3/3] Opening frontend and starting backend...
start "" "%~dp0frontend\index.html"
echo        Frontend opened in browser.
echo.

echo  =========================================================
echo    Backend API  :  http://localhost:8000
echo    API Docs     :  http://localhost:8000/docs
echo    Frontend     :  frontend/index.html
echo.
echo    Press Ctrl+C to stop.
echo  =========================================================
echo.

REM ── Start server ─────────────────────────────────────────────
cd backend
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

echo.
echo  Server stopped.
cd ..
pause