"""Helpers for manual BYT reminder checks."""


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
