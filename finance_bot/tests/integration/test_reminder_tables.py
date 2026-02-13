"""Integration tests for reminder database tables."""

from Bot.database import crud
from Bot.database.crud import TABLES


def _fresh_db(tmp_path, monkeypatch) -> crud.FinanceDatabase:
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None
    return crud.FinanceDatabase()


def test_reminder_tables_created(tmp_path, monkeypatch) -> None:
    """Verify all 4 reminder tables exist after init_db."""
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        table_names = {row["name"] for row in cursor.fetchall()}
        assert TABLES.reminders in table_names
        assert TABLES.reminder_schedules in table_names
        assert TABLES.reminder_events in table_names
        assert TABLES.reminder_stats_daily in table_names
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_create_and_list_reminders(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        rid = db.create_reminder(1, "habits", "Бег")
        assert rid is not None

        reminders = db.list_reminders_by_category(1, "habits")
        assert len(reminders) == 1
        assert reminders[0]["title"] == "Бег"
        assert reminders[0]["is_enabled"] == 1

        reminder = db.get_reminder(rid)
        assert reminder is not None
        assert reminder["category"] == "habits"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_toggle_reminder_enabled(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        rid = db.create_reminder(1, "habits", "Чтение")
        # Initially enabled
        new_val = db.toggle_reminder_enabled(rid, 1)
        assert new_val is False

        new_val = db.toggle_reminder_enabled(rid, 1)
        assert new_val is True
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_reminder_schedule_crud(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        rid = db.create_reminder(1, "habits", "Зарядка")
        sid = db.set_reminder_schedule(
            rid, "specific_times", times_json='["09:00","18:00"]'
        )
        assert sid is not None

        schedule = db.get_reminder_schedule(rid)
        assert schedule is not None
        assert schedule["schedule_type"] == "specific_times"
        assert "09:00" in schedule["times_json"]

        # Replace schedule
        db.set_reminder_schedule(rid, "interval", interval_minutes=30)
        schedule = db.get_reminder_schedule(rid)
        assert schedule["schedule_type"] == "interval"
        assert schedule["interval_minutes"] == 30
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_event_idempotency_via_hash(tmp_path, monkeypatch) -> None:
    """UNIQUE(callback_hash) prevents duplicate events."""
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        rid = db.create_reminder(1, "habits", "Вода")
        cb_hash = "test_hash_123"

        eid1 = db.record_reminder_event(
            rid, 1, "shown", "2026-01-01T12:00:00", callback_hash=cb_hash
        )
        assert eid1 is not None

        eid2 = db.record_reminder_event(
            rid, 1, "shown", "2026-01-01T12:00:00", callback_hash=cb_hash
        )
        assert eid2 is None  # Duplicate rejected
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_event_action_idempotency(tmp_path, monkeypatch) -> None:
    """action_at check prevents double-acting on same event."""
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        rid = db.create_reminder(1, "habits", "Йога")
        eid = db.record_reminder_event(rid, 1, "shown", "2026-01-01T09:00:00")

        ok1 = db.update_reminder_event_action(eid, "done", "2026-01-01T09:05:00")
        assert ok1 is True

        ok2 = db.update_reminder_event_action(eid, "skip", "2026-01-01T09:06:00")
        assert ok2 is False  # Already acted
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_reminder_stats(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        db.increment_reminder_stat(1, "2026-01-01", "habits", "shown_count")
        db.increment_reminder_stat(1, "2026-01-01", "habits", "shown_count")
        db.increment_reminder_stat(1, "2026-01-01", "habits", "done_count")

        stats = db.get_reminder_stats(1, "2026-01-01", "habits")
        assert len(stats) == 1
        assert stats[0]["shown_count"] == 2
        assert stats[0]["done_count"] == 1
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_delete_reminder_cascades_schedule(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        rid = db.create_reminder(1, "habits", "Тест")
        db.set_reminder_schedule(rid, "specific_times", times_json='["10:00"]')

        assert db.get_reminder_schedule(rid) is not None
        db.delete_reminder(rid, 1)
        assert db.get_reminder(rid) is None
        assert db.get_reminder_schedule(rid) is None
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_get_users_with_active_reminders(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        db.create_reminder(10, "habits", "A")
        db.create_reminder(20, "habits", "B")

        users = db.get_users_with_active_reminders()
        assert 10 in users
        assert 20 in users
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_pending_snooze_events(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        rid = db.create_reminder(1, "habits", "Тест")
        eid = db.record_reminder_event(rid, 1, "shown", "2026-01-01T12:00:00")

        # Set snooze action
        db.update_reminder_event_action(
            eid, "snooze", "2026-01-01T12:00:00",
            snooze_until="2026-01-01T12:15:00",
        )

        # Before snooze time: no pending
        pending = db.get_pending_snooze_events(1, "2026-01-01T12:10:00")
        assert len(pending) == 0

        # After snooze time: pending
        pending = db.get_pending_snooze_events(1, "2026-01-01T12:16:00")
        assert len(pending) == 1
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


# ------------------------------------------------------------------ #
#  Phase 2: Food & Supplements integration tests                       #
# ------------------------------------------------------------------ #


def test_create_food_reminders(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        rid1 = db.create_reminder(1, "food", "Обед", text="meal")
        rid2 = db.create_reminder(1, "food", "Витамин D", text="supplement")
        assert rid1 is not None
        assert rid2 is not None

        items = db.list_reminders_by_category(1, "food")
        assert len(items) == 2
        titles = [i["title"] for i in items]
        assert "Обед" in titles
        assert "Витамин D" in titles

        # Check sub-type is stored in text field
        meal = next(i for i in items if i["title"] == "Обед")
        assert meal["text"] == "meal"
        supp = next(i for i in items if i["title"] == "Витамин D")
        assert supp["text"] == "supplement"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_food_stats(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        db.increment_reminder_stat(1, "2026-01-01", "food", "shown_count")
        db.increment_reminder_stat(1, "2026-01-01", "food", "done_count")

        stats = db.get_reminder_stats(1, "2026-01-01", "food")
        assert len(stats) == 1
        assert stats[0]["shown_count"] == 1
        assert stats[0]["done_count"] == 1
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


# ------------------------------------------------------------------ #
#  Phase 3: Motivation integration tests                               #
# ------------------------------------------------------------------ #


def test_create_motivation_with_media(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        rid = db.create_reminder(
            1, "motivation", "Фото",
            media_type="photo", media_ref="AgACtest123",
        )
        assert rid is not None

        reminder = db.get_reminder(rid)
        assert reminder["media_type"] == "photo"
        assert reminder["media_ref"] == "AgACtest123"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_motivation_stats(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        db.increment_reminder_stat(1, "2026-01-01", "motivation", "shown_count")
        db.increment_reminder_stat(1, "2026-01-01", "motivation", "done_count")

        stats = db.get_reminder_stats(1, "2026-01-01", "motivation")
        assert len(stats) == 1
        assert stats[0]["shown_count"] == 1
        assert stats[0]["done_count"] == 1
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


# ------------------------------------------------------------------ #
#  Phase 4: Wishlist/BYT migration integration tests                   #
# ------------------------------------------------------------------ #


def test_create_wishlist_reminders(tmp_path, monkeypatch) -> None:
    """Wishlist reminders can be created and listed."""
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        rid = db.create_reminder(1, "wishlist", "Быт", text="byt_category_id:5")
        assert rid is not None

        items = db.list_reminders_by_category(1, "wishlist")
        assert len(items) == 1
        assert items[0]["title"] == "Быт"
        assert items[0]["text"] == "byt_category_id:5"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_all_four_categories_coexist(tmp_path, monkeypatch) -> None:
    """All 4 reminder categories can coexist for the same user."""
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        db.create_reminder(1, "habits", "Бег")
        db.create_reminder(1, "food", "Обед")
        db.create_reminder(1, "motivation", "Верь!")
        db.create_reminder(1, "wishlist", "Быт")

        assert len(db.list_reminders_by_category(1, "habits")) == 1
        assert len(db.list_reminders_by_category(1, "food")) == 1
        assert len(db.list_reminders_by_category(1, "motivation")) == 1
        assert len(db.list_reminders_by_category(1, "wishlist")) == 1

        users = db.get_users_with_active_reminders()
        assert 1 in users
    finally:
        db.close()
        crud.FinanceDatabase._instance = None
