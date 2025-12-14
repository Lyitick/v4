"""Tests for household payments workflow."""
from datetime import datetime

import pytest

from Bot.database.crud import FinanceDatabase
from Bot.handlers.household_payments import (
    HOUSEHOLD_QUESTIONS,
    get_first_unpaid_question_index,
    get_next_unpaid_question_index,
    reset_household_cycle_if_needed,
)
from Bot.config import settings
from Bot.utils.datetime_utils import current_month_str


@pytest.mark.asyncio
async def test_reset_cycle_creates_statuses_after_threshold() -> None:
    """Statuses should appear after threshold date only once."""

    db = FinanceDatabase()
    user_id = 99991
    month = "2025-01"
    db.connection.execute("DELETE FROM household_payments WHERE user_id = ?", (user_id,))
    db.connection.commit()

    before_threshold = datetime(2025, 1, 5, 10, 0, tzinfo=settings.TIMEZONE)
    await reset_household_cycle_if_needed(user_id, db, now=before_threshold)
    assert not await db.household_status_exists(user_id, month)

    after_threshold = datetime(2025, 1, 6, 12, 0, tzinfo=settings.TIMEZONE)
    await reset_household_cycle_if_needed(user_id, db, now=after_threshold)
    assert await db.has_unpaid_household_questions(user_id, month)

    await reset_household_cycle_if_needed(user_id, db, now=after_threshold)
    cursor = db.connection.execute(
        "SELECT COUNT(*) FROM household_payments WHERE user_id = ? AND month = ?",
        (user_id, month),
    )
    assert cursor.fetchone()[0] == len(HOUSEHOLD_QUESTIONS)


@pytest.mark.asyncio
async def test_mark_and_check_unpaid_questions() -> None:
    """Marking paid questions should update unpaid check."""

    db = FinanceDatabase()
    user_id = 99992
    month = current_month_str(datetime(2025, 2, 6, 12, 0, tzinfo=settings.TIMEZONE))
    db.connection.execute("DELETE FROM household_payments WHERE user_id = ?", (user_id,))
    db.connection.commit()

    await db.init_household_questions_for_month(user_id, month)
    assert await db.has_unpaid_household_questions(user_id, month)

    for question in HOUSEHOLD_QUESTIONS:
        await db.mark_household_question_paid(user_id, month, question["code"])
    assert not await db.has_unpaid_household_questions(user_id, month)


@pytest.mark.asyncio
async def test_question_flow_and_savings_update() -> None:
    """Yes/No answers adjust savings and skip paid questions."""

    db = FinanceDatabase()
    user_id = 99993
    month = current_month_str(datetime(2025, 3, 6, 12, 0, tzinfo=settings.TIMEZONE))
    db.connection.execute("DELETE FROM household_payments WHERE user_id = ?", (user_id,))
    db.connection.execute("DELETE FROM savings WHERE user_id = ? AND category = 'быт'", (user_id,))
    db.connection.commit()

    db.update_saving(user_id, "быт", 5000)
    await db.init_household_questions_for_month(user_id, month)

    first_index = await get_first_unpaid_question_index(user_id, month, db)
    assert first_index == 0

    first_question = HOUSEHOLD_QUESTIONS[first_index]
    db.update_saving(user_id, "быт", -float(first_question["amount"]))
    await db.mark_household_question_paid(user_id, month, first_question["code"])

    savings_map = db.get_user_savings_map(user_id)
    assert savings_map.get("быт") == 5000 - float(first_question["amount"])

    next_index = await get_next_unpaid_question_index(first_index, user_id, month, db)
    assert next_index == 1

    next_after_second = await get_next_unpaid_question_index(next_index, user_id, month, db)
    assert next_after_second == 2

    first_unpaid_again = await get_first_unpaid_question_index(user_id, month, db)
    assert first_unpaid_again == 1
