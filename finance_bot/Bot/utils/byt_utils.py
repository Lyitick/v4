"""Utilities for BYT reminder source category."""

from __future__ import annotations

import logging
from typing import Optional

from Bot.database.crud import FinanceDatabase

LOGGER = logging.getLogger(__name__)


def normalize_wishlist_category_title(value: str) -> str:
    """Normalize wishlist category titles for comparison."""

    normalized = str(value or "").strip().casefold()
    if normalized == "byt":
        return "быт"
    return normalized


def wishlist_category_matches(wish_category: str, source_title: str) -> bool:
    """Return True when wish category matches selected BYT source."""

    return normalize_wishlist_category_title(wish_category) == normalize_wishlist_category_title(
        source_title
    )


def get_byt_source_category_id(db: FinanceDatabase, user_id: int) -> Optional[int]:
    """Return BYT source wishlist category id with fallback by name."""

    db.ensure_user_settings(user_id)
    settings_row = db.get_user_settings(user_id)
    raw_id = settings_row.get("byt_wishlist_category_id")
    category_id: Optional[int] = None
    if raw_id is not None:
        try:
            category_id = int(raw_id)
        except (TypeError, ValueError):
            category_id = None
    if category_id is not None:
        category_row = db.get_wishlist_category_by_id(user_id, category_id)
        if category_row:
            return int(category_row.get("id"))
        db.set_byt_wishlist_category_id(user_id, None)

    fallback = db.get_wishlist_category_by_title(user_id, "быт")
    if fallback:
        fallback_id = int(fallback.get("id"))
        db.set_byt_wishlist_category_id(user_id, fallback_id)
        LOGGER.info(
            "USER=%s ACTION=BYT_SOURCE_CATEGORY_SET META=category_id=%s",
            user_id,
            fallback_id,
        )
        return fallback_id
    return None


def get_byt_source_category(
    db: FinanceDatabase, user_id: int
) -> tuple[Optional[int], Optional[str]]:
    """Return BYT source category id and title."""

    category_id = get_byt_source_category_id(db, user_id)
    if category_id is None:
        return None, None
    category_row = db.get_wishlist_category_by_id(user_id, category_id)
    if not category_row:
        return None, None
    return category_id, str(category_row.get("title", ""))
