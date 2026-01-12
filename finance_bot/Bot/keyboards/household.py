"""Keyboards for household payments."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from Bot.constants.ui_labels import NAV_BACK, NAV_HOME


def household_payments_answer_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard with Yes/No and Back options for household payments."""

    buttons = [
        [
            KeyboardButton(text="✅ Да"),
            KeyboardButton(text="❌ Нет"),
            KeyboardButton(text=NAV_BACK),
            KeyboardButton(text=NAV_HOME),
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def household_payments_inline_keyboard(
    show_back: bool, question_code: str | None = None
) -> InlineKeyboardMarkup:
    """Inline keyboard with Yes/No/Back options for household payments."""

    suffix = f":{question_code}" if question_code else ""
    buttons = [
        [
            InlineKeyboardButton(text="Да", callback_data=f"hh_pay:yes{suffix}"),
            InlineKeyboardButton(text="Нет", callback_data=f"hh_pay:no{suffix}"),
        ]
    ]
    if show_back:
        buttons[0].append(
            InlineKeyboardButton(text=NAV_BACK, callback_data=f"hh_pay:back{suffix}")
        )
    buttons.append(
        [InlineKeyboardButton(text=NAV_HOME, callback_data="nav:home")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
