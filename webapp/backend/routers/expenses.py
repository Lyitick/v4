"""Expense tracking REST API endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from Bot.database.get_db import get_db

from webapp.backend.dependencies import get_current_user

router = APIRouter()


# ── Schemas ───────────────────────────────────────────

class ExpenseOut(BaseModel):
    id: int
    amount: float
    category: str
    note: str = ""
    created_at: str


class CreateExpenseRequest(BaseModel):
    amount: float = Field(..., gt=0)
    category: str = Field(..., min_length=1)
    note: str = ""


class ExpenseCategoryOut(BaseModel):
    id: int
    code: str
    title: str


# ── Endpoints ─────────────────────────────────────────

@router.get("/categories", response_model=list[ExpenseCategoryOut])
async def list_categories(user: dict = Depends(get_current_user)):
    """List active expense categories."""
    db = get_db()
    db.ensure_expense_categories_seeded(user["id"])
    cats = db.list_active_expense_categories(user["id"])
    return [ExpenseCategoryOut(id=c["id"], code=c["code"], title=c["title"]) for c in cats]


@router.get("/", response_model=list[ExpenseOut])
async def list_expenses(
    year: int = Query(default=None),
    month: int = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """List expenses for a given month."""
    if year is None or month is None:
        now = datetime.utcnow()
        year = year or now.year
        month = month or now.month
    db = get_db()
    items = db.list_expenses(user["id"], year, month)
    return [ExpenseOut(**item) for item in items]


@router.post("/", response_model=ExpenseOut)
async def create_expense(
    body: CreateExpenseRequest,
    user: dict = Depends(get_current_user),
):
    """Create a new expense entry."""
    db = get_db()
    new_id = db.add_expense(
        user_id=user["id"],
        amount=body.amount,
        category=body.category,
        note=body.note,
    )
    return ExpenseOut(
        id=new_id,
        amount=body.amount,
        category=body.category,
        note=body.note,
        created_at=datetime.utcnow().isoformat(),
    )


@router.delete("/{expense_id}")
async def delete_expense(
    expense_id: int,
    user: dict = Depends(get_current_user),
):
    """Delete an expense entry."""
    db = get_db()
    deleted = db.delete_expense(user["id"], expense_id)
    return {"ok": deleted}
