"""Household service layer."""
from __future__ import annotations

from typing import Any, Callable

from Bot.services.types import ServiceError


async def ensure_household_month(
    db,
    clock: Callable[[int], Any],
    logger,
    user_id: int,
    month: str,
) -> ServiceError | None:
    """Ensure household questions exist for month."""

    if not month:
        return ServiceError(code="invalid_month", message="Month is required")
    try:
        await db.init_household_questions_for_month(user_id, month)
    except Exception as exc:  # pragma: no cover - DB layer handles logging
        if logger:
            logger.error("Failed to init household month %s for user %s", month, user_id, exc_info=True)
        return ServiceError(code="db_error", message="Failed to init household month")
    return None


def list_active_byt_wishes(
    db,
    logger,
    user_id: int,
    category_title: str,
) -> dict | ServiceError:
    """Return active BYT wishlist items for a category."""

    if not category_title:
        return ServiceError(code="invalid_category", message="Category is required")
    try:
        items = db.get_active_byt_wishes(user_id, category_title)
        return {"items": items}
    except Exception:  # pragma: no cover - DB layer handles logging
        if logger:
            logger.error(
                "Failed to list active BYT wishes (user_id=%s, category=%s)",
                user_id,
                category_title,
                exc_info=True,
            )
        return ServiceError(code="db_error", message="Failed to list BYT wishes")
