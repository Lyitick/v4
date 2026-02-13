"""Keyboard definitions."""
from typing import Any

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from Bot.constants.ui_labels import NAV_BACK, NAV_HOME


def main_menu_keyboard(
    show_household: bool = False,
    show_settings: bool = True,
) -> ReplyKeyboardMarkup:
    """Create main menu keyboard.

    Args:
        show_household: Whether to show household payments button.
        show_settings: Whether to show settings button.

    Returns:
        Configured reply keyboard markup.
    """
    buttons = [[KeyboardButton(text="Рассчитать доход")], [KeyboardButton(text="📋 Вишлист")]]

    if show_household:
        buttons.append([KeyboardButton(text="Бытовые платежи")])
    if show_settings:
        buttons.append([KeyboardButton(text="⚙️")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def yes_no_keyboard() -> ReplyKeyboardMarkup:
    """Create keyboard with Yes/No options.

    Returns:
        Reply keyboard markup with Да/Нет buttons.
    """
    buttons = [[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def yes_no_inline_keyboard() -> InlineKeyboardMarkup:
    """Create inline keyboard with Yes/No options to avoid opening system keyboard.

    Returns:
        Inline keyboard markup with Да/Нет buttons.
    """
    buttons = [
        [
            InlineKeyboardButton(text="Да", callback_data="confirm_yes"),
            InlineKeyboardButton(text="Нет", callback_data="confirm_no"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_to_main_keyboard() -> ReplyKeyboardMarkup:
    """Create keyboard with back to main option.

    Returns:
        Reply keyboard markup with home navigation button.
    """
    buttons = [[KeyboardButton(text=NAV_HOME)]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def back_only_keyboard() -> ReplyKeyboardMarkup:
    """Create keyboard with back and home buttons.

    Returns:
        Reply keyboard markup with back and home navigation buttons.
    """
    buttons = [[KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_reply_keyboard() -> ReplyKeyboardMarkup:
    """Create keyboard for wishlist actions.

    Returns:
        Reply keyboard markup with add, purchased, back, and home buttons.
    """
    buttons = [
        [KeyboardButton(text="➕"), KeyboardButton(text="Купленное")],
        [KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_reply_keyboard_no_add() -> ReplyKeyboardMarkup:
    """Create keyboard for wishlist actions without add button.

    Returns:
        Reply keyboard markup with purchased, back, and home buttons.
    """
    buttons = [
        [KeyboardButton(text="Купленное")],
        [KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_categories_keyboard(categories: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    """Create inline keyboard for wishlist categories.

    Args:
        categories: List of category dictionaries with 'id' and 'title' keys.

    Returns:
        Inline keyboard markup with category buttons arranged in rows of 2.
    """
    inline_keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for category in categories:
        row.append(
            InlineKeyboardButton(
                text=category.get("title", ""),
                callback_data=f"wlcat:{category.get('id')}",
            )
        )
        if len(row) == 2:
            inline_keyboard.append(row)
            row = []
    if row:
        inline_keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def wishlist_url_keyboard() -> InlineKeyboardMarkup:
    """Create inline keyboard for skipping wishlist URL input.

    Returns:
        Inline keyboard markup with skip button.
    """
    buttons = [[InlineKeyboardButton(text="скип", callback_data="wishlist_skip_url")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def purchase_confirmation_keyboard() -> ReplyKeyboardMarkup:
    """Create keyboard for confirming purchase suggestion.

    Returns:
        Reply keyboard markup with purchase confirmation buttons.
    """
    buttons = [[KeyboardButton(text="✅ Купил"), KeyboardButton(text="🔄 Продолжить копить")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def income_confirm_keyboard() -> InlineKeyboardMarkup:
    """Create inline keyboard with confirm income button.

    Returns:
        Inline keyboard markup with income confirmation button.
    """
    buttons = [[InlineKeyboardButton(text="✅ Получено", callback_data="income_confirm")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
