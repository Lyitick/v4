"""Calculator keyboard definitions."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def income_calculator_keyboard() -> ReplyKeyboardMarkup:
    """Общая цифровая клавиатура для ввода сумм."""

    keyboard = [
        [KeyboardButton(text="7"), KeyboardButton(text="8"), KeyboardButton(text="9")],
        [KeyboardButton(text="4"), KeyboardButton(text="5"), KeyboardButton(text="6")],
        [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3")],
        [
            KeyboardButton(text="Очистить"),
            KeyboardButton(text="0"),
            KeyboardButton(text="✅ Газ"),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
    )
