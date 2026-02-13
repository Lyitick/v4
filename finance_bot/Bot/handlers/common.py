"""Common handlers and fallbacks."""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardMarkup

from Bot.config.settings import get_settings
from Bot.database.get_db import get_db
from Bot.keyboards.main import main_menu_keyboard
from Bot.utils.datetime_utils import current_month_str
from Bot.utils.messages import HINT_USE_BUTTONS
from Bot.utils.ui_cleanup import ui_register_message, ui_cleanup_messages
from Bot.utils.time import now_for_user
from Bot.utils.user_id import get_user_id_from_message, get_user_id_from_callback

LOGGER = logging.getLogger(__name__)

router = Router()
DEFAULT_TZ = (
    get_settings().timezone.key
    if hasattr(get_settings().timezone, "key")
    else str(get_settings().timezone)
)


async def build_main_menu_for_user(user_id: int) -> ReplyKeyboardMarkup:
    """Construct main menu keyboard with optional household button.

    Args:
        user_id: Telegram user ID.

    Returns:
        Configured reply keyboard markup for main menu.
    """
    db = get_db()
    from Bot.handlers.household_payments import reset_household_cycle_if_needed

    await reset_household_cycle_if_needed(user_id, db)
    month = current_month_str(now_for_user(db, user_id, DEFAULT_TZ))
    show_household = await db.should_show_household_payments_button(user_id, month)
    return main_menu_keyboard(
        show_household=show_household,
        show_settings=True,
    )


async def delete_welcome_message_if_exists(message: Message, state: FSMContext) -> None:
    """Compatibility no-op; welcome messages are kept."""

    return None


@router.callback_query(F.data == "nav:home")
async def navigate_home(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle Home navigation via inline buttons.

    Args:
        callback: Telegram callback query.
        state: FSM context.
    """
    await ui_cleanup_messages(callback.bot, state)
    await state.clear()
    if callback.message:
        sent = await callback.message.answer(
            "Главное меню.",
            reply_markup=await build_main_menu_for_user(get_user_id_from_callback(callback)),
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)


@router.message()
async def fallback_handler(message: Message, state: FSMContext) -> None:
    """Handle unmatched messages.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    await delete_welcome_message_if_exists(message, state)
    current_state = await state.get_state()
    user_id = get_user_id_from_message(message)
    LOGGER.debug("Fallback triggered. User: %s State: %s Text: %s", user_id, current_state, message.text)
    sent = await message.answer(
        HINT_USE_BUTTONS,
        reply_markup=await build_main_menu_for_user(user_id),
    )
    await ui_register_message(state, sent.chat.id, sent.message_id)
