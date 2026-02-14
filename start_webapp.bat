@echo off
REM ============================================
REM  Start Finance Mini App Backend (Windows)
REM ============================================
REM  This starts the FastAPI backend server.
REM  The bot (finance_bot/Bot/main.py) must be
REM  started separately in another terminal.
REM ============================================

cd /d "%~dp0"

set PYTHONPATH=%~dp0;%~dp0finance_bot

echo.
echo === Finance Mini App Backend ===
echo PYTHONPATH=%PYTHONPATH%
echo Starting uvicorn on http://0.0.0.0:8080 ...
echo.
echo After startup, check: http://localhost:8080/api/health
echo Press Ctrl+C to stop.
echo.

python -m uvicorn webapp.backend.main:app --host 0.0.0.0 --port 8080 --reload

pause
