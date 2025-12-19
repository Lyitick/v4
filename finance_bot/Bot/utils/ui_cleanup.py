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


async def ui_register_protected_message(
    state: FSMContext, chat_id: int, message_id: int
) -> None:
    """Track a UI message id that should never be deleted."""

    data = await state.get_data()
    ids: List[int] = list(data.get("ui_protected_message_ids") or [])
    if message_id not in ids:
        ids.append(int(message_id))
    await state.update_data(ui_chat_id=chat_id, ui_protected_message_ids=ids)


async def ui_register_user_message(state: FSMContext, chat_id: int, message_id: int) -> None:
    """Track a user message id for later cleanup."""

    data = await state.get_data()
    ids: List[int] = list(data.get("user_message_ids") or [])
    if message_id not in ids:
        ids.append(int(message_id))
    await state.update_data(ui_chat_id=chat_id, user_message_ids=ids)


async def ui_cleanup_messages(bot: Bot, state: FSMContext) -> None:
    """Delete tracked UI messages, ignoring errors."""

    data = await state.get_data()
    chat_id = data.get("ui_chat_id")
    user_message_ids: List[int] = list(data.get("user_message_ids") or [])
    protected_message_ids: set[int] = {
        int(mid) for mid in list(data.get("ui_protected_message_ids") or [])
    }
    if chat_id is None:
        await state.update_data(ui_message_ids=[], user_message_ids=[])
        return

    def _log_bad_request(exc: TelegramBadRequest, message_id: int) -> None:
        description = str(exc)
        ignored = (
            "message to delete not found",
            "message can't be deleted",
            "MESSAGE_ID_INVALID",
            "chat not found",
            "bot was blocked by the user",
        )
        if any(text in description for text in ignored):
            LOGGER.warning(
                "Failed to delete message (chat_id=%s, message_id=%s): %s",
                chat_id,
                message_id,
                description,
            )
        else:
            LOGGER.exception(
                "Unexpected TelegramBadRequest deleting message (chat_id=%s, message_id=%s)",
                chat_id,
                message_id,
                exc_info=True,
            )

    processed: set[int] = set()
    user_ids = sorted({int(mid) for mid in user_message_ids}, reverse=True)
    ui_ids = sorted({int(mid) for mid in list(data.get("ui_message_ids") or [])}, reverse=True)

    for message_id in user_ids:
        if message_id in protected_message_ids:
            continue
        processed.add(message_id)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except TelegramBadRequest as exc:
            _log_bad_request(exc, message_id)
        except Exception:
            LOGGER.exception(
                "Unexpected error deleting message (chat_id=%s, message_id=%s)",
                chat_id,
                message_id,
                exc_info=True,
            )

    for message_id in ui_ids:
        if message_id in processed:
            continue
        if message_id in protected_message_ids:
            continue
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except TelegramBadRequest as exc:
            _log_bad_request(exc, message_id)
        except Exception:
            LOGGER.exception(
                "Unexpected error deleting UI message (chat_id=%s, message_id=%s)",
                chat_id,
                message_id,
                exc_info=True,
            )

    await state.update_data(ui_message_ids=[], user_message_ids=[])
