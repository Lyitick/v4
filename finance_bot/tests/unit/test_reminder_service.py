"""Tests for reminder service layer."""

from datetime import datetime, timezone

from Bot.database import crud
from Bot.services.reminder_service import (
    build_callback_hash,
    create_habit,
    delete_habit,
    list_habits,
    record_reminder_action,
    schedule_snooze,
    should_fire_at,
    is_within_activity_window,
)
from Bot.services.types import ServiceError


def _fresh_db(tmp_path, monkeypatch) -> crud.FinanceDatabase:
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None
    return crud.FinanceDatabase()


def test_create_habit(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_habit(db, 1, "Бег")
        assert isinstance(result, dict)
        assert result["id"] is not None
        assert result["title"] == "Бег"

        habits = list_habits(db, 1)
        assert len(habits) == 1
        assert habits[0]["title"] == "Бег"
        assert habits[0]["category"] == "habits"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_create_habit_with_times(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_habit(db, 1, "Медитация", times=["09:00", "21:00"])
        assert isinstance(result, dict)
        rid = result["id"]

        schedule = db.get_reminder_schedule(rid)
        assert schedule is not None
        assert schedule["schedule_type"] == "specific_times"
        assert "09:00" in schedule["times_json"]
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_create_habit_empty_title(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_habit(db, 1, "  ")
        assert isinstance(result, ServiceError)
        assert result.code == "empty_title"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_delete_habit(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_habit(db, 1, "Чтение")
        rid = result["id"]

        ok = delete_habit(db, 1, rid)
        assert ok is True

        habits = list_habits(db, 1)
        assert len(habits) == 0
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_delete_habit_not_found(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = delete_habit(db, 1, 9999)
        assert isinstance(result, ServiceError)
        assert result.code == "not_found"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_record_action_idempotent(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        create_result = create_habit(db, 1, "Вода")
        rid = create_result["id"]
        now_iso = "2026-01-01T12:00:00"
        cb_hash = build_callback_hash(rid, 1, now_iso)

        event_id = db.record_reminder_event(rid, 1, "shown", now_iso, callback_hash=cb_hash)
        assert event_id is not None

        # First action: done
        result1 = record_reminder_action(db, 1, event_id, "done", now_iso)
        assert isinstance(result1, dict)
        assert result1["event_type"] == "done"

        # Second action: should be rejected
        result2 = record_reminder_action(db, 1, event_id, "done", now_iso)
        assert isinstance(result2, ServiceError)
        assert result2.code == "already_done"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_schedule_snooze(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        create_result = create_habit(db, 1, "Зарядка")
        rid = create_result["id"]
        now_dt = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        now_iso = now_dt.isoformat()
        cb_hash = build_callback_hash(rid, 1, now_iso)

        event_id = db.record_reminder_event(rid, 1, "shown", now_iso, callback_hash=cb_hash)

        result = schedule_snooze(db, 1, event_id, 60, now_dt)
        assert isinstance(result, dict)
        assert result["snooze_until"] is not None
        assert "13:00" in result["snooze_until"]

        # Second snooze: should be rejected (already acted)
        result2 = schedule_snooze(db, 1, event_id, 30, now_dt)
        assert isinstance(result2, ServiceError)
        assert result2.code == "already_done"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_should_fire_specific_times() -> None:
    schedule = {
        "schedule_type": "specific_times",
        "times_json": '["09:00", "12:00", "18:00"]',
    }
    now = datetime(2026, 1, 1, 12, 0)
    assert should_fire_at(schedule, "12:00", now) is True
    assert should_fire_at(schedule, "13:00", now) is False
    assert should_fire_at(schedule, "09:00", now) is True


def test_should_fire_outside_window() -> None:
    schedule = {
        "schedule_type": "specific_times",
        "times_json": '["08:00"]',
        "active_from": "09:00",
        "active_to": "22:00",
    }
    now = datetime(2026, 1, 1, 8, 0)
    assert should_fire_at(schedule, "08:00", now) is False


def test_should_fire_interval() -> None:
    schedule = {
        "schedule_type": "interval",
        "interval_minutes": 60,
        "active_from": "09:00",
        "active_to": "22:00",
    }
    now = datetime(2026, 1, 1, 10, 0)
    assert should_fire_at(schedule, "10:00", now) is True
    assert should_fire_at(schedule, "10:30", now) is False
    assert should_fire_at(schedule, "11:00", now) is True


def test_should_fire_interval_min_15() -> None:
    schedule = {
        "schedule_type": "interval",
        "interval_minutes": 10,
    }
    now = datetime(2026, 1, 1, 10, 0)
    assert should_fire_at(schedule, "10:00", now) is False


def test_build_callback_hash_deterministic() -> None:
    h1 = build_callback_hash(1, 100, "2026-01-01T12:00:00")
    h2 = build_callback_hash(1, 100, "2026-01-01T12:00:00")
    h3 = build_callback_hash(1, 100, "2026-01-01T12:01:00")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16


def test_is_within_activity_window() -> None:
    schedule_in = {"active_from": "09:00", "active_to": "22:00"}
    schedule_out = {"active_from": "09:00", "active_to": "22:00"}
    schedule_none = {}

    assert is_within_activity_window(schedule_in, "12:00") is True
    assert is_within_activity_window(schedule_out, "08:00") is False
    assert is_within_activity_window(schedule_none, "03:00") is True
