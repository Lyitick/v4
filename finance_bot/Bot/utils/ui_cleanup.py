import logging
from typing import List

from aiogram import Bot
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from Bot.database.get_db import get_db
from Bot.utils.telegram_safe import (
    safe_delete_message,
    safe_edit_message_text,
    safe_send_message,
)

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

    data = await state.get_data()
    ids: List[int] = list(data.get("ui_protected_message_ids") or [])
    if message_id not in ids:
        ids.append(int(message_id))
    if len(ids) > 300:
        ids = ids[-300:]
    current_chat_id = data.get("ui_chat_id")
    await state.update_data(
        ui_chat_id=current_chat_id if current_chat_id is not None else chat_id,
        ui_protected_message_ids=ids,
    )


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
    state: FSMContext | None = None,
) -> bool:
    if state is not None:
        protected_ids = await ui_get_protected_ids(state)
        if int(message_id) in protected_ids:
            LOGGER.info("SKIP_DELETE_PROTECTED message_id=%s", message_id)
            return False
    return await safe_delete_message(
        bot,
        chat_id=chat_id,
        message_id=message_id,
        logger=LOGGER,
    )


async def ui_get_welcome_id(state: FSMContext) -> int | None:
    data = await state.get_data()
    welcome_id = data.get("ui_welcome_message_id")
    return int(welcome_id) if welcome_id is not None else None


async def ui_get_protected_ids(state: FSMContext) -> set[int]:
    welcome_id = await ui_get_welcome_id(state)
    if welcome_id is None:
        return set()
    return {int(welcome_id)}


async def ui_set_welcome_id(
    state: FSMContext, message_id: int, chat_id: int | None = None
) -> None:
    update = {"ui_welcome_message_id": int(message_id)}
    if chat_id is not None:
        update["ui_chat_id"] = int(chat_id)
    await state.update_data(**update)


async def ui_set_welcome_message(
    bot: Bot, state: FSMContext, chat_id: int, text: str
) -> int:
    welcome_id = await ui_get_welcome_id(state)
    if welcome_id is not None:
        edited = await safe_edit_message_text(
            bot,
            chat_id=chat_id,
            message_id=int(welcome_id),
            text=text,
            logger=LOGGER,
        )
        if edited:
            LOGGER.info("WELCOME reused (chat_id=%s, message_id=%s)", chat_id, welcome_id)
            return int(welcome_id)

    if welcome_id is None:
        db = get_db()
        persisted = db.get_welcome_message_id(chat_id)
        if persisted is not None:
            await ui_set_welcome_id(state, int(persisted), chat_id=chat_id)
            LOGGER.info("WELCOME reused (chat_id=%s, message_id=%s)", chat_id, persisted)
            return int(persisted)

    sent = await safe_send_message(bot, chat_id=chat_id, text=text, logger=LOGGER)
    if sent:
        await ui_set_welcome_id(state, int(sent.message_id), chat_id=chat_id)
        get_db().set_welcome_message_id(chat_id, int(sent.message_id))
        LOGGER.info("WELCOME created (chat_id=%s, message_id=%s)", chat_id, sent.message_id)
        return int(sent.message_id)
    return 0


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
    tracked_ids: List[int] = list(data.get("ui_tracked_message_ids") or [])
    protected_ids = await ui_get_protected_ids(state)
    extra_protected_ids: List[int] = list(data.get("ui_protected_message_ids") or [])
    keep_id_set = {int(item) for item in (keep_ids or []) if item is not None}
    for protected_id in extra_protected_ids:
        protected_ids.add(int(protected_id))
    keep_id_set.update(protected_ids)
    delete_ids = []
    for mid in tracked_ids:
        mid_int = int(mid)
        if mid_int in keep_id_set:
            continue
        delete_ids.append(mid_int)
    kept_ids = {mid for mid in (int(item) for item in tracked_ids) if mid in keep_id_set}
    deleted_count = 0
    for message_id in delete_ids:
        deleted = await ui_safe_delete_message(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            log_context=f"context={context_name}",
            state=state,
        )
        if deleted:
            deleted_count += 1

    LOGGER.info(
        "UI_CLEANUP context=%s deleted=%s kept=%s welcome_id=%s",
        context_name,
        deleted_count,
        len(kept_ids),
        await ui_get_welcome_id(state),
    )
    await state.update_data(
        ui_tracked_message_ids=list(
            {
                int(item)
                for item in (keep_ids or [])
                if item is not None
                and int(item) not in protected_ids
            }
        ),
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
    if screen_id is not None and not isinstance(
        reply_markup, (ReplyKeyboardMarkup, ReplyKeyboardRemove)
    ):
        edited = await safe_edit_message_text(
            bot,
            chat_id=chat_id,
            message_id=int(screen_id),
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            logger=LOGGER,
        )
        if edited:
            await ui_set_screen_message(state, chat_id, int(screen_id))
            return int(screen_id)
    sent = await safe_send_message(
        bot,
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        logger=LOGGER,
    )
    if sent:
        await ui_set_screen_message(state, chat_id, sent.message_id)
        return int(sent.message_id)
    return int(screen_id or 0)
