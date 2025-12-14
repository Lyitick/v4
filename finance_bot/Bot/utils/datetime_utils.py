"""Datetime utilities for the bot."""
from datetime import datetime, timedelta

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
