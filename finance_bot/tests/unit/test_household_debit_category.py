"""Tests for household debit category settings."""
from Bot.database import crud


def _fresh_db(tmp_path, monkeypatch) -> crud.FinanceDatabase:
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None
    return crud.FinanceDatabase()


def test_set_and_get_household_debit_category(tmp_path, monkeypatch) -> None:
    """Household debit category should persist in user settings."""

    db = _fresh_db(tmp_path, monkeypatch)
    try:
        db.set_household_debit_category(1, "alpha")
        assert db.get_household_debit_category(1) == "alpha"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_apply_household_debit_category_updates_savings(tmp_path, monkeypatch) -> None:
    """Yes answer should debit savings from selected category."""

    db = _fresh_db(tmp_path, monkeypatch)
    try:
        db.set_household_debit_category(2, "custom_cat")
        changed = db.apply_household_payment_answer(
            user_id=2,
            month="2026-01",
            question_code="q1",
            amount=100.0,
            answer="yes",
            debit_category="custom_cat",
        )
        assert changed is True
        savings_map = db.get_user_savings_map(2)
        assert savings_map.get("custom_cat") == -100.0
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_resolve_household_debit_category_fallback(tmp_path, monkeypatch) -> None:
    """Fallback should select first available income category."""

    db = _fresh_db(tmp_path, monkeypatch)
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            f"""
            INSERT INTO {crud.TABLES.income_categories} (user_id, code, title, percent, position, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (3, "alpha", "Alpha", 50, 1),
        )
        cursor.execute(
            f"""
            INSERT INTO {crud.TABLES.income_categories} (user_id, code, title, percent, position, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (3, "beta", "Beta", 50, 2),
        )
        db.connection.commit()

        code, title = db.resolve_household_debit_category(3)
        assert code == "alpha"
        assert title == "Alpha"
    finally:
        db.close()
        crud.FinanceDatabase._instance = None
