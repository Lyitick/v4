"""Tests for time utilities."""
from datetime import datetime

from Bot.database import crud
from Bot.utils.time import get_user_timezone, set_user_timezone, today_for_user


def _fresh_db(tmp_path, monkeypatch) -> crud.FinanceDatabase:
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None
    return crud.FinanceDatabase()


def test_get_user_timezone_default(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        assert get_user_timezone(db, 1, "Europe/Moscow") == "Europe/Moscow"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_get_user_timezone_selected(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        set_user_timezone(db, 2, "UTC", "Europe/Moscow")
        assert get_user_timezone(db, 2, "Europe/Moscow") == "UTC"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_get_user_timezone_invalid(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        set_user_timezone(db, 3, "Invalid/Zone", "Europe/Moscow")
        assert get_user_timezone(db, 3, "Europe/Moscow") == "Europe/Moscow"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_today_for_user_format(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        today_value = today_for_user(db, 4, "UTC")
        datetime.strptime(today_value, "%Y-%m-%d")
    finally:
        db.close()
        crud.FinanceDatabase._instance = None
