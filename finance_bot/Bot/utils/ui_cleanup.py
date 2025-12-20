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
    current_chat_id = data.get("ui_chat_id")
    await state.update_data(
        ui_chat_id=current_chat_id if current_chat_id is not None else chat_id,
        ui_message_ids=ids,
    )


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

    await ui_register_message(state, chat_id, message_id)


async def ui_cleanup_messages(bot: Bot, state: FSMContext) -> None:
    """Delete tracked UI messages, ignoring errors."""

    data = await state.get_data()
    chat_id = data.get("ui_chat_id")
    protected_message_ids: set[int] = {
        int(mid) for mid in list(data.get("ui_protected_message_ids") or [])
    }
    # protected_message_ids содержит приветствие и другие защищенные сообщения,
    # которые нельзя удалять массовыми чистками UI.
    if chat_id is None:
        await state.update_data(ui_message_ids=[], user_message_ids=[])
        return

    legacy_user_ids: List[int] = list(data.get("user_message_ids") or [])
    ui_ids = list(data.get("ui_message_ids") or [])
    all_ids = sorted({int(mid) for mid in (ui_ids + legacy_user_ids)}, reverse=True)

    for message_id in all_ids:
        if message_id in protected_message_ids:
            continue
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except TelegramBadRequest as exc:
            LOGGER.debug(
                "Failed to delete message (chat_id=%s, message_id=%s): %s",
                chat_id,
                message_id,
                exc,
                exc_info=True,
            )
        except Exception:
            LOGGER.debug(
                "Unexpected error deleting message (chat_id=%s, message_id=%s)",
                chat_id,
                message_id,
                exc_info=True,
            )

    await state.update_data(ui_message_ids=[], user_message_ids=[])
