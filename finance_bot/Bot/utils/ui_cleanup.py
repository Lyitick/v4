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
    await state.update_data(
        ui_chat_id=chat_id, ui_settings_mode_message_id=int(message_id)
    )


async def ui_set_screen_message(
    state: FSMContext, chat_id: int, message_id: int
) -> None:
    await state.update_data(ui_chat_id=chat_id, ui_screen_message_id=int(message_id))


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
    settings_mode_id = data.get("ui_settings_mode_message_id")
    screen_message_id = data.get("ui_screen_message_id")
    tracked_ids: List[int] = list(data.get("ui_tracked_message_ids") or [])

    keep_ids = {int(welcome_id)} if welcome_id else set()
    if context_name in {"SETTINGS_MENU", "SETTINGS_HOUSEHOLD_PAYMENTS"}:
        if settings_mode_id:
            keep_ids.add(int(settings_mode_id))

    delete_ids = [int(mid) for mid in tracked_ids]
    if settings_mode_id:
        delete_ids.append(int(settings_mode_id))
    if screen_message_id:
        delete_ids.append(int(screen_message_id))

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
        ui_screen_message_id=None,
    )


async def ui_cleanup_messages(bot: Bot, state: FSMContext, *args, **kwargs) -> None:
    data = await state.get_data()
    chat_id = kwargs.get("chat_id") or data.get("ui_chat_id")
    if chat_id is None:
        return
    await ui_cleanup_to_context(bot, state, int(chat_id), "MAIN_MENU")
