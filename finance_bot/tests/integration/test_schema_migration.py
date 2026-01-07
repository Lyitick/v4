"""Integration tests for schema migration."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Bot.database.crud import TABLES, migrate_schema


def test_schema_migration_renames_tables(tmp_path: Path) -> None:
    """Rename legacy tables without losing data."""

    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE savings (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            category TEXT,
            current REAL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE wishes (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            name TEXT,
            price REAL,
            category TEXT,
            is_purchased INTEGER,
            saved_amount REAL,
            purchased_at TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE purchases (
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
        CREATE TABLE household_payment_items (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            code TEXT,
            text TEXT,
            amount INTEGER,
            position INTEGER,
            is_active INTEGER
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE household_payments (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            month TEXT,
            question_code TEXT,
            is_paid INTEGER
        )
        """
    )
    cursor.execute(
        "INSERT INTO savings (user_id, category, current) VALUES (?,?,?)",
        (1, "БЫТ", 500.0),
    )
    cursor.execute(
        """
        INSERT INTO wishes (user_id, name, price, category, is_purchased, saved_amount, purchased_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (1, "Чайник", 1200.0, "БЫТ", 0, 0, None),
    )
    cursor.execute(
        "INSERT INTO purchases (user_id, wish_name, price, category, purchased_at) VALUES (?,?,?,?,?)",
        (1, "Тест", 100.0, "БЫТ", "2025-01-01"),
    )
    cursor.execute(
        """
        INSERT INTO household_payment_items (user_id, code, text, amount, position, is_active)
        VALUES (?,?,?,?,?,?)
        """,
        (1, "rent", "Квартплата", 4000, 1, 1),
    )
    cursor.execute(
        """
        INSERT INTO household_payments (user_id, month, question_code, is_paid)
        VALUES (?,?,?,?)
        """,
        (1, "2025-01", "rent", 0),
    )
    connection.commit()

    migrate_schema(connection)
    migrate_schema(connection)

    cursor.execute(f"SELECT category, current FROM {TABLES.savings}")
    savings_row = cursor.fetchone()
    assert savings_row == ("БЫТ", 500.0)

    cursor.execute(f"SELECT name FROM {TABLES.wishes}")
    assert cursor.fetchone()[0] == "Чайник"

    cursor.execute(f"SELECT wish_name FROM {TABLES.purchases}")
    assert cursor.fetchone()[0] == "Тест"

    cursor.execute(f"SELECT code FROM {TABLES.household_payment_items}")
    assert cursor.fetchone()[0] == "rent"

    cursor.execute(f"SELECT question_code FROM {TABLES.household_payments}")
    assert cursor.fetchone()[0] == "rent"

    connection.close()
