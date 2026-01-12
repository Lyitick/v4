"""Integration tests for startup indexes."""
import sqlite3

from Bot.database.crud import TABLES, FinanceDatabase


def _create_min_schema(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        f'CREATE TABLE "{TABLES.savings}" (user_id INTEGER)'
    )
    cursor.execute(
        f'CREATE TABLE "{TABLES.wishes}" (user_id INTEGER, category TEXT)'
    )
    cursor.execute(
        f'CREATE TABLE "{TABLES.purchases}" (user_id INTEGER)'
    )
    cursor.execute(
        f'CREATE TABLE "{TABLES.household_payments}" (user_id INTEGER)'
    )
    cursor.execute(
        f'CREATE TABLE "{TABLES.household_payment_items}" (user_id INTEGER)'
    )
    cursor.execute(
        f'CREATE TABLE "{TABLES.ui_pins}" (chat_id INTEGER PRIMARY KEY, welcome_message_id INTEGER, updated_at TEXT)'
    )
    cursor.execute(
        f'CREATE TABLE "{TABLES.income_categories}" (user_id INTEGER)'
    )
    cursor.execute(
        f'CREATE TABLE "{TABLES.expense_categories}" (user_id INTEGER)'
    )
    cursor.execute(
        f'CREATE TABLE "{TABLES.wishlist_categories}" (user_id INTEGER)'
    )
    cursor.execute(
        f'CREATE TABLE "{TABLES.byt_timer_times}" (user_id INTEGER, hour INTEGER, minute INTEGER)'
    )
    cursor.execute(
        f'CREATE TABLE "{TABLES.byt_reminder_categories}" (user_id INTEGER)'
    )
    cursor.execute(
        f'CREATE TABLE "{TABLES.byt_reminder_times}" (user_id INTEGER)'
    )


def test_ensure_indexes_skips_missing_ui_pins_user_id() -> None:
    """Ensure ui_pins user_id index is skipped when the column is missing."""

    connection = sqlite3.connect(":memory:")
    cursor = connection.cursor()
    _create_min_schema(cursor)

    db = FinanceDatabase.__new__(FinanceDatabase)
    db._ensure_indexes(cursor)

    cursor.execute(f'PRAGMA index_list("{TABLES.ui_pins}")')
    index_names = [row[1] for row in cursor.fetchall()]
    assert "idx_ui_pins_user_id" not in index_names
