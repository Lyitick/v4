"""Handlers for household payments scenario."""
from datetime import datetime
import logging
from typing import Dict, List, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from Bot.config import settings
from Bot.database.crud import FinanceDatabase
from Bot.handlers.common import build_main_menu_for_user
from Bot.keyboards.household import household_yes_no_keyboard
from Bot.keyboards.main import back_to_main_keyboard
from Bot.states.money_states import HouseholdPaymentsState
from Bot.utils.datetime_utils import current_month_str
from Bot.utils.savings import format_savings_summary

LOGGER = logging.getLogger(__name__)

router = Router(name="household_payments")

HOUSEHOLD_QUESTIONS: List[Dict[str, int | str]] = [
    {"code": "phone", "text": "Телефон 600р?", "amount": 600},
    {"code": "internet", "text": "Интернет 700р?", "amount": 700},
    {"code": "vpn", "text": "VPN 100р?", "amount": 100},
    {"code": "gpt", "text": "GPT 2000р?", "amount": 2000},
    {"code": "yandex_sub", "text": "Яндекс подписка 400р?", "amount": 400},
    {
        "code": "rent",
        "text": "Квартплата 4000р? Папе скинул?",
        "amount": 4000,
    },
    {
        "code": "training_495",
        "text": "Оплатил тренировки 495 за 5000р?",
        "amount": 5000,
    },
]


async def reset_household_cycle_if_needed(
    user_id: int, db: FinanceDatabase, now: datetime | None = None
) -> None:
    """Lazily reset household payments cycle after 6th of month at noon."""

    current = now or datetime.now(tz=settings.TIMEZONE)
    month = current_month_str(current)

    threshold = datetime(current.year, current.month, 6, 12, 0, tzinfo=settings.TIMEZONE)
    if current >= threshold:
        await db.init_household_questions_for_month(user_id, month)


async def get_first_unpaid_question_index(user_id: int, month: str, db: FinanceDatabase) -> Optional[int]:
    """Return first unpaid question index for user/month."""

    unpaid_codes = await db.get_unpaid_household_questions(user_id, month)
    for index, question in enumerate(HOUSEHOLD_QUESTIONS):
        if question["code"] in unpaid_codes:
            return index
    return None


async def get_next_unpaid_question_index(
    start_index: int, user_id: int, month: str, db: FinanceDatabase
) -> Optional[int]:
    """Return next unpaid question index after given start."""

    unpaid_codes = await db.get_unpaid_household_questions(user_id, month)
    for index in range(start_index + 1, len(HOUSEHOLD_QUESTIONS)):
        if HOUSEHOLD_QUESTIONS[index]["code"] in unpaid_codes:
            return index
    return None


def _get_question_by_code(code: str) -> Optional[Dict[str, int | str]]:
    for question in HOUSEHOLD_QUESTIONS:
        if question["code"] == code:
            return question
    return None


@router.message(F.text == "Бытовые платежи")
async def start_household_payments(message: Message, state: FSMContext) -> None:
    """Start household payments flow."""

    user_id = message.from_user.id
    db = FinanceDatabase()

    await reset_household_cycle_if_needed(user_id, db)
    month = current_month_str()
    index = await get_first_unpaid_question_index(user_id, month, db)

    if index is None:
        await state.clear()
        await message.answer(
            "Все бытовые платежи на этот месяц уже учтены.",
            reply_markup=await build_main_menu_for_user(user_id),
        )
        LOGGER.info("User %s has no unpaid household questions for month %s", user_id, month)
        return

    await state.set_state(HouseholdPaymentsState.waiting_for_answer)
    await state.update_data(current_index=index, month=month)

    await message.answer(
        "Используй кнопку ⏪ На главную, чтобы выйти.", reply_markup=back_to_main_keyboard()
    )
    question = HOUSEHOLD_QUESTIONS[index]
    await message.answer(
        question["text"], reply_markup=household_yes_no_keyboard(question["code"])
    )
    LOGGER.info("User %s started household payments for month %s", user_id, month)


@router.callback_query(F.data.startswith("household:"))
async def handle_household_answer(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle Yes/No answers for household questions."""

    await callback.answer()
    if not callback.data:
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        return

    _, question_code, answer = parts

    data = await state.get_data()
    current_state = await state.get_state()
    if current_state != HouseholdPaymentsState.waiting_for_answer.state:
        return

    month = data.get("month")
    current_index = int(data.get("current_index", 0))
    user_id = callback.from_user.id
    db = FinanceDatabase()
    question = _get_question_by_code(question_code)

    if not month or question is None:
        await state.clear()
        await callback.message.answer(
            "Что-то пошло не так. Вернёмся в главное меню.",
            reply_markup=await build_main_menu_for_user(user_id),
        )
        return

    if answer == "yes":
        db.update_saving(user_id, "быт", -float(question["amount"]))
        await db.mark_household_question_paid(user_id, month, question_code)
        LOGGER.info("User %s answered YES for household question %s", user_id, question_code)
    else:
        LOGGER.info("User %s answered NO for household question %s", user_id, question_code)

    next_index = await get_next_unpaid_question_index(current_index, user_id, month, db)

    if next_index is None:
        await state.clear()
        savings = db.get_user_savings(user_id)
        summary = format_savings_summary(savings)
        await callback.message.answer(
            f"Текущие накопления:\n{summary}",
            reply_markup=await build_main_menu_for_user(user_id),
        )
        LOGGER.info(
            "User %s completed household payments for month %s", user_id, month
        )
        return

    await state.update_data(current_index=next_index)
    next_question = HOUSEHOLD_QUESTIONS[next_index]
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        LOGGER.debug("Failed to clear inline keyboard for household question", exc_info=True)
    await callback.message.answer(
        next_question["text"],
        reply_markup=household_yes_no_keyboard(next_question["code"]),
    )
