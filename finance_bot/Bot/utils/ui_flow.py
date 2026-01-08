import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from Bot.utils.telegram_safe import safe_delete_message
from Bot.utils.ui_cleanup import ui_get_protected_ids
LOGGER = logging.getLogger(__name__)


async def ui_get(state: FSMContext) -> dict[str, Any]:
    data = await state.get_data()
    return {
        "greeting_id": data.get("ui_welcome_message_id"),
        "tracked_ids": list(data.get("ui_tracked_message_ids") or []),
    }


async def ui_set_greeting(state: FSMContext, message_id: int) -> None:
    ui = await ui_get(state)
    if ui.get("greeting_id") is not None:
        return
    # greeting_id не удаляем никогда
    await state.update_data(ui_welcome_message_id=int(message_id))


async def ui_track(
    state: FSMContext, message_id: int, kind: str, screen: str | None
) -> None:
    ui = await ui_get(state)
    tracked: list[int] = list(ui.get("tracked_ids") or [])
    tracked.append(int(message_id))
    if len(tracked) > 300:
        tracked = tracked[-300:]
    await state.update_data(ui_tracked_message_ids=tracked)


async def ui_set_screen_message(
    state: FSMContext, screen: str, message_id: int
) -> None:
    await ui_track(state, message_id, kind="ui", screen=screen)


async def ui_cleanup_for_transition(
    bot: Bot, state: FSMContext, chat_id: int, keep_greeting: bool = True
) -> None:
    ui = await ui_get(state)
    greeting_id = ui.get("greeting_id") if keep_greeting else None
    tracked: list[int] = list(ui.get("tracked_ids") or [])
    data = await state.get_data()
    protected_ids = await ui_get_protected_ids(state)
    extra_protected_ids = {
        int(item)
        for item in (data.get("ui_protected_message_ids") or [])
        if item is not None
    }
    protected_ids.update(extra_protected_ids)
    ids = [int(item) for item in tracked]
    for message_id in ids:
        if greeting_id and message_id == greeting_id:
            continue
        if message_id in protected_ids:
            continue
        await safe_delete_message(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            logger=LOGGER,
        )
    await state.update_data(ui_tracked_message_ids=[])


async def ui_transition(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    new_screen: str,
    send_screen: Callable[[], Awaitable[Message]],
) -> Message:
    await ui_cleanup_for_transition(bot, state, chat_id, keep_greeting=True)
    sent = await send_screen()
    await ui_set_screen_message(state, new_screen, sent.message_id)
    return sent
