"""Database CRUD operations for finance bot."""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from Bot.config.settings import get_settings
from Bot.utils.datetime_utils import add_one_month, now_tz
from Bot.utils.text_sanitizer import sanitize_income_title


LOGGER = logging.getLogger(__name__)
DB_PATH = Path(__file__).resolve().parents[2] / "finance.db"
TARGET_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TableNames:
    savings: str = "накопления"
    wishes: str = "желания"
    purchases: str = "покупки"
    household_payments: str = "бытовые_платежи"
    household_payment_items: str = "позиции_бытовых_платежей"
    ui_pins: str = "закрепы_интерфейса"
    income_categories: str = "категории_доходов"
    expense_categories: str = "категории_расходов"
    wishlist_categories: str = "категории_желаний"
    user_settings: str = "настройки_пользователя"
    byt_timer_times: str = "время_быт_таймера"


TABLES = TableNames()
TABLE_RENAMES: dict[str, str] = {
    "savings": TABLES.savings,
    "wishes": TABLES.wishes,
    "purchases": TABLES.purchases,
    "household_payments": TABLES.household_payments,
    "household_payment_items": TABLES.household_payment_items,
    "ui_pins": TABLES.ui_pins,
    "income_categories": TABLES.income_categories,
    "expense_categories": TABLES.expense_categories,
    "wishlist_categories": TABLES.wishlist_categories,
    "user_settings": TABLES.user_settings,
    "byt_timer_times": TABLES.byt_timer_times,
}
LEGACY_TABLE_NAMES = tuple(TABLE_RENAMES.keys())


def _get_bot_user_id() -> int | None:
    try:
        token = get_settings().bot_token
        if not token:
            return None
        return int(str(token).split(":")[0])
    except (AttributeError, IndexError, TypeError, ValueError):
        return None


BOT_USER_ID = _get_bot_user_id()
DEFAULT_HOUSEHOLD_ITEMS = [
    {"code": "phone", "text": "Телефон 600р?", "amount": 600},
    {"code": "internet", "text": "Интернет 700р?", "amount": 700},
    {"code": "vpn", "text": "VPN 100р?", "amount": 100},
    {"code": "gpt", "text": "GPT 2000р?", "amount": 2000},
    {"code": "yandex_sub", "text": "Яндекс подписка 400р?", "amount": 400},
    {"code": "rent", "text": "Квартплата 4000р? Папе скинул?", "amount": 4000},
    {"code": "training_495", "text": "Оплатил тренировки 495 - 5000р?", "amount": 5000},
]

DEFAULT_EXPENSE_CATEGORIES = [
    {"code": "базовые", "title": "Базовые расходы", "percent": 40, "position": 1},
    {"code": "жилье", "title": "Жилье и ЖКУ", "percent": 20, "position": 2},
    {"code": "транспорт", "title": "Транспорт", "percent": 15, "position": 3},
    {"code": "еда", "title": "Еда", "percent": 15, "position": 4},
    {"code": "другое", "title": "Другое", "percent": 10, "position": 5},
]



def _get_user_version(cursor: sqlite3.Cursor) -> int:
    cursor.execute("PRAGMA user_version")
    row = cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _list_user_tables(cursor: sqlite3.Cursor) -> list[str]:
    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )
    return [str(row[0]) for row in cursor.fetchall()]


def _fetch_schema_definitions(cursor: sqlite3.Cursor) -> list[tuple[str, str]]:
    cursor.execute(
        """
        SELECT name, sql
        FROM sqlite_master
        WHERE type IN ('table', 'index', 'trigger', 'view') AND sql IS NOT NULL
        """
    )
    return [(str(row[0]), str(row[1])) for row in cursor.fetchall()]


def _assert_no_legacy_table_names(cursor: sqlite3.Cursor) -> None:
    schema_rows = _fetch_schema_definitions(cursor)
    for name, sql in schema_rows:
        for legacy_name in LEGACY_TABLE_NAMES:
            if legacy_name in sql:
                raise RuntimeError(
                    f"Legacy table name '{legacy_name}' found in schema object '{name}'"
                )


def migrate_schema(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    current_version = _get_user_version(cursor)
    if current_version >= TARGET_SCHEMA_VERSION:
        return

    existing_tables = set(_list_user_tables(cursor))
    LOGGER.info(
        "DB_MIGRATION start from_version=%s to_version=%s",
        current_version,
        TARGET_SCHEMA_VERSION,
    )
    renamed = 0
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("PRAGMA foreign_keys = OFF")
        for old_name, new_name in TABLE_RENAMES.items():
            if old_name in existing_tables and new_name not in existing_tables:
                cursor.execute(
                    f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"'
                )
                renamed += 1
                LOGGER.info("DB_MIGRATION rename %s->%s", old_name, new_name)
                existing_tables.discard(old_name)
                existing_tables.add(new_name)
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA foreign_key_check")
        fk_issues = cursor.fetchall()
        if fk_issues:
            raise RuntimeError(f"Foreign key issues after migration: {fk_issues}")
        _assert_no_legacy_table_names(cursor)
        cursor.execute(f"PRAGMA user_version = {TARGET_SCHEMA_VERSION}")
        cursor.execute("COMMIT")
        LOGGER.info("DB_MIGRATION success renamed=%s", renamed)
    except Exception:
        cursor.execute("ROLLBACK")
        LOGGER.error("DB_MIGRATION failed", exc_info=True)
        raise


class FinanceDatabase:
    """Singleton class handling all database interactions."""

    _instance: Optional["FinanceDatabase"] = None
    _lock: Lock = Lock()

    def __new__(cls) -> "FinanceDatabase":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize_connection()
        return cls._instance

    def _initialize_connection(self) -> None:
        """Initialize SQLite connection and create tables."""

        DB_PATH.touch(exist_ok=True)
        self.connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        migrate_schema(self.connection)
        self.init_db()
        LOGGER.info("Database initialized at %s", DB_PATH)

    @staticmethod
    def _to_float(value: Any) -> float:
        """Safely convert a value to float, returning 0.0 on failure."""

        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    def init_db(self) -> None:
        """Create required tables if they do not exist."""

        cursor = self.connection.cursor()
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{TABLES.savings}" (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                category TEXT,
                current REAL,
                goal REAL,
                purpose TEXT
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{TABLES.wishes}" (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                name TEXT,
                price REAL,
                url TEXT,
                category TEXT,
                is_purchased INTEGER,
                saved_amount REAL DEFAULT 0,
                purchased_at TEXT,
                debited_at TEXT,
                deferred_until TEXT
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{TABLES.purchases}" (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                wish_name TEXT,
                price REAL,
                category TEXT,
                purchased_at TEXT
            )
            """
        )
        self._add_column_if_missing(
            cursor, TABLES.wishes, "deferred_until", "TEXT"
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{TABLES.household_payments}" (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                month TEXT,
                question_code TEXT,
                is_paid INTEGER DEFAULT 0,
                UNIQUE(user_id, month, question_code)
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{TABLES.household_payment_items}" (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                code TEXT,
                text TEXT,
                amount INTEGER,
                position INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                paid_month TEXT,
                is_paid INTEGER DEFAULT 0,
                created_at TEXT,
                UNIQUE(user_id, code)
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{TABLES.ui_pins}" (
                chat_id INTEGER PRIMARY KEY,
                welcome_message_id INTEGER,
                updated_at TEXT
            )
            """
        )
        self._add_column_if_missing(
            cursor, TABLES.household_payment_items, "paid_month", "TEXT"
        )
        self._add_column_if_missing(
            cursor, TABLES.household_payment_items, "is_paid", "INTEGER DEFAULT 0"
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{TABLES.income_categories}" (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                title TEXT NOT NULL,
                percent INTEGER NOT NULL,
                position INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(user_id, code)
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{TABLES.expense_categories}" (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                title TEXT NOT NULL,
                percent INTEGER NOT NULL,
                position INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(user_id, code)
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{TABLES.wishlist_categories}" (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                position INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                purchased_mode TEXT DEFAULT 'days',
                purchased_days INTEGER DEFAULT 30
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{TABLES.user_settings}" (
                user_id INTEGER PRIMARY KEY,
                purchased_keep_days INTEGER NOT NULL DEFAULT 30,
                byt_reminders_enabled INTEGER NOT NULL DEFAULT 1,
                byt_defer_enabled INTEGER NOT NULL DEFAULT 1,
                byt_defer_max_days INTEGER NOT NULL DEFAULT 365,
                household_debit_category TEXT,
                wishlist_debit_category_id TEXT
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{TABLES.byt_timer_times}" (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                minute INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        self._add_column_if_missing(cursor, TABLES.wishes, "purchased_at", "TEXT")
        self._add_column_if_missing(
            cursor, TABLES.wishlist_categories, "purchased_mode", "TEXT DEFAULT 'days'"
        )
        self._add_column_if_missing(
            cursor, TABLES.wishlist_categories, "purchased_days", "INTEGER DEFAULT 30"
        )
        self._add_column_if_missing(
            cursor, TABLES.user_settings, "household_debit_category", "TEXT"
        )
        self._add_column_if_missing(
            cursor, TABLES.user_settings, "wishlist_debit_category_id", "TEXT"
        )
        self._add_column_if_missing(cursor, TABLES.wishes, "debited_at", "TEXT")
        self.connection.commit()
        self.sanitize_income_category_titles()

    def ensure_household_items_seeded(self, user_id: int) -> None:
        """No-op: household items are managed by user and stored in DB."""
        LOGGER.debug("Household item seeding disabled (user_id=%s)", user_id)

    def list_active_household_items(self, user_id: int) -> List[Dict[str, Any]]:
        """Return active household payment items for user ordered by position."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT code, text, amount, position
                FROM {TABLES.household_payment_items}
                WHERE user_id = ? AND is_active = 1
                ORDER BY position, id
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to list active household items for user %s: %s",
                user_id,
                error,
            )
            return []

    def get_household_item_by_code(
        self, user_id: int, code: str
    ) -> Optional[Dict[str, Any]]:
        """Return household payment item by code."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT code, text, amount, position
                FROM {TABLES.household_payment_items}
                WHERE user_id = ? AND code = ? AND is_active = 1
                LIMIT 1
                """,
                (user_id, code),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to fetch household item %s for user %s: %s",
                code,
                user_id,
                error,
            )
            return None

    def get_next_household_position(self, user_id: int) -> int:
        """Return next position value for household items."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT MAX(position) FROM {TABLES.household_payment_items} WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            max_pos = row[0] if row and row[0] is not None else 0
            return int(max_pos) + 1
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to get next household position for user %s: %s", user_id, error
            )
            return 1

    def add_household_payment_item(
        self, user_id: int, code: str, text: str, amount: int, position: int
    ) -> None:
        """Add new household payment item."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                INSERT INTO {TABLES.household_payment_items} (
                    user_id, code, text, amount, position, is_active, created_at
                )
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (user_id, code, text, amount, position, now_tz().isoformat()),
            )
            self.connection.commit()
            LOGGER.info("Added household payment item %s for user %s", code, user_id)
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to add household item %s for user %s: %s",
                code,
                user_id,
                error,
            )

    def deactivate_household_payment_item(self, user_id: int, code: str) -> None:
        """Deactivate household payment item."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                UPDATE {TABLES.household_payment_items}
                SET is_active = 0
                WHERE user_id = ? AND code = ?
                """,
                (user_id, code),
            )
            self.connection.commit()
            LOGGER.info("Deactivated household payment item %s for user %s", code, user_id)
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to deactivate household item %s for user %s: %s",
                code,
                user_id,
                error,
            )

    def sanitize_income_category_titles(self) -> None:
        """Sanitize stored income category titles."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(f"SELECT id, title FROM {TABLES.income_categories}")
            rows = cursor.fetchall()
            updates = []
            for row in rows:
                current_title = str(row["title"])
                sanitized = sanitize_income_title(current_title)
                if sanitized != current_title:
                    updates.append((sanitized, int(row["id"])))
            if updates:
                cursor.executemany(
                    f"UPDATE {TABLES.income_categories} SET title = ? WHERE id = ?",
                    updates,
                )
                self.connection.commit()
                LOGGER.info("Sanitized income category titles: %s", len(updates))
        except sqlite3.Error as error:
            LOGGER.error("Failed to sanitize income category titles: %s", error)

    def get_welcome_message_id(self, chat_id: int) -> int | None:
        """Fetch persisted welcome message id for chat."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT welcome_message_id FROM {TABLES.ui_pins} WHERE chat_id = ?",
                (chat_id,),
            )
            row = cursor.fetchone()
            if row and row["welcome_message_id"] is not None:
                return int(row["welcome_message_id"])
            return None
        except sqlite3.Error as error:
            LOGGER.error("Failed to fetch welcome message id for chat %s: %s", chat_id, error)
            return None

    def set_welcome_message_id(self, chat_id: int, message_id: int) -> None:
        """Persist welcome message id for chat."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                INSERT INTO {TABLES.ui_pins} (chat_id, welcome_message_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    welcome_message_id=excluded.welcome_message_id,
                    updated_at=excluded.updated_at
                """,
                (chat_id, message_id, datetime.utcnow().isoformat()),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error("Failed to persist welcome message id for chat %s: %s", chat_id, error)

    def list_active_income_categories(self, user_id: int) -> List[Dict[str, Any]]:
        """Return active income categories ordered by position."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id, code, title, percent, position
                FROM {TABLES.income_categories}
                WHERE user_id = ? AND is_active = 1
                ORDER BY position, id
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to list income categories for user %s: %s",
                user_id,
                error,
            )
            return []

    def get_income_categories_map(self, user_id: int) -> Dict[str, str]:
        """Return mapping of income category code to title."""

        categories = self.list_active_income_categories(user_id)
        category_map: Dict[str, str] = {}
        for item in categories:
            code = str(item.get("code", "")).strip()
            if not code:
                continue
            title = str(item.get("title", "")).strip()
            category_map[code] = title
        return category_map

    def ensure_expense_categories_seeded(self, user_id: int) -> None:
        """Seed default expense categories if user has none."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT 1 FROM {TABLES.expense_categories} WHERE user_id = ? AND is_active = 1 LIMIT 1",
                (user_id,),
            )
            if cursor.fetchone():
                return

            for item in DEFAULT_EXPENSE_CATEGORIES:
                cursor.execute(
                    f"""
                    INSERT INTO {TABLES.expense_categories} (
                        user_id, code, title, percent, position, is_active
                    )
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (
                        user_id,
                        item["code"],
                        item["title"],
                        item["percent"],
                        item["position"],
                    ),
                )
            self.connection.commit()
            LOGGER.info("Seeded default expense categories for user %s", user_id)
        except sqlite3.Error as error:
            LOGGER.error("Failed to seed expense categories for user %s: %s", user_id, error)

    def ensure_user_settings(self, user_id: int) -> None:
        """Ensure user_settings row exists with defaults."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT 1 FROM {TABLES.user_settings} WHERE user_id = ?",
                (user_id,),
            )
            if cursor.fetchone():
                return

            cursor.execute(
                f"""
                INSERT OR IGNORE INTO {TABLES.user_settings} (
                    user_id,
                    purchased_keep_days,
                    byt_reminders_enabled,
                    byt_defer_enabled,
                    byt_defer_max_days,
                    household_debit_category,
                    wishlist_debit_category_id
                )
                VALUES (?, 30, 1, 1, 365, NULL, NULL)
                """,
                (user_id,),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error("Failed to ensure user_settings for user %s: %s", user_id, error)

    def ensure_byt_timer_defaults(self, user_id: int) -> None:
        """Seed default BYT timer times (12:00, 18:00)."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT 1 FROM {TABLES.byt_timer_times} WHERE user_id = ? AND is_active = 1 LIMIT 1",
                (user_id,),
            )
            if cursor.fetchone():
                return

            for hour, minute in [(12, 0), (18, 0)]:
                cursor.execute(
                    f"""
                    INSERT INTO {TABLES.byt_timer_times} (user_id, hour, minute, is_active)
                    VALUES (?, ?, ?, 1)
                    """,
                    (user_id, hour, minute),
                )
            self.connection.commit()
            LOGGER.info("Seeded default BYT timer times for user %s", user_id)
        except sqlite3.Error as error:
            LOGGER.error("Failed to seed BYT timer times for user %s: %s", user_id, error)

    def list_active_expense_categories(self, user_id: int) -> List[Dict[str, Any]]:
        """Return active expense categories ordered by position."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id, code, title, percent, position
                FROM {TABLES.expense_categories}
                WHERE user_id = ? AND is_active = 1
                ORDER BY position, id
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to list expense categories for user %s: %s",
                user_id,
                error,
            )
            return []

    def list_active_wishlist_categories(self, user_id: int) -> List[Dict[str, Any]]:
        """Return active wishlist categories ordered by position."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id, title, position, is_active, purchased_mode, purchased_days
                FROM {TABLES.wishlist_categories}
                WHERE user_id = ? AND is_active = 1
                ORDER BY position, id
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to list wishlist categories for user %s: %s",
                user_id,
                error,
            )
            return []

    def create_income_category(self, user_id: int, title: str) -> Optional[int]:
        """Create a new income category with zero percent."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT COALESCE(MAX(position), 0) FROM {TABLES.income_categories} WHERE user_id = ?",
                (user_id,),
            )
            current_position = cursor.fetchone()[0] or 0
            code = f"custom_{time.time_ns()}"
            cursor.execute(
                f"""
                INSERT INTO {TABLES.income_categories} (user_id, code, title, percent, position)
                VALUES (?, ?, ?, 0, ?)
                """,
                (user_id, code, title, current_position + 1),
            )
            self.connection.commit()
            return cursor.lastrowid
        except sqlite3.Error as error:
            LOGGER.error("Failed to create income category for user %s: %s", user_id, error)
            return None

    def create_expense_category(self, user_id: int, title: str) -> Optional[int]:
        """Create a new expense category with zero percent."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT COALESCE(MAX(position), 0) FROM {TABLES.expense_categories} WHERE user_id = ?",
                (user_id,),
            )
            current_position = cursor.fetchone()[0] or 0
            code = f"custom_{time.time_ns()}"
            cursor.execute(
                f"""
                INSERT INTO {TABLES.expense_categories} (user_id, code, title, percent, position)
                VALUES (?, ?, ?, 0, ?)
                """,
                (user_id, code, title, current_position + 1),
            )
            self.connection.commit()
            return cursor.lastrowid
        except sqlite3.Error as error:
            LOGGER.error("Failed to create expense category for user %s: %s", user_id, error)
            return None

    def create_wishlist_category(self, user_id: int, title: str) -> Optional[int]:
        """Create a new wishlist category."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT COALESCE(MAX(position), 0) FROM {TABLES.wishlist_categories} WHERE user_id = ?",
                (user_id,),
            )
            current_position = cursor.fetchone()[0] or 0
            self.ensure_user_settings(user_id)
            cursor.execute(
                f"SELECT purchased_keep_days FROM {TABLES.user_settings} WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            default_days = int(row[0]) if row and row[0] is not None else 30
            cursor.execute(
                f"""
                INSERT INTO {TABLES.wishlist_categories} (user_id, title, position, purchased_mode, purchased_days)
                VALUES (?, ?, ?, 'days', ?)
                """,
                (user_id, title, current_position + 1, default_days),
            )
            self.connection.commit()
            return cursor.lastrowid
        except sqlite3.Error as error:
            LOGGER.error("Failed to create wishlist category for user %s: %s", user_id, error)
            return None

    def deactivate_income_category(self, user_id: int, category_id: int) -> None:
        """Deactivate income category."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                UPDATE {TABLES.income_categories}
                SET is_active = 0
                WHERE user_id = ? AND id = ?
                """,
                (user_id, category_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to deactivate income category %s for user %s: %s",
                category_id,
                user_id,
                error,
            )

    def deactivate_expense_category(self, user_id: int, category_id: int) -> None:
        """Deactivate expense category."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                UPDATE {TABLES.expense_categories}
                SET is_active = 0
                WHERE user_id = ? AND id = ?
                """,
                (user_id, category_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to deactivate expense category %s for user %s: %s",
                category_id,
                user_id,
                error,
            )

    def update_income_category_percent(self, user_id: int, category_id: int, percent: int) -> None:
        """Update percent for income category."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                UPDATE {TABLES.income_categories}
                SET percent = ?
                WHERE user_id = ? AND id = ?
                """,
                (percent, user_id, category_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update percent for income category %s of user %s: %s",
                category_id,
                user_id,
                error,
            )

    def update_expense_category_percent(
        self, user_id: int, category_id: int, percent: int
    ) -> None:
        """Update percent for expense category."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                UPDATE {TABLES.expense_categories}
                SET percent = ?
                WHERE user_id = ? AND id = ?
                """,
                (percent, user_id, category_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update percent for expense category %s of user %s: %s",
                category_id,
                user_id,
                error,
            )

    def sum_income_category_percents(self, user_id: int) -> int:
        """Return sum of percents for active income categories."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT COALESCE(SUM(percent), 0) FROM {TABLES.income_categories} WHERE user_id = ? AND is_active = 1",
                (user_id,),
            )
            result = cursor.fetchone()
            return int(result[0]) if result and result[0] is not None else 0
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to calculate percent sum for user %s: %s",
                user_id,
                error,
            )
            return 0

    def sum_expense_category_percents(self, user_id: int) -> int:
        """Return sum of percents for active expense categories."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT COALESCE(SUM(percent), 0) FROM {TABLES.expense_categories} WHERE user_id = ? AND is_active = 1",
                (user_id,),
            )
            result = cursor.fetchone()
            return int(result[0]) if result and result[0] is not None else 0
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to calculate expense percent sum for user %s: %s",
                user_id,
                error,
            )
            return 0

    def get_income_category_by_id(self, user_id: int, category_id: int) -> Optional[Dict[str, Any]]:
        """Return income category by id."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id, code, title, percent, position
                FROM {TABLES.income_categories}
                WHERE user_id = ? AND id = ? AND is_active = 1
                LIMIT 1
                """,
                (user_id, category_id),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to fetch income category %s for user %s: %s",
                category_id,
                user_id,
                error,
            )
            return None

    def get_income_category_by_code(
        self, user_id: int, code: str
    ) -> Optional[Dict[str, Any]]:
        """Return income category by code."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id, code, title, percent, position
                FROM {TABLES.income_categories}
                WHERE user_id = ? AND code = ? AND is_active = 1
                LIMIT 1
                """,
                (user_id, code),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to fetch income category %s for user %s: %s",
                code,
                user_id,
                error,
            )
            return None

    def get_expense_category_by_id(
        self, user_id: int, category_id: int
    ) -> Optional[Dict[str, Any]]:
        """Return expense category by id."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id, code, title, percent, position
                FROM {TABLES.expense_categories}
                WHERE user_id = ? AND id = ? AND is_active = 1
                LIMIT 1
                """,
                (user_id, category_id),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to fetch expense category %s for user %s: %s",
                category_id,
                user_id,
                error,
            )
            return None

    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """Return user settings ensuring defaults exist."""

        self.ensure_user_settings(user_id)
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT
                    user_id,
                    purchased_keep_days,
                    byt_reminders_enabled,
                    byt_defer_enabled,
                    byt_defer_max_days,
                    household_debit_category,
                    wishlist_debit_category_id
                FROM {TABLES.user_settings}
                WHERE user_id = ?
                LIMIT 1
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else {}
        except sqlite3.Error as error:
            LOGGER.error("Failed to fetch user settings for %s: %s", user_id, error)
            return {}

    def get_household_debit_category(self, user_id: int) -> str | None:
        """Return household debit category for user."""

        try:
            self.ensure_user_settings(user_id)
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT household_debit_category FROM {TABLES.user_settings} WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if row:
                return row["household_debit_category"]
            return None
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to fetch household debit category for user %s: %s",
                user_id,
                error,
            )
            return None

    def set_household_debit_category(self, user_id: int, category: str) -> None:
        """Set household debit category for user."""

        try:
            self.ensure_user_settings(user_id)
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                UPDATE {TABLES.user_settings}
                SET household_debit_category = ?
                WHERE user_id = ?
                """,
                (category, user_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update household debit category for user %s: %s",
                user_id,
                error,
            )

    def get_wishlist_debit_category(self, user_id: int) -> str | None:
        """Return wishlist debit category for user."""

        try:
            self.ensure_user_settings(user_id)
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT wishlist_debit_category_id FROM {TABLES.user_settings} WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if row:
                return row["wishlist_debit_category_id"]
            return None
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to fetch wishlist debit category for user %s: %s",
                user_id,
                error,
            )
            return None

    def set_wishlist_debit_category(self, user_id: int, category: str | None) -> None:
        """Set wishlist debit category for user."""

        try:
            self.ensure_user_settings(user_id)
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                UPDATE {TABLES.user_settings}
                SET wishlist_debit_category_id = ?
                WHERE user_id = ?
                """,
                (category, user_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update wishlist debit category for user %s: %s",
                user_id,
                error,
            )

    def resolve_household_debit_category(self, user_id: int) -> tuple[str, str]:
        """Resolve household debit category code and title with fallback."""

        categories = self.list_active_income_categories(user_id)
        category_map = {str(item.get("code", "")): str(item.get("title", "")) for item in categories}
        selected = self.get_household_debit_category(user_id)
        if selected and selected in category_map:
            return selected, category_map[selected]

        fallback_code = None
        if "быт" in category_map:
            fallback_code = "быт"
        elif categories:
            fallback_code = str(categories[0].get("code", "быт"))
        else:
            fallback_code = "быт"

        if selected and selected not in category_map:
            LOGGER.warning(
                "Household debit category invalid for user %s: %s, fallback to %s",
                user_id,
                selected,
                fallback_code,
            )

        return fallback_code, category_map.get(fallback_code, fallback_code)

    def update_purchased_keep_days(self, user_id: int, days: int) -> None:
        """Update purchased_keep_days value."""

        self.ensure_user_settings(user_id)
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"UPDATE {TABLES.user_settings} SET purchased_keep_days = ? WHERE user_id = ?",
                (days, user_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update purchased_keep_days for user %s: %s", user_id, error
            )

    def update_wishlist_category_purchased_mode(
        self, user_id: int, category_id: int, mode: str
    ) -> None:
        """Update purchased display mode for wishlist category."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"UPDATE {TABLES.wishlist_categories} SET purchased_mode = ? WHERE user_id = ? AND id = ?",
                (mode, user_id, category_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update purchased mode for category %s user %s: %s",
                category_id,
                user_id,
                error,
            )

    def update_wishlist_category_purchased_days(
        self, user_id: int, category_id: int, days: int
    ) -> None:
        """Update purchased days retention for wishlist category."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"UPDATE {TABLES.wishlist_categories} SET purchased_days = ? WHERE user_id = ? AND id = ?",
                (days, user_id, category_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update purchased days for category %s user %s: %s",
                category_id,
                user_id,
                error,
            )

    def set_byt_reminders_enabled(self, user_id: int, enabled: bool) -> None:
        """Toggle BYT reminders enabled flag."""

        self.ensure_user_settings(user_id)
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"UPDATE {TABLES.user_settings} SET byt_reminders_enabled = ? WHERE user_id = ?",
                (1 if enabled else 0, user_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update byt_reminders_enabled for user %s: %s", user_id, error
            )

    def set_byt_defer_enabled(self, user_id: int, enabled: bool) -> None:
        """Toggle BYT defer feature flag."""

        self.ensure_user_settings(user_id)
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"UPDATE {TABLES.user_settings} SET byt_defer_enabled = ? WHERE user_id = ?",
                (1 if enabled else 0, user_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update byt_defer_enabled for user %s: %s", user_id, error
            )

    def set_byt_defer_max_days(self, user_id: int, max_days: int) -> None:
        """Update max defer days setting."""

        self.ensure_user_settings(user_id)
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"UPDATE {TABLES.user_settings} SET byt_defer_max_days = ? WHERE user_id = ?",
                (max_days, user_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update byt_defer_max_days for user %s: %s", user_id, error
            )

    def update_byt_defer_max_days(self, user_id: int, days: int) -> None:
        """Alias for set_byt_defer_max_days for compatibility."""

        self.set_byt_defer_max_days(user_id, days)

    def get_wishlist_category_by_id(
        self, user_id: int, category_id: int
    ) -> Optional[Dict[str, Any]]:
        """Return wishlist category by id."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id, title, position, is_active, purchased_mode, purchased_days
                FROM {TABLES.wishlist_categories}
                WHERE user_id = ? AND id = ?
                LIMIT 1
                """,
                (user_id, category_id),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to fetch wishlist category %s for user %s: %s",
                category_id,
                user_id,
                error,
            )
            return None

    def deactivate_wishlist_category(self, user_id: int, category_id: int) -> None:
        """Soft delete wishlist category."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                UPDATE {TABLES.wishlist_categories}
                SET is_active = 0
                WHERE user_id = ? AND id = ?
                """,
                (user_id, category_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to deactivate wishlist category %s for user %s: %s",
                category_id,
                user_id,
                error,
            )

    @staticmethod
    def _column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
        """Return True if column exists in table."""

        cursor.execute(f'PRAGMA table_info("{table}")')
        return any(row[1] == column for row in cursor.fetchall())

    def _add_column_if_missing(
        self, cursor: sqlite3.Cursor, table: str, column: str, definition: str
    ) -> None:
        """Add column to table if it does not already exist."""

        if not self._column_exists(cursor, table, column):
            cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN {column} {definition}')

    def get_user_savings(self, user_id: int) -> Dict[str, Dict[str, Any]]:
        """Get all savings for a user.

        Args:
            user_id (int): Telegram user id.

        Returns:
            dict: Mapping category to saving details.
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT category, current, goal, purpose FROM {TABLES.savings} WHERE user_id = ?",
                (user_id,),
            )
            rows = cursor.fetchall()
            savings = {}
            for row in rows:
                current = self._to_float(row["current"])
                goal = self._to_float(row["goal"])
                savings[row["category"]] = {
                    "current": current,
                    "goal": goal,
                    "purpose": row["purpose"],
                }
            LOGGER.info("Fetched savings for user %s", user_id)
            return savings
        except sqlite3.Error as error:
            LOGGER.error("Failed to fetch savings for user %s: %s", user_id, error)
            return {}

    def get_user_savings_map(self, user_id: int) -> Dict[str, float]:
        """Return a simple mapping of category to current savings.

        Args:
            user_id (int): Telegram user id.

        Returns:
            dict[str, float]: Mapping of category names to current amount.
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT category, current FROM {TABLES.savings} WHERE user_id = ?",
                (user_id,),
            )
            rows = cursor.fetchall()
            mapping = {}
            for row in rows:
                mapping[row["category"]] = self._to_float(row["current"])
            LOGGER.info("Fetched savings map for user %s", user_id)
            return mapping
        except sqlite3.Error as error:
            LOGGER.error("Failed to fetch savings map for user %s: %s", user_id, error)
            return {}

    def update_saving(self, user_id: int, category: str, amount_delta: float) -> None:
        """Update saving for category by amount delta.

        Args:
            user_id (int): Telegram user id.
            category (str): Category name.
            amount_delta (float): Amount to add or subtract.
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT id, current FROM {TABLES.savings} WHERE user_id = ? AND category = ?",
                (user_id, category),
            )
            row = cursor.fetchone()
            delta = self._to_float(amount_delta)
            if row:
                current = self._to_float(row["current"])
                new_value = current + delta
                cursor.execute(
                    f"UPDATE {TABLES.savings} SET current = ? WHERE id = ?",
                    (new_value, row["id"]),
                )
            else:
                cursor.execute(
                    f"INSERT INTO {TABLES.savings} (user_id, category, current, goal, purpose) VALUES (?, ?, ?, 0, '')",
                    (user_id, category, delta),
                )
            self.connection.commit()
            LOGGER.info(
                "Updated saving for user %s category %s by %s",
                user_id,
                category,
                amount_delta,
            )
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update saving for user %s category %s: %s",
                user_id,
                category,
                error,
            )

    def _update_saving_in_transaction(
        self,
        cursor: sqlite3.Cursor,
        user_id: int,
        category: str,
        amount_delta: float,
    ) -> None:
        cursor.execute(
            f"SELECT id, current FROM {TABLES.savings} WHERE user_id = ? AND category = ?",
            (user_id, category),
        )
        row = cursor.fetchone()
        delta = self._to_float(amount_delta)
        if row:
            current = self._to_float(row["current"])
            new_value = current + delta
            cursor.execute(
                f"UPDATE {TABLES.savings} SET current = ? WHERE id = ?",
                (new_value, row["id"]),
            )
        else:
            cursor.execute(
                f"INSERT INTO {TABLES.savings} (user_id, category, current, goal, purpose) VALUES (?, ?, ?, 0, '')",
                (user_id, category, delta),
            )

    def decrease_savings(self, user_id: int, category: str, amount: float) -> None:
        """Decrease savings for category by amount."""

        self.update_saving(user_id, category, -abs(amount))

    def set_goal(self, user_id: int, category: str, goal: float, purpose: str) -> None:
        """Set goal and purpose for saving category."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT id FROM {TABLES.savings} WHERE user_id = ? AND category = ?",
                (user_id, category),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    f"UPDATE {TABLES.savings} SET goal = ?, purpose = ? WHERE id = ?",
                    (goal, purpose, row["id"]),
                )
            else:
                cursor.execute(
                    f"INSERT INTO {TABLES.savings} (user_id, category, current, goal, purpose) VALUES (?, ?, 0, ?, ?)",
                    (user_id, category, goal, goal, purpose),
                )
            self.connection.commit()
            LOGGER.info("Set goal for user %s category %s", user_id, category)
        except sqlite3.Error as error:
            LOGGER.error("Failed to set goal for user %s category %s: %s", user_id, category, error)

    def reset_goals(self, user_id: int) -> None:
        """Reset goals for user."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"UPDATE {TABLES.savings} SET goal = 0, purpose = '' WHERE user_id = ?",
                (user_id,),
            )
            self.connection.commit()
            LOGGER.info("Reset goals for user %s", user_id)
        except sqlite3.Error as error:
            LOGGER.error("Failed to reset goals for user %s: %s", user_id, error)

    def add_wish(self, user_id: int, name: str, price: float, url: Optional[str], category: str) -> int:
        """Add a wish to the wishlist."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"INSERT INTO {TABLES.wishes} (user_id, name, price, url, category, is_purchased, saved_amount, purchased_at) VALUES (?, ?, ?, ?, ?, 0, 0, NULL)",
                (user_id, name, price, url, category),
            )
            self.connection.commit()
            wish_id = cursor.lastrowid
            LOGGER.info("Added wish %s for user %s", wish_id, user_id)
            return wish_id
        except sqlite3.Error as error:
            LOGGER.error("Failed to add wish for user %s: %s", user_id, error)
            return 0

    def get_wishes_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all wishes for a user."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id, name, price, url, category, is_purchased, saved_amount, purchased_at, debited_at, deferred_until
                FROM {TABLES.wishes}
                WHERE user_id = ?
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            LOGGER.info("Fetched wishes for user %s", user_id)
            return [dict(row) for row in rows]
        except sqlite3.Error as error:
            LOGGER.error("Failed to fetch wishes for user %s: %s", user_id, error)
            return []

    def get_wish(self, wish_id: int) -> Optional[Dict[str, Any]]:
        """Get wish by id."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id, user_id, name, price, url, category, is_purchased, saved_amount, purchased_at, debited_at, deferred_until
                FROM {TABLES.wishes}
                WHERE id = ?
                """,
                (wish_id,),
            )
            row = cursor.fetchone()
            LOGGER.info("Fetched wish %s", wish_id)
            return dict(row) if row else None
        except sqlite3.Error as error:
            LOGGER.error("Failed to fetch wish %s: %s", wish_id, error)
            return None

    def get_active_byt_wishes(self, user_id: int) -> List[Dict[str, Any]]:
        """Return active BYT wishes for user."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id, user_id, name, price, url, category, is_purchased, saved_amount, purchased_at, deferred_until
                FROM {TABLES.wishes}
                WHERE user_id = ? AND category IN ('byt', 'БЫТ') AND (is_purchased = 0 OR is_purchased IS NULL)
                ORDER BY id
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            LOGGER.info("Fetched active BYT wishes for user %s", user_id)
            return [dict(row) for row in rows]
        except sqlite3.Error as error:
            LOGGER.error("Failed to fetch BYT wishes for user %s: %s", user_id, error)
            return []

    def list_active_byt_items_for_reminder(
        self, user_id: int, now_dt: datetime
    ) -> List[Dict[str, Any]]:
        """Return BYT wishlist items available for reminders at given time."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id, user_id, name, price, url, category, is_purchased, saved_amount, purchased_at, deferred_until
                FROM {TABLES.wishes}
                WHERE user_id = ?
                  AND category IN ('byt', 'БЫТ')
                  AND (is_purchased = 0 OR is_purchased IS NULL)
                  AND (deferred_until IS NULL OR deferred_until <= ?)
                ORDER BY id
                """,
                (user_id, now_dt.isoformat()),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to fetch BYT reminder wishes for user %s: %s", user_id, error
            )
            return []

    def set_wishlist_item_deferred_until(
        self, user_id: int, item_id: int, deferred_until_iso: Optional[str]
    ) -> None:
        """Set deferred_until for wishlist item."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                UPDATE {TABLES.wishes}
                SET deferred_until = ?
                WHERE id = ? AND user_id = ?
                """,
                (deferred_until_iso, item_id, user_id),
            )
            self.connection.commit()
            LOGGER.info(
                "Set deferred_until for wish %s user %s to %s",
                item_id,
                user_id,
                deferred_until_iso,
            )
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to set deferred_until for wish %s user %s: %s",
                item_id,
                user_id,
                error,
            )

    def mark_wish_purchased(self, wish_id: int, purchased_at: Optional[datetime] = None) -> None:
        """Mark wish as purchased with timestamp."""

        try:
            cursor = self.connection.cursor()
            purchased_value = (purchased_at or now_tz()).isoformat()
            cursor.execute(
                f"""
                UPDATE {TABLES.wishes}
                SET is_purchased = 1, purchased_at = ?, deferred_until = NULL
                WHERE id = ?
                """,
                (purchased_value, wish_id),
            )
            self.connection.commit()
            LOGGER.info("Marked wish %s as purchased", wish_id)
        except sqlite3.Error as error:
            LOGGER.error("Failed to mark wish %s as purchased: %s", wish_id, error)

    def purchase_wish(
        self, user_id: int, wish_id: int, debit_category: str | None
    ) -> Dict[str, Any]:
        """Purchase wish with debit in a single transaction."""

        cursor = self.connection.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                f"""
                SELECT id, user_id, name, price, category, is_purchased, debited_at
                FROM {TABLES.wishes}
                WHERE id = ? AND user_id = ?
                LIMIT 1
                """,
                (wish_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                cursor.execute("ROLLBACK")
                return {"status": "not_found"}

            if row["is_purchased"] or row["debited_at"]:
                cursor.execute("ROLLBACK")
                return {"status": "already"}

            price = self._to_float(row["price"])
            if price <= 0 or debit_category is None:
                purchased_value = now_tz().isoformat()
                cursor.execute(
                    f"""
                    UPDATE {TABLES.wishes}
                    SET is_purchased = 1, purchased_at = ?, deferred_until = NULL
                    WHERE id = ?
                    """,
                    (purchased_value, wish_id),
                )
                cursor.execute(
                    f"""
                    INSERT INTO {TABLES.purchases} (user_id, wish_name, price, category, purchased_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, row["name"], price, row["category"], purchased_value),
                )
                cursor.execute("COMMIT")
                return {
                    "status": "no_debit",
                    "price": price,
                    "wish_name": row["name"],
                    "category": row["category"],
                }

            cursor.execute(
                f"SELECT id, current FROM {TABLES.savings} WHERE user_id = ? AND category = ?",
                (user_id, debit_category),
            )
            savings_row = cursor.fetchone()
            savings_before = self._to_float(savings_row["current"]) if savings_row else 0.0
            if savings_before < price:
                cursor.execute("ROLLBACK")
                return {
                    "status": "insufficient",
                    "price": price,
                    "available": savings_before,
                }

            self._update_saving_in_transaction(cursor, user_id, debit_category, -price)
            purchased_value = now_tz().isoformat()
            cursor.execute(
                f"""
                UPDATE {TABLES.wishes}
                SET is_purchased = 1, purchased_at = ?, debited_at = ?, deferred_until = NULL
                WHERE id = ?
                """,
                (purchased_value, purchased_value, wish_id),
            )
            cursor.execute(
                f"""
                INSERT INTO {TABLES.purchases} (user_id, wish_name, price, category, purchased_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, row["name"], price, row["category"], purchased_value),
            )
            cursor.execute("COMMIT")
            return {
                "status": "debited",
                "price": price,
                "wish_name": row["name"],
                "category": row["category"],
                "savings_before": savings_before,
            }
        except sqlite3.Error as error:
            cursor.execute("ROLLBACK")
            LOGGER.error("Failed to purchase wish %s for user %s: %s", wish_id, user_id, error)
            return {"status": "error"}

    def add_purchase(
        self,
        user_id: int,
        wish_name: str,
        price: float,
        category: str,
        purchased_at: Optional[datetime] = None,
    ) -> None:
        """Add purchase record."""

        try:
            cursor = self.connection.cursor()
            purchased_value = (purchased_at or now_tz()).isoformat()
            cursor.execute(
                f"INSERT INTO {TABLES.purchases} (user_id, wish_name, price, category, purchased_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, wish_name, price, category, purchased_value),
            )
            self.connection.commit()
            LOGGER.info("Added purchase for user %s", user_id)
        except sqlite3.Error as error:
            LOGGER.error("Failed to add purchase for user %s: %s", user_id, error)

    async def household_status_exists(self, user_id: int, month: str) -> bool:
        """Check if household payment statuses exist for month."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT 1 FROM {TABLES.household_payments} WHERE user_id = ? AND month = ? LIMIT 1",
                (user_id, month),
            )
            return cursor.fetchone() is not None
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to check household status for user %s month %s: %s",
                user_id,
                month,
                error,
            )
            return False

    async def init_household_questions_for_month(self, user_id: int, month: str) -> None:
        """Initialize household payment questions for month."""

        try:
            if BOT_USER_ID is not None and user_id == BOT_USER_ID:
                LOGGER.warning(
                    "Skipping household questions init for bot user %s", user_id
                )
                return
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                INSERT OR IGNORE INTO {TABLES.household_payments} (user_id, month, question_code, is_paid)
                SELECT ?, ?, code, 0
                FROM {TABLES.household_payment_items}
                WHERE user_id = ? AND is_active = 1
                """,
                (user_id, month, user_id),
            )
            self.connection.commit()
            LOGGER.info(
                "Initialized household questions for user %s month %s", user_id, month
            )
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to init household questions for user %s month %s: %s",
                user_id,
                month,
                error,
            )

    async def mark_household_question_paid(
        self, user_id: int, month: str, question_code: str
    ) -> None:
        """Mark household question as paid."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                INSERT INTO {TABLES.household_payments} (user_id, month, question_code, is_paid)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, month, question_code)
                DO UPDATE SET is_paid = excluded.is_paid
                """,
                (user_id, month, question_code),
            )
            self.connection.commit()
            LOGGER.info(
                "Marked household question %s as paid for user %s month %s",
                question_code,
                user_id,
                month,
            )
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to mark household question %s paid for user %s month %s: %s",
                question_code,
                user_id,
                month,
                error,
            )

    async def mark_household_question_unpaid(
        self, user_id: int, month: str, question_code: str
    ) -> None:
        """Mark household question as unpaid."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                INSERT INTO {TABLES.household_payments} (user_id, month, question_code, is_paid)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(user_id, month, question_code)
                DO UPDATE SET is_paid = excluded.is_paid
                """,
                (user_id, month, question_code),
            )
            self.connection.commit()
            LOGGER.info(
                "Marked household question %s as unpaid for user %s month %s",
                question_code,
                user_id,
                month,
            )
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to mark household question %s unpaid for user %s month %s: %s",
                question_code,
                user_id,
                month,
                error,
            )

    def apply_household_payment_answer(
        self,
        user_id: int,
        month: str,
        question_code: str,
        amount: float | None,
        answer: str,
        debit_category: str | None = None,
    ) -> bool:
        """Apply household answer and savings update atomically.

        Returns True if state changed, False if it was already applied.
        """

        try:
            cursor = self.connection.cursor()
            self.connection.execute("BEGIN")
            cursor.execute(
                f"""
                SELECT is_paid
                FROM {TABLES.household_payments}
                WHERE user_id = ? AND month = ? AND question_code = ?
                """,
                (user_id, month, question_code),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    f"""
                    INSERT INTO {TABLES.household_payments} (user_id, month, question_code, is_paid)
                    VALUES (?, ?, ?, 0)
                    """,
                    (user_id, month, question_code),
                )
                current_paid = 0
            else:
                current_paid = int(row["is_paid"])

            target_paid = 1 if answer == "yes" else 0
            if current_paid == target_paid:
                self.connection.commit()
                return False

            cursor.execute(
                f"""
                UPDATE {TABLES.household_payments}
                SET is_paid = ?
                WHERE user_id = ? AND month = ? AND question_code = ?
                """,
                (target_paid, user_id, month, question_code),
            )
            if amount is not None:
                delta = -abs(amount) if answer == "yes" else abs(amount)
                target_category = debit_category or "быт"
                self._update_saving_in_transaction(cursor, user_id, target_category, delta)
            self.connection.commit()
            return True
        except sqlite3.Error as error:
            self.connection.rollback()
            LOGGER.error(
                "Failed to apply household answer for user %s month %s code %s: %s",
                user_id,
                month,
                question_code,
                error,
            )
            return False

    async def get_unpaid_household_questions(self, user_id: int, month: str) -> List[str]:
        """Get unpaid household question codes for user and month."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT items.code
                FROM {TABLES.household_payment_items} AS items
                LEFT JOIN {TABLES.household_payments} AS payments
                  ON payments.user_id = items.user_id
                 AND payments.month = ?
                 AND payments.question_code = items.code
                WHERE items.user_id = ?
                  AND items.is_active = 1
                  AND COALESCE(payments.is_paid, 0) = 0
                ORDER BY items.position, items.id
                """,
                (month, user_id),
            )
            rows = cursor.fetchall()
            return [row["code"] for row in rows]
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to get unpaid household questions for user %s month %s: %s",
                user_id,
                month,
                error,
            )
            return []

    async def get_household_payment_status_map(
        self, user_id: int, month: str
    ) -> Dict[str, int]:
        """Return mapping: question_code -> is_paid (0/1) for the given month."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT items.code, COALESCE(payments.is_paid, 0) AS is_paid
                FROM {TABLES.household_payment_items} AS items
                LEFT JOIN {TABLES.household_payments} AS payments
                  ON payments.user_id = items.user_id
                 AND payments.month = ?
                 AND payments.question_code = items.code
                WHERE items.user_id = ? AND items.is_active = 1
                """,
                (month, user_id),
            )
            rows = cursor.fetchall()
            return {row["code"]: int(row["is_paid"]) for row in rows}
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to get household payment status for user %s month %s: %s",
                user_id,
                month,
                error,
            )
            return {}

    async def has_unpaid_household_questions(self, user_id: int, month: str) -> bool:
        """Return True if unpaid household questions exist for month."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT 1
                FROM {TABLES.household_payment_items} AS items
                LEFT JOIN {TABLES.household_payments} AS payments
                  ON payments.user_id = items.user_id
                 AND payments.month = ?
                 AND payments.question_code = items.code
                WHERE items.user_id = ?
                  AND items.is_active = 1
                  AND COALESCE(payments.is_paid, 0) = 0
                LIMIT 1
                """,
                (month, user_id),
            )
            return cursor.fetchone() is not None
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to check unpaid household questions for user %s month %s: %s",
                user_id,
                month,
                error,
            )
            return False

    async def should_show_household_payments_button(
        self, user_id: int, month: str
    ) -> bool:
        """Return True if any active household payment is unpaid for the month."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT 1
                FROM {TABLES.household_payment_items} AS items
                LEFT JOIN {TABLES.household_payments} AS payments
                  ON payments.user_id = items.user_id
                 AND payments.month = ?
                 AND payments.question_code = items.code
                WHERE items.user_id = ?
                  AND items.is_active = 1
                  AND COALESCE(payments.is_paid, 0) = 0
                LIMIT 1
                """,
                (month, user_id),
            )
            return cursor.fetchone() is not None
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to decide household payments button for user %s month %s: %s",
                user_id,
                month,
                error,
            )
            return False

    async def reset_household_questions_for_month(self, user_id: int, month: str) -> None:
        """Reset household payment progress for a specific month."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                UPDATE {TABLES.household_payments}
                SET is_paid = 0
                WHERE user_id = ? AND month = ?
                """,
                (user_id, month),
            )
            cursor.execute(
                f"""
                INSERT OR IGNORE INTO {TABLES.household_payments} (user_id, month, question_code, is_paid)
                SELECT ?, ?, code, 0
                FROM {TABLES.household_payment_items}
                WHERE user_id = ? AND is_active = 1
                """,
                (user_id, month, user_id),
            )
            self.connection.commit()
            LOGGER.info(
                "Reset household questions for user %s month %s", user_id, month
            )
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to reset household questions for user %s month %s: %s",
                user_id,
                month,
                error,
            )

    def get_purchases_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Get purchases for user honoring retention settings."""

        self.ensure_user_settings(user_id)
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT id, wish_name, price, category, purchased_at FROM {TABLES.purchases} WHERE user_id = ? ORDER BY purchased_at DESC",
                (user_id,),
            )
            rows = cursor.fetchall()
            LOGGER.info("Fetched purchases for user %s", user_id)
            purchases = [dict(row) for row in rows]
            filtered: list[Dict[str, Any]] = []
            current_time = now_tz()
            settings_row = self.get_user_settings(user_id)
            default_days = int(settings_row.get("purchased_keep_days", 30) or 30)
            categories = self.list_active_wishlist_categories(user_id)
            category_map = {
                cat.get("title", ""): {
                    "mode": (cat.get("purchased_mode") or "days"),
                    "days": int(cat.get("purchased_days") or default_days),
                }
                for cat in categories
            }
            for purchase in purchases:
                cat_settings = category_map.get(
                    str(purchase.get("category", "")),
                    {"mode": "days", "days": default_days},
                )
                if cat_settings.get("mode") == "always":
                    filtered.append(purchase)
                    continue
                keep_delta = timedelta(days=int(cat_settings.get("days", default_days)))
                timestamp = purchase.get("purchased_at")
                if timestamp:
                    try:
                        purchase_dt = datetime.fromisoformat(str(timestamp))
                        if purchase_dt.tzinfo is None:
                            purchase_dt = purchase_dt.replace(tzinfo=settings.TIMEZONE)
                    except ValueError:
                        continue
                    if purchase_dt + keep_delta <= current_time:
                        continue
                filtered.append(purchase)
            return filtered
        except sqlite3.Error as error:
            LOGGER.error("Failed to fetch purchases for user %s: %s", user_id, error)
            return []

    def list_active_byt_timer_times(self, user_id: int) -> List[Dict[str, Any]]:
        """Return active BYT timer times for user."""

        self.ensure_byt_timer_defaults(user_id)
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id, hour, minute
                FROM {TABLES.byt_timer_times}
                WHERE user_id = ? AND is_active = 1
                ORDER BY hour, minute, id
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to fetch BYT timer times for user %s: %s", user_id, error
            )
            return []

    def add_byt_timer_time(self, user_id: int, hour: int, minute: int) -> Optional[int]:
        """Add a new BYT timer time if not duplicate."""

        self.ensure_byt_timer_defaults(user_id)
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT id FROM {TABLES.byt_timer_times}
                WHERE user_id = ? AND hour = ? AND minute = ? AND is_active = 1
                LIMIT 1
                """,
                (user_id, hour, minute),
            )
            existing = cursor.fetchone()
            if existing:
                return int(existing["id"])

            cursor.execute(
                f"""
                INSERT INTO {TABLES.byt_timer_times} (user_id, hour, minute, is_active)
                VALUES (?, ?, ?, 1)
                """,
                (user_id, hour, minute),
            )
            self.connection.commit()
            return cursor.lastrowid
        except sqlite3.Error as error:
            LOGGER.error("Failed to add BYT timer time for user %s: %s", user_id, error)
            return None

    def deactivate_byt_timer_time(self, user_id: int, timer_id: int) -> None:
        """Deactivate specific BYT timer time."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                UPDATE {TABLES.byt_timer_times}
                SET is_active = 0
                WHERE user_id = ? AND id = ?
                """,
                (user_id, timer_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to deactivate BYT timer time %s for user %s: %s",
                timer_id,
                user_id,
                error,
            )

    def reset_byt_timer_times(self, user_id: int) -> None:
        """Reset BYT timer times to defaults."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"UPDATE {TABLES.byt_timer_times} SET is_active = 0 WHERE user_id = ?",
                (user_id,),
            )
            for hour, minute in [(12, 0), (18, 0)]:
                cursor.execute(
                    f"""
                    INSERT INTO {TABLES.byt_timer_times} (user_id, hour, minute, is_active)
                    VALUES (?, ?, ?, 1)
                    """,
                    (user_id, hour, minute),
                )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error("Failed to reset BYT timer times for user %s: %s", user_id, error)

    def get_users_with_byt_timer_times(self) -> List[int]:
        """Return users that have BYT timer times configured."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT DISTINCT user_id
                FROM {TABLES.byt_timer_times}
                WHERE is_active = 1
                """
            )
            rows = cursor.fetchall()
            return [int(row["user_id"]) for row in rows]
        except sqlite3.Error as error:
            LOGGER.error("Failed to get users with BYT timer times: %s", error)
            return []

    def get_users_with_active_byt_wishes(self) -> List[int]:
        """Return user ids that have active BYT wishes."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"""
                SELECT DISTINCT user_id
                FROM {TABLES.wishes}
                WHERE category IN ('byt', 'БЫТ') AND (is_purchased = 0 OR is_purchased IS NULL)
                """
            )
            rows = cursor.fetchall()
            return [int(row["user_id"]) for row in rows]
        except sqlite3.Error as error:
            LOGGER.error("Failed to get users with active BYT wishes: %s", error)
            return []

    def cleanup_old_byt_purchases(self, now: Optional[datetime] = None) -> None:
        """Remove BYT purchases older than one month from purchases and wishes."""

        current_time = now or now_tz()
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT id, purchased_at FROM {TABLES.purchases} WHERE category IN ('byt', 'БЫТ')"
            )
            purchases = cursor.fetchall()
            ids_to_delete: list[int] = []
            for purchase in purchases:
                timestamp = purchase["purchased_at"]
                if not timestamp:
                    continue
                try:
                    purchase_dt = datetime.fromisoformat(timestamp)
                    if purchase_dt.tzinfo is None:
                        purchase_dt = purchase_dt.replace(tzinfo=settings.TIMEZONE)
                except ValueError:
                    continue
                if add_one_month(purchase_dt) <= current_time:
                    ids_to_delete.append(int(purchase["id"]))

            if ids_to_delete:
                placeholders = ",".join("?" * len(ids_to_delete))
                query = "DELETE FROM {} WHERE id IN ({})".format(
                    TABLES.purchases,
                    placeholders,
                )
                cursor.execute(
                    query,
                    ids_to_delete,
                )

            cursor.execute(
                f"SELECT id, purchased_at FROM {TABLES.wishes} WHERE category IN ('byt', 'БЫТ') AND is_purchased = 1"
            )
            wish_rows = cursor.fetchall()
            wish_ids: list[int] = []
            for wish in wish_rows:
                purchased_at = wish["purchased_at"]
                if not purchased_at:
                    continue
                try:
                    wish_dt = datetime.fromisoformat(purchased_at)
                    if wish_dt.tzinfo is None:
                        wish_dt = wish_dt.replace(tzinfo=settings.TIMEZONE)
                except ValueError:
                    continue
                if add_one_month(wish_dt) <= current_time:
                    wish_ids.append(int(wish["id"]))

            if wish_ids:
                placeholders = ",".join("?" * len(wish_ids))
                query = "DELETE FROM {} WHERE id IN ({})".format(
                    TABLES.wishes,
                    placeholders,
                )
                cursor.execute(
                    query,
                    wish_ids,
                )
            if ids_to_delete or wish_ids:
                self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error("Failed to cleanup old BYT purchases: %s", error)

    def close(self) -> None:
        """Close database connection."""

        try:
            self.connection.close()
            LOGGER.info("Database connection closed")
        except sqlite3.Error as error:
            LOGGER.error("Failed to close database connection: %s", error)
