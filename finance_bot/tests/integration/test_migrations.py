"""Integration tests for migrations and indexes."""
from Bot.database import crud


def test_migrations_create_user_settings_and_indexes(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(crud, "DB_PATH", db_path)
    crud.FinanceDatabase._instance = None
    db = crud.FinanceDatabase()
    try:
        cursor = db.connection.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (crud.TABLES.user_settings,),
        )
        assert cursor.fetchone() is not None

        cursor.execute(f'PRAGMA index_list("{crud.TABLES.wishes}")')
        wish_indexes = {row[1] for row in cursor.fetchall()}
        assert "idx_wishes_user_id" in wish_indexes

        cursor.execute(f'PRAGMA index_list("{crud.TABLES.byt_timer_times}")')
        timer_indexes = {row[1] for row in cursor.fetchall()}
        assert "idx_byt_timer_times_user_id" in timer_indexes
    finally:
        db.close()
        crud.FinanceDatabase._instance = None
