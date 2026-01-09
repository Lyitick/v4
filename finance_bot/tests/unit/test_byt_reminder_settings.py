"""Tests for BYT reminder category and time settings."""

from datetime import datetime

from Bot.database import crud
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from Bot.keyboards.settings import byt_timer_categories_inline_keyboard
from Bot.utils.byt_render import (
    format_byt_categories_status_text,
    format_byt_category_checklist_text,
    format_byt_defer_confirmation_text,
)


def _fresh_db(tmp_path, monkeypatch) -> crud.FinanceDatabase:
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None
    return crud.FinanceDatabase()


def test_toggle_byt_category_and_times(tmp_path, monkeypatch) -> None:
    db = _fresh_db(tmp_path, monkeypatch)
    try:
        category_id = db.create_wishlist_category(1, "Дом")
        assert db.get_byt_reminder_category_enabled(1, category_id) is False
        enabled = db.toggle_byt_reminder_category(1, category_id)
        assert enabled is True
        assert db.get_byt_reminder_category_enabled(1, category_id) is True
        enabled = db.toggle_byt_reminder_category(1, category_id)
        assert enabled is False

        db.add_byt_reminder_time(1, category_id, "09:00")
        times = db.list_byt_reminder_times(1, category_id)
        assert times == [{"time_hhmm": "09:00"}]
        db.remove_byt_reminder_time(1, category_id, "09:00")
        assert db.list_byt_reminder_times(1, category_id) == []
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_defer_confirmation_text_contains_details() -> None:
    item = {"name": "Швабра", "price": 1990}
    deferred_until = datetime(2026, 1, 9, 12, 0)
    checklist_text = format_byt_category_checklist_text("Быт", [item], [])
    text = format_byt_defer_confirmation_text(
        item, "Быт", deferred_until, checklist_text
    )
    assert "Швабра" in text
    assert "2026-01-09 12:00" in text
    assert "Категория: Быт" in text


def test_byt_categories_status_text_format() -> None:
    categories = [
        {"title": "Быт", "enabled": 1},
        {"title": "Еда", "enabled": 0},
    ]
    text = format_byt_categories_status_text(categories)
    lines = [line for line in text.splitlines() if line.strip()]
    status_lines = lines[1:]
    assert status_lines == ["✅ Быт", "❌ Еда"]
    assert all(not any(char.isdigit() for char in line) for line in status_lines)


def test_byt_timer_categories_keyboard_inline() -> None:
    categories = [{"id": 1, "title": "Быт", "enabled": 1}]
    keyboard = byt_timer_categories_inline_keyboard(categories, "byt:timer_category")
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert not isinstance(keyboard, ReplyKeyboardMarkup)
