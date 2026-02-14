"""Rendering helpers for scheduled reminders."""

from __future__ import annotations


_CATEGORY_EMOJI = {
    "habits": "🏃",
    "food": "🍽",
    "motivation": "💡",
    "wishlist": "📋",
}


def format_reminder_text(reminder: dict) -> str:
    """Format a reminder message for sending to user."""
    category = reminder.get("category", "")
    title = reminder.get("title", "")
    text = reminder.get("text", "")
    emoji = _CATEGORY_EMOJI.get(category, "🔔")
    lines = [f"{emoji} <b>{title}</b>"]
    if text:
        lines.append("")
        lines.append(text)
    return "\n".join(lines)


def format_habits_settings_text(habits: list[dict]) -> str:
    """Format the habits settings screen."""
    if not habits:
        return "🏃 <b>ПРИВЫЧКИ</b>\n\nПривычек пока нет.\nНажми «➕ Добавить привычку» чтобы создать."
    lines = ["🏃 <b>ПРИВЫЧКИ</b>", ""]
    for i, h in enumerate(habits, 1):
        enabled = bool(h.get("is_enabled", 1))
        icon = "✅" if enabled else "❌"
        lines.append(f"{i}. {icon} {h.get('title', '—')}")
    lines.append("")
    lines.append("Нажми на привычку чтобы вкл/выкл.")
    return "\n".join(lines)


def format_habit_stats_text(
    habits: list[dict], stats: list[dict], date_str: str
) -> str:
    """Format habit statistics for a date."""
    if not habits:
        return "📊 Нет привычек для статистики."
    stat_row = next(
        (s for s in stats if s.get("category") == "habits"), None
    )
    shown = stat_row.get("shown_count", 0) if stat_row else 0
    done = stat_row.get("done_count", 0) if stat_row else 0
    skipped = stat_row.get("skip_count", 0) if stat_row else 0
    snoozed = stat_row.get("snooze_count", 0) if stat_row else 0
    lines = [
        f"📊 <b>Статистика привычек</b> ({date_str})",
        "",
        f"Всего привычек: {len(habits)}",
        f"Показано: {shown}",
        f"Выполнено: {done}",
        f"Пропущено: {skipped}",
        f"Отложено: {snoozed}",
    ]
    return "\n".join(lines)


def format_motivation_settings_text(items: list[dict], schedule: dict | None = None) -> str:
    """Format the motivation settings screen."""
    if not items:
        text = (
            "💡 <b>МОТИВАЦИЯ</b>\n\n"
            "Контента пока нет.\n"
            "Нажми «➕ Добавить контент» чтобы загрузить текст, фото, видео или GIF."
        )
    else:
        lines = ["💡 <b>МОТИВАЦИЯ</b>", ""]
        for i, item in enumerate(items, 1):
            media = item.get("media_type")
            emoji = {"photo": "🖼", "video": "🎬", "animation": "🎞"}.get(media or "", "📝")
            enabled = bool(item.get("is_enabled", 1))
            icon = "✅" if enabled else "❌"
            lines.append(f"{i}. {icon} {emoji} {item.get('title', '—')}")
        lines.append("")
        lines.append(f"Всего: {len(items)}")
        text = "\n".join(lines)

    if schedule:
        stype = schedule.get("schedule_type", "—")
        if stype == "interval":
            mins = schedule.get("interval_minutes", 0)
            text += f"\n\n⏱ Расписание: каждые {mins} мин"
        elif stype == "specific_times":
            import json
            try:
                times = json.loads(schedule.get("times_json", "[]"))
            except (json.JSONDecodeError, TypeError):
                times = []
            text += f"\n\n🕐 Расписание: {', '.join(times)}" if times else ""
        afrom = schedule.get("active_from")
        ato = schedule.get("active_to")
        if afrom and ato:
            text += f"\n🕰 Окно: {afrom}—{ato}"
    else:
        text += "\n\n⚠️ Расписание не настроено"

    return text


def format_motivation_stats_text(
    items: list[dict], stats: list[dict], date_str: str
) -> str:
    """Format motivation statistics for a date."""
    if not items:
        return "📊 Нет контента для статистики."
    stat_row = next(
        (s for s in stats if s.get("category") == "motivation"), None
    )
    shown = stat_row.get("shown_count", 0) if stat_row else 0
    seen = stat_row.get("done_count", 0) if stat_row else 0
    lines = [
        f"📊 <b>Статистика мотивации</b> ({date_str})",
        "",
        f"Контента: {len(items)}",
        f"Показано: {shown}",
        f"Отмечено (👂): {seen}",
    ]
    return "\n".join(lines)


def format_food_settings_text(items: list[dict]) -> str:
    """Format the food & supplements settings screen."""
    if not items:
        return (
            "🍽 <b>ПИТАНИЕ И ДОБАВКИ</b>\n\n"
            "Напоминаний пока нет.\n"
            "Нажми «🍽 Добавить приём пищи» или «💊 Добавить БАД»."
        )
    lines = ["🍽 <b>ПИТАНИЕ И ДОБАВКИ</b>", ""]
    for i, item in enumerate(items, 1):
        enabled = bool(item.get("is_enabled", 1))
        icon = "✅" if enabled else "❌"
        sub_type = item.get("text", "meal")
        emoji = "🍽" if sub_type == "meal" else "💊"
        lines.append(f"{i}. {icon} {emoji} {item.get('title', '—')}")
    lines.append("")
    lines.append("Нажми на элемент чтобы вкл/выкл.")
    return "\n".join(lines)


def format_food_stats_text(
    items: list[dict], stats: list[dict], date_str: str
) -> str:
    """Format food & supplements statistics for a date."""
    if not items:
        return "📊 Нет напоминаний питания для статистики."
    stat_row = next(
        (s for s in stats if s.get("category") == "food"), None
    )
    shown = stat_row.get("shown_count", 0) if stat_row else 0
    done = stat_row.get("done_count", 0) if stat_row else 0
    skipped = stat_row.get("skip_count", 0) if stat_row else 0
    snoozed = stat_row.get("snooze_count", 0) if stat_row else 0
    meals = [i for i in items if i.get("text") == "meal"]
    supps = [i for i in items if i.get("text") == "supplement"]
    lines = [
        f"📊 <b>Статистика питания</b> ({date_str})",
        "",
        f"Приёмов пищи: {len(meals)}",
        f"БАДов: {len(supps)}",
        f"Показано: {shown}",
        f"Выполнено: {done}",
        f"Пропущено: {skipped}",
        f"Отложено: {snoozed}",
    ]
    return "\n".join(lines)


def format_wishlist_settings_text(items: list[dict]) -> str:
    """Format the wishlist reminders settings screen."""
    if not items:
        return (
            "📋 <b>ВИШЛИСТ (БЫТ)</b>\n\n"
            "Напоминаний пока нет.\n"
            "Нажми «➕ Добавить напоминание» чтобы создать."
        )
    lines = ["📋 <b>ВИШЛИСТ (БЫТ)</b>", ""]
    for i, item in enumerate(items, 1):
        enabled = bool(item.get("is_enabled", 1))
        icon = "✅" if enabled else "❌"
        lines.append(f"{i}. {icon} {item.get('title', '—')}")
    lines.append("")
    lines.append("Нажми на элемент чтобы вкл/выкл.")
    return "\n".join(lines)


def format_wishlist_stats_text(
    items: list[dict], stats: list[dict], date_str: str
) -> str:
    """Format wishlist reminder statistics for a date."""
    if not items:
        return "📊 Нет напоминаний вишлиста для статистики."
    stat_row = next(
        (s for s in stats if s.get("category") == "wishlist"), None
    )
    shown = stat_row.get("shown_count", 0) if stat_row else 0
    done = stat_row.get("done_count", 0) if stat_row else 0
    skipped = stat_row.get("skip_count", 0) if stat_row else 0
    snoozed = stat_row.get("snooze_count", 0) if stat_row else 0
    lines = [
        f"📊 <b>Статистика вишлиста</b> ({date_str})",
        "",
        f"Всего напоминаний: {len(items)}",
        f"Показано: {shown}",
        f"Выполнено: {done}",
        f"Пропущено: {skipped}",
        f"Отложено: {snoozed}",
    ]
    return "\n".join(lines)


def format_reminder_done_text(reminder: dict) -> str:
    """Format confirmation after marking done."""
    title = reminder.get("title", "")
    return f"✅ <b>{title}</b> — выполнено!"


def format_reminder_snoozed_text(reminder: dict, until: str) -> str:
    """Format confirmation after snooze."""
    title = reminder.get("title", "")
    return f"⏳ <b>{title}</b> — отложено до {until}"


def format_reminder_skipped_text(reminder: dict) -> str:
    """Format confirmation after skip."""
    title = reminder.get("title", "")
    return f"🙅 <b>{title}</b> — пропущено"


def format_reminder_seen_text(reminder: dict) -> str:
    """Format confirmation after seen (motivation)."""
    title = reminder.get("title", "")
    return f"👂 <b>{title}</b> — отмечено"
