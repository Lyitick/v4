"""FastAPI entry point for Telegram Mini App backend."""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Allow importing Bot.database from finance_bot
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FINANCE_BOT_ROOT = PROJECT_ROOT / "finance_bot"
for p in (str(PROJECT_ROOT), str(FINANCE_BOT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from Bot.database.get_db import get_db
from webapp.backend.routers import wishlist

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
app.include_router(wishlist.router, prefix="/api/wishlist", tags=["wishlist"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
