"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from Bot.config.settings import get_settings
from webapp.backend.auth import validate_init_data

_settings = get_settings()
_BOT_TOKEN = (_settings.bot_token or "").strip()


def get_current_user(request: Request) -> dict[str, Any]:
    """Extract and validate Telegram user from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("tma "):
        raise HTTPException(status_code=401, detail="Missing authorization")
    init_data = auth[4:]
    try:
        user = validate_init_data(init_data, _BOT_TOKEN)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return user
