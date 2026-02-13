"""FastAPI entry point for Telegram Mini App backend."""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Allow importing Bot.database from finance_bot
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FINANCE_BOT_ROOT = PROJECT_ROOT / "finance_bot"
for p in (str(PROJECT_ROOT), str(FINANCE_BOT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from Bot.database.get_db import get_db
from webapp.backend.routers import debts, expenses, export, household, income, recurring, reports, savings, settings, wishlist

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown."""
    db = get_db()
    logger.info("Mini App backend started, DB ready")
    yield
    db.close()
    logger.info("Mini App backend stopped")


app = FastAPI(title="Finance Mini App", lifespan=lifespan)

# CORS — allow Telegram WebApp origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(expenses.router, prefix="/api/expenses", tags=["expenses"])
app.include_router(wishlist.router, prefix="/api/wishlist", tags=["wishlist"])
app.include_router(income.router, prefix="/api/income", tags=["income"])
app.include_router(household.router, prefix="/api/household", tags=["household"])
app.include_router(savings.router, prefix="/api/savings", tags=["savings"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(recurring.router, prefix="/api/recurring", tags=["recurring"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(debts.router, prefix="/api/debts", tags=["debts"])
app.include_router(export.router, prefix="/api/export", tags=["export"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── Serve frontend static files in production ─────────
FRONTEND_DIST = PROJECT_ROOT / "webapp" / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(request: Request, path: str):
        """Serve frontend SPA — fallback all non-API routes to index.html."""
        file_path = FRONTEND_DIST / path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")
