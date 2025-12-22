"""Tests for UI cleanup utilities."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import asyncio
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "aiogram" not in sys.modules:
    aiogram = types.ModuleType("aiogram")

    class DummyRouter:
        def message(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    class DummyF:
        class _Field:
            def __eq__(self, other):
                return ("eq", other)

        text = _Field()

    class Bot:
        pass

    aiogram.F = DummyF()
    aiogram.Router = DummyRouter
    aiogram.Bot = Bot

    exceptions = types.ModuleType("aiogram.exceptions")

    class TelegramBadRequest(Exception):
        pass

    exceptions.TelegramBadRequest = TelegramBadRequest
    aiogram.exceptions = exceptions

    filters = types.ModuleType("aiogram.filters")

    class Command:
        def __init__(self, *args, **kwargs):
            return None

    filters.Command = Command
    aiogram.filters = filters

    fsm = types.ModuleType("aiogram.fsm")
    fsm_context = types.ModuleType("aiogram.fsm.context")

    class FSMContext:
        pass

    fsm_context.FSMContext = FSMContext
    fsm.context = fsm_context
    aiogram.fsm = fsm

    types_mod = types.ModuleType("aiogram.types")

    class Message:
        pass

    class ReplyKeyboardMarkup:
        pass

    class InlineKeyboardButton:
        def __init__(self, *args, **kwargs):
            return None

    class InlineKeyboardMarkup:
        def __init__(self, *args, **kwargs):
            return None

    class KeyboardButton:
        def __init__(self, *args, **kwargs):
            return None

    types_mod.Message = Message
    types_mod.ReplyKeyboardMarkup = ReplyKeyboardMarkup
    types_mod.InlineKeyboardButton = InlineKeyboardButton
    types_mod.InlineKeyboardMarkup = InlineKeyboardMarkup
    types_mod.KeyboardButton = KeyboardButton
    aiogram.types = types_mod

    sys.modules["aiogram"] = aiogram
    sys.modules["aiogram.exceptions"] = exceptions
    sys.modules["aiogram.filters"] = filters
    sys.modules["aiogram.fsm"] = fsm
    sys.modules["aiogram.fsm.context"] = fsm_context
    sys.modules["aiogram.types"] = types_mod

from Bot.handlers.start import back_to_main
from Bot.utils.ui_cleanup import ui_cleanup_to_context, ui_register_message


class DummyState:
    """Minimal FSMContext stand-in for unit tests."""

    def __init__(self, initial=None) -> None:
        self.data = dict(initial or {})

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)


class DummyBot:
    """Minimal bot mock with async delete_message."""

    def __init__(self) -> None:
        self.delete_message = AsyncMock()


def test_ui_cleanup_keeps_welcome() -> None:
    """Cleanup removes tracked messages while keeping welcome."""

    async def run_test() -> None:
        state = DummyState()
        await ui_register_message(state, 1, 10)
        await ui_register_message(state, 1, 11)
        await ui_register_message(state, 1, 12)
        await state.update_data(ui_welcome_message_id=11)

        bot = DummyBot()
        await ui_cleanup_to_context(bot, state, 1, "MAIN_MENU", keep_ids=[11])

        deleted_ids = {
            call.kwargs["message_id"] for call in bot.delete_message.call_args_list
        }
        assert deleted_ids == {10, 12}
        data = await state.get_data()
        assert data["ui_tracked_message_ids"] == [11]
        assert data["ui_message_ids"] == [11]

    asyncio.run(run_test())


def test_back_to_main_deletes_and_cleans(monkeypatch) -> None:
    """back_to_main deletes user message, cleans UI, and renders menu."""

    async def run_test() -> None:
        state = DummyState({"ui_welcome_message_id": 55})
        cleanup_mock = AsyncMock()
        set_screen_mock = AsyncMock()
        build_menu_mock = AsyncMock(return_value=MagicMock())

        monkeypatch.setattr("Bot.handlers.start.ui_cleanup_to_context", cleanup_mock)
        monkeypatch.setattr("Bot.handlers.start.ui_set_screen_message", set_screen_mock)
        monkeypatch.setattr(
            "Bot.handlers.start.build_main_menu_for_user", build_menu_mock
        )

        sent_message = SimpleNamespace(chat=SimpleNamespace(id=1), message_id=99)
        message = SimpleNamespace(
            chat=SimpleNamespace(id=1),
            from_user=SimpleNamespace(id=2),
            message_id=10,
            bot=SimpleNamespace(),
        )
        message.delete = AsyncMock()
        message.answer = AsyncMock(return_value=sent_message)

        await back_to_main(message, state)

        message.delete.assert_awaited_once()
        cleanup_mock.assert_awaited_once()
        _, kwargs = cleanup_mock.await_args
        assert kwargs["keep_ids"] == [55]
        build_menu_mock.assert_awaited_once_with(2)
        set_screen_mock.assert_awaited_once_with(state, 1, 99)

    asyncio.run(run_test())
