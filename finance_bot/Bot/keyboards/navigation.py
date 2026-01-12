"""Navigation inline keyboards."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from Bot.constants.ui_labels import NAV_BACK, NAV_HOME


def nav_back_home(back_cb: str, home_cb: str) -> InlineKeyboardMarkup:
    """Inline keyboard with Back and Home buttons."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=NAV_BACK, callback_data=back_cb),
                InlineKeyboardButton(text=NAV_HOME, callback_data=home_cb),
            ]
        ]
    )
