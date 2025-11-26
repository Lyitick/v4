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


def back_to_main_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard with back to main option."""

    buttons = [[KeyboardButton(text="⏪ На главную")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_reply_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard for wishlist actions."""

    buttons = [[KeyboardButton(text="➕"), KeyboardButton(text="Купленное")], [KeyboardButton(text="⏪ На главную")]]
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
