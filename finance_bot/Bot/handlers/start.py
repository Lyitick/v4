"""Handlers for start and cancel commands."""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from Bot.handlers.common import build_main_menu_for_user
from Bot.utils.ui_cleanup import (
    ui_cleanup_to_context,
    ui_set_screen_message,
    ui_set_welcome_message,
    ui_track_message,
)

LOGGER = logging.getLogger(__name__)

router = Router()


async def _handle_start_common(message: Message, state: FSMContext) -> None:
    """Shared start logic for /start and "Поехалиии" commands."""

    # ПРИВЕТСТВИЕ (PROTECTED)
    # Это сообщение защищено и НЕ должно удаляться массовыми чистками.
    # Автоматическое удаление запрещено. Удаление допускается только в отдельной задаче
    # после явного подтверждения пользователя.
    greeting = "Поработаем бл"
    greeting_message = await message.answer(greeting)
    await ui_set_welcome_message(
        state, greeting_message.chat.id, greeting_message.message_id
    )
    await ui_cleanup_to_context(message.bot, state, message.chat.id, "MAIN_MENU")
    sent = await message.answer(
        "Главное меню",
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
    await ui_set_screen_message(state, sent.chat.id, sent.message_id)
    LOGGER.info(
        "User %s started bot", message.from_user.id if message.from_user else "unknown"
    )


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command."""

    await ui_track_message(state, message.chat.id, message.message_id)
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        LOGGER.warning("Failed to delete /start message", exc_info=True)
    await _handle_start_common(message, state)


@router.message(F.text == "Поехалиии")
async def handle_poehali(message: Message, state: FSMContext) -> None:
    """Handle alternative start phrase."""

    await ui_track_message(state, message.chat.id, message.message_id)
    await _handle_start_common(message, state)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Handle /cancel command."""

    await ui_track_message(state, message.chat.id, message.message_id)
    await ui_cleanup_to_context(message.bot, state, message.chat.id, "MAIN_MENU")
    sent = await message.answer(
        "Операция отменена. Вы в главном меню.",
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
    await ui_set_screen_message(state, sent.chat.id, sent.message_id)
    LOGGER.info("User %s cancelled current operation", message.from_user.id if message.from_user else "unknown")


@router.message(F.text == "⏪ На главную")
async def back_to_main(message: Message, state: FSMContext) -> None:
    """Return user to main menu."""

    await ui_track_message(state, message.chat.id, message.message_id)
    await ui_cleanup_to_context(message.bot, state, message.chat.id, "MAIN_MENU")
    sent = await message.answer(
        "Главное меню",
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
    await ui_set_screen_message(state, sent.chat.id, sent.message_id)
    LOGGER.info("User %s returned to main menu", message.from_user.id if message.from_user else "unknown")
