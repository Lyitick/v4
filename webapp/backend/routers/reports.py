"""Monthly reports REST API endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from Bot.database.get_db import get_db

from webapp.backend.dependencies import get_current_user

router = APIRouter()


# ── Schemas ───────────────────────────────────────────

class CategoryAmount(BaseModel):
    category: str
    amount: float


class MonthlyReportOut(BaseModel):
    month: str
    total_income: float
    total_expense: float
    balance: float
    income_by_category: list[CategoryAmount]
    expense_by_category: list[CategoryAmount]
    household_paid: float
    household_total: float


class ReportDayRequest(BaseModel):
    day: int = Field(..., ge=1, le=28)


# ── Endpoints ─────────────────────────────────────────

@router.get("/monthly", response_model=MonthlyReportOut)
async def get_monthly_report(
    year: int = Query(default=None),
    month: int = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """Get aggregated monthly report."""
    if year is None or month is None:
        now = datetime.utcnow()
        year = year or now.year
        month = month or now.month

    db = get_db()
    data = db.get_monthly_report_data(user["id"], year, month)
    return MonthlyReportOut(
        month=data["month"],
        total_income=data["total_income"],
        total_expense=data["total_expense"],
        balance=round(data["total_income"] - data["total_expense"], 2),
        income_by_category=[CategoryAmount(**c) for c in data["income_by_category"]],
        expense_by_category=[CategoryAmount(**c) for c in data["expense_by_category"]],
        household_paid=data["household_paid"],
        household_total=data["household_total"],
    )


@router.get("/report-day")
async def get_report_day(user: dict = Depends(get_current_user)):
    """Get the configured report day."""
    db = get_db()
    day = db.get_report_day(user["id"])
    return {"day": day}


@router.post("/report-day")
async def set_report_day(
    body: ReportDayRequest,
    user: dict = Depends(get_current_user),
):
    """Set the day of month for auto-reports."""
    db = get_db()
    db.set_report_day(user["id"], body.day)
    return {"ok": True, "day": body.day}
