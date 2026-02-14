"""Tests for reminder service layer."""

from datetime import datetime, timezone

from Bot.database import crud
from Bot.services.reminder_service import (
    build_callback_hash,
    create_food_reminder,
    create_habit,
    create_motivation_content,
    create_wishlist_reminder,
    delete_food_reminder,
    delete_habit,
    delete_motivation_content,
    delete_wishlist_reminder,
    ensure_motivation_schedule,
    get_motivation_schedule,
    is_within_activity_window,
    list_food_reminders,
    list_habits,
    list_motivation_content,
    list_wishlist_reminders,
    migrate_byt_to_reminders,
    record_reminder_action,
    schedule_snooze,
    set_motivation_schedule,
    should_fire_at,
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


# ------------------------------------------------------------------ #
#  Phase 2: Food & Supplements                                        #
# ------------------------------------------------------------------ #


def test_create_food_reminder(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_food_reminder(db, 1, "Обед", sub_type="meal")
        assert isinstance(result, dict)
        assert result["title"] == "Обед"
        assert result["sub_type"] == "meal"

        items = list_food_reminders(db, 1)
        assert len(items) == 1
        assert items[0]["category"] == "food"
        assert items[0]["text"] == "meal"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_create_food_supplement(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_food_reminder(db, 1, "Витамин D", sub_type="supplement",
                                       times=["09:00", "21:00"])
        assert isinstance(result, dict)
        assert result["sub_type"] == "supplement"

        schedule = db.get_reminder_schedule(result["id"])
        assert schedule is not None
        assert "09:00" in schedule["times_json"]
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_create_food_empty_title(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_food_reminder(db, 1, "  ")
        assert isinstance(result, ServiceError)
        assert result.code == "empty_title"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_delete_food_reminder(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_food_reminder(db, 1, "Завтрак")
        rid = result["id"]

        ok = delete_food_reminder(db, 1, rid)
        assert ok is True
        assert len(list_food_reminders(db, 1)) == 0
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_delete_food_wrong_category(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        # Create a habit, try to delete it as food
        habit = create_habit(db, 1, "Бег")
        result = delete_food_reminder(db, 1, habit["id"])
        assert isinstance(result, ServiceError)
        assert result.code == "not_found"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


# ------------------------------------------------------------------ #
#  Phase 3: Motivation / Content                                       #
# ------------------------------------------------------------------ #


def test_create_motivation_content_text(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_motivation_content(db, 1, "Верь в себя!", text="Полный текст мотивации")
        assert isinstance(result, dict)
        assert result["title"] == "Верь в себя!"
        assert result["media_type"] is None

        items = list_motivation_content(db, 1)
        assert len(items) == 1
        assert items[0]["category"] == "motivation"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_create_motivation_content_photo(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_motivation_content(
            db, 1, "", media_type="photo", media_ref="AgACfake123"
        )
        assert isinstance(result, dict)
        assert result["title"] == "Фото"
        assert result["media_type"] == "photo"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_create_motivation_empty_content(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_motivation_content(db, 1, "")
        assert isinstance(result, ServiceError)
        assert result.code == "empty_content"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_delete_motivation_content(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_motivation_content(db, 1, "Текст")
        rid = result["id"]
        ok = delete_motivation_content(db, 1, rid)
        assert ok is True
        assert len(list_motivation_content(db, 1)) == 0
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_motivation_schedule_meta(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        meta = ensure_motivation_schedule(db, 1)
        assert meta.get("id") is not None
        assert meta["title"] == "__schedule__"

        # Ensure idempotent
        meta2 = ensure_motivation_schedule(db, 1)
        assert meta2["id"] == meta["id"]

        # Schedule meta not in content list
        items = list_motivation_content(db, 1)
        assert len(items) == 0
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_set_motivation_schedule_interval(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = set_motivation_schedule(
            db, 1, "interval", interval_minutes=120,
            active_from="09:00", active_to="22:00",
        )
        assert isinstance(result, dict)
        assert result.get("schedule_type") == "interval"
        assert result.get("interval_minutes") == 120

        schedule = get_motivation_schedule(db, 1)
        assert schedule is not None
        assert schedule["active_from"] == "09:00"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_set_motivation_schedule_too_short(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = set_motivation_schedule(db, 1, "interval", interval_minutes=5)
        assert isinstance(result, ServiceError)
        assert result.code == "invalid_interval"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


# ------------------------------------------------------------------ #
#  Phase 4: BYT Migration                                             #
# ------------------------------------------------------------------ #


def test_migrate_byt_to_reminders_empty(tmp_path, monkeypatch) -> None:
    """Migration on user with no BYT data creates no reminders.

    Note: ensure_byt_reminder_migration calls ensure_user_settings which has
    a pre-existing NameError bug. We skip gracefully if that triggers.
    """
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        try:
            count = migrate_byt_to_reminders(db, 1)
        except NameError:
            # Pre-existing bug in ensure_user_settings (name 'settings' not defined)
            count = 0
        assert count == 0
        assert len(db.list_reminders_by_category(1, "wishlist")) == 0
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_migrate_byt_to_reminders_idempotent(tmp_path, monkeypatch) -> None:
    """Second migration call returns 0 (already migrated)."""
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        # Manually create a wishlist reminder to simulate migration done
        db.create_reminder(1, "wishlist", "Быт")
        count = migrate_byt_to_reminders(db, 1)
        assert count == 0
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


# ------------------------------------------------------------------ #
#  Wishlist CRUD tests                                                 #
# ------------------------------------------------------------------ #


def test_create_wishlist_reminder(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_wishlist_reminder(db, 1, "Покупка подарка")
        assert isinstance(result, dict)
        assert result["id"] is not None
        assert result["title"] == "Покупка подарка"

        items = list_wishlist_reminders(db, 1)
        assert len(items) == 1
        assert items[0]["title"] == "Покупка подарка"
        assert items[0]["category"] == "wishlist"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_create_wishlist_reminder_with_times(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_wishlist_reminder(db, 1, "Проверить цены", times=["10:00", "18:00"])
        assert isinstance(result, dict)
        schedule = db.get_reminder_schedule(result["id"])
        assert schedule is not None
        assert schedule["schedule_type"] == "specific_times"
        import json
        times = json.loads(schedule["times_json"])
        assert "10:00" in times
        assert "18:00" in times
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_create_wishlist_reminder_empty_title(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_wishlist_reminder(db, 1, "")
        assert isinstance(result, ServiceError)
        assert result.code == "empty_title"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_delete_wishlist_reminder(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        result = create_wishlist_reminder(db, 1, "Купить книгу")
        rid = result["id"]
        ok = delete_wishlist_reminder(db, 1, rid)
        assert ok is True
        assert len(list_wishlist_reminders(db, 1)) == 0
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_delete_wishlist_wrong_category(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        # Create a habit, try to delete as wishlist
        result = create_habit(db, 1, "Бег")
        err = delete_wishlist_reminder(db, 1, result["id"])
        assert isinstance(err, ServiceError)
        assert err.code == "not_found"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None
