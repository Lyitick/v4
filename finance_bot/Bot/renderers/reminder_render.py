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
