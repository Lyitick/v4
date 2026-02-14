@echo off
REM ============================================
REM  Start Bot + WebApp Backend (Windows)
REM ============================================
REM  Opens two separate windows:
REM    1. Finance Bot (Telegram polling)
REM    2. WebApp Backend (FastAPI on port 8080)
REM
REM  You also need Cloudflare tunnel running:
REM    cloudflared tunnel --url http://localhost:8080
REM ============================================

cd /d "%~dp0"

echo Starting Finance Bot...
start "Finance Bot" cmd /k "cd /d "%~dp0" && set PYTHONPATH=%~dp0finance_bot && python finance_bot/Bot/main.py"

echo Starting WebApp Backend...
start "WebApp Backend" cmd /k "cd /d "%~dp0" && set PYTHONPATH=%~dp0;%~dp0finance_bot && python -m uvicorn webapp.backend.main:app --host 0.0.0.0 --port 8080 --reload"

echo.
echo Both services started in separate windows.
echo.
echo Don't forget to start Cloudflare tunnel:
echo   cloudflared tunnel --url http://localhost:8080
echo.
pause
