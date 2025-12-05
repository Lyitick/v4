"""Common handlers and fallbacks."""
import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from Bot.keyboards.main import main_menu_keyboard

LOGGER = logging.getLogger(__name__)

router = Router()


async def delete_welcome_message_if_exists(message: Message, state: FSMContext) -> None:
    """Delete stored welcome message if present in FSM."""

    data = await state.get_data()
    welcome_message_id = data.get("welcome_message_id")
    if welcome_message_id is None:
        return

    try:
        await message.bot.delete_message(
            chat_id=message.chat.id,
            message_id=welcome_message_id,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed to delete welcome message %s: %s", welcome_message_id, exc)
    finally:
        await state.update_data(welcome_message_id=None)


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
