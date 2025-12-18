import logging
from typing import List

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

LOGGER = logging.getLogger(__name__)


async def ui_register_message(state: FSMContext, chat_id: int, message_id: int) -> None:
    """Track a UI message id for later cleanup."""

    data = await state.get_data()
    ids: List[int] = list(data.get("ui_message_ids") or [])
    if message_id not in ids:
        ids.append(int(message_id))
    await state.update_data(ui_chat_id=chat_id, ui_message_ids=ids)


async def ui_cleanup_messages(bot: Bot, state: FSMContext) -> None:
    """Delete tracked UI messages, ignoring errors."""

    data = await state.get_data()
    chat_id = data.get("ui_chat_id")
    message_ids: List[int] = list(data.get("ui_message_ids") or [])
    if chat_id is None or not message_ids:
        await state.update_data(ui_message_ids=[])
        return

    for message_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=int(message_id))
        except TelegramBadRequest:
            LOGGER.warning(
                "Failed to delete UI message (chat_id=%s, message_id=%s)",
                chat_id,
                message_id,
                exc_info=True,
            )
        except Exception:
            LOGGER.warning(
                "Unexpected error deleting UI message (chat_id=%s, message_id=%s)",
                chat_id,
                message_id,
                exc_info=True,
            )
    await state.update_data(ui_message_ids=[])
