"""Tests for BYT source category selection."""

from Bot.database import crud
from Bot.utils.byt_utils import get_byt_source_category_id
from Bot.utils.datetime_utils import now_tz


def _fresh_db(tmp_path, monkeypatch) -> crud.FinanceDatabase:
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None
    return crud.FinanceDatabase()


def test_byt_source_category_respects_setting(tmp_path, monkeypatch) -> None:
    """Return stored BYT source category id when configured."""

    db = _fresh_db(tmp_path, monkeypatch)
    try:
        category_id = db.create_wishlist_category(1, "Дом")
        db.set_byt_wishlist_category_id(1, category_id)
        assert get_byt_source_category_id(db, 1) == category_id
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_byt_source_category_fallback_by_name(tmp_path, monkeypatch) -> None:
    """Fallback should pick wishlist category named 'быт' and persist it."""

    db = _fresh_db(tmp_path, monkeypatch)
    try:
        category_id = db.create_wishlist_category(1, "быт")
        assert get_byt_source_category_id(db, 1) == category_id
        assert db.get_byt_wishlist_category_id(1) == category_id
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_byt_source_category_missing_returns_none(tmp_path, monkeypatch) -> None:
    """Return None when no BYT category is configured or found."""

    db = _fresh_db(tmp_path, monkeypatch)
    try:
        assert get_byt_source_category_id(db, 1) is None
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_byt_query_filters_by_category(tmp_path, monkeypatch) -> None:
    """BYT query should return items only from selected category."""

    db = _fresh_db(tmp_path, monkeypatch)
    try:
        category_a = db.create_wishlist_category(1, "быт")
        category_b = db.create_wishlist_category(1, "подарки")
        db.add_wish(1, "Швабра", 100, None, "быт")
        db.add_wish(1, "Подарок", 200, None, "подарки")
        now_dt = now_tz()
        items = db.list_active_byt_items_for_reminder(1, now_dt, "быт")
        assert {item["name"] for item in items} == {"Швабра"}
        assert db.get_active_byt_wishes(1, "быт")[0]["name"] == "Швабра"
        assert category_a != category_b
    finally:
        db.close()
        crud.FinanceDatabase._instance = None
