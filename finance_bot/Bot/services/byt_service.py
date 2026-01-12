"""BYT service layer."""
from __future__ import annotations

from typing import Any, Callable

from Bot.services.types import ManualCheckResult, ServiceError
from Bot.utils.byt_render import get_byt_category_items


def build_manual_check_summary(
    db,
    clock: Callable[[int], Any],
    logger,
    user_id: int,
    time_str: str,
    category_ids: list[int],
) -> dict | ServiceError:
    """Build manual BYT check summary for selected categories/time."""

    if not time_str:
        return ServiceError(code="invalid_time", message="Time is required")
    now_dt = clock(user_id)
    try:
        hour_str, minute_str = time_str.split(":", maxsplit=1)
        trigger_dt = now_dt.replace(
            hour=int(hour_str),
            minute=int(minute_str),
            second=0,
            microsecond=0,
        )
    except (ValueError, TypeError):
        return ServiceError(code="invalid_time", message="Invalid time format")

    categories = []
    total = due = deferred = 0
    per_category: list[dict[str, Any]] = []
    for category_id in category_ids:
        category = db.get_wishlist_category_by_id(user_id, int(category_id))
        if not category:
            continue
        title = str(category.get("title", ""))
        if not title:
            continue
        db.cleanup_old_byt_purchases(user_id, title, trigger_dt)
        due_items, deferred_items = get_byt_category_items(db, user_id, title, trigger_dt)
        categories.append(title)
        total += len(due_items) + len(deferred_items)
        due += len(due_items)
        deferred += len(deferred_items)
        per_category.append(
            {
                "category_id": int(category_id),
                "category_title": title,
                "due_items": due_items,
                "deferred_items": deferred_items,
            }
        )
    summary = ManualCheckResult(
        time_str=time_str,
        categories=categories,
        total=total,
        due=due,
        deferred=deferred,
    )
    if logger:
        logger.info(
            "BYT_MANUAL_CHECK_SUMMARY user_id=%s time=%s total=%s due=%s deferred=%s",
            user_id,
            time_str,
            total,
            due,
            deferred,
        )
    return {"summary": summary, "categories": per_category, "trigger_dt": trigger_dt}
