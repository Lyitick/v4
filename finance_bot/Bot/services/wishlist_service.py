"""Wishlist service layer."""
from __future__ import annotations

from typing import Any, Callable

from Bot.services.types import ServiceError, WishlistPurchaseResult


def list_wishlist_categories(db, user_id: int) -> list[dict]:
    """Return active wishlist categories."""

    return db.list_active_wishlist_categories(user_id)


def add_wish(
    db,
    clock: Callable[[int], Any],
    logger,
    user_id: int,
    name: str,
    price: float,
    url: str | None,
    category: str,
) -> dict | ServiceError:
    """Add a wish."""

    wish_id = db.add_wish(user_id=user_id, name=name, price=price, url=url, category=category)
    if not wish_id:
        if logger:
            logger.error("Failed to add wish (user_id=%s, category=%s)", user_id, category)
        return ServiceError(code="db_error", message="Failed to add wish")
    return {
        "id": wish_id,
        "name": name,
        "price": price,
        "url": url,
        "category": category,
        "created_at": clock(user_id).isoformat(),
    }


def purchase_wish(
    db,
    clock: Callable[[int], Any],
    logger,
    user_id: int,
    wish_id: int,
    debit_category: str | None,
) -> WishlistPurchaseResult | ServiceError:
    """Purchase a wish and optionally debit savings."""

    purchase_time = clock(user_id)
    result = db.purchase_wish(user_id, wish_id, debit_category, purchased_at=purchase_time)
    status = result.get("status")
    if status == "not_found":
        return ServiceError(code="not_found", message="Wish not found")
    if status == "already":
        return WishlistPurchaseResult(
            ok=False,
            already_done=True,
            message="already",
            balance_before=None,
            balance_after=None,
        )
    if status == "insufficient":
        return ServiceError(
            code="insufficient",
            message=str(result.get("available", 0)),
        )
    if status == "error":
        return ServiceError(code="db_error", message="Database error")
    if status in {"no_debit", "debited"}:
        before = result.get("savings_before")
        after = None
        if status == "debited" and before is not None:
            try:
                after = float(before) - float(result.get("price", 0))
            except (TypeError, ValueError):
                after = None
        return WishlistPurchaseResult(
            ok=True,
            already_done=False,
            message=status,
            balance_before=int(before) if isinstance(before, (int, float)) else None,
            balance_after=int(after) if isinstance(after, (int, float)) else None,
        )
    if logger:
        logger.error("Unexpected purchase wish status (user_id=%s, status=%s)", user_id, status)
    return ServiceError(code="unexpected", message="Unexpected status")


# DEPRECATED: use Bot.services.wishlist_service
def list_wishlist_categories_deprecated(db, user_id: int) -> list[dict]:
    return list_wishlist_categories(db, user_id)


# DEPRECATED: use Bot.services.wishlist_service
def add_wish_deprecated(
    db,
    clock: Callable[[int], Any],
    logger,
    user_id: int,
    name: str,
    price: float,
    url: str | None,
    category: str,
) -> dict | ServiceError:
    return add_wish(db, clock, logger, user_id, name, price, url, category)


# DEPRECATED: use Bot.services.wishlist_service
def purchase_wish_deprecated(
    db,
    clock: Callable[[int], Any],
    logger,
    user_id: int,
    wish_id: int,
    debit_category: str | None,
) -> WishlistPurchaseResult | ServiceError:
    return purchase_wish(db, clock, logger, user_id, wish_id, debit_category)
