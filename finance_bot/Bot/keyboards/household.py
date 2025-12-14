"""Keyboards for household payments."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def household_yes_no_keyboard(question_code: str) -> InlineKeyboardMarkup:
    """Inline keyboard with Yes/No options for household payments."""

    buttons = [
        [
            InlineKeyboardButton(
                text="Да", callback_data=f"household:{question_code}:yes"
            ),
            InlineKeyboardButton(
                text="Нет", callback_data=f"household:{question_code}:no"
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
