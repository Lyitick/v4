"""Tests for BYT reminder schedule helpers."""

from datetime import datetime
from zoneinfo import ZoneInfo

from Bot.utils.datetime_utils import get_next_reminder_dt


def test_get_next_reminder_dt_today() -> None:
    now = datetime(2026, 1, 8, 10, 30, tzinfo=ZoneInfo("UTC"))
    result = get_next_reminder_dt(now, ["12:00", "18:00"])
    assert result == datetime(2026, 1, 8, 12, 0, tzinfo=ZoneInfo("UTC"))


def test_get_next_reminder_dt_tomorrow() -> None:
    now = datetime(2026, 1, 8, 19, 0, tzinfo=ZoneInfo("UTC"))
    result = get_next_reminder_dt(now, ["12:00", "18:00"])
    assert result == datetime(2026, 1, 9, 12, 0, tzinfo=ZoneInfo("UTC"))


def test_get_next_reminder_dt_default() -> None:
    now = datetime(2026, 1, 8, 13, 0, tzinfo=ZoneInfo("UTC"))
    result = get_next_reminder_dt(now, [])
    assert result == datetime(2026, 1, 9, 12, 0, tzinfo=ZoneInfo("UTC"))
