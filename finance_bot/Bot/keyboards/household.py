"""Keyboards for household payments."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


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


def household_payments_inline_keyboard(show_back: bool) -> InlineKeyboardMarkup:
    """Inline keyboard with Yes/No/Back options for household payments."""

    buttons = [
        [
            InlineKeyboardButton(text="Да", callback_data="hh_pay:yes"),
            InlineKeyboardButton(text="Нет", callback_data="hh_pay:no"),
            InlineKeyboardButton(text="Назад", callback_data="hh_pay:back"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
