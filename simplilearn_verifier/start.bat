@echo off
title Simplilearn Certificate Verifier
color 0B

echo.
echo  ╔════════════════════════════════════════════╗
echo  ║   Simplilearn Certificate Verifier v9.0    ║
echo  ╚════════════════════════════════════════════╝
echo.

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause & exit /b 1
)

echo [1/2] Installing backend dependencies...
cd /d "%BACKEND%"
pip install -r requirements.txt -q
echo       Done.
echo.

echo [2/2] Starting both servers...
echo.

powershell -NoExit -Command "$f='%FRONTEND%'; $b='%BACKEND%'; Write-Host ''; Write-Host '  Frontend  ->  http://localhost:5500' -ForegroundColor Cyan; Write-Host '  Backend   ->  http://localhost:8000' -ForegroundColor Green; Write-Host '  API Docs  ->  http://localhost:8000/docs' -ForegroundColor Yellow; Write-Host ''; Write-Host '  Ctrl+C to stop.' -ForegroundColor Gray; Write-Host ''; Start-Job -Name Frontend -ScriptBlock { param($dir) python -m http.server 5500 --directory $dir } -ArgumentList $f | Out-Null; Start-Sleep 1; Start-Process 'http://localhost:5500'; Set-Location $b; uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
