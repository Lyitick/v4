"""Handlers for start and cancel commands."""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from Bot.constants.ui import WELCOME_TEXT
from Bot.constants.ui_labels import NAV_HOME
from Bot.handlers.common import build_main_menu_for_user
from Bot.utils.ui_cleanup import (
    ui_cleanup_messages,
    ui_cleanup_to_context,
    ui_render_screen,
    ui_safe_delete_message,
    ui_set_welcome_message,
)

LOGGER = logging.getLogger(__name__)

router = Router()


async def _handle_start_common(message: Message, state: FSMContext) -> None:
    """Shared start logic for /start and "Поехалиии" commands."""

    # ПРИВЕТСТВИЕ (PROTECTED)
    # Это сообщение защищено и НЕ должно удаляться массовыми чистками.
    # Автоматическое удаление запрещено. Удаление допускается только в отдельной задаче
    # после явного подтверждения пользователя.
    # DO_NOT_DELETE_WELCOME_WITHOUT_USER_CONFIRMATION
    await ui_set_welcome_message(message.bot, state, message.chat.id, WELCOME_TEXT)
    await ui_cleanup_to_context(
        message.bot,
        state,
        message.chat.id,
        "MAIN_MENU",
    )
    await ui_render_screen(
        message.bot,
        state,
        message.chat.id,
        "Главное меню",
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
    LOGGER.info(
        "USER=%s ACTION=START STATE=%s META=-",
        message.from_user.id if message.from_user else "unknown",
        await state.get_state(),
    )


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command."""

    await ui_safe_delete_message(
        message.bot,
        chat_id=message.chat.id,
        message_id=message.message_id,
        log_context="cmd_start",
        state=state,
    )
    await _handle_start_common(message, state)


@router.message(F.text == "Поехалиии")
async def handle_poehali(message: Message, state: FSMContext) -> None:
    """Handle alternative start phrase."""

    await _handle_start_common(message, state)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Handle /cancel command."""

    await ui_cleanup_messages(message.bot, state, chat_id=message.chat.id)
    await state.clear()
    await ui_render_screen(
        message.bot,
        state,
        message.chat.id,
        "Операция отменена. Вы в главном меню.",
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
    LOGGER.info(
        "USER=%s ACTION=CANCEL STATE=%s META=-",
        message.from_user.id if message.from_user else "unknown",
        await state.get_state(),
    )


@router.message(F.text.in_({NAV_HOME, "⏪ На главную", "🏠 На главную"}))
async def back_to_main(message: Message, state: FSMContext) -> None:
    """Return user to main menu."""

    deleted = await ui_safe_delete_message(
        message.bot,
        chat_id=message.chat.id,
        message_id=message.message_id,
        log_context="back_to_main_user_msg",
        state=state,
    )
    LOGGER.info(
        "USER=%s ACTION=BACK_TO_MAIN_DELETE STATE=%s META=user_msg_deleted=%s",
        message.from_user.id if message.from_user else "unknown",
        await state.get_state(),
        str(deleted).lower(),
    )
    await ui_cleanup_to_context(
        message.bot,
        state,
        message.chat.id,
        "MAIN_MENU",
    )
    await ui_render_screen(
        message.bot,
        state,
        message.chat.id,
        "Главное меню",
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
    LOGGER.info(
        "USER=%s ACTION=BACK_TO_MAIN STATE=%s META=-",
        message.from_user.id if message.from_user else "unknown",
        await state.get_state(),
    )
