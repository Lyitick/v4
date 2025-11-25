"""Database CRUD operations for finance bot."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional


LOGGER = logging.getLogger(__name__)
DB_PATH = Path(__file__).resolve().parents[2] / "finance.db"


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
            savings = {
                row["category"]: {
                    "current": row["current"],
                    "goal": row["goal"],
                    "purpose": row["purpose"],
                }
                for row in rows
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
            mapping = {row["category"]: row["current"] for row in rows}
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
            if row:
                new_value = row["current"] + amount_delta
                cursor.execute(
                    "UPDATE savings SET current = ? WHERE id = ?",
                    (new_value, row["id"]),
                )
            else:
                cursor.execute(
                    "INSERT INTO savings (user_id, category, current, goal, purpose) VALUES (?, ?, ?, 0, '')",
                    (user_id, category, amount_delta),
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
