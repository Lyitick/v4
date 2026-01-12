"""Tests for household service."""
import asyncio
from datetime import datetime, timezone

from Bot.database import crud
from Bot.services.household_service import ensure_household_month, list_active_byt_wishes


def _fresh_db(tmp_path, monkeypatch) -> crud.FinanceDatabase:
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None
    return crud.FinanceDatabase()


def test_list_active_byt_wishes(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        db.add_wish(1, "Test", 10.0, None, "БЫТ")
        result = list_active_byt_wishes(db, None, 1, "БЫТ")
        assert isinstance(result, dict)
        assert len(result.get("items", [])) == 1
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_ensure_household_month(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        month = "2025-01"
        clock = lambda uid: datetime(2025, 1, 1, tzinfo=timezone.utc)
        asyncio.run(
            ensure_household_month(
                db=db,
                clock=clock,
                logger=None,
                user_id=1,
                month=month,
            )
        )
        exists = asyncio.run(db.household_status_exists(1, month))
        assert exists is True
    finally:
        db.close()
        crud.FinanceDatabase._instance = None
