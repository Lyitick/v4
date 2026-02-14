#!/usr/bin/env bash
# Development startup script for Mini App
# Starts FastAPI backend and Vite dev server

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Starting Mini App development servers ==="

# Start backend
echo "[1/2] Starting FastAPI backend on :8000 ..."
cd "$PROJECT_ROOT"
PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/finance_bot" \
  uvicorn webapp.backend.main:app --reload --host 0.0.0.0 --port 8080 &
BACKEND_PID=$!

# Start frontend
echo "[2/2] Starting Vite dev server on :3000 ..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  Backend:  http://localhost:8080/api/health"
echo "  Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
