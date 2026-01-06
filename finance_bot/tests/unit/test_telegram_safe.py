"""Tests for telegram_safe utilities."""
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("aiogram")

from aiogram.exceptions import TelegramNetworkError  # noqa: E402

from Bot.utils.telegram_safe import safe_edit_message_text  # noqa: E402


@pytest.mark.asyncio
async def test_safe_edit_message_text_retries_network_error() -> None:
    """Network errors should trigger retries for edit operations."""

    bot = AsyncMock()
    bot.edit_message_text = AsyncMock(
        side_effect=[TelegramNetworkError("fail"), None]
    )

    result = await safe_edit_message_text(
        bot,
        chat_id=123,
        message_id=456,
        text="hello",
    )

    assert result is True
    assert bot.edit_message_text.call_count == 2
