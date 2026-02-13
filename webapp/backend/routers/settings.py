"""User settings REST API endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from Bot.database.get_db import get_db

from webapp.backend.dependencies import get_current_user

router = APIRouter()


# ── Schemas ───────────────────────────────────────────

class UserSettingsOut(BaseModel):
    timezone: str
    purchased_keep_days: int
    byt_reminders_enabled: bool
    byt_defer_enabled: bool
    byt_defer_max_days: int
    household_debit_category: Optional[str] = None
    wishlist_debit_category_id: Optional[str] = None


class UpdateTimezoneRequest(BaseModel):
    timezone: str = Field(..., min_length=1)


class UpdateKeepDaysRequest(BaseModel):
    days: int = Field(..., ge=1, le=365)


# ── Endpoints ─────────────────────────────────────────

@router.get("/", response_model=UserSettingsOut)
async def get_settings(user: dict = Depends(get_current_user)):
    """Get user settings."""
    db = get_db()
    user_id = user["id"]
    s = db.get_user_settings(user_id)
    return UserSettingsOut(
        timezone=s.get("timezone", "Europe/Moscow"),
        purchased_keep_days=int(s.get("purchased_keep_days", 30)),
        byt_reminders_enabled=bool(s.get("byt_reminders_enabled", 1)),
        byt_defer_enabled=bool(s.get("byt_defer_enabled", 1)),
        byt_defer_max_days=int(s.get("byt_defer_max_days", 365)),
        household_debit_category=s.get("household_debit_category"),
        wishlist_debit_category_id=s.get("wishlist_debit_category_id"),
    )


@router.post("/timezone")
async def update_timezone(
    body: UpdateTimezoneRequest,
    user: dict = Depends(get_current_user),
):
    """Update user timezone."""
    db = get_db()
    user_id = user["id"]
    db.ensure_user_settings(user_id)
    cursor = db.connection.cursor()
    cursor.execute(
        f'UPDATE "{db.tables.user_settings}" SET timezone = ? WHERE user_id = ?',
        (body.timezone, user_id),
    )
    db.connection.commit()
    return {"ok": True, "timezone": body.timezone}


@router.post("/keep-days")
async def update_keep_days(
    body: UpdateKeepDaysRequest,
    user: dict = Depends(get_current_user),
):
    """Update purchased keep days."""
    db = get_db()
    user_id = user["id"]
    db.update_purchased_keep_days(user_id, body.days)
    return {"ok": True, "days": body.days}


@router.post("/byt-reminders/toggle")
async def toggle_byt_reminders(user: dict = Depends(get_current_user)):
    """Toggle BYT reminders on/off."""
    db = get_db()
    user_id = user["id"]
    s = db.get_user_settings(user_id)
    current = bool(s.get("byt_reminders_enabled", 1))
    db.set_byt_reminders_enabled(user_id, not current)
    return {"ok": True, "enabled": not current}
