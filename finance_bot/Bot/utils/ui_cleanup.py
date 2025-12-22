import logging
from typing import Iterable, List, Optional

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
    if len(ids) > 300:
        ids = ids[-300:]
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
    bot: Bot, state: FSMContext, chat_id: int, text: str
) -> int:
    data = await state.get_data()
    welcome_id = data.get("ui_welcome_message_id")
    if welcome_id is not None:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(welcome_id),
                text=text,
            )
            LOGGER.info(
                "Reused welcome message (chat_id=%s, message_id=%s)",
                chat_id,
                welcome_id,
            )
            return int(welcome_id)
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                LOGGER.info(
                    "Welcome message already up to date (chat_id=%s, message_id=%s)",
                    chat_id,
                    welcome_id,
                )
                return int(welcome_id)
            LOGGER.warning(
                "Failed to edit welcome message (chat_id=%s, message_id=%s): %s",
                chat_id,
                welcome_id,
                exc,
            )
        except Exception:
            LOGGER.warning(
                "Unexpected error editing welcome message (chat_id=%s, message_id=%s)",
                chat_id,
                welcome_id,
                exc_info=True,
            )
    sent = await bot.send_message(chat_id=chat_id, text=text)
    await state.update_data(
        ui_chat_id=chat_id, ui_welcome_message_id=int(sent.message_id)
    )
    LOGGER.info(
        "Created welcome message (chat_id=%s, message_id=%s)",
        chat_id,
        sent.message_id,
    )
    if welcome_id is not None and int(welcome_id) != int(sent.message_id):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=int(welcome_id))
        except TelegramBadRequest as exc:
            LOGGER.warning(
                "Failed to delete previous welcome message (chat_id=%s, message_id=%s): %s",
                chat_id,
                welcome_id,
                exc,
            )
        except Exception:
            LOGGER.warning(
                "Unexpected error deleting previous welcome message (chat_id=%s, message_id=%s)",
                chat_id,
                welcome_id,
                exc_info=True,
            )
    return int(sent.message_id)


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
    await ui_register_message(state, chat_id, message_id)


async def ui_cleanup_to_context(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    context_name: str,
    keep_ids: List[int] | None = None,
) -> None:
    data = await state.get_data()
    welcome_id = data.get("ui_welcome_message_id")
    tracked_ids: List[int] = list(data.get("ui_tracked_message_ids") or [])
    legacy_ids: List[int] = list(data.get("ui_message_ids") or [])
    combined_ids = list(dict.fromkeys([*legacy_ids, *tracked_ids]))

    keep_id_set = {int(welcome_id)} if welcome_id else set()
    if keep_ids:
        keep_id_set.update(int(item) for item in keep_ids if item is not None)
    delete_ids = [int(mid) for mid in tracked_ids if int(mid) not in keep_id_set]

    for message_id in delete_ids:
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
            )

    remaining_ids = [mid for mid in combined_ids if int(mid) in keep_id_set]
    await state.update_data(
        ui_tracked_message_ids=[],
    )


async def ui_cleanup_messages(bot: Bot, state: FSMContext, *args, **kwargs) -> None:
    data = await state.get_data()
    chat_id = kwargs.get("chat_id") or data.get("ui_chat_id")
    if chat_id is None:
        return
    await ui_cleanup_to_context(bot, state, int(chat_id), "MAIN_MENU")
