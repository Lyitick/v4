"""Wishlist REST API endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from Bot.config.settings import get_settings
from Bot.database.get_db import get_db
from Bot.utils.time import now_for_user

from webapp.backend.dependencies import get_current_user

router = APIRouter()

_settings = get_settings()
DEFAULT_TZ = (
    _settings.timezone.key
    if hasattr(_settings.timezone, "key")
    else str(_settings.timezone)
)


def _clock(db, user_id: int):
    return now_for_user(db, user_id, DEFAULT_TZ)


# ── Pydantic schemas ──────────────────────────────────────────────

class WishCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    price: float = Field(..., gt=0)
    url: Optional[str] = None
    category: str = Field(..., min_length=1)


class WishDefer(BaseModel):
    deferred_until: str = Field(..., description="ISO datetime string")


class CategoryOut(BaseModel):
    id: int
    title: str
    position: int
    purchased_mode: Optional[str] = None
    purchased_days: Optional[int] = None


class WishOut(BaseModel):
    id: int
    name: str
    price: float
    url: Optional[str] = None
    category: str
    is_purchased: bool
    saved_amount: float
    purchased_at: Optional[str] = None
    deferred_until: Optional[str] = None
    deleted_at: Optional[str] = None


class PurchaseOut(BaseModel):
    id: int
    wish_name: str
    price: float
    category: str
    purchased_at: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(user: dict = Depends(get_current_user)):
    """List active wishlist categories."""
    db = get_db()
    user_id = user["id"]
    categories = db.list_active_wishlist_categories(user_id)
    return [
        CategoryOut(
            id=c["id"],
            title=c["title"],
            position=c["position"],
            purchased_mode=c.get("purchased_mode"),
            purchased_days=c.get("purchased_days"),
        )
        for c in categories
    ]


@router.get("/wishes", response_model=list[WishOut])
async def list_wishes(
    category: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """List wishes for user, optionally filtered by category."""
    db = get_db()
    user_id = user["id"]

    # Cleanup expired soft-deleted wishes (older than 24h)
    db.cleanup_expired_deleted_wishes(user_id, _clock(db, user_id))

    all_wishes = db.get_wishes_by_user(user_id)

    result = []
    for w in all_wishes:
        if category and str(w.get("category", "")).strip().lower() != category.strip().lower():
            continue
        result.append(
            WishOut(
                id=w["id"],
                name=w["name"],
                price=w["price"],
                url=w.get("url"),
                category=w.get("category", ""),
                is_purchased=bool(w.get("is_purchased")),
                saved_amount=float(w.get("saved_amount", 0)),
                purchased_at=w.get("purchased_at"),
                deferred_until=w.get("deferred_until"),
                deleted_at=w.get("deleted_at"),
            )
        )
    return result


@router.post("/wishes", response_model=WishOut)
async def create_wish(body: WishCreate, user: dict = Depends(get_current_user)):
    """Add a new wish."""
    db = get_db()
    user_id = user["id"]

    wish_id = db.add_wish(
        user_id=user_id,
        name=body.name,
        price=body.price,
        url=body.url,
        category=body.category,
    )
    if not wish_id:
        raise HTTPException(status_code=500, detail="Failed to add wish")

    return WishOut(
        id=wish_id,
        name=body.name,
        price=body.price,
        url=body.url,
        category=body.category,
        is_purchased=False,
        saved_amount=0,
    )


@router.post("/wishes/{wish_id}/purchase")
async def purchase_wish(wish_id: int, user: dict = Depends(get_current_user)):
    """Mark a wish as purchased."""
    db = get_db()
    user_id = user["id"]

    debit_category = db.get_wishlist_debit_category(user_id)
    purchased_at = _clock(db, user_id)
    result = db.purchase_wish(user_id, wish_id, debit_category, purchased_at=purchased_at)

    status = result.get("status")
    if status == "not_found":
        raise HTTPException(status_code=404, detail="Wish not found")
    if status == "already":
        return {"ok": False, "message": "Already purchased"}
    if status == "insufficient":
        return {
            "ok": False,
            "message": "Insufficient savings",
            "available": result.get("available", 0),
        }
    if status == "error":
        raise HTTPException(status_code=500, detail="Database error")

    return {
        "ok": True,
        "status": status,
        "price": result.get("price"),
        "wish_name": result.get("wish_name"),
    }


@router.post("/wishes/{wish_id}/defer")
async def defer_wish(
    wish_id: int,
    body: WishDefer,
    user: dict = Depends(get_current_user),
):
    """Defer a wish until a specific date."""
    db = get_db()
    user_id = user["id"]

    wish = db.get_wish(wish_id)
    if not wish or wish.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Wish not found")

    db.set_wishlist_item_deferred_until(user_id, wish_id, body.deferred_until)
    return {"ok": True, "deferred_until": body.deferred_until}


@router.delete("/wishes/{wish_id}")
async def delete_wish(wish_id: int, user: dict = Depends(get_current_user)):
    """Soft-delete a wish (recoverable for 24 hours)."""
    db = get_db()
    user_id = user["id"]

    wish = db.get_wish(wish_id)
    if not wish or wish.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Wish not found")
    if wish.get("deleted_at"):
        raise HTTPException(status_code=400, detail="Already deleted")

    db.mark_wish_deleted(wish_id, deleted_at=_clock(db, user_id))
    return {"ok": True}


@router.post("/wishes/{wish_id}/restore")
async def restore_wish(wish_id: int, user: dict = Depends(get_current_user)):
    """Restore a soft-deleted wish."""
    db = get_db()
    user_id = user["id"]

    wish = db.get_wish(wish_id)
    if not wish or wish.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Wish not found")
    if not wish.get("deleted_at"):
        raise HTTPException(status_code=400, detail="Wish is not deleted")

    db.restore_wish(wish_id)
    return {"ok": True}


@router.get("/purchases", response_model=list[PurchaseOut])
async def list_purchases(user: dict = Depends(get_current_user)):
    """List recent purchases."""
    db = get_db()
    user_id = user["id"]
    purchases = db.get_purchases_by_user(user_id)
    return [
        PurchaseOut(
            id=p["id"],
            wish_name=p["wish_name"],
            price=p["price"],
            category=p.get("category", ""),
            purchased_at=p.get("purchased_at"),
        )
        for p in purchases
    ]
