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
    ui = dict(data.get("ui") or {})
    ui.setdefault("greeting_id", None)
    ui.setdefault("current_screen", None)
    ui.setdefault("screen_message_id", None)
    ui.setdefault("tracked_ids", [])
    return ui


async def ui_set_greeting(state: FSMContext, message_id: int) -> None:
    ui = await ui_get(state)
    if ui.get("greeting_id") is not None:
        return
    # greeting_id не удаляем никогда
    ui["greeting_id"] = int(message_id)
    await state.update_data(ui=ui)


async def ui_track(
    state: FSMContext, message_id: int, kind: str, screen: str | None
) -> None:
    ui = await ui_get(state)
    tracked: list[dict[str, Any]] = list(ui.get("tracked_ids") or [])
    tracked.append({"id": int(message_id), "kind": kind, "screen": screen})
    if len(tracked) > 300:
        tracked = tracked[-300:]
    ui["tracked_ids"] = tracked
    await state.update_data(ui=ui)


async def ui_set_screen_message(
    state: FSMContext, screen: str, message_id: int
) -> None:
    ui = await ui_get(state)
    previous = ui.get("screen_message_id")
    greeting_id = ui.get("greeting_id")
    if previous and previous != greeting_id:
        tracked: list[dict[str, Any]] = list(ui.get("tracked_ids") or [])
        tracked.append({"id": int(previous), "kind": "ui", "screen": ui.get("current_screen")})
        if len(tracked) > 300:
            tracked = tracked[-300:]
        ui["tracked_ids"] = tracked
    ui["screen_message_id"] = int(message_id)
    ui["current_screen"] = screen
    await state.update_data(ui=ui)


async def ui_cleanup_for_transition(
    bot: Bot, state: FSMContext, chat_id: int, keep_greeting: bool = True
) -> None:
    ui = await ui_get(state)
    greeting_id = ui.get("greeting_id") if keep_greeting else None
    tracked: list[dict[str, Any]] = list(ui.get("tracked_ids") or [])
    screen_message_id = ui.get("screen_message_id")
    ids = [int(item.get("id")) for item in tracked]
    if screen_message_id:
        ids.append(int(screen_message_id))
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
            )
        except Exception:
            LOGGER.warning(
                "Unexpected error deleting message (chat_id=%s, message_id=%s)",
                chat_id,
                message_id,
                exc_info=True,
            )
    ui["tracked_ids"] = []
    ui["screen_message_id"] = None
    await state.update_data(ui=ui)


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
