"""Common handlers and fallbacks."""
import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup

from Bot.config import settings
from Bot.database.crud import FinanceDatabase
from Bot.keyboards.main import main_menu_keyboard
from Bot.utils.datetime_utils import current_month_str
from Bot.utils.ui_cleanup import ui_register_message

LOGGER = logging.getLogger(__name__)

router = Router()


async def build_main_menu_for_user(user_id: int) -> ReplyKeyboardMarkup:
    """Construct main menu keyboard with optional household button."""

    db = FinanceDatabase()
    from Bot.handlers.household_payments import reset_household_cycle_if_needed

    await reset_household_cycle_if_needed(user_id, db)
    month = current_month_str()
    show_household = await db.should_show_household_payments_button(user_id, month)
    show_test_button = user_id == settings.ADMIN_ID
    return main_menu_keyboard(
        show_household=show_household,
        show_test_button=show_test_button,
        show_settings=True,
    )


async def delete_welcome_message_if_exists(message: Message, state: FSMContext) -> None:
    """Compatibility no-op; welcome messages are kept."""

    return None


@router.message()
async def fallback_handler(message: Message, state: FSMContext) -> None:
    """Handle unmatched messages."""

    await delete_welcome_message_if_exists(message, state)
    current_state = await state.get_state()
    LOGGER.debug("Fallback triggered. User: %s State: %s Text: %s", message.from_user.id, current_state, message.text)
    sent = await message.answer(
        "Не понял сообщение. Пожалуйста, пользуйся кнопками или командами.",
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
    await ui_register_message(state, sent.chat.id, sent.message_id)
