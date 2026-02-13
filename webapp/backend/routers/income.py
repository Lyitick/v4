"""Income distribution REST API endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from Bot.database.get_db import get_db
from Bot.config.settings import get_settings
from Bot.utils.time import now_for_user

from webapp.backend.dependencies import get_current_user

router = APIRouter()

_settings = get_settings()
DEFAULT_TZ = (
    _settings.timezone.key
    if hasattr(_settings.timezone, "key")
    else str(_settings.timezone)
)


# ── Schemas ───────────────────────────────────────────

class IncomeCategoryOut(BaseModel):
    id: int
    code: str
    title: str
    percent: int
    position: int


class AllocationItem(BaseModel):
    code: str
    title: str
    percent: int
    amount: float


class CalculateRequest(BaseModel):
    amount: float = Field(..., gt=0)


class CalculateResponse(BaseModel):
    amount: float
    allocations: list[AllocationItem]
    total_percent: int


class ConfirmRequest(BaseModel):
    amount: float = Field(..., gt=0)


# ── Endpoints ─────────────────────────────────────────

@router.get("/categories", response_model=list[IncomeCategoryOut])
async def list_income_categories(user: dict = Depends(get_current_user)):
    """List active income categories with percents."""
    db = get_db()
    user_id = user["id"]
    db.ensure_user_settings(user_id)
    categories = db.list_active_income_categories(user_id)
    return [
        IncomeCategoryOut(
            id=c["id"],
            code=c["code"],
            title=c["title"],
            percent=c["percent"],
            position=c["position"],
        )
        for c in categories
    ]


@router.post("/calculate", response_model=CalculateResponse)
async def calculate_distribution(
    body: CalculateRequest,
    user: dict = Depends(get_current_user),
):
    """Calculate income distribution without saving."""
    db = get_db()
    user_id = user["id"]
    categories = db.list_active_income_categories(user_id)

    allocations = []
    total_percent = 0
    for cat in categories:
        pct = int(cat.get("percent", 0))
        total_percent += pct
        allocated = body.amount * pct / 100
        allocations.append(
            AllocationItem(
                code=cat["code"],
                title=cat["title"],
                percent=pct,
                amount=round(allocated, 2),
            )
        )

    return CalculateResponse(
        amount=body.amount,
        allocations=allocations,
        total_percent=total_percent,
    )


@router.post("/confirm")
async def confirm_distribution(
    body: ConfirmRequest,
    user: dict = Depends(get_current_user),
):
    """Confirm income distribution — add amounts to savings."""
    db = get_db()
    user_id = user["id"]
    categories = db.list_active_income_categories(user_id)

    applied = []
    for cat in categories:
        pct = int(cat.get("percent", 0))
        if pct <= 0:
            continue
        allocated = round(body.amount * pct / 100, 2)
        db.update_saving(user_id, cat["code"], allocated)
        applied.append({"code": cat["code"], "title": cat["title"], "amount": allocated})

    return {"ok": True, "applied": applied}
