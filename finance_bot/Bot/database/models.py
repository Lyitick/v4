"""Database model helpers."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Saving:
    """Saving record representation."""

    id: int
    user_id: int
    category: str
    current: float
    goal: float
    purpose: str


@dataclass
class Wish:
    """Wish record representation."""

    id: int
    user_id: int
    name: str
    price: float
    url: Optional[str]
    category: str
    is_purchased: bool
    saved_amount: float
    purchased_at: Optional[str]
    deferred_until: Optional[str]


@dataclass
class Purchase:
    """Purchase record representation."""

    id: int
    user_id: int
    wish_name: str
    price: float
    category: str
    purchased_at: str


@dataclass
class Reminder:
    """Scheduled reminder record."""

    id: int
    user_id: int
    category: str
    title: str
    text: Optional[str]
    media_type: Optional[str]
    media_ref: Optional[str]
    is_enabled: bool
    position: int
    created_at: str
    updated_at: str


@dataclass
class ReminderSchedule:
    """Schedule definition for a reminder."""

    id: int
    reminder_id: int
    schedule_type: str
    interval_minutes: Optional[int]
    times_json: Optional[str]
    active_from: Optional[str]
    active_to: Optional[str]
    timezone: Optional[str]


@dataclass
class ReminderEvent:
    """Record of a reminder event (shown/done/snooze/skip/seen)."""

    id: int
    reminder_id: int
    user_id: int
    event_type: str
    shown_at: str
    action_at: Optional[str]
    snooze_until: Optional[str]
    message_id: Optional[int]
    callback_hash: Optional[str]
