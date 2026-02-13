"""Household payments REST API endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from Bot.database.get_db import get_db
from Bot.config.settings import get_settings
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

class HouseholdItemOut(BaseModel):
    code: str
    text: str
    amount: int
    position: int


class PaymentStatusOut(BaseModel):
    code: str
    text: str
    amount: int
    is_paid: bool


class AnswerRequest(BaseModel):
    question_code: str
    answer: str = Field(..., pattern="^(yes|no)$")


# ── Endpoints ─────────────────────────────────────────

@router.get("/items", response_model=list[HouseholdItemOut])
async def list_household_items(user: dict = Depends(get_current_user)):
    """List active household payment items."""
    db = get_db()
    user_id = user["id"]
    items = db.list_active_household_items(user_id)
    return [
        HouseholdItemOut(
            code=i["code"],
            text=i["text"],
            amount=i["amount"],
            position=i["position"],
        )
        for i in items
    ]


@router.get("/status", response_model=list[PaymentStatusOut])
async def get_payment_status(
    month: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Get payment status for current (or specified) month."""
    db = get_db()
    user_id = user["id"]

    if not month:
        now = now_for_user(db, user_id, DEFAULT_TZ)
        month = current_month_str(now)

    # Ensure month is initialized
    await db.init_household_questions_for_month(user_id, month)
    status_map = await db.get_household_payment_status_map(user_id, month)
    items = db.list_active_household_items(user_id)

    result = []
    for item in items:
        code = item["code"]
        result.append(
            PaymentStatusOut(
                code=code,
                text=item["text"],
                amount=item["amount"],
                is_paid=bool(status_map.get(code, 0)),
            )
        )
    return result


@router.post("/answer")
async def answer_question(
    body: AnswerRequest,
    month: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Mark a household payment as paid or unpaid."""
    db = get_db()
    user_id = user["id"]

    if not month:
        now = now_for_user(db, user_id, DEFAULT_TZ)
        month = current_month_str(now)

    # Get item amount for savings deduction
    item = db.get_household_item_by_code(user_id, body.question_code)
    amount = item["amount"] if item else None
    debit_category = db.get_household_debit_category(user_id)

    changed = db.apply_household_payment_answer(
        user_id=user_id,
        month=month,
        question_code=body.question_code,
        amount=amount,
        answer=body.answer,
        debit_category=debit_category,
    )

    return {"ok": True, "changed": changed, "month": month}


@router.post("/reset")
async def reset_month(
    month: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Reset all payments for a month."""
    db = get_db()
    user_id = user["id"]

    if not month:
        now = now_for_user(db, user_id, DEFAULT_TZ)
        month = current_month_str(now)

    await db.reset_household_questions_for_month(user_id, month)
    return {"ok": True, "month": month}
