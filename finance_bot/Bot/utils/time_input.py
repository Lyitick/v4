"""Utilities for normalizing time input."""

from __future__ import annotations

import re


def _is_valid_time(hour: int, minute: int) -> bool:
    return 0 <= hour <= 23 and 0 <= minute <= 59


def normalize_time_partial(text: str) -> tuple[str, bool]:
    """Normalize partial time input into HH:, HH:MM, or empty string.

    Returns a tuple of (normalized, is_complete).
    """

    value = (text or "").replace(" ", "")
    if not value:
        return "", False

    if re.fullmatch(r"\d{2}$", value):
        hour = int(value)
        if 0 <= hour <= 23:
            return f"{hour:02d}:", False
        return "", False

    if re.fullmatch(r"\d{2}:$", value):
        hour = int(value[:2])
        if 0 <= hour <= 23:
            return f"{hour:02d}:", False
        return "", False

    if re.fullmatch(r"\d{4}$", value):
        hour = int(value[:2])
        minute = int(value[2:])
        if _is_valid_time(hour, minute):
            return f"{hour:02d}:{minute:02d}", True
        return "", False

    if re.fullmatch(r"\d{2}:\d{2}$", value):
        hour = int(value[:2])
        minute = int(value[3:])
        if _is_valid_time(hour, minute):
            return f"{hour:02d}:{minute:02d}", True
        return "", False

    return "", False
