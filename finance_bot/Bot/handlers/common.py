"""Common handlers and fallbacks."""
import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from Bot.keyboards.main import main_menu_keyboard

LOGGER = logging.getLogger(__name__)

router = Router()


async def delete_welcome_message_if_exists(message: Message, state: FSMContext) -> None:
    """Compatibility no-op; welcome messages are kept."""

    return None


@router.message()
async def fallback_handler(message: Message, state: FSMContext) -> None:
    """Handle unmatched messages."""

    await delete_welcome_message_if_exists(message, state)
    current_state = await state.get_state()
    LOGGER.info("Fallback triggered. User: %s State: %s Text: %s", message.from_user.id, current_state, message.text)
    await message.answer(
        "Не понял сообщение. Пожалуйста, пользуйся кнопками или командами.",
        reply_markup=main_menu_keyboard(),
    )
