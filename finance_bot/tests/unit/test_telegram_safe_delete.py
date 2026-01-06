"""Tests for safe_delete_message."""

from unittest.mock import AsyncMock
import sys
import types
from pathlib import Path

import asyncio
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "aiogram" not in sys.modules:
    aiogram = types.ModuleType("aiogram")
    exceptions = types.ModuleType("aiogram.exceptions")
    types_mod = types.ModuleType("aiogram.types")
    filters = types.ModuleType("aiogram.filters")
    fsm = types.ModuleType("aiogram.fsm")
    fsm_context = types.ModuleType("aiogram.fsm.context")

    class TelegramBadRequest(Exception):
        pass

    class TelegramNetworkError(Exception):
        pass

    exceptions.TelegramBadRequest = TelegramBadRequest
    exceptions.TelegramNetworkError = TelegramNetworkError

    class ReplyKeyboardMarkup:
        pass

    class ReplyKeyboardRemove:
        pass

    class Message:
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

    class DummyRouter:
        def message(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    class Bot:
        pass

    class DummyF:
        class _Field:
            def __eq__(self, other):
                return ("eq", other)

        text = _Field()

    class FSMContext:
        pass

    class Command:
        def __init__(self, *args, **kwargs):
            return None

    types_mod.ReplyKeyboardMarkup = ReplyKeyboardMarkup
    types_mod.ReplyKeyboardRemove = ReplyKeyboardRemove
    types_mod.Message = Message
    types_mod.InlineKeyboardButton = InlineKeyboardButton
    types_mod.InlineKeyboardMarkup = InlineKeyboardMarkup
    types_mod.KeyboardButton = KeyboardButton
    aiogram.exceptions = exceptions
    aiogram.types = types_mod
    aiogram.Router = DummyRouter
    aiogram.F = DummyF()
    aiogram.Bot = Bot
    fsm_context.FSMContext = FSMContext
    fsm.context = fsm_context
    aiogram.fsm = fsm
    aiogram.filters = filters
    filters.Command = Command
    sys.modules["aiogram"] = aiogram
    sys.modules["aiogram.exceptions"] = exceptions
    sys.modules["aiogram.types"] = types_mod
    sys.modules["aiogram.filters"] = filters
    sys.modules["aiogram.fsm"] = fsm
    sys.modules["aiogram.fsm.context"] = fsm_context

if "aiohttp" not in sys.modules:
    aiohttp = types.ModuleType("aiohttp")

    class ClientConnectionError(Exception):
        pass

    class ClientOSError(Exception):
        pass

    aiohttp.ClientConnectionError = ClientConnectionError
    aiohttp.ClientOSError = ClientOSError
    sys.modules["aiohttp"] = aiohttp

from aiogram.exceptions import TelegramBadRequest  # noqa: E402

from Bot.utils.telegram_safe import safe_delete_message  # noqa: E402


def test_safe_delete_message_not_found() -> None:
    async def run() -> None:
        bot = AsyncMock()
        bot.delete_message = AsyncMock(
            side_effect=TelegramBadRequest("message to delete not found")
        )

        result = await safe_delete_message(bot, chat_id=1, message_id=2)

        assert result is False
        assert bot.delete_message.call_count == 1

    asyncio.run(run())
