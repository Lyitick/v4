"""Tests for wishlist service."""
from datetime import datetime, timezone

from Bot.database import crud
from Bot.services.types import ServiceError
from Bot.services.wishlist_service import purchase_wish


def _fresh_db(tmp_path, monkeypatch) -> crud.FinanceDatabase:
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None
    return crud.FinanceDatabase()


def test_wishlist_purchase_idempotent(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        wish_id = db.add_wish(1, "Phone", 50.0, None, "Fun")
        db.update_saving(1, "alpha", 100.0)
        clock = lambda uid: datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = purchase_wish(db, clock, None, 1, wish_id, "alpha")
        assert result.ok is True
        result_again = purchase_wish(db, clock, None, 1, wish_id, "alpha")
        assert result_again.already_done is True
        savings_map = db.get_user_savings_map(1)
        assert savings_map.get("alpha") == 50.0
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_wishlist_purchase_insufficient(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        wish_id = db.add_wish(2, "Laptop", 200.0, None, "Work")
        db.update_saving(2, "alpha", 100.0)
        clock = lambda uid: datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = purchase_wish(db, clock, None, 2, wish_id, "alpha")
        assert isinstance(result, ServiceError)
        assert result.code == "insufficient"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None
