"""Rendering helpers for BYT reminders."""

from __future__ import annotations

from datetime import datetime

from Bot.database.crud import FinanceDatabase


def format_byt_item_price(item: dict) -> str:
    price = item.get("price")
    if price in (None, "", 0):
        return ""
    try:
        value = float(price)
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    if value.is_integer():
        return f"{int(value)}р"
    return f"{value:.2f}".rstrip("0").rstrip(".") + "р"


def format_byt_item_line(item: dict) -> str:
    name = str(item.get("name", "")).strip()
    price_label = format_byt_item_price(item)
    if price_label:
        return f"• {name} — {price_label}"
    return f"• {name}"


def parse_deferred_until(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def format_byt_category_checklist_text(
    category_title: str, due_items: list[dict], deferred_items: list[dict]
) -> str:
    lines: list[str] = [f"📋 Категория: {category_title}", ""]
    if not due_items and not deferred_items:
        lines.append("В этой категории нет активных напоминаний.")
        return "\n".join(lines)

    if due_items:
        lines.append("🟢 Пора купить:")
        for item in due_items:
            lines.append(format_byt_item_line(item))
        lines.append("")

    if deferred_items:
        lines.append("⏳ Отложено:")
        for item in deferred_items:
            deferred_until = parse_deferred_until(item.get("deferred_until"))
            if deferred_until:
                lines.append(
                    f"{format_byt_item_line(item)} (до {deferred_until.strftime('%Y-%m-%d %H:%M')})"
                )
            else:
                lines.append(format_byt_item_line(item))
    return "\n".join(lines)


def format_byt_defer_confirmation_text(
    item: dict, category_title: str, deferred_until: datetime, checklist_text: str
) -> str:
    price_label = format_byt_item_price(item)
    price_part = f", сумма: {price_label}" if price_label else ""
    lines = [
        f"✅ Отложено: «{item.get('name', '')}» (категория: {category_title}{price_part})",
        f"⏰ До: {deferred_until.strftime('%Y-%m-%d %H:%M')}",
        "",
        checklist_text,
    ]
    return "\n".join(lines)


def get_byt_category_items(
    db: FinanceDatabase, user_id: int, category_title: str, now_dt: datetime
) -> tuple[list[dict], list[dict]]:
    total_items = db.get_active_byt_wishes(user_id, category_title)
    due_items = db.list_active_byt_items_for_reminder(user_id, now_dt, category_title)
    due_ids = {int(item.get("id")) for item in due_items if item.get("id") is not None}
    deferred_items = [
        item
        for item in total_items
        if item.get("id") is not None and int(item.get("id")) not in due_ids
    ]
    return due_items, deferred_items
