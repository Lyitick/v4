"""Recurring payments REST API endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from Bot.database.get_db import get_db

from webapp.backend.dependencies import get_current_user

router = APIRouter()


# ── Schemas ───────────────────────────────────────────

class RecurringPaymentOut(BaseModel):
    id: int
    title: str
    amount: float
    category: Optional[str] = None
    frequency: str
    day_of_month: int
    next_due_date: Optional[str] = None


class CreateRecurringRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0)
    category: Optional[str] = None
    frequency: str = "monthly"
    day_of_month: int = Field(1, ge=1, le=28)


# ── Endpoints ─────────────────────────────────────────

@router.get("/", response_model=list[RecurringPaymentOut])
async def list_recurring(user: dict = Depends(get_current_user)):
    """List active recurring payments."""
    db = get_db()
    items = db.list_recurring_payments(user["id"])
    return [RecurringPaymentOut(**item) for item in items]


@router.post("/", response_model=RecurringPaymentOut)
async def create_recurring(
    body: CreateRecurringRequest,
    user: dict = Depends(get_current_user),
):
    """Create a new recurring payment."""
    db = get_db()
    new_id = db.add_recurring_payment(
        user_id=user["id"],
        title=body.title,
        amount=body.amount,
        category=body.category,
        frequency=body.frequency,
        day_of_month=body.day_of_month,
    )
    items = db.list_recurring_payments(user["id"])
    item = next((i for i in items if i["id"] == new_id), items[-1] if items else {})
    return RecurringPaymentOut(**item)


@router.delete("/{payment_id}")
async def delete_recurring(
    payment_id: int,
    user: dict = Depends(get_current_user),
):
    """Deactivate a recurring payment."""
    db = get_db()
    db.deactivate_recurring_payment(user["id"], payment_id)
    return {"ok": True}
