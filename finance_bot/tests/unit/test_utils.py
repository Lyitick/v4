"""Utility tests."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from Bot.utils.datetime_utils import get_next_byt_run_dt, resolve_deferred_until
from Bot.utils.logging import init_logging


def test_init_logging_returns_logger() -> None:
    """init_logging should return a logger instance."""

    logger = init_logging()
    assert logger.name == "Bot.utils.logging"


def test_get_next_byt_run_dt_before_slot() -> None:
    """Return today's slot when current time is before it."""

    tz = ZoneInfo("UTC")
    now = datetime(2024, 1, 1, 10, 0, tzinfo=tz)
    result = get_next_byt_run_dt(now, [time(12, 0)])
    assert result == datetime(2024, 1, 1, 12, 0, tzinfo=tz)


def test_get_next_byt_run_dt_after_slot() -> None:
    """Return next day's slot when current time is after it."""

    tz = ZoneInfo("UTC")
    now = datetime(2024, 1, 1, 13, 0, tzinfo=tz)
    result = get_next_byt_run_dt(now, [time(12, 0)])
    assert result == datetime(2024, 1, 2, 12, 0, tzinfo=tz)


def test_get_next_byt_run_dt_multiple_slots() -> None:
    """Pick closest upcoming slot from multiple options."""

    tz = ZoneInfo("UTC")
    now = datetime(2024, 1, 1, 12, 0, tzinfo=tz)
    result = get_next_byt_run_dt(now, [time(9, 0), time(18, 0)])
    assert result == datetime(2024, 1, 1, 18, 0, tzinfo=tz)


def test_resolve_deferred_until_keeps_later() -> None:
    """Do not shorten existing deferred_until value."""

    tz = ZoneInfo("UTC")
    existing = datetime(2024, 1, 3, 12, 0, tzinfo=tz)
    candidate = datetime(2024, 1, 2, 12, 0, tzinfo=tz)
    result = resolve_deferred_until(existing, candidate)
    assert result == existing
