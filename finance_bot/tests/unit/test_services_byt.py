"""Tests for BYT service."""
from datetime import datetime, timedelta, timezone

from Bot.database import crud
from Bot.services.byt_service import build_manual_check_summary


def _fresh_db(tmp_path, monkeypatch) -> crud.FinanceDatabase:
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None
    return crud.FinanceDatabase()


def test_byt_manual_check_summary(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        category_id = db.create_wishlist_category(1, "БЫТ")
        assert category_id is not None
        wish_due = db.add_wish(1, "Чайник", 1000.0, None, "БЫТ")
        wish_deferred = db.add_wish(1, "Утюг", 500.0, None, "БЫТ")
        future_dt = datetime(2025, 1, 2, tzinfo=timezone.utc)
        db.set_wishlist_item_deferred_until(1, wish_deferred, future_dt.isoformat())
        clock = lambda uid: datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        result = build_manual_check_summary(
            db=db,
            clock=clock,
            logger=None,
            user_id=1,
            time_str="12:00",
            category_ids=[int(category_id)],
        )
        assert isinstance(result, dict)
        summary = result.get("summary")
        assert summary is not None
        assert summary.total == 2
        assert summary.due == 1
        assert summary.deferred == 1
    finally:
        db.close()
        crud.FinanceDatabase._instance = None
