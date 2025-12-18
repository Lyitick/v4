"""Database CRUD operations for finance bot."""
from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from Bot.config import settings
from Bot.utils.datetime_utils import add_one_month, now_tz


LOGGER = logging.getLogger(__name__)
DB_PATH = Path(__file__).resolve().parents[2] / "finance.db"
DEFAULT_HOUSEHOLD_ITEMS = [
    {"code": "phone", "text": "Телефон 600р?", "amount": 600},
    {"code": "internet", "text": "Интернет 700р?", "amount": 700},
    {"code": "vpn", "text": "VPN 100р?", "amount": 100},
    {"code": "gpt", "text": "GPT 2000р?", "amount": 2000},
    {"code": "yandex_sub", "text": "Яндекс подписка 400р?", "amount": 400},
    {"code": "rent", "text": "Квартплата 4000р? Папе скинул?", "amount": 4000},
    {"code": "training_495", "text": "Оплатил тренировки 495 - 5000р?", "amount": 5000},
]

DEFAULT_INCOME_CATEGORIES = [
    {"code": "долги", "title": "Убил боль?", "percent": 30, "position": 1},
    {
        "code": "быт",
        "title": "бытовые расходы на Тиньк",
        "percent": 20,
        "position": 2,
    },
    {
        "code": "инвестиции",
        "title": "Инвестиции на Альфу",
        "percent": 20,
        "position": 3,
    },
    {
        "code": "сбережения",
        "title": "Сбережения на Сбер",
        "percent": 20,
        "position": 4,
    },
    {
        "code": "спонтанные траты",
        "title": "спонтанные траты на Яндекс",
        "percent": 10,
        "position": 5,
    },
]

DEFAULT_EXPENSE_CATEGORIES = [
    {"code": "базовые", "title": "Базовые расходы", "percent": 40, "position": 1},
    {"code": "жилье", "title": "Жилье и ЖКУ", "percent": 20, "position": 2},
    {"code": "транспорт", "title": "Транспорт", "percent": 15, "position": 3},
    {"code": "еда", "title": "Еда", "percent": 15, "position": 4},
    {"code": "другое", "title": "Другое", "percent": 10, "position": 5},
]

DEFAULT_WISHLIST_CATEGORIES = [
    {"title": "инвестиции в работу", "position": 1},
    {"title": "вклад в себя", "position": 2},
    {"title": "кайфы", "position": 3},
    {"title": "БЫТ", "position": 4},
]


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
            """
            CREATE TABLE IF NOT EXISTS savings (
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
            """
            CREATE TABLE IF NOT EXISTS wishes (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                name TEXT,
                price REAL,
                url TEXT,
                category TEXT,
                is_purchased INTEGER,
                saved_amount REAL DEFAULT 0,
                purchased_at TEXT,
                deferred_until TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                wish_name TEXT,
                price REAL,
                category TEXT,
                purchased_at TEXT
            )
            """
        )
        self._add_column_if_missing(cursor, "wishes", "deferred_until", "TEXT")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS household_payments (
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
            """
            CREATE TABLE IF NOT EXISTS household_payment_items (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                code TEXT,
                text TEXT,
                amount INTEGER,
                position INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                UNIQUE(user_id, code)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS income_categories (
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
            """
            CREATE TABLE IF NOT EXISTS expense_categories (
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
            """
            CREATE TABLE IF NOT EXISTS wishlist_categories (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                position INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                purchased_keep_days INTEGER NOT NULL DEFAULT 30,
                byt_reminders_enabled INTEGER NOT NULL DEFAULT 1,
                byt_defer_enabled INTEGER NOT NULL DEFAULT 1,
                byt_defer_max_days INTEGER NOT NULL DEFAULT 365
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS byt_timer_times (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                minute INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        self._add_column_if_missing(cursor, "wishes", "purchased_at", "TEXT")
        self.connection.commit()

    def ensure_household_items_seeded(self, user_id: int) -> None:
        """Seed default household payment items if missing for user."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT 1 FROM household_payment_items WHERE user_id = ? LIMIT 1",
                (user_id,),
            )
            if cursor.fetchone():
                return

            now_iso = now_tz().isoformat()
            for position, item in enumerate(DEFAULT_HOUSEHOLD_ITEMS, start=1):
                cursor.execute(
                    """
                    INSERT INTO household_payment_items (
                        user_id, code, text, amount, position, is_active, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        user_id,
                        item["code"],
                        item["text"],
                        item["amount"],
                        position,
                        now_iso,
                    ),
                )
            self.connection.commit()
            LOGGER.info("Seeded default household items for user %s", user_id)
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to seed household items for user %s: %s", user_id, error
            )

    def list_active_household_items(self, user_id: int) -> List[Dict[str, Any]]:
        """Return active household payment items for user ordered by position."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT code, text, amount, position
                FROM household_payment_items
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
                """
                SELECT code, text, amount, position
                FROM household_payment_items
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
                "SELECT MAX(position) FROM household_payment_items WHERE user_id = ?",
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
                """
                INSERT INTO household_payment_items (
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
                """
                UPDATE household_payment_items
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

    def ensure_income_categories_seeded(self, user_id: int) -> None:
        """Seed default income categories if user has none."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT 1 FROM income_categories WHERE user_id = ? AND is_active = 1 LIMIT 1",
                (user_id,),
            )
            if cursor.fetchone():
                return

            for item in DEFAULT_INCOME_CATEGORIES:
                cursor.execute(
                    """
                    INSERT INTO income_categories (
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
            LOGGER.info("Seeded default income categories for user %s", user_id)
        except sqlite3.Error as error:
            LOGGER.error("Failed to seed income categories for user %s: %s", user_id, error)

    def list_active_income_categories(self, user_id: int) -> List[Dict[str, Any]]:
        """Return active income categories ordered by position."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT id, code, title, percent, position
                FROM income_categories
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

    def ensure_expense_categories_seeded(self, user_id: int) -> None:
        """Seed default expense categories if user has none."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT 1 FROM expense_categories WHERE user_id = ? AND is_active = 1 LIMIT 1",
                (user_id,),
            )
            if cursor.fetchone():
                return

            for item in DEFAULT_EXPENSE_CATEGORIES:
                cursor.execute(
                    """
                    INSERT INTO expense_categories (
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

    def ensure_wishlist_categories_seeded(self, user_id: int) -> None:
        """Seed default wishlist categories if user has none."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT 1 FROM wishlist_categories WHERE user_id = ? AND is_active = 1 LIMIT 1",
                (user_id,),
            )
            if cursor.fetchone():
                return

            for item in DEFAULT_WISHLIST_CATEGORIES:
                cursor.execute(
                    """
                    INSERT INTO wishlist_categories (user_id, title, position, is_active)
                    VALUES (?, ?, ?, 1)
                    """,
                    (
                        user_id,
                        item["title"],
                        item["position"],
                    ),
                )
            self.connection.commit()
            LOGGER.info("Seeded default wishlist categories for user %s", user_id)
        except sqlite3.Error as error:
            LOGGER.error("Failed to seed wishlist categories for user %s: %s", user_id, error)

    def ensure_user_settings(self, user_id: int) -> None:
        """Ensure user_settings row exists with defaults."""

        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1 FROM user_settings WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                return

            cursor.execute(
                """
                INSERT OR IGNORE INTO user_settings (
                    user_id, purchased_keep_days, byt_reminders_enabled, byt_defer_enabled, byt_defer_max_days
                )
                VALUES (?, 30, 1, 1, 365)
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
                "SELECT 1 FROM byt_timer_times WHERE user_id = ? AND is_active = 1 LIMIT 1",
                (user_id,),
            )
            if cursor.fetchone():
                return

            for hour, minute in [(12, 0), (18, 0)]:
                cursor.execute(
                    """
                    INSERT INTO byt_timer_times (user_id, hour, minute, is_active)
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
                """
                SELECT id, code, title, percent, position
                FROM expense_categories
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
                """
                SELECT id, title, position, is_active
                FROM wishlist_categories
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
                "SELECT COALESCE(MAX(position), 0) FROM income_categories WHERE user_id = ?",
                (user_id,),
            )
            current_position = cursor.fetchone()[0] or 0
            code = f"custom_{time.time_ns()}"
            cursor.execute(
                """
                INSERT INTO income_categories (user_id, code, title, percent, position)
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
                "SELECT COALESCE(MAX(position), 0) FROM expense_categories WHERE user_id = ?",
                (user_id,),
            )
            current_position = cursor.fetchone()[0] or 0
            code = f"custom_{time.time_ns()}"
            cursor.execute(
                """
                INSERT INTO expense_categories (user_id, code, title, percent, position)
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
                "SELECT COALESCE(MAX(position), 0) FROM wishlist_categories WHERE user_id = ?",
                (user_id,),
            )
            current_position = cursor.fetchone()[0] or 0
            cursor.execute(
                """
                INSERT INTO wishlist_categories (user_id, title, position)
                VALUES (?, ?, ?)
                """,
                (user_id, title, current_position + 1),
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
                """
                UPDATE income_categories
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
                """
                UPDATE expense_categories
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
                """
                UPDATE income_categories
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
                """
                UPDATE expense_categories
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
                "SELECT COALESCE(SUM(percent), 0) FROM income_categories WHERE user_id = ? AND is_active = 1",
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
                "SELECT COALESCE(SUM(percent), 0) FROM expense_categories WHERE user_id = ? AND is_active = 1",
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
                """
                SELECT id, code, title, percent, position
                FROM income_categories
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

    def get_expense_category_by_id(
        self, user_id: int, category_id: int
    ) -> Optional[Dict[str, Any]]:
        """Return expense category by id."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT id, code, title, percent, position
                FROM expense_categories
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
                """
                SELECT user_id, purchased_keep_days, byt_reminders_enabled, byt_defer_enabled, byt_defer_max_days
                FROM user_settings
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

    def update_purchased_keep_days(self, user_id: int, days: int) -> None:
        """Update purchased_keep_days value."""

        self.ensure_user_settings(user_id)
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "UPDATE user_settings SET purchased_keep_days = ? WHERE user_id = ?",
                (days, user_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update purchased_keep_days for user %s: %s", user_id, error
            )

    def set_byt_reminders_enabled(self, user_id: int, enabled: bool) -> None:
        """Toggle BYT reminders enabled flag."""

        self.ensure_user_settings(user_id)
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "UPDATE user_settings SET byt_reminders_enabled = ? WHERE user_id = ?",
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
                "UPDATE user_settings SET byt_defer_enabled = ? WHERE user_id = ?",
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
                "UPDATE user_settings SET byt_defer_max_days = ? WHERE user_id = ?",
                (max_days, user_id),
            )
            self.connection.commit()
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to update byt_defer_max_days for user %s: %s", user_id, error
            )

    def get_wishlist_category_by_id(
        self, user_id: int, category_id: int
    ) -> Optional[Dict[str, Any]]:
        """Return wishlist category by id."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT id, title, position, is_active
                FROM wishlist_categories
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
                """
                UPDATE wishlist_categories
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

        cursor.execute(f"PRAGMA table_info({table})")
        return any(row[1] == column for row in cursor.fetchall())

    def _add_column_if_missing(
        self, cursor: sqlite3.Cursor, table: str, column: str, definition: str
    ) -> None:
        """Add column to table if it does not already exist."""

        if not self._column_exists(cursor, table, column):
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

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
                "SELECT category, current, goal, purpose FROM savings WHERE user_id = ?",
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
                "SELECT category, current FROM savings WHERE user_id = ?",
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
                "SELECT id, current FROM savings WHERE user_id = ? AND category = ?",
                (user_id, category),
            )
            row = cursor.fetchone()
            delta = self._to_float(amount_delta)
            if row:
                current = self._to_float(row["current"])
                new_value = current + delta
                cursor.execute(
                    "UPDATE savings SET current = ? WHERE id = ?",
                    (new_value, row["id"]),
                )
            else:
                cursor.execute(
                    "INSERT INTO savings (user_id, category, current, goal, purpose) VALUES (?, ?, ?, 0, '')",
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

    def decrease_savings(self, user_id: int, category: str, amount: float) -> None:
        """Decrease savings for category by amount."""

        self.update_saving(user_id, category, -abs(amount))

    def set_goal(self, user_id: int, category: str, goal: float, purpose: str) -> None:
        """Set goal and purpose for saving category."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT id FROM savings WHERE user_id = ? AND category = ?",
                (user_id, category),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE savings SET goal = ?, purpose = ? WHERE id = ?",
                    (goal, purpose, row["id"]),
                )
            else:
                cursor.execute(
                    "INSERT INTO savings (user_id, category, current, goal, purpose) VALUES (?, ?, 0, ?, ?)",
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
            cursor.execute("UPDATE savings SET goal = 0, purpose = '' WHERE user_id = ?", (user_id,))
            self.connection.commit()
            LOGGER.info("Reset goals for user %s", user_id)
        except sqlite3.Error as error:
            LOGGER.error("Failed to reset goals for user %s: %s", user_id, error)

    def add_wish(self, user_id: int, name: str, price: float, url: Optional[str], category: str) -> int:
        """Add a wish to the wishlist."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "INSERT INTO wishes (user_id, name, price, url, category, is_purchased, saved_amount, purchased_at) VALUES (?, ?, ?, ?, ?, 0, 0, NULL)",
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
                """
                SELECT id, name, price, url, category, is_purchased, saved_amount, purchased_at, deferred_until
                FROM wishes
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
                """
                SELECT id, user_id, name, price, url, category, is_purchased, saved_amount, purchased_at, deferred_until
                FROM wishes
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
                """
                SELECT id, user_id, name, price, url, category, is_purchased, saved_amount, purchased_at, deferred_until
                FROM wishes
                WHERE user_id = ? AND category = 'byt' AND (is_purchased = 0 OR is_purchased IS NULL)
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
                """
                SELECT id, user_id, name, price, url, category, is_purchased, saved_amount, purchased_at, deferred_until
                FROM wishes
                WHERE user_id = ?
                  AND category = 'byt'
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
                """
                UPDATE wishes
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
                """
                UPDATE wishes
                SET is_purchased = 1, purchased_at = ?, deferred_until = NULL
                WHERE id = ?
                """,
                (purchased_value, wish_id),
            )
            self.connection.commit()
            LOGGER.info("Marked wish %s as purchased", wish_id)
        except sqlite3.Error as error:
            LOGGER.error("Failed to mark wish %s as purchased: %s", wish_id, error)

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
                "INSERT INTO purchases (user_id, wish_name, price, category, purchased_at) VALUES (?, ?, ?, ?, ?)",
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
                "SELECT 1 FROM household_payments WHERE user_id = ? AND month = ? LIMIT 1",
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
            cursor = self.connection.cursor()
            self.ensure_household_items_seeded(user_id)
            cursor.execute(
                """
                SELECT code
                FROM household_payment_items
                WHERE user_id = ? AND is_active = 1
                ORDER BY position, id
                """,
                (user_id,),
            )
            active_codes_rows = cursor.fetchall()
            active_codes = [row["code"] for row in active_codes_rows]
            for code in active_codes:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO household_payments (user_id, month, question_code, is_paid)
                    VALUES (?, ?, ?, 0)
                    """,
                    (user_id, month, code),
                )
            if active_codes:
                placeholders = ",".join(["?"] * len(active_codes))
                cursor.execute(
                    f"""
                    DELETE FROM household_payments
                    WHERE user_id = ? AND month = ? AND question_code NOT IN ({placeholders})
                    """,
                    (user_id, month, *active_codes),
                )
            else:
                cursor.execute(
                    """
                    DELETE FROM household_payments
                    WHERE user_id = ? AND month = ?
                    """,
                    (user_id, month),
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
                """
                UPDATE household_payments
                SET is_paid = 1
                WHERE user_id = ? AND month = ? AND question_code = ?
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

    async def get_unpaid_household_questions(self, user_id: int, month: str) -> List[str]:
        """Get unpaid household question codes for user and month."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT question_code
                FROM household_payments
                WHERE user_id = ? AND month = ? AND is_paid = 0
                ORDER BY id
                """,
                (user_id, month),
            )
            rows = cursor.fetchall()
            return [row["question_code"] for row in rows]
        except sqlite3.Error as error:
            LOGGER.error(
                "Failed to get unpaid household questions for user %s month %s: %s",
                user_id,
                month,
                error,
            )
            return []

    async def has_unpaid_household_questions(self, user_id: int, month: str) -> bool:
        """Return True if unpaid household questions exist for month."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT 1
                FROM household_payments
                WHERE user_id = ? AND month = ? AND is_paid = 0
                LIMIT 1
                """,
                (user_id, month),
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

    def get_purchases_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Get purchases for user honoring retention settings."""

        self.ensure_user_settings(user_id)
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT id, wish_name, price, category, purchased_at FROM purchases WHERE user_id = ? ORDER BY purchased_at DESC",
                (user_id,),
            )
            rows = cursor.fetchall()
            LOGGER.info("Fetched purchases for user %s", user_id)
            purchases = [dict(row) for row in rows]
            filtered: list[Dict[str, Any]] = []
            current_time = now_tz()
            settings_row = self.get_user_settings(user_id)
            keep_days = int(settings_row.get("purchased_keep_days", 30) or 30)
            keep_delta = timedelta(days=keep_days)
            for purchase in purchases:
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
                """
                SELECT id, hour, minute
                FROM byt_timer_times
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
                """
                SELECT id FROM byt_timer_times
                WHERE user_id = ? AND hour = ? AND minute = ? AND is_active = 1
                LIMIT 1
                """,
                (user_id, hour, minute),
            )
            existing = cursor.fetchone()
            if existing:
                return int(existing["id"])

            cursor.execute(
                """
                INSERT INTO byt_timer_times (user_id, hour, minute, is_active)
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
                """
                UPDATE byt_timer_times
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
                "UPDATE byt_timer_times SET is_active = 0 WHERE user_id = ?",
                (user_id,),
            )
            for hour, minute in [(12, 0), (18, 0)]:
                cursor.execute(
                    """
                    INSERT INTO byt_timer_times (user_id, hour, minute, is_active)
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
                """
                SELECT DISTINCT user_id
                FROM byt_timer_times
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
                """
                SELECT DISTINCT user_id
                FROM wishes
                WHERE category = 'byt' AND (is_purchased = 0 OR is_purchased IS NULL)
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
                "SELECT id, purchased_at FROM purchases WHERE category = 'byt'"
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
                cursor.execute(
                    "DELETE FROM purchases WHERE id IN ({})".format(
                        ",".join("?" * len(ids_to_delete))
                    ),
                    ids_to_delete,
                )

            cursor.execute(
                "SELECT id, purchased_at FROM wishes WHERE category = 'byt' AND is_purchased = 1"
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
                cursor.execute(
                    "DELETE FROM wishes WHERE id IN ({})".format(",".join("?" * len(wish_ids))),
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
