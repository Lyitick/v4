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
    """Do not track user messages for later cleanup."""

    data = await state.get_data()
    if data.get("ui_chat_id") is None:
        await state.update_data(ui_chat_id=chat_id)


async def ui_safe_delete_message(
    bot: Bot,
    chat_id: int,
    message_id: int,
    log_context: str | None = None,
) -> bool:
    context_label = f" ({log_context})" if log_context else ""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except TelegramBadRequest as exc:
        text = str(exc).lower()
        if (
            "message to delete not found" in text
            or "message can't be deleted" in text
            or "message can’t be deleted" in text
        ):
            LOGGER.debug(
                "UI safe delete skipped%s (chat_id=%s, message_id=%s): %s",
                context_label,
                chat_id,
                message_id,
                exc,
            )
            return False
        LOGGER.error(
            "UI safe delete failed%s (chat_id=%s, message_id=%s): %s",
            context_label,
            chat_id,
            message_id,
            exc,
            exc_info=True,
        )
        return False
    except Exception:  # noqa: BLE001
        LOGGER.error(
            "UI safe delete error%s (chat_id=%s, message_id=%s)",
            context_label,
            chat_id,
            message_id,
            exc_info=True,
        )
        return False


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
            LOGGER.info("WELCOME reused (chat_id=%s, message_id=%s)", chat_id, welcome_id)
            return int(welcome_id)
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                LOGGER.info(
                    "WELCOME reused (chat_id=%s, message_id=%s)", chat_id, welcome_id
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
    LOGGER.info("WELCOME recreated (chat_id=%s, message_id=%s)", chat_id, sent.message_id)
    # DO NOT DELETE WITHOUT USER CONFIRMATION.
    return int(sent.message_id)


async def ui_set_settings_mode_message(
    state: FSMContext, chat_id: int, message_id: int
) -> None:
    await ui_register_message(state, chat_id, message_id)


async def ui_set_screen_message(
    state: FSMContext, chat_id: int, message_id: int
) -> None:
    await ui_register_message(state, chat_id, message_id)
    await state.update_data(ui_screen_message_id=int(message_id), ui_chat_id=chat_id)


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
    keep_id_set = {int(welcome_id)} if welcome_id else set()
    if keep_ids:
        keep_id_set.update(int(item) for item in keep_ids if item is not None)
    delete_ids = [int(mid) for mid in tracked_ids if int(mid) not in keep_id_set]
    deleted_count = 0
    for message_id in delete_ids:
        deleted = await ui_safe_delete_message(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            log_context=f"context={context_name}",
        )
        if deleted:
            deleted_count += 1

    remaining_ids: List[int] = []
    for message_id in tracked_ids:
        normalized = int(message_id)
        if normalized in keep_id_set and normalized not in remaining_ids:
            remaining_ids.append(normalized)
    if keep_ids:
        for message_id in keep_ids:
            normalized = int(message_id)
            if normalized in keep_id_set and normalized not in remaining_ids:
                remaining_ids.append(normalized)
    if welcome_id is not None:
        normalized = int(welcome_id)
        if normalized not in remaining_ids:
            remaining_ids.append(normalized)

    LOGGER.info(
        "UI_CLEANUP context=%s deleted=%s kept=%s",
        context_name,
        deleted_count,
        len(remaining_ids),
    )
    await state.update_data(
        ui_tracked_message_ids=remaining_ids,
    )


async def ui_cleanup_messages(bot: Bot, state: FSMContext, *args, **kwargs) -> None:
    data = await state.get_data()
    chat_id = kwargs.get("chat_id") or data.get("ui_chat_id")
    if chat_id is None:
        return
    await ui_cleanup_to_context(bot, state, int(chat_id), "MAIN_MENU")


async def ui_render_screen(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    text: str,
    reply_markup=None,
    parse_mode: str | None = None,
) -> int:
    data = await state.get_data()
    screen_id = data.get("ui_screen_message_id")
    if screen_id is not None:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(screen_id),
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            await ui_set_screen_message(state, chat_id, int(screen_id))
            return int(screen_id)
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                await ui_set_screen_message(state, chat_id, int(screen_id))
                return int(screen_id)
            LOGGER.warning(
                "Failed to edit screen message (chat_id=%s, message_id=%s): %s",
                chat_id,
                screen_id,
                exc,
            )
        except Exception:
            LOGGER.warning(
                "Unexpected error editing screen message (chat_id=%s, message_id=%s)",
                chat_id,
                screen_id,
                exc_info=True,
            )
    sent = await bot.send_message(
        chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode
    )
    await ui_set_screen_message(state, chat_id, sent.message_id)
    return int(sent.message_id)
