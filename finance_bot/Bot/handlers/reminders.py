"""Handlers for scheduled reminders — callback actions + scheduler checks."""

from __future__ import annotations

import logging
import random
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from Bot.database.get_db import get_db
from Bot.keyboards.reminders import (
    reminder_action_keyboard_habits,
    reminder_action_keyboard_motivation,
    snooze_duration_keyboard,
)
from Bot.renderers.reminder_render import (
    format_reminder_done_text,
    format_reminder_seen_text,
    format_reminder_skipped_text,
    format_reminder_snoozed_text,
    format_reminder_text,
)
from Bot.services.reminder_service import (
    _MOTIVATION_SCHEDULE_TITLE,
    build_callback_hash,
    record_reminder_action,
    schedule_snooze,
    should_fire_at,
)
from Bot.services.types import ServiceError
from Bot.utils.telegram_safe import (
    safe_callback_answer,
    safe_edit_message_text,
    safe_send_message,
)

router = Router()
LOGGER = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  Runtime reminder callback handlers                                 #
# ------------------------------------------------------------------ #


@router.callback_query(F.data.regexp(r"^rem:done:\d+$"))
async def handle_reminder_done(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle Done button on a reminder."""
    await safe_callback_answer(callback, logger=LOGGER)
    event_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id
    now_iso = datetime.now().isoformat()

    result = record_reminder_action(get_db(), user_id, event_id, "done", now_iso)
    if isinstance(result, ServiceError):
        await safe_callback_answer(callback, result.message, show_alert=True, logger=LOGGER)
        return

    LOGGER.info("USER=%s ACTION=REMINDER_DONE META=event_id=%s", user_id, event_id)
    reminder = result.get("reminder") or {}
    text = format_reminder_done_text(reminder)
    await safe_edit_message_text(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        text,
        reply_markup=None,
        logger=LOGGER,
    )


@router.callback_query(F.data.regexp(r"^rem:skip:\d+$"))
async def handle_reminder_skip(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle Skip button on a reminder."""
    await safe_callback_answer(callback, logger=LOGGER)
    event_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id
    now_iso = datetime.now().isoformat()

    result = record_reminder_action(get_db(), user_id, event_id, "skip", now_iso)
    if isinstance(result, ServiceError):
        await safe_callback_answer(callback, result.message, show_alert=True, logger=LOGGER)
        return

    LOGGER.info("USER=%s ACTION=REMINDER_SKIP META=event_id=%s", user_id, event_id)
    reminder = result.get("reminder") or {}
    text = format_reminder_skipped_text(reminder)
    await safe_edit_message_text(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        text,
        reply_markup=None,
        logger=LOGGER,
    )


@router.callback_query(F.data.regexp(r"^rem:seen:\d+$"))
async def handle_reminder_seen(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle Seen button on a motivation reminder."""
    await safe_callback_answer(callback, logger=LOGGER)
    event_id = int(callback.data.split(":")[2])
    user_id = callback.from_user.id
    now_iso = datetime.now().isoformat()

    result = record_reminder_action(get_db(), user_id, event_id, "seen", now_iso)
    if isinstance(result, ServiceError):
        await safe_callback_answer(callback, result.message, show_alert=True, logger=LOGGER)
        return

    LOGGER.info("USER=%s ACTION=REMINDER_SEEN META=event_id=%s", user_id, event_id)
    reminder = result.get("reminder") or {}
    text = format_reminder_seen_text(reminder)
    await safe_edit_message_text(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        text,
        reply_markup=None,
        logger=LOGGER,
    )


@router.callback_query(F.data.regexp(r"^rem:snooze_menu:\d+$"))
async def handle_reminder_snooze_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Show snooze duration options."""
    await safe_callback_answer(callback, logger=LOGGER)
    event_id = int(callback.data.split(":")[2])

    # Check event is still actionable
    event = get_db().get_reminder_event(event_id)
    if not event or event["action_at"] is not None:
        await safe_callback_answer(callback, "Уже учтено", show_alert=True, logger=LOGGER)
        return

    keyboard = snooze_duration_keyboard(event_id)
    reminder = get_db().get_reminder(event["reminder_id"])
    text = format_reminder_text(reminder) if reminder else "Выбери время отложки:"
    text += "\n\n⏳ На сколько отложить?"
    await safe_edit_message_text(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        text,
        reply_markup=keyboard,
        logger=LOGGER,
    )


@router.callback_query(F.data.regexp(r"^rem:snooze:\d+:\d+$"))
async def handle_reminder_snooze(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle snooze duration selection."""
    await safe_callback_answer(callback, logger=LOGGER)
    parts = callback.data.split(":")
    minutes = int(parts[2])
    event_id = int(parts[3])
    user_id = callback.from_user.id
    now_dt = datetime.now()

    result = schedule_snooze(get_db(), user_id, event_id, minutes, now_dt)
    if isinstance(result, ServiceError):
        await safe_callback_answer(callback, result.message, show_alert=True, logger=LOGGER)
        return

    LOGGER.info(
        "USER=%s ACTION=REMINDER_SNOOZE META=event_id=%s minutes=%s",
        user_id, event_id, minutes,
    )
    reminder = result.get("reminder") or {}
    until_str = result.get("snooze_until", "")[:16].replace("T", " ")
    text = format_reminder_snoozed_text(reminder, until_str)
    await safe_edit_message_text(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        text,
        reply_markup=None,
        logger=LOGGER,
    )


@router.callback_query(F.data.regexp(r"^rem:snooze_back:\d+$"))
async def handle_snooze_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Return from snooze menu to reminder action buttons."""
    await safe_callback_answer(callback, logger=LOGGER)
    event_id = int(callback.data.split(":")[2])

    event = get_db().get_reminder_event(event_id)
    if not event or event["action_at"] is not None:
        await safe_callback_answer(callback, "Уже учтено", show_alert=True, logger=LOGGER)
        return

    reminder = get_db().get_reminder(event["reminder_id"])
    text = format_reminder_text(reminder) if reminder else "🔔 Напоминание"
    category = reminder.get("category", "habits") if reminder else "habits"

    if category == "motivation":
        keyboard = reminder_action_keyboard_motivation(event_id)
    else:
        keyboard = reminder_action_keyboard_habits(event_id)

    await safe_edit_message_text(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        text,
        reply_markup=keyboard,
        logger=LOGGER,
    )


# ------------------------------------------------------------------ #
#  Scheduler check functions (called from main.py background task)    #
# ------------------------------------------------------------------ #


async def _send_motivation_content(
    bot: Bot, db, user_id: int, reminder: dict, event_id: int,
) -> bool:
    """Send a motivation content item (text/photo/video/animation) with Seen button."""
    keyboard = reminder_action_keyboard_motivation(event_id)
    media_type = reminder.get("media_type")
    media_ref = reminder.get("media_ref")
    caption = reminder.get("title", "")
    body_text = reminder.get("text")
    if body_text and body_text != "__meta__":
        caption = body_text

    try:
        if media_type == "photo" and media_ref:
            sent = await bot.send_photo(
                user_id, photo=media_ref, caption=caption,
                reply_markup=keyboard, parse_mode="HTML",
            )
        elif media_type == "video" and media_ref:
            sent = await bot.send_video(
                user_id, video=media_ref, caption=caption,
                reply_markup=keyboard, parse_mode="HTML",
            )
        elif media_type == "animation" and media_ref:
            sent = await bot.send_animation(
                user_id, animation=media_ref, caption=caption,
                reply_markup=keyboard, parse_mode="HTML",
            )
        else:
            text = format_reminder_text(reminder)
            sent = await safe_send_message(
                bot, user_id, text, reply_markup=keyboard, logger=LOGGER,
            )
        return bool(sent)
    except Exception as exc:  # noqa: BLE001
        LOGGER.error(
            "USER=%s ACTION=MOTIVATION_SEND_ERROR META=reminder_id=%s error=%s",
            user_id, reminder.get("id"), exc,
        )
        return False


async def run_reminder_check(
    bot: Bot, db, user_id: int, category: str, now_dt: datetime
) -> None:
    """Check and send due reminders for a user+category at the current time."""
    time_label = now_dt.strftime("%H:%M")

    if category == "motivation":
        await _run_motivation_check(bot, db, user_id, now_dt, time_label)
        return

    reminders = db.list_reminders_by_category(user_id, category)

    for reminder in reminders:
        if not reminder.get("is_enabled"):
            continue

        schedule = db.get_reminder_schedule(reminder["id"])
        if not schedule:
            continue

        if not should_fire_at(schedule, time_label, now_dt):
            continue

        callback_hash = build_callback_hash(
            reminder["id"], user_id, now_dt.isoformat()
        )
        existing = db.get_reminder_event_by_hash(callback_hash)
        if existing:
            continue

        event_id = db.record_reminder_event(
            reminder["id"], user_id, "shown", now_dt.isoformat(),
            callback_hash=callback_hash,
        )
        if not event_id:
            continue

        LOGGER.info(
            "USER=%s ACTION=REMINDER_SHOWN META=reminder_id=%s event_id=%s cat=%s",
            user_id, reminder["id"], event_id, category,
        )

        text = format_reminder_text(reminder)
        keyboard = reminder_action_keyboard_habits(event_id)

        try:
            sent = await safe_send_message(
                bot, user_id, text, reply_markup=keyboard, logger=LOGGER,
            )
            if sent:
                db.increment_reminder_stat(
                    user_id, now_dt.date().isoformat(), category, "shown_count"
                )
        except Exception as exc:  # noqa: BLE001
            LOGGER.error(
                "USER=%s ACTION=REMINDER_SEND_ERROR META=reminder_id=%s error=%s",
                user_id, reminder["id"], exc,
            )


async def _run_motivation_check(
    bot: Bot, db, user_id: int, now_dt: datetime, time_label: str
) -> None:
    """Check and send motivation content on schedule."""
    all_items = db.list_reminders_by_category(user_id, "motivation")
    meta = next(
        (i for i in all_items if i.get("title") == _MOTIVATION_SCHEDULE_TITLE), None
    )
    if not meta:
        return

    schedule = db.get_reminder_schedule(meta["id"])
    if not schedule:
        return

    if not should_fire_at(schedule, time_label, now_dt):
        return

    # Idempotency: check if we already fired for this time slot
    sched_hash = build_callback_hash(meta["id"], user_id, now_dt.isoformat())
    if db.get_reminder_event_by_hash(sched_hash):
        return

    # Pick a random enabled content item
    content_items = [
        i for i in all_items
        if i.get("title") != _MOTIVATION_SCHEDULE_TITLE and bool(i.get("is_enabled", 1))
    ]
    if not content_items:
        return

    chosen = random.choice(content_items)

    # Record event against the chosen content item
    callback_hash = build_callback_hash(chosen["id"], user_id, now_dt.isoformat())
    event_id = db.record_reminder_event(
        chosen["id"], user_id, "shown", now_dt.isoformat(),
        callback_hash=callback_hash,
    )
    if not event_id:
        # If hash collision (already sent this content at this time), record on meta for idempotency
        db.record_reminder_event(
            meta["id"], user_id, "shown", now_dt.isoformat(),
            callback_hash=sched_hash,
        )
        return

    # Also record the schedule-level hash to prevent double-firing
    if sched_hash != callback_hash:
        db.record_reminder_event(
            meta["id"], user_id, "shown", now_dt.isoformat(),
            callback_hash=sched_hash,
        )

    LOGGER.info(
        "USER=%s ACTION=MOTIVATION_SHOWN META=reminder_id=%s event_id=%s",
        user_id, chosen["id"], event_id,
    )

    ok = await _send_motivation_content(bot, db, user_id, chosen, event_id)
    if ok:
        db.increment_reminder_stat(
            user_id, now_dt.date().isoformat(), "motivation", "shown_count"
        )


async def run_snooze_check(
    bot: Bot, db, user_id: int, now_dt: datetime
) -> None:
    """Re-send reminders whose snooze has expired."""
    events = db.get_pending_snooze_events(user_id, now_dt.isoformat())

    for event in events:
        if not event.get("is_enabled"):
            continue

        reminder_id = event["reminder_id"]
        reminder = db.get_reminder(reminder_id)
        if not reminder or not reminder.get("is_enabled"):
            continue

        new_hash = build_callback_hash(reminder_id, user_id, now_dt.isoformat())
        new_event_id = db.record_reminder_event(
            reminder_id, user_id, "shown", now_dt.isoformat(),
            callback_hash=new_hash,
        )
        if not new_event_id:
            continue

        LOGGER.info(
            "USER=%s ACTION=REMINDER_SNOOZE_RESEND META=reminder_id=%s event_id=%s",
            user_id, reminder_id, new_event_id,
        )

        category = reminder.get("category", "habits")

        try:
            if category == "motivation":
                sent = await _send_motivation_content(
                    bot, db, user_id, reminder, new_event_id,
                )
            else:
                text = format_reminder_text(reminder)
                keyboard = reminder_action_keyboard_habits(new_event_id)
                sent = await safe_send_message(
                    bot, user_id, text, reply_markup=keyboard, logger=LOGGER,
                )
            if sent:
                db.increment_reminder_stat(
                    user_id, now_dt.date().isoformat(), category, "shown_count"
                )
        except Exception as exc:  # noqa: BLE001
            LOGGER.error(
                "USER=%s ACTION=REMINDER_SNOOZE_SEND_ERROR META=reminder_id=%s error=%s",
                user_id, reminder_id, exc,
            )
