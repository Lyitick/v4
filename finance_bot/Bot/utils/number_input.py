"""Utilities for parsing numeric input."""

from __future__ import annotations


def parse_int_choice(text: str) -> int | None:
    """Parse a simple integer choice like "2" or "+2"."""

    value = (text or "").strip()
    if not value:
        return None
    if value.startswith("+"):
        value = value[1:]
    if not value.isdigit():
        return None
    return int(value)


def parse_positive_int(text: str) -> int | None:
    """Parse a positive integer (> 0) from input."""

    value = parse_int_choice(text)
    if value is None or value <= 0:
        return None
    return value
