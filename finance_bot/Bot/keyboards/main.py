"""Keyboard definitions."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Create main menu keyboard."""

    buttons = [[KeyboardButton(text="Рассчитать доход")], [KeyboardButton(text="📋 Вишлист")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def yes_no_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard with Yes/No options."""

    buttons = [[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def yes_no_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard with Yes/No options to avoid opening system keyboard."""

    buttons = [
        [
            InlineKeyboardButton(text="Да", callback_data="confirm_yes"),
            InlineKeyboardButton(text="Нет", callback_data="confirm_no"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def income_calculator_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard with digit buttons for income input."""

    buttons = [
        [KeyboardButton(text="7"), KeyboardButton(text="8"), KeyboardButton(text="9")],
        [KeyboardButton(text="4"), KeyboardButton(text="5"), KeyboardButton(text="6")],
        [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3")],
        [
            KeyboardButton(text="Очистить"),
            KeyboardButton(text="0"),
            KeyboardButton(text="✅ Газ"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=False)


def back_to_main_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard with back to main option."""

    buttons = [[KeyboardButton(text="⏪ На главную")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_reply_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard for wishlist actions."""

    buttons = [[KeyboardButton(text="➕"), KeyboardButton(text="Купленное")], [KeyboardButton(text="⏪ На главную")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_reply_keyboard_no_add() -> ReplyKeyboardMarkup:
    """Keyboard for wishlist actions without add button (+)."""

    buttons = [
        [KeyboardButton(text="Купленное")],
        [KeyboardButton(text="⏪ На главную")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_categories_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for wishlist categories."""

    buttons = [
        [InlineKeyboardButton(text="🛠 инвестиции в работу", callback_data="wishlist_cat_tools")],
        [InlineKeyboardButton(text="💸 вклад в себя", callback_data="wishlist_cat_currency")],
        [InlineKeyboardButton(text="✨ кайфы", callback_data="wishlist_cat_magic")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def wishlist_url_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for skipping wishlist URL input."""

    buttons = [[InlineKeyboardButton(text="Скип", callback_data="wishlist_skip_url")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def purchase_confirmation_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard for confirming purchase suggestion."""

    buttons = [[KeyboardButton(text="✅ Купил"), KeyboardButton(text="🔄 Продолжить копить")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)
