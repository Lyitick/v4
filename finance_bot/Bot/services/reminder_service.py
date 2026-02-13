"""Service layer for scheduled reminders."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from Bot.services.types import ServiceError

LOGGER = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  Habits CRUD                                                        #
# ------------------------------------------------------------------ #


def create_habit(
    db: Any,
    user_id: int,
    title: str,
    times: list[str] | None = None,
) -> dict | ServiceError:
    """Create a habit reminder with optional schedule times."""
    title = title.strip()
    if not title:
        return ServiceError(code="empty_title", message="Название не может быть пустым")
    if len(title) > 100:
        return ServiceError(code="title_too_long", message="Максимум 100 символов")

    reminder_id = db.create_reminder(user_id, "habits", title)
    if not reminder_id:
        return ServiceError(code="db_error", message="Не удалось создать привычку")

    if times:
        times_json = json.dumps(times)
        db.set_reminder_schedule(reminder_id, "specific_times", times_json=times_json)

    LOGGER.info("USER=%s ACTION=HABIT_CREATED META=reminder_id=%s title=%s", user_id, reminder_id, title)
    return {"id": reminder_id, "title": title}


def list_habits(db: Any, user_id: int) -> list[dict]:
    """List habit reminders for user."""
    return db.list_reminders_by_category(user_id, "habits")


def delete_habit(db: Any, user_id: int, reminder_id: int) -> bool | ServiceError:
    """Delete a habit reminder."""
    reminder = db.get_reminder(reminder_id)
    if not reminder:
        return ServiceError(code="not_found", message="Привычка не найдена")
    if reminder["user_id"] != user_id or reminder["category"] != "habits":
        return ServiceError(code="not_found", message="Привычка не найдена")

    ok = db.delete_reminder(reminder_id, user_id)
    if not ok:
        return ServiceError(code="db_error", message="Не удалось удалить")

    LOGGER.info("USER=%s ACTION=HABIT_DELETED META=reminder_id=%s", user_id, reminder_id)
    return True


# ------------------------------------------------------------------ #
#  Food & Supplements CRUD                                            #
# ------------------------------------------------------------------ #


def create_food_reminder(
    db: Any,
    user_id: int,
    title: str,
    sub_type: str = "meal",
    times: list[str] | None = None,
) -> dict | ServiceError:
    """Create a food/supplement reminder with optional schedule times."""
    title = title.strip()
    if not title:
        return ServiceError(code="empty_title", message="Название не может быть пустым")
    if len(title) > 100:
        return ServiceError(code="title_too_long", message="Максимум 100 символов")

    reminder_id = db.create_reminder(user_id, "food", title, text=sub_type)
    if not reminder_id:
        return ServiceError(code="db_error", message="Не удалось создать напоминание")

    if times:
        times_json = json.dumps(times)
        db.set_reminder_schedule(reminder_id, "specific_times", times_json=times_json)

    LOGGER.info(
        "USER=%s ACTION=FOOD_REMINDER_CREATED META=reminder_id=%s sub_type=%s title=%s",
        user_id, reminder_id, sub_type, title,
    )
    return {"id": reminder_id, "title": title, "sub_type": sub_type}


def list_food_reminders(db: Any, user_id: int) -> list[dict]:
    """List food/supplement reminders for user."""
    return db.list_reminders_by_category(user_id, "food")


def delete_food_reminder(db: Any, user_id: int, reminder_id: int) -> bool | ServiceError:
    """Delete a food/supplement reminder."""
    reminder = db.get_reminder(reminder_id)
    if not reminder:
        return ServiceError(code="not_found", message="Напоминание не найдено")
    if reminder["user_id"] != user_id or reminder["category"] != "food":
        return ServiceError(code="not_found", message="Напоминание не найдено")

    ok = db.delete_reminder(reminder_id, user_id)
    if not ok:
        return ServiceError(code="db_error", message="Не удалось удалить")

    LOGGER.info("USER=%s ACTION=FOOD_REMINDER_DELETED META=reminder_id=%s", user_id, reminder_id)
    return True


# ------------------------------------------------------------------ #
#  Motivation / Content CRUD                                          #
# ------------------------------------------------------------------ #

_MOTIVATION_SCHEDULE_TITLE = "__schedule__"


def ensure_motivation_schedule(db: Any, user_id: int) -> dict:
    """Get or create the motivation schedule meta-record."""
    items = db.list_reminders_by_category(user_id, "motivation")
    meta = next((i for i in items if i.get("title") == _MOTIVATION_SCHEDULE_TITLE), None)
    if meta:
        return meta
    rid = db.create_reminder(user_id, "motivation", _MOTIVATION_SCHEDULE_TITLE, text="__meta__")
    if not rid:
        return {}
    return db.get_reminder(rid) or {}


def create_motivation_content(
    db: Any,
    user_id: int,
    title: str,
    text: str | None = None,
    media_type: str | None = None,
    media_ref: str | None = None,
) -> dict | ServiceError:
    """Create a motivation content item."""
    title = title.strip() if title else ""
    if not title and not media_ref:
        return ServiceError(code="empty_content", message="Нужен текст или медиа")
    if not title:
        title = {"photo": "Фото", "video": "Видео", "animation": "GIF"}.get(media_type or "", "Контент")
    if len(title) > 100:
        title = title[:100]

    reminder_id = db.create_reminder(user_id, "motivation", title, text=text,
                                     media_type=media_type, media_ref=media_ref)
    if not reminder_id:
        return ServiceError(code="db_error", message="Не удалось сохранить контент")

    LOGGER.info(
        "USER=%s ACTION=MOTIVATION_CONTENT_CREATED META=reminder_id=%s media_type=%s",
        user_id, reminder_id, media_type,
    )
    return {"id": reminder_id, "title": title, "media_type": media_type}


def list_motivation_content(db: Any, user_id: int) -> list[dict]:
    """List motivation content items (excluding schedule meta-record)."""
    items = db.list_reminders_by_category(user_id, "motivation")
    return [i for i in items if i.get("title") != _MOTIVATION_SCHEDULE_TITLE]


def delete_motivation_content(
    db: Any, user_id: int, reminder_id: int
) -> bool | ServiceError:
    """Delete a motivation content item."""
    reminder = db.get_reminder(reminder_id)
    if not reminder:
        return ServiceError(code="not_found", message="Контент не найден")
    if reminder["user_id"] != user_id or reminder["category"] != "motivation":
        return ServiceError(code="not_found", message="Контент не найден")
    if reminder["title"] == _MOTIVATION_SCHEDULE_TITLE:
        return ServiceError(code="protected", message="Нельзя удалить расписание")

    ok = db.delete_reminder(reminder_id, user_id)
    if not ok:
        return ServiceError(code="db_error", message="Не удалось удалить")

    LOGGER.info("USER=%s ACTION=MOTIVATION_CONTENT_DELETED META=reminder_id=%s", user_id, reminder_id)
    return True


def set_motivation_schedule(
    db: Any,
    user_id: int,
    schedule_type: str,
    interval_minutes: int | None = None,
    times_json: str | None = None,
    active_from: str | None = None,
    active_to: str | None = None,
) -> dict | ServiceError:
    """Set the motivation schedule (applied to the meta-record)."""
    meta = ensure_motivation_schedule(db, user_id)
    if not meta or not meta.get("id"):
        return ServiceError(code="db_error", message="Не удалось создать расписание")

    if schedule_type == "interval" and (not interval_minutes or interval_minutes < 15):
        return ServiceError(code="invalid_interval", message="Интервал минимум 15 минут")

    db.set_reminder_schedule(
        meta["id"],
        schedule_type,
        interval_minutes=interval_minutes,
        times_json=times_json,
        active_from=active_from,
        active_to=active_to,
    )
    LOGGER.info(
        "USER=%s ACTION=MOTIVATION_SCHEDULE_SET META=type=%s interval=%s",
        user_id, schedule_type, interval_minutes,
    )
    schedule = db.get_reminder_schedule(meta["id"])
    return schedule or {}


def get_motivation_schedule(db: Any, user_id: int) -> dict | None:
    """Get the motivation schedule."""
    meta = ensure_motivation_schedule(db, user_id)
    if not meta or not meta.get("id"):
        return None
    return db.get_reminder_schedule(meta["id"])


# ------------------------------------------------------------------ #
#  Callback hash & idempotency                                       #
# ------------------------------------------------------------------ #


def build_callback_hash(reminder_id: int, user_id: int, shown_at_iso: str) -> str:
    """Build a deterministic hash for callback idempotency."""
    raw = f"{reminder_id}:{user_id}:{shown_at_iso}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ------------------------------------------------------------------ #
#  Reminder actions                                                   #
# ------------------------------------------------------------------ #


def record_reminder_action(
    db: Any,
    user_id: int,
    event_id: int,
    event_type: str,
    now_iso: str,
) -> dict | ServiceError:
    """Record a reminder action (done/skip/seen) with idempotency.

    Returns dict with event info or ServiceError if already processed.
    """
    event = db.get_reminder_event(event_id)
    if not event:
        return ServiceError(code="not_found", message="Событие не найдено")
    if event["user_id"] != user_id:
        return ServiceError(code="not_found", message="Событие не найдено")
    if event["action_at"] is not None:
        return ServiceError(code="already_done", message="Уже учтено")

    ok = db.update_reminder_event_action(event_id, event_type, now_iso)
    if not ok:
        return ServiceError(code="already_done", message="Уже учтено")

    reminder = db.get_reminder(event["reminder_id"])
    category = reminder["category"] if reminder else "unknown"

    stat_field = {
        "done": "done_count",
        "skip": "skip_count",
        "seen": "done_count",
    }.get(event_type)
    if stat_field:
        date_str = now_iso[:10]
        db.increment_reminder_stat(user_id, date_str, category, stat_field)

    return {"event_id": event_id, "reminder": reminder, "event_type": event_type}


def schedule_snooze(
    db: Any,
    user_id: int,
    event_id: int,
    minutes: int,
    now_dt: datetime,
) -> dict | ServiceError:
    """Schedule a snooze for a reminder event."""
    if minutes < 15:
        return ServiceError(code="invalid_duration", message="Минимум 15 минут")

    event = db.get_reminder_event(event_id)
    if not event:
        return ServiceError(code="not_found", message="Событие не найдено")
    if event["user_id"] != user_id:
        return ServiceError(code="not_found", message="Событие не найдено")
    if event["action_at"] is not None:
        return ServiceError(code="already_done", message="Уже учтено")

    snooze_until = (now_dt + timedelta(minutes=minutes)).isoformat()
    ok = db.update_reminder_event_action(
        event_id, "snooze", now_dt.isoformat(), snooze_until=snooze_until
    )
    if not ok:
        return ServiceError(code="already_done", message="Уже учтено")

    reminder = db.get_reminder(event["reminder_id"])
    category = reminder["category"] if reminder else "unknown"
    db.increment_reminder_stat(user_id, now_dt.date().isoformat(), category, "snooze_count")

    return {
        "event_id": event_id,
        "reminder": reminder,
        "snooze_until": snooze_until,
    }


# ------------------------------------------------------------------ #
#  Schedule logic                                                     #
# ------------------------------------------------------------------ #


def should_fire_at(
    schedule: dict, time_label: str, now_dt: datetime
) -> bool:
    """Determine if a reminder should fire at the given HH:MM."""
    active_from = schedule.get("active_from")
    active_to = schedule.get("active_to")
    if active_from and active_to:
        if not (active_from <= time_label <= active_to):
            return False

    schedule_type = schedule.get("schedule_type", "specific_times")

    if schedule_type == "specific_times":
        times_json = schedule.get("times_json")
        if not times_json:
            return False
        try:
            times = json.loads(times_json) if isinstance(times_json, str) else times_json
        except (json.JSONDecodeError, TypeError):
            return False
        return time_label in times

    if schedule_type == "interval":
        interval = schedule.get("interval_minutes")
        if not interval or interval < 15:
            return False
        start_minutes = 0
        if active_from:
            parts = active_from.split(":")
            if len(parts) == 2:
                start_minutes = int(parts[0]) * 60 + int(parts[1])
        current_parts = time_label.split(":")
        if len(current_parts) != 2:
            return False
        current_minutes = int(current_parts[0]) * 60 + int(current_parts[1])
        elapsed = current_minutes - start_minutes
        if elapsed < 0:
            return False
        return elapsed % interval == 0

    return False


# ------------------------------------------------------------------ #
#  Wishlist / BYT migration                                           #
# ------------------------------------------------------------------ #


def migrate_byt_to_reminders(db: Any, user_id: int) -> int:
    """Migrate BYT wishlist data into the new reminder tables.

    Creates one 'wishlist' category reminder per enabled BYT category,
    with schedule matching the BYT category times.
    Returns the number of reminders created.
    """
    existing = db.list_reminders_by_category(user_id, "wishlist")
    if existing:
        return 0  # Already migrated

    db.ensure_byt_reminder_migration(user_id)
    categories = db.list_byt_reminder_categories(user_id)
    created = 0

    for cat in categories:
        cat_id = cat.get("id")
        cat_title = cat.get("title", "")
        enabled = bool(cat.get("enabled", 0))

        if not cat_title:
            continue

        reminder_id = db.create_reminder(
            user_id, "wishlist", cat_title,
            text=f"byt_category_id:{cat_id}",
        )
        if not reminder_id:
            continue

        if not enabled:
            db.toggle_reminder_enabled(reminder_id, user_id)

        times = db.list_byt_reminder_times(user_id, cat_id)
        time_values = [t.get("time_hhmm") for t in times if t.get("time_hhmm")]

        if time_values:
            db.set_reminder_schedule(
                reminder_id,
                "specific_times",
                times_json=json.dumps(time_values),
            )

        created += 1
        LOGGER.info(
            "USER=%s ACTION=BYT_MIGRATED META=category=%s reminder_id=%s times=%s",
            user_id, cat_title, reminder_id, time_values,
        )

    return created


def is_within_activity_window(
    schedule: dict, time_label: str
) -> bool:
    """Check if current time is within the schedule's activity window."""
    active_from = schedule.get("active_from")
    active_to = schedule.get("active_to")
    if not active_from or not active_to:
        return True
    return active_from <= time_label <= active_to
