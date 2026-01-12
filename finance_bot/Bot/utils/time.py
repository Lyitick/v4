"""Time utilities with per-user timezone support."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def _resolve_timezone(value: str | None, default_tz: str) -> str:
    if not value:
        return default_tz
    try:
        ZoneInfo(str(value))
    except Exception:
        return default_tz
    return str(value)


def get_user_timezone(db, user_id: int, default_tz: str) -> str:
    """Return user timezone from settings or fallback to default."""

    db.ensure_user_settings(user_id)
    settings_row = db.get_user_settings(user_id)
    tz_value = settings_row.get("timezone")
    tz = _resolve_timezone(tz_value, default_tz)
    if tz_value != tz:
        set_user_timezone(db, user_id, tz, default_tz)
    return tz


def set_user_timezone(db, user_id: int, tz: str, default_tz: str) -> None:
    """Persist user timezone."""

    resolved = _resolve_timezone(tz, default_tz)
    now_iso = datetime.now(tz=ZoneInfo(resolved)).isoformat()
    db.ensure_user_settings(user_id)
    cursor = db.connection.cursor()
    cursor.execute(
        f"""
        UPDATE {db.tables.user_settings}
        SET timezone = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (resolved, now_iso, user_id),
    )
    if cursor.rowcount == 0:
        cursor.execute(
            f"""
            INSERT INTO {db.tables.user_settings} (user_id, timezone, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, resolved, now_iso, now_iso),
        )
    db.connection.commit()


def now_for_user(db, user_id: int, default_tz: str) -> datetime:
    """Return current datetime in user's timezone."""

    tz = get_user_timezone(db, user_id, default_tz)
    return datetime.now(tz=ZoneInfo(tz))


def today_for_user(db, user_id: int, default_tz: str) -> str:
    """Return today's date string for user in YYYY-MM-DD format."""

    return now_for_user(db, user_id, default_tz).date().isoformat()
