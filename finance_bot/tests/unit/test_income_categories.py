"""Tests for income category seeding and flow guards."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from Bot.database import crud


def test_income_categories_not_seeded(tmp_path, monkeypatch) -> None:
    """Income categories should start empty for a new user."""

    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None

    db = crud.FinanceDatabase()
    try:
        assert db.list_active_income_categories(12345) == []
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_start_income_flow_with_empty_categories(monkeypatch) -> None:
    """Handler should stop flow when no income categories exist."""

    pytest.importorskip("aiogram")

    from Bot.handlers import finances  # noqa: WPS433

    db_stub = SimpleNamespace(list_active_income_categories=MagicMock(return_value=[]))
    monkeypatch.setattr("Bot.handlers.finances.get_db", lambda: db_stub)
    monkeypatch.setattr(
        "Bot.handlers.finances.build_main_menu_for_user",
        AsyncMock(return_value="menu"),
    )
    monkeypatch.setattr("Bot.handlers.finances.ui_register_message", AsyncMock())
    monkeypatch.setattr("Bot.handlers.finances.safe_delete_message", AsyncMock())

    sent_message = SimpleNamespace(message_id=10, chat=SimpleNamespace(id=20))
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=1),
        chat=SimpleNamespace(id=20),
        message_id=5,
        bot=SimpleNamespace(),
        answer=AsyncMock(return_value=sent_message),
    )
    state = SimpleNamespace(clear=AsyncMock(), set_state=AsyncMock(), update_data=AsyncMock())

    async def _run() -> None:
        await finances.start_income_flow(message, state)

    asyncio.run(_run())

    assert db_stub.list_active_income_categories.call_count == 1
    state.set_state.assert_not_awaited()
    message.answer.assert_awaited_once()
    assert "Категории дохода не настроены" in message.answer.await_args.args[0]
