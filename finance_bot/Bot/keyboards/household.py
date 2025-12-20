"""Keyboards for household payments."""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def household_payments_answer_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard with Yes/No and Back options for household payments."""

    buttons = [
        [
            KeyboardButton(text="✅ Да"),
            KeyboardButton(text="❌ Нет"),
            KeyboardButton(text="⬅️ Назад"),
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False,
    )
