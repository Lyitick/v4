"""Datetime utilities for the bot."""
from datetime import datetime

from Bot.config import settings


def now_tz() -> datetime:
    """Return current datetime in configured timezone."""

    return datetime.now(tz=settings.TIMEZONE)


def current_month_str(now: datetime | None = None) -> str:
    """Return current month label as YYYY-MM using configured timezone."""

    current = now or now_tz()
    return f"{current.year:04d}-{current.month:02d}"
