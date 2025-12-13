"""Database CRUD operations for finance bot."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional


LOGGER = logging.getLogger(__name__)
DB_PATH = Path(__file__).resolve().parents[2] / "finance.db"
HOUSEHOLD_QUESTION_CODES = [
    "phone",
    "internet",
    "vpn",
    "gpt",
    "yandex_sub",
    "rent",
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
                saved_amount REAL DEFAULT 0
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
        self.connection.commit()

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
                "INSERT INTO wishes (user_id, name, price, url, category, is_purchased, saved_amount) VALUES (?, ?, ?, ?, ?, 0, 0)",
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
                "SELECT id, name, price, url, category, is_purchased, saved_amount FROM wishes WHERE user_id = ?",
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
                "SELECT id, user_id, name, price, url, category, is_purchased, saved_amount FROM wishes WHERE id = ?",
                (wish_id,),
            )
            row = cursor.fetchone()
            LOGGER.info("Fetched wish %s", wish_id)
            return dict(row) if row else None
        except sqlite3.Error as error:
            LOGGER.error("Failed to fetch wish %s: %s", wish_id, error)
            return None

    def mark_wish_purchased(self, wish_id: int) -> None:
        """Mark wish as purchased."""

        try:
            cursor = self.connection.cursor()
            cursor.execute("UPDATE wishes SET is_purchased = 1 WHERE id = ?", (wish_id,))
            self.connection.commit()
            LOGGER.info("Marked wish %s as purchased", wish_id)
        except sqlite3.Error as error:
            LOGGER.error("Failed to mark wish %s as purchased: %s", wish_id, error)

    def add_purchase(self, user_id: int, wish_name: str, price: float, category: str) -> None:
        """Add purchase record."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "INSERT INTO purchases (user_id, wish_name, price, category, purchased_at) VALUES (?, ?, ?, ?, datetime('now'))",
                (user_id, wish_name, price, category),
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
            for code in HOUSEHOLD_QUESTION_CODES:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO household_payments (user_id, month, question_code, is_paid)
                    VALUES (?, ?, ?, 0)
                    """,
                    (user_id, month, code),
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
        """Get all purchases for user."""

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT id, wish_name, price, category, purchased_at FROM purchases WHERE user_id = ? ORDER BY purchased_at DESC",
                (user_id,),
            )
            rows = cursor.fetchall()
            LOGGER.info("Fetched purchases for user %s", user_id)
            return [dict(row) for row in rows]
        except sqlite3.Error as error:
            LOGGER.error("Failed to fetch purchases for user %s: %s", user_id, error)
            return []

    def close(self) -> None:
        """Close database connection."""

        try:
            self.connection.close()
            LOGGER.info("Database connection closed")
        except sqlite3.Error as error:
            LOGGER.error("Failed to close database connection: %s", error)
