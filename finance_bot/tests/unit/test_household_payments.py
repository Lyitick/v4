"""Tests for household payments workflow."""
from datetime import datetime

import pytest

from Bot.config import settings
from Bot.database.crud import FinanceDatabase, TABLES
from Bot.handlers.household_payments import reset_household_cycle_if_needed
from Bot.utils.datetime_utils import current_month_str


@pytest.mark.asyncio
async def test_reset_cycle_creates_statuses_after_threshold() -> None:
    """Statuses should appear after threshold date only once."""

    db = FinanceDatabase()
    user_id = 99991
    month = "2025-01"
    db.connection.execute(
        f"DELETE FROM {TABLES.household_payments} WHERE user_id = ?",
        (user_id,),
    )
    db.connection.execute(
        f"DELETE FROM {TABLES.household_payment_items} WHERE user_id = ?",
        (user_id,),
    )
    db.connection.commit()
    db.ensure_household_items_seeded(user_id)
    items = db.list_active_household_items(user_id)

    before_threshold = datetime(2025, 1, 5, 10, 0, tzinfo=settings.TIMEZONE)
    await reset_household_cycle_if_needed(user_id, db, now=before_threshold)
    assert not await db.household_status_exists(user_id, month)

    after_threshold = datetime(2025, 1, 6, 12, 0, tzinfo=settings.TIMEZONE)
    await reset_household_cycle_if_needed(user_id, db, now=after_threshold)
    assert await db.has_unpaid_household_questions(user_id, month)

    await reset_household_cycle_if_needed(user_id, db, now=after_threshold)
    cursor = db.connection.execute(
        f"SELECT COUNT(*) FROM {TABLES.household_payments} WHERE user_id = ? AND month = ?",
        (user_id, month),
    )
    assert cursor.fetchone()[0] == len(items)


@pytest.mark.asyncio
async def test_mark_and_check_unpaid_questions() -> None:
    """Marking paid questions should update unpaid check."""

    db = FinanceDatabase()
    user_id = 99992
    month = current_month_str(datetime(2025, 2, 6, 12, 0, tzinfo=settings.TIMEZONE))
    db.connection.execute(
        f"DELETE FROM {TABLES.household_payments} WHERE user_id = ?",
        (user_id,),
    )
    db.connection.execute(
        f"DELETE FROM {TABLES.household_payment_items} WHERE user_id = ?",
        (user_id,),
    )
    db.connection.commit()
    db.ensure_household_items_seeded(user_id)
    items = db.list_active_household_items(user_id)

    await db.init_household_questions_for_month(user_id, month)
    assert await db.has_unpaid_household_questions(user_id, month)

    for item in items:
        await db.mark_household_question_paid(user_id, month, str(item.get("code")))
    assert not await db.has_unpaid_household_questions(user_id, month)


@pytest.mark.asyncio
async def test_question_flow_and_savings_update() -> None:
    """Yes/No answers adjust savings and skip paid questions."""

    db = FinanceDatabase()
    user_id = 99993
    month = current_month_str(datetime(2025, 3, 6, 12, 0, tzinfo=settings.TIMEZONE))
    db.connection.execute(
        f"DELETE FROM {TABLES.household_payments} WHERE user_id = ?",
        (user_id,),
    )
    db.connection.execute(
        f"DELETE FROM {TABLES.savings} WHERE user_id = ? AND category = 'быт'",
        (user_id,),
    )
    db.connection.execute(
        f"DELETE FROM {TABLES.household_payment_items} WHERE user_id = ?",
        (user_id,),
    )
    db.connection.commit()
    db.ensure_household_items_seeded(user_id)
    items = db.list_active_household_items(user_id)

    db.update_saving(user_id, "быт", 5000)
    await db.init_household_questions_for_month(user_id, month)

    unpaid = await db.get_unpaid_household_questions(user_id, month)
    assert unpaid
    first_code = str(unpaid[0])
    first_item = next(item for item in items if str(item.get("code")) == first_code)
    amount = float(first_item.get("amount") or 0)

    changed = db.apply_household_payment_answer(
        user_id=user_id,
        month=month,
        question_code=first_code,
        amount=amount,
        answer="yes",
    )
    assert changed is True

    savings_map = db.get_user_savings_map(user_id)
    assert savings_map.get("быт") == 5000 - amount

    changed_again = db.apply_household_payment_answer(
        user_id=user_id,
        month=month,
        question_code=first_code,
        amount=amount,
        answer="yes",
    )
    assert changed_again is False

    changed_back = db.apply_household_payment_answer(
        user_id=user_id,
        month=month,
        question_code=first_code,
        amount=amount,
        answer="no",
    )
    assert changed_back is True
    savings_map = db.get_user_savings_map(user_id)
    assert savings_map.get("быт") == 5000
