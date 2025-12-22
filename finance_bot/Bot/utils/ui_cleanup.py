import logging
from typing import List

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

LOGGER = logging.getLogger(__name__)


async def ui_register_message(state: FSMContext, chat_id: int, message_id: int) -> None:
    """Track a UI message id for later cleanup."""

    data = await state.get_data()
    ids: List[int] = list(data.get("ui_tracked_message_ids") or [])
    if message_id not in ids:
        ids.append(int(message_id))
    current_chat_id = data.get("ui_chat_id")
    await state.update_data(
        ui_chat_id=current_chat_id if current_chat_id is not None else chat_id,
        ui_tracked_message_ids=ids,
    )


async def ui_register_protected_message(
    state: FSMContext, chat_id: int, message_id: int
) -> None:
    """Track a UI message id that should never be deleted."""

    await ui_register_message(state, chat_id, message_id)


async def ui_register_user_message(state: FSMContext, chat_id: int, message_id: int) -> None:
    """Track a user message id for later cleanup."""

    await ui_register_message(state, chat_id, message_id)


async def ui_set_welcome_message(
    state: FSMContext, chat_id: int, message_id: int
) -> None:
    data = await state.get_data()
    if data.get("ui_welcome_message_id") is not None:
        return
    # НЕ УДАЛЯТЬ БЕЗ ПОДТВЕРЖДЕНИЯ ТИМЛИДА
    await state.update_data(ui_chat_id=chat_id, ui_welcome_message_id=int(message_id))


async def ui_set_settings_mode_message(
    state: FSMContext, chat_id: int, message_id: int
) -> None:
    await ui_register_message(state, chat_id, message_id)


async def ui_set_screen_message(
    state: FSMContext, chat_id: int, message_id: int
) -> None:
    await ui_register_message(state, chat_id, message_id)


async def ui_track_message(
    state: FSMContext, chat_id: int, message_id: int
) -> None:
    data = await state.get_data()
    ids: List[int] = list(data.get("ui_tracked_message_ids") or [])
    ids.append(int(message_id))
    if len(ids) > 300:
        ids = ids[-300:]
    await state.update_data(ui_chat_id=chat_id, ui_tracked_message_ids=ids)


async def ui_cleanup_to_context(
    bot: Bot, state: FSMContext, chat_id: int, context_name: str
) -> None:
    data = await state.get_data()
    welcome_id = data.get("ui_welcome_message_id")
    tracked_ids: List[int] = list(data.get("ui_tracked_message_ids") or [])

    keep_ids = {int(welcome_id)} if welcome_id else set()
    delete_ids = [int(mid) for mid in tracked_ids]

    for message_id in delete_ids:
        if message_id in keep_ids:
            continue
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except TelegramBadRequest as exc:
            LOGGER.warning(
                "Failed to delete message (chat_id=%s, message_id=%s): %s",
                chat_id,
                message_id,
                exc,
                exc_info=True,
            )
        except Exception:
            LOGGER.warning(
                "Unexpected error deleting message (chat_id=%s, message_id=%s)",
                chat_id,
                message_id,
                exc_info=True,
            )

    await state.update_data(
        ui_tracked_message_ids=[],
    )


async def ui_cleanup_messages(bot: Bot, state: FSMContext, *args, **kwargs) -> None:
    data = await state.get_data()
    chat_id = kwargs.get("chat_id") or data.get("ui_chat_id")
    if chat_id is None:
        return
    await ui_cleanup_to_context(bot, state, int(chat_id), "MAIN_MENU")
