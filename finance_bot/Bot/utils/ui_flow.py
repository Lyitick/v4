import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

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
    ids = [int(item) for item in tracked]
    for message_id in ids:
        if greeting_id and message_id == greeting_id:
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
