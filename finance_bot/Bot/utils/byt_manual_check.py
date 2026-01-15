"""Helpers for manual BYT reminder checks."""

from typing import Any


def parse_byt_manual_cursor_index(raw: Any) -> int:
    """Parse FSM stored cursor index for BYT manual check.

    FSM may store index as int or str. Returns -1 when missing/invalid.
    """
    if raw is None:
        return -1
    try:
        if isinstance(raw, str) and raw.strip() == "":
            return -1
        return int(raw)
    except (TypeError, ValueError):
        return -1


def build_byt_times_sorted(times_by_category: dict[int, list[str]]) -> list[str]:
    """Build a unique sorted list of HH:MM times from category mapping."""

    times: set[str] = set()
    for values in times_by_category.values():
        for value in values:
            cleaned = str(value).strip()
            if cleaned:
                times.add(cleaned)
    return sorted(times)


def select_next_byt_manual_time(
    times_sorted: list[str],
    current_date: str,
    saved_date: str | None,
    index: int,
) -> tuple[str, int, str]:
    """Select next time slot and return selected time, updated index, restart notice."""

    if saved_date != current_date:
        index = -1
    next_index = index + 1
    restart_notice = ""
    if next_index >= len(times_sorted):
        next_index = 0
        restart_notice = "Сегодня все времена уже проверены — начинаю заново."
    return times_sorted[next_index], next_index, restart_notice
