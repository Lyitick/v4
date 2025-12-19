"""Handlers for start and cancel commands."""
import logging
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from Bot.handlers.common import build_main_menu_for_user
from Bot.keyboards.main import back_to_main_keyboard
from Bot.utils.ui_cleanup import ui_register_message, ui_register_protected_message

LOGGER = logging.getLogger(__name__)

router = Router()


async def _handle_start_common(message: Message, state: FSMContext) -> None:
    """Shared start logic for /start and "Поехалиии" commands."""

    await state.clear()
    greeting = "Поработаем бл"
    sent = await message.answer(
        greeting, reply_markup=await build_main_menu_for_user(message.from_user.id)
    )
    await ui_register_protected_message(state, sent.chat.id, sent.message_id)
    LOGGER.info("User %s started bot", message.from_user.id if message.from_user else "unknown")


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command."""

    await _handle_start_common(message, state)
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        LOGGER.warning("Failed to delete /start message", exc_info=True)


@router.message(F.text == "Поехалиии")
async def handle_poehali(message: Message, state: FSMContext) -> None:
    """Handle alternative start phrase."""

    await _handle_start_common(message, state)
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        LOGGER.warning("Failed to delete 'Поехалиии' message", exc_info=True)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Handle /cancel command."""

    await state.clear()
    sent = await message.answer(
        "Операция отменена. Вы в главном меню.",
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
    await ui_register_message(state, sent.chat.id, sent.message_id)
    LOGGER.info("User %s cancelled current operation", message.from_user.id if message.from_user else "unknown")


@router.message(F.text == "⏪ На главную")
async def back_to_main(message: Message, state: FSMContext) -> None:
    """Return user to main menu."""

    await state.clear()
    sent = await message.answer(
        "Главное меню",
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
    await ui_register_message(state, sent.chat.id, sent.message_id)
    LOGGER.info("User %s returned to main menu", message.from_user.id if message.from_user else "unknown")
