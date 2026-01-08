"""Tests for wishlist debit category settings."""
from Bot.database import crud


def _fresh_db(tmp_path, monkeypatch) -> crud.FinanceDatabase:
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None
    return crud.FinanceDatabase()


def test_set_and_get_wishlist_debit_category(tmp_path, monkeypatch) -> None:
    """Wishlist debit category should persist in user settings."""

    db = _fresh_db(tmp_path, monkeypatch)
    try:
        db.set_wishlist_debit_category(1, "alpha")
        assert db.get_wishlist_debit_category(1) == "alpha"
        db.set_wishlist_debit_category(1, None)
        assert db.get_wishlist_debit_category(1) is None
    finally:
        db.close()
        crud.FinanceDatabase._instance = None
