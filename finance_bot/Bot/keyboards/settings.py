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


def household_settings_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for household payments settings actions."""

    buttons = [
        [KeyboardButton(text="➕ Добавить"), KeyboardButton(text="➖ Удалить")],
        [KeyboardButton(text="🔄 Обнулить")],
        [KeyboardButton(text="⬅ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def household_payments_remove_reply_keyboard(
    items: list[dict],
) -> ReplyKeyboardMarkup:
    """Reply keyboard for removing household payments in settings."""

    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for item in items:
        title = str(item.get("text", "")).rstrip("?")
        amount = item.get("amount")
        label = f"{title} — {amount}" if amount is not None else title
        row.append(KeyboardButton(text=label))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text="⬅ Назад")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def household_payments_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for household payments settings."""

    inline_keyboard = [
        [InlineKeyboardButton(text="➕ Добавить платеж", callback_data="hp:add_payment")],
        [InlineKeyboardButton(text="➖ Удалить платеж", callback_data="hp:del_payment_menu")],
        [InlineKeyboardButton(text="🔄 Обнулить", callback_data="hp:reset_questions")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def household_payments_remove_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    """Inline keyboard for removing household payments in settings."""

    inline_keyboard: list[list[InlineKeyboardButton]] = []
    for item in items:
        title = str(item.get("text", "")).rstrip("?")
        amount = item.get("amount")
        label = f"{title} — {amount}" if amount is not None else title
        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"hp:del_payment:{item.get('code', '')}",
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
        [InlineKeyboardButton(text="🧺 БЫТ условия", callback_data="st:byt_rules")],
        [InlineKeyboardButton(text="🧾 Бытовые платежи", callback_data="st:household_payments")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def wishlist_settings_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for wishlist settings."""

    inline_keyboard = [
        [
            InlineKeyboardButton(text="➕ Категорию", callback_data="wl:add_cat"),
            InlineKeyboardButton(text="➖ Категорию", callback_data="wl:del_cat_menu"),
        ],
        [
            InlineKeyboardButton(text="⏳ Срок купленного", callback_data="wl:purchased_select_category"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def wishlist_categories_select_keyboard(
    categories: list[dict], action_prefix: str
) -> InlineKeyboardMarkup:
    """Inline keyboard for selecting wishlist category."""

    inline_keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for category in categories:
        button = InlineKeyboardButton(
            text=category.get("title", ""),
            callback_data=f"{action_prefix}:{category.get('id')}",
        )
        row.append(button)
        if len(row) == 2:
            inline_keyboard.append(row)
            row = []
    if row:
        inline_keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def wishlist_purchased_mode_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for selecting wishlist purchased mode."""

    inline_keyboard = [
        [InlineKeyboardButton(text="Всегда", callback_data="wl:purchased_mode:always")],
        [InlineKeyboardButton(text="Несколько дней", callback_data="wl:purchased_mode:days")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def byt_rules_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for BYT rules settings."""

    inline_keyboard = [
        [
            InlineKeyboardButton(
                text="🔁 Вкл/Выкл напоминания", callback_data="byt:toggle_enabled"
            ),
            InlineKeyboardButton(
                text="🔁 ОТЛОЖИТЬ Вкл/Выкл", callback_data="byt:toggle_defer"
            ),
        ],
        [
            InlineKeyboardButton(text="⏳ Макс. дни отложить", callback_data="byt:edit_max_defer_days"),
            InlineKeyboardButton(text="⏰ Таймер", callback_data="byt:timer_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def byt_timer_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for BYT timer settings."""

    inline_keyboard = [
        [
            InlineKeyboardButton(text="➕ Добавить время", callback_data="bt:add_time_hour"),
            InlineKeyboardButton(text="➖ Удалить время", callback_data="bt:del_time_menu"),
        ],
        [
            InlineKeyboardButton(text="🔁 Сбросить по умолчанию", callback_data="bt:reset_default"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def byt_timer_times_select_keyboard(times: list[dict], action_prefix: str) -> InlineKeyboardMarkup:
    """Inline keyboard for selecting BYT timer time."""

    inline_keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for timer in times:
        label = f"{int(timer.get('hour', 0)):02d}:{int(timer.get('minute', 0)):02d}"
        row.append(
            InlineKeyboardButton(text=label, callback_data=f"{action_prefix}:{timer.get('id')}")
        )
        if len(row) == 2:
            inline_keyboard.append(row)
            row = []
    if row:
        inline_keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def settings_back_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard with a single back button for settings mode."""

    buttons = [[KeyboardButton(text="Назад")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def income_settings_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for income settings actions."""

    inline_keyboard = [
        [
            InlineKeyboardButton(text="➕ Категорию", callback_data="inc:add"),
            InlineKeyboardButton(text="➖ Категорию", callback_data="inc:del_menu"),
        ],
        [
            InlineKeyboardButton(text="✏️ Проценты", callback_data="inc:pct_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def income_categories_select_keyboard(
    categories: list[dict], action_prefix: str
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

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def settings_stub_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for stub sections with back button."""

    return InlineKeyboardMarkup(inline_keyboard=[])
