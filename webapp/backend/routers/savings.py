"""Savings REST API endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from Bot.database.get_db import get_db
from Bot.config.settings import get_settings

from webapp.backend.dependencies import get_current_user

router = APIRouter()


# ── Schemas ───────────────────────────────────────────

class SavingOut(BaseModel):
    category: str
    current: float
    goal: float
    purpose: str


class SetGoalRequest(BaseModel):
    category: str
    goal: float = Field(..., ge=0)
    purpose: str = ""


# ── Endpoints ─────────────────────────────────────────

@router.get("/", response_model=list[SavingOut])
async def list_savings(user: dict = Depends(get_current_user)):
    """Get all savings for user."""
    db = get_db()
    user_id = user["id"]
    savings = db.get_user_savings(user_id)
    categories_map = db.get_income_categories_map(user_id)

    result = []
    for category, data in savings.items():
        display_name = categories_map.get(category, category)
        result.append(
            SavingOut(
                category=display_name,
                current=data.get("current", 0),
                goal=data.get("goal", 0),
                purpose=data.get("purpose", ""),
            )
        )
    return result


@router.post("/goal")
async def set_goal(body: SetGoalRequest, user: dict = Depends(get_current_user)):
    """Set savings goal for a category."""
    db = get_db()
    user_id = user["id"]
    db.set_goal(user_id, body.category, body.goal, body.purpose)
    return {"ok": True}


@router.post("/reset-goals")
async def reset_goals(user: dict = Depends(get_current_user)):
    """Reset all goals."""
    db = get_db()
    user_id = user["id"]
    db.reset_goals(user_id)
    return {"ok": True}
