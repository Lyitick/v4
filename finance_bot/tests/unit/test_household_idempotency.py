"""Tests for household idempotency handling."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("aiogram")

from Bot.handlers.household_payments import handle_household_answer  # noqa: E402


class DummyState:
    def __init__(self, data: dict) -> None:
        self._data = data
        self.update_data = AsyncMock(side_effect=self._update)
        self.get_data = AsyncMock(side_effect=self._get)
        self.get_state = AsyncMock(return_value="state")

    async def _get(self) -> dict:
        return self._data

    async def _update(self, **kwargs) -> None:
        self._data.update(kwargs)


@pytest.mark.asyncio
async def test_handle_household_answer_skips_processed_code(monkeypatch) -> None:
    """Duplicate callbacks should not reapply DB updates."""

    db_stub = SimpleNamespace(apply_household_payment_answer=MagicMock(return_value=True))
    monkeypatch.setattr("Bot.handlers.household_payments.get_db", lambda: db_stub)

    message = SimpleNamespace(message_id=10, chat=SimpleNamespace(id=20))
    callback = SimpleNamespace(
        data="hh_pay:yes:q1",
        from_user=SimpleNamespace(id=1),
        message=message,
        bot=SimpleNamespace(edit_message_text=AsyncMock(return_value=None)),
        answer=AsyncMock(return_value=None),
    )

    state = SimpleNamespace(
        get_data=AsyncMock(
            return_value={
                "hh_month": "2025-01",
                "hh_questions": [
                    {"code": "q1", "text": "Q1", "amount": 10},
                    {"code": "q2", "text": "Q2", "amount": 5},
                ],
                "current_step_index": 0,
                "hh_index": 0,
                "hh_answers": {},
                "hh_ui_message_id": 10,
                "processed_steps": [],
            }
        ),
        update_data=AsyncMock(return_value=None),
        get_state=AsyncMock(return_value="state"),
    )

    await handle_household_answer(callback, state)
    assert db_stub.apply_household_payment_answer.call_count == 1

    state.get_data = AsyncMock(
        return_value={
            "hh_month": "2025-01",
            "hh_questions": [
                {"code": "q1", "text": "Q1", "amount": 10},
                {"code": "q2", "text": "Q2", "amount": 5},
            ],
            "current_step_index": 0,
            "hh_index": 0,
            "hh_answers": {"q1": "yes"},
            "hh_ui_message_id": 10,
            "processed_steps": ["q1"],
        }
    )

    await handle_household_answer(callback, state)
    assert db_stub.apply_household_payment_answer.call_count == 1


@pytest.mark.asyncio
async def test_handle_household_answer_no_updates_ui_on_unchanged_db(
    monkeypatch,
) -> None:
    """No answers should still update UI when DB reports no change."""

    db_stub = SimpleNamespace(apply_household_payment_answer=MagicMock(return_value=False))
    monkeypatch.setattr("Bot.handlers.household_payments.get_db", lambda: db_stub)

    message = SimpleNamespace(message_id=10, chat=SimpleNamespace(id=20))
    callback = SimpleNamespace(
        data="hh_pay:no:q1",
        from_user=SimpleNamespace(id=1),
        message=message,
        bot=SimpleNamespace(edit_message_text=AsyncMock(return_value=None)),
        answer=AsyncMock(return_value=None),
    )

    state = DummyState(
        {
            "hh_month": "2025-01",
            "hh_questions": [
                {"code": "q1", "text": "Q1", "amount": 10},
                {"code": "q2", "text": "Q2", "amount": 5},
            ],
            "current_step_index": 0,
            "hh_index": 0,
            "hh_answers": {},
            "hh_ui_message_id": 10,
            "processed_steps": [],
        }
    )

    await handle_household_answer(callback, state)

    assert db_stub.apply_household_payment_answer.call_count == 1
    kwargs = state.update_data.await_args.kwargs
    assert kwargs["hh_answers"]["q1"] == "no"
    assert "q1" in kwargs["processed_steps"]
    assert kwargs["current_step_index"] == 1
    callback.bot.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_household_answer_no_double_tap_is_idempotent(
    monkeypatch,
) -> None:
    """Duplicate no answers should not reapply DB or UI updates."""

    db_stub = SimpleNamespace(apply_household_payment_answer=MagicMock(return_value=False))
    monkeypatch.setattr("Bot.handlers.household_payments.get_db", lambda: db_stub)

    message = SimpleNamespace(message_id=10, chat=SimpleNamespace(id=20))
    callback = SimpleNamespace(
        data="hh_pay:no:q1",
        from_user=SimpleNamespace(id=1),
        message=message,
        bot=SimpleNamespace(edit_message_text=AsyncMock(return_value=None)),
        answer=AsyncMock(return_value=None),
    )

    state = DummyState(
        {
            "hh_month": "2025-01",
            "hh_questions": [
                {"code": "q1", "text": "Q1", "amount": 10},
                {"code": "q2", "text": "Q2", "amount": 5},
            ],
            "current_step_index": 0,
            "hh_index": 0,
            "hh_answers": {},
            "hh_ui_message_id": 10,
            "processed_steps": [],
        }
    )

    await handle_household_answer(callback, state)
    await handle_household_answer(callback, state)

    assert db_stub.apply_household_payment_answer.call_count == 1
    callback.bot.edit_message_text.assert_awaited_once()
