"""User settings REST API endpoints."""
from __future__ import annotations

import time as _time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from Bot.config.settings import get_settings
from Bot.database.get_db import get_db
from Bot.utils.time import now_for_user
from Bot.utils.datetime_utils import current_month_str

from webapp.backend.dependencies import get_current_user

router = APIRouter()

_settings = get_settings()
DEFAULT_TZ = (
    _settings.timezone.key
    if hasattr(_settings.timezone, "key")
    else str(_settings.timezone)
)


# ── Schemas ───────────────────────────────────────────

class UserSettingsOut(BaseModel):
    timezone: str
    purchased_keep_days: int
    byt_reminders_enabled: bool
    byt_defer_enabled: bool
    byt_defer_max_days: int
    household_debit_category: Optional[str] = None
    wishlist_debit_category_id: Optional[str] = None
    byt_wishlist_category_id: Optional[int] = None


class UpdateTimezoneRequest(BaseModel):
    timezone: str = Field(..., min_length=1)


class UpdateKeepDaysRequest(BaseModel):
    days: int = Field(..., ge=1, le=365)


# ── Income schemas ────────────────────────────────────

class IncomeCategoryOut(BaseModel):
    id: int
    code: str
    title: str
    percent: int
    position: int


class CreateIncomeCategoryRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class UpdatePercentRequest(BaseModel):
    percent: int = Field(..., ge=0, le=100)


# ── Wishlist schemas ──────────────────────────────────

class WishlistCategoryOut(BaseModel):
    id: int
    title: str
    position: int
    purchased_mode: Optional[str] = None
    purchased_days: Optional[int] = None


class CreateWishlistCategoryRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class UpdatePurchasedModeRequest(BaseModel):
    mode: str = Field(..., pattern=r"^(always|days)$")


class UpdatePurchasedDaysRequest(BaseModel):
    days: int = Field(..., ge=1, le=365)


class SetDebitCategoryRequest(BaseModel):
    category_id: Optional[str] = None


class SetBytCategoryRequest(BaseModel):
    category_id: Optional[int] = None


# ── BYT schemas ───────────────────────────────────────

class BytReminderCategoryOut(BaseModel):
    id: int
    title: str
    position: int
    enabled: int


class BytReminderTimeOut(BaseModel):
    time_hhmm: str


class AddReminderTimeRequest(BaseModel):
    time_hhmm: str = Field(..., pattern=r"^\d{2}:\d{2}$")


class UpdateMaxDeferDaysRequest(BaseModel):
    days: int = Field(..., ge=1, le=365)


# ── Household schemas ─────────────────────────────────

class HouseholdItemOut(BaseModel):
    code: str
    text: str
    amount: int
    position: int


class AddHouseholdItemRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=200)
    amount: int = Field(..., gt=0)


class SetHouseholdDebitRequest(BaseModel):
    category: Optional[str] = None


# ── General settings endpoints ────────────────────────

@router.get("/", response_model=UserSettingsOut)
async def get_settings_endpoint(user: dict = Depends(get_current_user)):
    """Get user settings."""
    db = get_db()
    user_id = user["id"]
    s = db.get_user_settings(user_id)
    byt_cat_id = s.get("byt_wishlist_category_id")
    return UserSettingsOut(
        timezone=s.get("timezone", "Europe/Moscow"),
        purchased_keep_days=int(s.get("purchased_keep_days", 30)),
        byt_reminders_enabled=bool(s.get("byt_reminders_enabled", 1)),
        byt_defer_enabled=bool(s.get("byt_defer_enabled", 1)),
        byt_defer_max_days=int(s.get("byt_defer_max_days", 365)),
        household_debit_category=s.get("household_debit_category"),
        wishlist_debit_category_id=s.get("wishlist_debit_category_id"),
        byt_wishlist_category_id=int(byt_cat_id) if byt_cat_id is not None else None,
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


# ── Income category endpoints ─────────────────────────

@router.get("/income-categories", response_model=list[IncomeCategoryOut])
async def list_income_categories(user: dict = Depends(get_current_user)):
    """List active income categories."""
    db = get_db()
    categories = db.list_active_income_categories(user["id"])
    return [
        IncomeCategoryOut(
            id=c["id"],
            code=c["code"],
            title=c["title"],
            percent=int(c.get("percent", 0)),
            position=int(c.get("position", 0)),
        )
        for c in categories
    ]


@router.post("/income-categories")
async def add_income_category(
    body: CreateIncomeCategoryRequest,
    user: dict = Depends(get_current_user),
):
    """Add a new income category."""
    db = get_db()
    cat_id = db.create_income_category(user["id"], body.title)
    if not cat_id:
        raise HTTPException(status_code=500, detail="Failed to create category")
    return {"ok": True, "id": cat_id}


@router.delete("/income-categories/{category_id}")
async def remove_income_category(
    category_id: int,
    user: dict = Depends(get_current_user),
):
    """Remove (deactivate) an income category."""
    db = get_db()
    db.deactivate_income_category(user["id"], category_id)
    return {"ok": True}


@router.post("/income-categories/{category_id}/percent")
async def update_income_percent(
    category_id: int,
    body: UpdatePercentRequest,
    user: dict = Depends(get_current_user),
):
    """Update percent for an income category."""
    db = get_db()
    db.update_income_category_percent(user["id"], category_id, body.percent)
    return {"ok": True}


# ── Wishlist category endpoints ───────────────────────

@router.get("/wishlist-categories", response_model=list[WishlistCategoryOut])
async def list_wishlist_categories(user: dict = Depends(get_current_user)):
    """List active wishlist categories."""
    db = get_db()
    categories = db.list_active_wishlist_categories(user["id"])
    return [
        WishlistCategoryOut(
            id=c["id"],
            title=c["title"],
            position=int(c.get("position", 0)),
            purchased_mode=c.get("purchased_mode"),
            purchased_days=c.get("purchased_days"),
        )
        for c in categories
    ]


@router.post("/wishlist-categories")
async def add_wishlist_category(
    body: CreateWishlistCategoryRequest,
    user: dict = Depends(get_current_user),
):
    """Add a new wishlist category."""
    db = get_db()
    cat_id = db.create_wishlist_category(user["id"], body.title)
    if not cat_id:
        raise HTTPException(status_code=500, detail="Failed to create category")
    return {"ok": True, "id": cat_id}


@router.delete("/wishlist-categories/{category_id}")
async def remove_wishlist_category(
    category_id: int,
    user: dict = Depends(get_current_user),
):
    """Remove (deactivate) a wishlist category."""
    db = get_db()
    db.deactivate_wishlist_category(user["id"], category_id)
    return {"ok": True}


@router.post("/wishlist-categories/{category_id}/purchased-mode")
async def update_purchased_mode(
    category_id: int,
    body: UpdatePurchasedModeRequest,
    user: dict = Depends(get_current_user),
):
    """Update purchased display mode for a wishlist category."""
    db = get_db()
    db.update_wishlist_category_purchased_mode(user["id"], category_id, body.mode)
    return {"ok": True}


@router.post("/wishlist-categories/{category_id}/purchased-days")
async def update_purchased_days(
    category_id: int,
    body: UpdatePurchasedDaysRequest,
    user: dict = Depends(get_current_user),
):
    """Update purchased days retention for a wishlist category."""
    db = get_db()
    db.update_wishlist_category_purchased_days(user["id"], category_id, body.days)
    return {"ok": True}


@router.post("/wishlist-debit-category")
async def set_wishlist_debit_category(
    body: SetDebitCategoryRequest,
    user: dict = Depends(get_current_user),
):
    """Set wishlist debit category."""
    db = get_db()
    db.set_wishlist_debit_category(user["id"], body.category_id)
    return {"ok": True}


@router.post("/byt-wishlist-category")
async def set_byt_wishlist_category(
    body: SetBytCategoryRequest,
    user: dict = Depends(get_current_user),
):
    """Set BYT wishlist category."""
    db = get_db()
    db.set_byt_wishlist_category_id(user["id"], body.category_id)
    return {"ok": True}


# ── BYT reminder endpoints ───────────────────────────

@router.post("/byt-defer/toggle")
async def toggle_byt_defer(user: dict = Depends(get_current_user)):
    """Toggle BYT defer on/off."""
    db = get_db()
    user_id = user["id"]
    s = db.get_user_settings(user_id)
    current = bool(s.get("byt_defer_enabled", 1))
    db.set_byt_defer_enabled(user_id, not current)
    return {"ok": True, "enabled": not current}


@router.post("/byt-defer/max-days")
async def update_max_defer_days(
    body: UpdateMaxDeferDaysRequest,
    user: dict = Depends(get_current_user),
):
    """Update max defer days setting."""
    db = get_db()
    db.set_byt_defer_max_days(user["id"], body.days)
    return {"ok": True, "days": body.days}


@router.get("/byt-reminder-categories", response_model=list[BytReminderCategoryOut])
async def list_byt_reminder_categories(user: dict = Depends(get_current_user)):
    """List BYT reminder categories with toggle status."""
    db = get_db()
    categories = db.list_byt_reminder_categories(user["id"])
    return [
        BytReminderCategoryOut(
            id=c["id"],
            title=c["title"],
            position=int(c.get("position", 0)),
            enabled=int(c.get("enabled", 0)),
        )
        for c in categories
    ]


@router.post("/byt-reminder-categories/{category_id}/toggle")
async def toggle_byt_reminder_category(
    category_id: int,
    user: dict = Depends(get_current_user),
):
    """Toggle a BYT reminder category on/off."""
    db = get_db()
    new_state = db.toggle_byt_reminder_category(user["id"], category_id)
    return {"ok": True, "enabled": new_state}


@router.get("/byt-reminder-times/{category_id}", response_model=list[BytReminderTimeOut])
async def list_byt_reminder_times(
    category_id: int,
    user: dict = Depends(get_current_user),
):
    """List reminder times for a BYT category."""
    db = get_db()
    times = db.list_byt_reminder_times(user["id"], category_id)
    return [BytReminderTimeOut(time_hhmm=t.get("time_hhmm", "")) for t in times]


@router.post("/byt-reminder-times/{category_id}")
async def add_byt_reminder_time(
    category_id: int,
    body: AddReminderTimeRequest,
    user: dict = Depends(get_current_user),
):
    """Add a reminder time for a BYT category."""
    db = get_db()
    db.add_byt_reminder_time(user["id"], category_id, body.time_hhmm)
    return {"ok": True}


@router.delete("/byt-reminder-times/{category_id}/{time_hhmm}")
async def remove_byt_reminder_time(
    category_id: int,
    time_hhmm: str,
    user: dict = Depends(get_current_user),
):
    """Remove a reminder time for a BYT category."""
    db = get_db()
    db.remove_byt_reminder_time(user["id"], category_id, time_hhmm)
    return {"ok": True}


# ── Household payment endpoints ───────────────────────

@router.get("/household-items", response_model=list[HouseholdItemOut])
async def list_household_items(user: dict = Depends(get_current_user)):
    """List active household payment items."""
    db = get_db()
    items = db.list_active_household_items(user["id"])
    return [
        HouseholdItemOut(
            code=i.get("code", ""),
            text=i.get("text", ""),
            amount=int(i.get("amount", 0)),
            position=int(i.get("position", 0)),
        )
        for i in items
    ]


@router.post("/household-items")
async def add_household_item(
    body: AddHouseholdItemRequest,
    user: dict = Depends(get_current_user),
):
    """Add a new household payment item."""
    db = get_db()
    user_id = user["id"]
    code = f"custom_{_time.time_ns()}"
    position = db.get_next_household_position(user_id)
    db.add_household_payment_item(user_id, code, body.text, body.amount, position)
    return {"ok": True, "code": code}


@router.delete("/household-items/{code}")
async def remove_household_item(
    code: str,
    user: dict = Depends(get_current_user),
):
    """Remove (deactivate) a household payment item."""
    db = get_db()
    db.deactivate_household_payment_item(user["id"], code)
    return {"ok": True}


@router.post("/household-debit-category")
async def set_household_debit_category(
    body: SetHouseholdDebitRequest,
    user: dict = Depends(get_current_user),
):
    """Set household debit category."""
    db = get_db()
    db.set_household_debit_category(user["id"], body.category)
    return {"ok": True}


@router.post("/household-reset")
async def reset_household_payments(user: dict = Depends(get_current_user)):
    """Reset household payment states for current month."""
    db = get_db()
    user_id = user["id"]
    now = now_for_user(db, user_id, DEFAULT_TZ)
    month = current_month_str(now)
    await db.reset_household_questions_for_month(user_id, month)
    return {"ok": True}
