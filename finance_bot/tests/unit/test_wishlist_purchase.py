"""Tests for wishlist purchase flow."""
from Bot.database import crud


def _fresh_db(tmp_path, monkeypatch) -> crud.FinanceDatabase:
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None
    return crud.FinanceDatabase()


def test_purchase_wishlist_without_debit(tmp_path, monkeypatch) -> None:
    """Purchase without debit should not change savings."""

    db = _fresh_db(tmp_path, monkeypatch)
    try:
        wish_id = db.add_wish(1, "Laptop", 100.0, None, "Work")
        result = db.purchase_wish(1, wish_id, None)
        assert result.get("status") == "no_debit"
        wish = db.get_wish(wish_id)
        assert wish is not None
        assert wish.get("is_purchased") == 1
        assert wish.get("debited_at") is None
        savings_map = db.get_user_savings_map(1)
        assert "alpha" not in savings_map
    finally:
        db.close()
        crud.FinanceDatabase._instance = None


def test_purchase_wishlist_debit_idempotent(tmp_path, monkeypatch) -> None:
    """Purchase should debit once and be idempotent."""

    db = _fresh_db(tmp_path, monkeypatch)
    try:
        wish_id = db.add_wish(2, "Phone", 50.0, None, "Fun")
        db.update_saving(2, "alpha", 100.0)
        result = db.purchase_wish(2, wish_id, "alpha")
        assert result.get("status") == "debited"
        savings_map = db.get_user_savings_map(2)
        assert savings_map.get("alpha") == 50.0
        result_again = db.purchase_wish(2, wish_id, "alpha")
        assert result_again.get("status") == "already"
        savings_map_again = db.get_user_savings_map(2)
        assert savings_map_again.get("alpha") == 50.0
        wish = db.get_wish(wish_id)
        assert wish is not None
        assert wish.get("debited_at") is not None
    finally:
        db.close()
        crud.FinanceDatabase._instance = None
