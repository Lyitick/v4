"""Database accessor for a shared FinanceDatabase instance."""
from __future__ import annotations

from Bot.database.crud import FinanceDatabase

_DB_INSTANCE: FinanceDatabase | None = None


def get_db() -> FinanceDatabase:
    global _DB_INSTANCE
    if _DB_INSTANCE is None:
        _DB_INSTANCE = FinanceDatabase()
    return _DB_INSTANCE
