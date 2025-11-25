"""Integration tests for database operations."""
from Bot.database.crud import FinanceDatabase


def setup_module(module) -> None:  # noqa: D401
    """Clean database tables before tests."""

    db = FinanceDatabase()
    cursor = db.connection.cursor()
    cursor.execute("DELETE FROM wishes")
    cursor.execute("DELETE FROM purchases")
    cursor.execute("DELETE FROM savings")
    db.connection.commit()


def test_add_and_get_wish() -> None:
    """Add wish and retrieve it."""

    db = FinanceDatabase()
    wish_id = db.add_wish(1, "Test", 10.0, None, "Инструменты")
    wish = db.get_wish(wish_id)
    assert wish is not None
    assert wish["name"] == "Test"


def test_update_saving_and_purchase() -> None:
    """Update savings and add purchase entry."""

    db = FinanceDatabase()
    db.update_saving(1, "Инструменты", 20.0)
    savings = db.get_user_savings(1)
    assert savings.get("Инструменты", {}).get("current") == 20.0
    db.add_purchase(1, "Test", 10.0, "Инструменты")
    purchases = db.get_purchases_by_user(1)
    assert len(purchases) == 1
