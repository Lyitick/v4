"""Common handlers and fallbacks."""
import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards.main import main_menu_keyboard

LOGGER = logging.getLogger(__name__)

router = Router()


@router.message()
async def fallback_handler(message: Message, state: FSMContext) -> None:
    """Handle unmatched messages."""

    current_state = await state.get_state()
    LOGGER.info("Fallback triggered. User: %s State: %s Text: %s", message.from_user.id, current_state, message.text)
    await message.answer(
        "Не понял сообщение. Пожалуйста, пользуйся кнопками или командами.",
        reply_markup=main_menu_keyboard(),
    )
