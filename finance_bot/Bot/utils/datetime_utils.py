"""Datetime utilities for the bot."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from Bot.config import settings


def now_tz() -> datetime:
    """Return current datetime in configured timezone."""

    return datetime.now(tz=settings.TIMEZONE)


def current_month_str(now: datetime | None = None) -> str:
    """Return current month label as YYYY-MM using configured timezone."""

    current = now or now_tz()
    return f"{current.year:04d}-{current.month:02d}"


def add_one_month(source: datetime) -> datetime:
    """Add one calendar month to datetime without external dependencies."""

    year = source.year + (source.month // 12)
    month = 1 if source.month == 12 else source.month + 1
    last_day = (
        (source.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    ).day
    day = min(source.day, last_day)
    return source.replace(year=year, month=month, day=day)


def get_next_byt_run_dt(now: datetime, schedule_times: list[time]) -> datetime:
    """Return next BYT reminder datetime based on schedule times."""

    if not schedule_times:
        return now

    sorted_times = sorted(
        schedule_times, key=lambda value: (value.hour, value.minute, value.second)
    )
    candidates = [
        now.replace(
            hour=slot.hour,
            minute=slot.minute,
            second=slot.second,
            microsecond=0,
        )
        for slot in sorted_times
    ]
    for candidate in candidates:
        if candidate >= now:
            return candidate
    return candidates[0] + timedelta(days=1)


def get_next_reminder_dt(
    now: datetime, times_hhmm: list[str], tz: ZoneInfo | None = None
) -> datetime:
    """Return next reminder datetime based on HH:MM list."""

    timezone = tz or now.tzinfo
    valid_times: list[time] = []
    for raw in times_hhmm:
        if not raw:
            continue
        parts = str(raw).strip().split(":", maxsplit=1)
        if len(parts) != 2:
            continue
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except (TypeError, ValueError):
            continue
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            continue
        valid_times.append(time(hour=hour, minute=minute))
    if not valid_times:
        valid_times = [time(hour=12, minute=0)]

    sorted_times = sorted(valid_times, key=lambda value: (value.hour, value.minute))
    candidates = [
        now.replace(
            hour=slot.hour,
            minute=slot.minute,
            second=0,
            microsecond=0,
            tzinfo=timezone,
        )
        for slot in sorted_times
    ]
    for candidate in candidates:
        if candidate > now:
            return candidate
    return candidates[0] + timedelta(days=1)


def resolve_deferred_until(
    existing: datetime | None, candidate: datetime
) -> datetime:
    """Pick later deferred_until value."""

    if existing and existing > candidate:
        return existing
    return candidate
