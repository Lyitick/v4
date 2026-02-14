"""Keyboard builders for scheduled reminders."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from Bot.constants.ui_labels import (
    NAV_BACK,
    REM_CATEGORY_FOOD,
    REM_CATEGORY_HABITS,
    REM_CATEGORY_MOTIVATION,
    REM_CATEGORY_WISHLIST,
    REM_FOOD_ADD_MEAL,
    REM_FOOD_ADD_SUPP,
    REM_FOOD_DELETE,
    REM_FOOD_STATS,
    REM_HABIT_ADD,
    REM_HABIT_DELETE,
    REM_HABIT_STATS,
    REM_MOTIV_ADD,
    REM_MOTIV_DELETE,
    REM_MOTIV_SCHEDULE,
    REM_MOTIV_TOGGLE,
    REM_WISH_ADD,
    REM_WISH_DELETE,
    REM_WISH_STATS,
)


# ------------------------------------------------------------------ #
#  Settings keyboards (Reply)                                         #
# ------------------------------------------------------------------ #


def reminder_categories_keyboard() -> ReplyKeyboardMarkup:
    """Settings sub-menu: pick a reminder category to configure."""
    buttons = [
        [KeyboardButton(text=REM_CATEGORY_MOTIVATION), KeyboardButton(text=REM_CATEGORY_HABITS)],
        [KeyboardButton(text=REM_CATEGORY_FOOD), KeyboardButton(text=REM_CATEGORY_WISHLIST)],
        [KeyboardButton(text=NAV_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def motivation_settings_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for motivation settings screen."""
    buttons = [
        [KeyboardButton(text=REM_MOTIV_ADD), KeyboardButton(text=REM_MOTIV_DELETE)],
        [KeyboardButton(text=REM_MOTIV_SCHEDULE), KeyboardButton(text=REM_MOTIV_TOGGLE)],
        [KeyboardButton(text=NAV_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def food_settings_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for food & supplements settings screen."""
    buttons = [
        [KeyboardButton(text=REM_FOOD_ADD_MEAL), KeyboardButton(text=REM_FOOD_ADD_SUPP)],
        [KeyboardButton(text=REM_FOOD_DELETE), KeyboardButton(text=REM_FOOD_STATS)],
        [KeyboardButton(text=NAV_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def habit_settings_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for habits settings screen."""
    buttons = [
        [KeyboardButton(text=REM_HABIT_ADD), KeyboardButton(text=REM_HABIT_DELETE)],
        [KeyboardButton(text=REM_HABIT_STATS)],
        [KeyboardButton(text=NAV_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def wishlist_settings_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard for wishlist reminder settings screen."""
    buttons = [
        [KeyboardButton(text=REM_WISH_ADD), KeyboardButton(text=REM_WISH_DELETE)],
        [KeyboardButton(text=REM_WISH_STATS)],
        [KeyboardButton(text=NAV_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# ------------------------------------------------------------------ #
#  Settings keyboards (Inline)                                        #
# ------------------------------------------------------------------ #


def habit_list_inline_keyboard(
    habits: list[dict], action_prefix: str = "rem:habit_toggle"
) -> InlineKeyboardMarkup:
    """Inline keyboard listing habits for toggle/select."""
    rows: list[list[InlineKeyboardButton]] = []
    for habit in habits:
        enabled = bool(habit.get("is_enabled", 1))
        icon = "✅" if enabled else "❌"
        label = f"{icon} {habit.get('title', '')}"
        rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"{action_prefix}:{habit.get('id')}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def habit_delete_inline_keyboard(
    habits: list[dict],
) -> InlineKeyboardMarkup:
    """Inline keyboard listing habits for deletion."""
    rows: list[list[InlineKeyboardButton]] = []
    for habit in habits:
        rows.append([
            InlineKeyboardButton(
                text=f"🗑 {habit.get('title', '')}",
                callback_data=f"rem:habit_del:{habit.get('id')}",
            )
        ])
    rows.append([InlineKeyboardButton(text=NAV_BACK, callback_data="rem:habits_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def habit_times_inline_keyboard(
    reminder_id: int, times: list[str]
) -> InlineKeyboardMarkup:
    """Inline keyboard showing schedule times for a habit."""
    rows: list[list[InlineKeyboardButton]] = []
    for t in times:
        rows.append([
            InlineKeyboardButton(
                text=f"🕐 {t}",
                callback_data=f"rem:habit_time_del:{reminder_id}:{t}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text="➕ Время", callback_data=f"rem:habit_time_add:{reminder_id}"),
    ])
    rows.append([InlineKeyboardButton(text=NAV_BACK, callback_data="rem:habits_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def food_list_inline_keyboard(
    items: list[dict], action_prefix: str = "rem:food_toggle"
) -> InlineKeyboardMarkup:
    """Inline keyboard listing food/supplement items for toggle/select."""
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        enabled = bool(item.get("is_enabled", 1))
        icon = "✅" if enabled else "❌"
        sub_type = item.get("text", "meal")
        emoji = "🍽" if sub_type == "meal" else "💊"
        label = f"{icon} {emoji} {item.get('title', '')}"
        rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"{action_prefix}:{item.get('id')}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def food_delete_inline_keyboard(
    items: list[dict],
) -> InlineKeyboardMarkup:
    """Inline keyboard listing food/supplement items for deletion."""
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        sub_type = item.get("text", "meal")
        emoji = "🍽" if sub_type == "meal" else "💊"
        rows.append([
            InlineKeyboardButton(
                text=f"🗑 {emoji} {item.get('title', '')}",
                callback_data=f"rem:food_del:{item.get('id')}",
            )
        ])
    rows.append([InlineKeyboardButton(text=NAV_BACK, callback_data="rem:food_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wishlist_list_inline_keyboard(
    items: list[dict], action_prefix: str = "rem:wish_toggle"
) -> InlineKeyboardMarkup:
    """Inline keyboard listing wishlist reminders for toggle."""
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        enabled = bool(item.get("is_enabled", 1))
        icon = "✅" if enabled else "❌"
        label = f"{icon} 📋 {item.get('title', '')}"
        rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"{action_prefix}:{item.get('id')}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wishlist_delete_inline_keyboard(
    items: list[dict],
) -> InlineKeyboardMarkup:
    """Inline keyboard listing wishlist reminders for deletion."""
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        rows.append([
            InlineKeyboardButton(
                text=f"🗑 📋 {item.get('title', '')}",
                callback_data=f"rem:wish_del:{item.get('id')}",
            )
        ])
    rows.append([InlineKeyboardButton(text=NAV_BACK, callback_data="rem:wish_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def motivation_delete_inline_keyboard(
    items: list[dict],
) -> InlineKeyboardMarkup:
    """Inline keyboard listing motivation content for deletion."""
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        media = item.get("media_type")
        emoji = {"photo": "🖼", "video": "🎬", "animation": "🎞"}.get(media or "", "📝")
        rows.append([
            InlineKeyboardButton(
                text=f"🗑 {emoji} {item.get('title', '')}",
                callback_data=f"rem:motiv_del:{item.get('id')}",
            )
        ])
    rows.append([InlineKeyboardButton(text=NAV_BACK, callback_data="rem:motiv_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def motivation_schedule_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for motivation schedule type selection."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ Интервал (каждые N мин)", callback_data="rem:motiv_sched:interval")],
        [InlineKeyboardButton(text="🕐 Конкретное время", callback_data="rem:motiv_sched:times")],
        [InlineKeyboardButton(text=NAV_BACK, callback_data="rem:motiv_back")],
    ])


# ------------------------------------------------------------------ #
#  Runtime reminder keyboards (Inline, sent with reminder message)    #
# ------------------------------------------------------------------ #


def reminder_action_keyboard_habits(event_id: int) -> InlineKeyboardMarkup:
    """Inline buttons for a habits/food reminder message (no Back/Home)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сделано", callback_data=f"rem:done:{event_id}"),
            InlineKeyboardButton(text="⏳ Отложить", callback_data=f"rem:snooze_menu:{event_id}"),
            InlineKeyboardButton(text="🙅 Пропущено", callback_data=f"rem:skip:{event_id}"),
        ]
    ])


def reminder_action_keyboard_motivation(event_id: int) -> InlineKeyboardMarkup:
    """Inline button for a motivation reminder message."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Услышал 👂", callback_data=f"rem:seen:{event_id}")]
    ])


def snooze_duration_keyboard(event_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard for snooze duration selection."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="+15 мин", callback_data=f"rem:snooze:15:{event_id}"),
            InlineKeyboardButton(text="+1 час", callback_data=f"rem:snooze:60:{event_id}"),
        ],
        [
            InlineKeyboardButton(text="+3 часа", callback_data=f"rem:snooze:180:{event_id}"),
            InlineKeyboardButton(text="+1 день", callback_data=f"rem:snooze:1440:{event_id}"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"rem:snooze_back:{event_id}")],
    ])
