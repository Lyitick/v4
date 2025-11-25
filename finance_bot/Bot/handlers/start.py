"""Handlers for start and cancel commands."""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from Bot.keyboards.main import back_to_main_keyboard, main_menu_keyboard

LOGGER = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command."""

    await state.clear()
    greeting = (
        "Привет! Я финансовый помощник. Помогу распределить доход, вести накопления "
        "и управлять твоим вишлистом."
    )
    await message.answer(greeting, reply_markup=main_menu_keyboard())
    LOGGER.info("User %s started bot", message.from_user.id if message.from_user else "unknown")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Handle /cancel command."""

    await state.clear()
    await message.answer("Операция отменена. Вы в главном меню.", reply_markup=main_menu_keyboard())
    LOGGER.info("User %s cancelled current operation", message.from_user.id if message.from_user else "unknown")


@router.message(F.text == "⏪ На главную")
async def back_to_main(message: Message, state: FSMContext) -> None:
    """Return user to main menu."""

    await state.clear()
    await message.answer("Главное меню", reply_markup=main_menu_keyboard())
    LOGGER.info("User %s returned to main menu", message.from_user.id if message.from_user else "unknown")
