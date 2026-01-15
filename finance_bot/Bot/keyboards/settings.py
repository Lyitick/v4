"""Settings keyboards."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from Bot.constants.ui_labels import (
    NAV_BACK,
    NAV_HOME,
    WISHLIST_DEBIT_CATEGORY_BUTTON,
    WISHLIST_DEBIT_CATEGORY_NONE,
    WISHLIST_BYT_CATEGORY_BUTTON,
)
from Bot.keyboards.navigation import nav_back_home


def settings_menu_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for settings menu."""

    buttons = [
        [KeyboardButton(text="⚙️ Бытовые платежи ⚙️")],
        [KeyboardButton(text=NAV_HOME)],
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
        [KeyboardButton(text="💰 Категория списания"), KeyboardButton(text="🧹 Обнулить")],
        [KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def household_debit_category_select_reply_keyboard(
    categories: list[dict],
) -> ReplyKeyboardMarkup:
    """Reply keyboard for selecting household debit category."""

    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for category in categories:
        row.append(KeyboardButton(text=category.get("title", "")))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


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
    rows.append([KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)])
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
        [InlineKeyboardButton(text="Напоминания", callback_data="st:byt_rules")],
        [InlineKeyboardButton(text="🧾 Бытовые платежи", callback_data="st:household_payments")],
        [InlineKeyboardButton(text="Таймзона", callback_data="st:timezone")],
        [InlineKeyboardButton(text=NAV_HOME, callback_data="nav:home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def settings_home_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for settings home screen."""

    buttons = [
        [KeyboardButton(text="📊 Доход"), KeyboardButton(text="🧾 Вишлист")],
        [KeyboardButton(text="Напоминания"), KeyboardButton(text="🧾 Бытовые платежи")],
        [KeyboardButton(text="Таймзона")],
        [KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


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
        [InlineKeyboardButton(text="💰 Категория списания", callback_data="wl:debit_category_menu")],
    ]
    inline_keyboard.extend(nav_back_home("st:wishlist", "nav:home").inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def wishlist_settings_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for wishlist settings actions."""

    buttons = [
        [
            KeyboardButton(text="➕ Добавить категорию вишлиста"),
            KeyboardButton(text="➖ Удалить категорию вишлиста"),
        ],
        [KeyboardButton(text="🕒 Настроить купленное")],
        [KeyboardButton(text=WISHLIST_DEBIT_CATEGORY_BUTTON)],
        [KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_categories_select_reply_keyboard(categories: list[dict]) -> ReplyKeyboardMarkup:
    """Reply keyboard for selecting wishlist category."""

    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for category in categories:
        row.append(KeyboardButton(text=category.get("title", "")))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def wishlist_purchased_mode_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for selecting wishlist purchased mode."""

    buttons = [
        [KeyboardButton(text="Всегда")],
        [KeyboardButton(text="Настроить дни")],
        [KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_debit_category_select_reply_keyboard(
    categories: list[dict],
) -> ReplyKeyboardMarkup:
    """Reply keyboard for selecting wishlist debit category."""

    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for category in categories:
        row.append(KeyboardButton(text=category.get("title", "")))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text=WISHLIST_DEBIT_CATEGORY_NONE)])
    rows.append([KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def wishlist_byt_category_select_reply_keyboard(
    categories: list[dict],
) -> ReplyKeyboardMarkup:
    """Reply keyboard for selecting BYT wishlist category."""

    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for category in categories:
        row.append(KeyboardButton(text=category.get("title", "")))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def byt_category_toggle_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    """Inline keyboard for toggling BYT categories."""

    inline_keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for category in categories:
        enabled = bool(category.get("enabled", 0))
        label = f"{'✅' if enabled else '❌'} {category.get('title', '')}"
        next_state = 0 if enabled else 1
        row.append(
            InlineKeyboardButton(
                text=label,
                callback_data=f"byt:category_toggle:{category.get('id')}:{next_state}",
            )
        )
        if len(row) == 2:
            inline_keyboard.append(row)
            row = []
    if row:
        inline_keyboard.append(row)
    inline_keyboard.append(
        [
            InlineKeyboardButton(text=NAV_BACK, callback_data="st:byt_rules"),
            InlineKeyboardButton(text=NAV_HOME, callback_data="nav:home"),
        ]
    )
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
    inline_keyboard.extend(nav_back_home("st:byt_rules", "nav:home").inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def byt_timer_categories_inline_keyboard(
    categories: list[dict], action_prefix: str
) -> InlineKeyboardMarkup:
    """Inline keyboard for selecting BYT timer category."""

    inline_keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for category in categories:
        enabled = bool(category.get("enabled", 0))
        label = f"{'✅' if enabled else '❌'} {category.get('title', '')}"
        row.append(
            InlineKeyboardButton(
                text=label,
                callback_data=f"{action_prefix}:{category.get('id')}",
            )
        )
        if len(row) == 2:
            inline_keyboard.append(row)
            row = []
    if row:
        inline_keyboard.append(row)
    inline_keyboard.append(
        [
            InlineKeyboardButton(text=NAV_BACK, callback_data="st:byt_rules"),
            InlineKeyboardButton(text=NAV_HOME, callback_data="nav:home"),
        ]
    )
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
                text="Выбор категории для напоминаний", callback_data="wl:byt_category_menu"
            )
        ],
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
            InlineKeyboardButton(text="⏰ Время напоминаний", callback_data="byt:timer_menu"),
        ],
    ]
    inline_keyboard.extend(nav_back_home("st:home", "nav:home").inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def byt_rules_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for BYT rules settings."""

    buttons = [
        [KeyboardButton(text=WISHLIST_BYT_CATEGORY_BUTTON)],
        [
            KeyboardButton(text="🔁 Вкл/Выкл напоминания"),
            KeyboardButton(text="🔁 ОТЛОЖИТЬ Вкл/Выкл"),
        ],
        [KeyboardButton(text="⏰ Время напоминаний")],
        [KeyboardButton(text="⏳ Макс. дни отложить")],
        [KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def byt_timer_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for BYT timer settings."""

    inline_keyboard = [
        [
            InlineKeyboardButton(text="➕ Добавить время", callback_data="bt:add_time"),
            InlineKeyboardButton(text="🗑 Удалить время", callback_data="bt:del_time_menu"),
        ],
        [
            InlineKeyboardButton(text=NAV_BACK, callback_data="byt:timer_menu"),
            InlineKeyboardButton(text=NAV_HOME, callback_data="nav:home"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def byt_timer_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for BYT timer settings."""

    buttons = [
        [
            KeyboardButton(text="➕ Добавить время"),
            KeyboardButton(text="🗑 Удалить время"),
        ],
        [KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def byt_timer_times_select_reply_keyboard(times: list[dict]) -> ReplyKeyboardMarkup:
    """Reply keyboard for selecting BYT timer time."""

    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for timer in times:
        if timer.get("time_hhmm"):
            label = str(timer.get("time_hhmm"))
        else:
            label = f"{int(timer.get('hour', 0)):02d}:{int(timer.get('minute', 0)):02d}"
        row.append(KeyboardButton(text=label))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def byt_timer_times_select_keyboard(times: list[dict], action_prefix: str) -> InlineKeyboardMarkup:
    """Inline keyboard for selecting BYT timer time."""

    inline_keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for timer in times:
        if timer.get("time_hhmm"):
            label = str(timer.get("time_hhmm"))
            callback_value = label
        else:
            label = f"{int(timer.get('hour', 0)):02d}:{int(timer.get('minute', 0)):02d}"
            callback_value = str(timer.get("id"))
        row.append(
            InlineKeyboardButton(text=label, callback_data=f"{action_prefix}:{callback_value}")
        )
        if len(row) == 2:
            inline_keyboard.append(row)
            row = []
    if row:
        inline_keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def settings_back_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard with a single back button for settings mode."""

    buttons = [[KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)]]
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


def income_settings_reply_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for income settings actions."""

    buttons = [
        [
            KeyboardButton(text="➕ Добавить категорию дохода"),
            KeyboardButton(text="➖ Удалить категорию дохода"),
        ],
        [KeyboardButton(text="⚙️ Проценты доходов")],
        [KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def income_categories_select_reply_keyboard(
    categories: list[dict],
) -> ReplyKeyboardMarkup:
    """Reply keyboard for selecting income category."""

    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for category in categories:
        title = category.get("title", "")
        percent = category.get("percent", 0)
        row.append(KeyboardButton(text=f"{title} — {percent}%"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text=NAV_BACK), KeyboardButton(text=NAV_HOME)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


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


def timezone_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for timezone selection."""

    inline_keyboard = [
        [
            InlineKeyboardButton(text="Europe/Amsterdam", callback_data="st:tz:Europe/Amsterdam"),
            InlineKeyboardButton(text="Europe/Moscow", callback_data="st:tz:Europe/Moscow"),
        ],
        [
            InlineKeyboardButton(text="Asia/Tashkent", callback_data="st:tz:Asia/Tashkent"),
            InlineKeyboardButton(text="UTC", callback_data="st:tz:UTC"),
        ],
    ]
    inline_keyboard.extend(nav_back_home("st:home", "nav:home").inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def settings_stub_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for stub sections with back button."""

    return InlineKeyboardMarkup(inline_keyboard=[])
