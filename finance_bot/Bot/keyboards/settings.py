"""Settings keyboards."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def settings_menu_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for settings menu."""

    buttons = [
        [KeyboardButton(text="⚙️ Бытовые платежи ⚙️")],
        [KeyboardButton(text="⏪ На главную")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def household_settings_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for household settings actions."""

    buttons = [
        [
            InlineKeyboardButton(text="➕", callback_data="hh_set:add"),
            InlineKeyboardButton(text="➖", callback_data="hh_set:del"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def household_remove_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    """Inline keyboard for removing household items."""

    inline_keyboard: list[list[InlineKeyboardButton]] = []
    for item in items:
        title = str(item.get("text", "")).rstrip("?")
        amount = item.get("amount")
        label = f"{title} — {amount}" if amount is not None else title
        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"hh_set:remove:{item.get('code', '')}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def settings_home_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for settings home screen."""

    inline_keyboard = [
        [
            InlineKeyboardButton(text="📊 Доход", callback_data="st:income"),
            InlineKeyboardButton(text="🧾 Вишлист", callback_data="st:wishlist"),
        ],
        [
            InlineKeyboardButton(text="🧺 БЫТ условия", callback_data="st:byt_rules"),
            InlineKeyboardButton(text="⏰ Таймер БЫТ", callback_data="st:byt_timer"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="st:back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def income_settings_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for income settings actions."""

    inline_keyboard = [
        [
            InlineKeyboardButton(text="➕ Категорию", callback_data="inc:add"),
            InlineKeyboardButton(text="➖ Категорию", callback_data="inc:del_menu"),
        ],
        [
            InlineKeyboardButton(text="✏️ Проценты", callback_data="inc:pct_menu"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="st:home"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def income_categories_select_keyboard(
    categories: list[dict], action_prefix: str, back_callback: str
) -> InlineKeyboardMarkup:
    """Inline keyboard for selecting an income category."""

    inline_keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for category in categories:
        button = InlineKeyboardButton(
            text=f"{category['title']} ({category['percent']}%)",
            callback_data=f"{action_prefix}:{category['id']}",
        )
        row.append(button)
        if len(row) == 2:
            inline_keyboard.append(row)
            row = []
    if row:
        inline_keyboard.append(row)

    inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def settings_stub_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for stub sections with back button."""

    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="st:home")]]
    )
