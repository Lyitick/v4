"""Keyboard definitions."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from Bot.config.settings import get_settings
from Bot.constants.ui_labels import NAV_BACK, NAV_HOME


def main_menu_keyboard(
    show_household: bool = False,
    show_test_button: bool = False,
    show_settings: bool = True,
) -> ReplyKeyboardMarkup:
    """Create main menu keyboard."""

    buttons = [[KeyboardButton(text="Рассчитать доход")], [KeyboardButton(text="📋 Вишлист")]]

    webapp_url = get_settings().webapp_url
    if webapp_url:
        buttons.append([KeyboardButton(text="📱 Mini App", web_app=WebAppInfo(url=webapp_url))])

    if show_household:
        buttons.append([KeyboardButton(text="Бытовые платежи")])
    if show_settings:
        buttons.append([KeyboardButton(text="⚙️")])
    if show_test_button:
        buttons.append([KeyboardButton(text="Проверить напоминания")])  # TODO: удалить после тестов
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


def back_to_main_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard with back to main option."""

    buttons = [[KeyboardButton(text=NAV_HOME)]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def back_only_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard with a single back button."""

    buttons = [[KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_reply_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard for wishlist actions."""

    buttons = [
        [KeyboardButton(text="➕"), KeyboardButton(text="Купленное")],
        [KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_reply_keyboard_no_add() -> ReplyKeyboardMarkup:
    """Keyboard for wishlist actions without add button (+)."""

    buttons = [
        [KeyboardButton(text="Купленное")],
        [KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_categories_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    """Inline keyboard for wishlist categories."""

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
    """Inline keyboard for skipping wishlist URL input."""

    buttons = [[InlineKeyboardButton(text="скип", callback_data="wishlist_skip_url")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def purchase_confirmation_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard for confirming purchase suggestion."""

    buttons = [[KeyboardButton(text="✅ Купил"), KeyboardButton(text="🔄 Продолжить копить")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def income_confirm_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard with confirm income button."""

    buttons = [[InlineKeyboardButton(text="✅ Получено", callback_data="income_confirm")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
