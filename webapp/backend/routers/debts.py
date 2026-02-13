"""Debt tracking REST API endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from Bot.database.get_db import get_db

from webapp.backend.dependencies import get_current_user

router = APIRouter()


# ── Schemas ───────────────────────────────────────────

class DebtOut(BaseModel):
    id: int
    person: str
    amount: float
    direction: str
    description: str = ""
    is_settled: bool = False
    settled_at: str | None = None
    created_at: str


class CreateDebtRequest(BaseModel):
    person: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    direction: str = Field(..., pattern="^(owe|owed)$")
    description: str = ""


class DebtSummaryOut(BaseModel):
    owed_to_me: float
    i_owe: float
    net_balance: float


# ── Endpoints ─────────────────────────────────────────

@router.get("/", response_model=list[DebtOut])
async def list_debts(
    settled: bool = False,
    user: dict = Depends(get_current_user),
):
    """List debts (active or settled)."""
    db = get_db()
    items = db.list_debts(user["id"], settled=settled)
    return [DebtOut(**item) for item in items]


@router.post("/", response_model=DebtOut)
async def create_debt(
    body: CreateDebtRequest,
    user: dict = Depends(get_current_user),
):
    """Create a new debt entry."""
    db = get_db()
    new_id = db.add_debt(
        user_id=user["id"],
        person=body.person,
        amount=body.amount,
        direction=body.direction,
        description=body.description,
    )
    return DebtOut(
        id=new_id,
        person=body.person,
        amount=body.amount,
        direction=body.direction,
        description=body.description,
        is_settled=False,
        settled_at=None,
        created_at=datetime.utcnow().isoformat(),
    )


@router.post("/{debt_id}/settle")
async def settle_debt(
    debt_id: int,
    user: dict = Depends(get_current_user),
):
    """Mark a debt as settled."""
    db = get_db()
    ok = db.settle_debt(user["id"], debt_id)
    return {"ok": ok}


@router.delete("/{debt_id}")
async def delete_debt(
    debt_id: int,
    user: dict = Depends(get_current_user),
):
    """Delete a debt entry."""
    db = get_db()
    ok = db.delete_debt(user["id"], debt_id)
    return {"ok": ok}


@router.get("/summary", response_model=DebtSummaryOut)
async def get_debt_summary(
    user: dict = Depends(get_current_user),
):
    """Get debt summary (total owed to me, I owe, net balance)."""
    db = get_db()
    return db.get_debt_summary(user["id"])
