"""Handlers for start and cancel commands."""
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from Bot.handlers.common import build_main_menu_for_user
from Bot.utils.ui_cleanup import (
    ui_cleanup_messages,
    ui_cleanup_to_context,
    ui_render_screen,
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
    await ui_set_welcome_message(message.bot, state, message.chat.id, greeting)
    await ui_cleanup_to_context(
        message.bot, state, message.chat.id, "MAIN_MENU"
    )
    await ui_render_screen(
        message.bot,
        state,
        message.chat.id,
        "Главное меню",
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
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
    await ui_cleanup_messages(message.bot, state, chat_id=message.chat.id)
    await state.clear()
    await ui_render_screen(
        message.bot,
        state,
        message.chat.id,
        "Операция отменена. Вы в главном меню.",
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
    LOGGER.info("User %s cancelled current operation", message.from_user.id if message.from_user else "unknown")


@router.message(F.text == "⏪ На главную")
async def back_to_main(message: Message, state: FSMContext) -> None:
    """Return user to main menu."""

    await ui_track_message(state, message.chat.id, message.message_id)
    try:
        await message.delete()
        LOGGER.info(
            "Deleted back_to_main user message (chat_id=%s, message_id=%s)",
            message.chat.id,
            message.message_id,
        )
    except TelegramBadRequest as exc:
        LOGGER.warning(
            "Failed to delete back_to_main user message (chat_id=%s, message_id=%s): %s",
            message.chat.id,
            message.message_id,
            exc,
        )
    except Exception:
        LOGGER.warning(
            "Unexpected error deleting back_to_main user message (chat_id=%s, message_id=%s)",
            message.chat.id,
            message.message_id,
            exc_info=True,
        )
    await ui_cleanup_messages(message.bot, state, chat_id=message.chat.id)
    await state.clear()
    await ui_render_screen(
        message.bot,
        state,
        message.chat.id,
        "Главное меню",
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
    LOGGER.info("User %s returned to main menu", message.from_user.id if message.from_user else "unknown")
