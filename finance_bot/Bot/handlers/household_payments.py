"""Handlers for household payments scenario."""
from datetime import datetime, time as dt_time
import logging
import time
from typing import Dict, List, Optional

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from Bot.config import settings
from Bot.database.crud import FinanceDatabase
from Bot.handlers.common import build_main_menu_for_user
from Bot.keyboards.calculator import income_calculator_keyboard
from Bot.keyboards.household import household_yes_no_keyboard
from Bot.keyboards.main import back_to_main_keyboard
from Bot.keyboards.settings import (
    household_remove_keyboard,
    household_settings_inline_keyboard,
    settings_menu_keyboard,
)
from Bot.states.money_states import HouseholdPaymentsState, HouseholdSettingsState
from Bot.utils.datetime_utils import current_month_str
from Bot.utils.savings import format_savings_summary
from Bot.utils.ui_cleanup import ui_register_message
from Bot.handlers.wishlist import run_byt_timer_check

LOGGER = logging.getLogger(__name__)

router = Router(name="household_payments")


async def reset_household_cycle_if_needed(
    user_id: int, db: FinanceDatabase, now: datetime | None = None
) -> None:
    """Lazily reset household payments cycle after 6th of month at noon."""

    current = now or datetime.now(tz=settings.TIMEZONE)
    month = current_month_str(current)

    threshold = datetime(current.year, current.month, 6, 12, 0, tzinfo=settings.TIMEZONE)
    if current >= threshold:
        await db.init_household_questions_for_month(user_id, month)


def _get_first_unpaid_item(
    items: List[Dict[str, int | str]], unpaid_set: set[str]
) -> Optional[Dict[str, int | str]]:
    for item in items:
        if item.get("code") in unpaid_set:
            return item
    return None


def _get_next_unpaid_item(
    items: List[Dict[str, int | str]], current_code: str, unpaid_set: set[str]
) -> Optional[Dict[str, int | str]]:
    found_current = False
    for item in items:
        if found_current and item.get("code") in unpaid_set:
            return item
        if item.get("code") == current_code:
            found_current = True
    return None


def _format_household_items(items: List[Dict[str, int | str]]) -> str:
    if not items:
        return "Список платежей пуст."

    lines = ["Текущий список платежей:"]
    for index, item in enumerate(items, start=1):
        title = str(item.get("text", "")).rstrip("?")
        amount = item.get("amount")
        if amount is not None:
            lines.append(f"{index}) {title} — {amount}")
        else:
            lines.append(f"{index}) {title}")
    return "\n".join(lines)


async def _send_household_settings_overview(
    message: Message, db: FinanceDatabase, user_id: int
) -> None:
    db.ensure_household_items_seeded(user_id)
    items = db.list_active_household_items(user_id)
    await message.answer(
        _format_household_items(items),
        reply_markup=household_settings_inline_keyboard(),
    )


@router.message(F.text == "⚙️ Бытовые платежи ⚙️")
async def open_household_settings(message: Message, state: FSMContext) -> None:
    """Open household payments settings menu."""

    if message.from_user.id != settings.ADMIN_ID:
        sent = await message.answer(
            "Что-то пошло не так. Вернёмся в главное меню.",
            reply_markup=await build_main_menu_for_user(message.from_user.id),
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)
        return

    await state.clear()
    db = FinanceDatabase()
    sent = await message.answer(
        "⚙️ Бытовые платежи ⚙️", reply_markup=settings_menu_keyboard()
    )
    await ui_register_message(state, sent.chat.id, sent.message_id)
    await _send_household_settings_overview(message, db, message.from_user.id)


@router.callback_query(F.data == "hh_set:add")
async def household_add_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    """Prompt for new household payment title."""

    await callback.answer()
    if callback.from_user.id != settings.ADMIN_ID:
        return

    await state.clear()
    await state.set_state(HouseholdSettingsState.waiting_for_title)
    await callback.message.answer("Введи название платежа")


@router.message(HouseholdSettingsState.waiting_for_title)
async def household_add_set_title(message: Message, state: FSMContext) -> None:
    """Handle title input for new household payment."""

    title = (message.text or "").strip()
    if not title:
        await message.answer("Нужно ввести название платежа.")
        return

    await state.update_data(title=title)
    await state.set_state(HouseholdSettingsState.waiting_for_amount)

    question = await message.answer(
        "Введи сумму (используй кнопки ниже).",
        reply_markup=income_calculator_keyboard(),
    )
    prompt = await message.answer(": 0")

    await state.update_data(
        amount_sum="0",
        amount_message_id=prompt.message_id,
        amount_question_message_id=question.message_id,
    )


@router.message(
    HouseholdSettingsState.waiting_for_amount,
    F.text.in_({"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "Очистить", "✅ Газ"}),
)
async def household_add_amount_calc(message: Message, state: FSMContext) -> None:
    """Handle calculator input for new household payment amount."""

    data = await state.get_data()
    current_sum = str(data.get("amount_sum", "0"))
    amount_message_id = data.get("amount_message_id")

    if message.text == "Очистить":
        new_sum = "0"
    elif message.text == "✅ Газ":
        amount_str = current_sum.strip()
        if not amount_str:
            await message.answer("Нужно ввести число. Попробуй снова.")
            try:
                await message.delete()
            except Exception:
                pass
            return

        try:
            amount = int(amount_str)
        except (TypeError, ValueError):
            await message.answer("Нужно ввести число. Попробуй снова.")
            try:
                await message.delete()
            except Exception:
                pass
            return

        if amount <= 0:
            await message.answer("Сумма должна быть больше нуля. Попробуй снова.")
            try:
                await message.delete()
            except Exception:
                pass
            return

        user_id = message.from_user.id
        db = FinanceDatabase()
        position = db.get_next_household_position(user_id)
        title = str(data.get("title", "")).strip() or "Платёж"
        code = f"custom_{time.time_ns()}"
        text = f"{title} {amount}р?"
        db.add_household_payment_item(user_id, code, text, amount, position)
        await reset_household_cycle_if_needed(user_id, db)
        await state.clear()
        await message.answer(
            "Платёж добавлен.", reply_markup=ReplyKeyboardRemove()
        )
        await message.answer(
            "⚙️ Бытовые платежи ⚙️", reply_markup=settings_menu_keyboard()
        )
        await _send_household_settings_overview(message, db, user_id)
        try:
            await message.delete()
        except Exception:
            pass
        return
    else:
        if current_sum == "0":
            new_sum = message.text
        else:
            new_sum = current_sum + message.text

    if amount_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=amount_message_id,
                text=f": {new_sum}",
            )
        except Exception:
            pass

    await state.update_data(amount_sum=new_sum, amount_message_id=amount_message_id)

    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "hh_set:del")
async def household_remove_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    """Show list of household payments for removal."""

    await callback.answer()
    if callback.from_user.id != settings.ADMIN_ID:
        return

    await state.clear()
    db = FinanceDatabase()
    db.ensure_household_items_seeded(callback.from_user.id)
    items = db.list_active_household_items(callback.from_user.id)
    if not items:
        await callback.message.answer("Список платежей пуст.")
        return

    await callback.message.answer(
        "Выбери платеж для удаления:",
        reply_markup=household_remove_keyboard(items),
    )


@router.callback_query(F.data.startswith("hh_set:remove:"))
async def household_remove_item(callback: CallbackQuery, state: FSMContext) -> None:
    """Deactivate selected household payment item."""

    await callback.answer()
    if callback.from_user.id != settings.ADMIN_ID:
        return

    parts = callback.data.split(":") if callback.data else []
    if len(parts) != 3:
        return
    code = parts[2]
    db = FinanceDatabase()
    db.deactivate_household_payment_item(callback.from_user.id, code)
    await reset_household_cycle_if_needed(callback.from_user.id, db)
    await _send_household_settings_overview(callback.message, db, callback.from_user.id)


@router.message(F.text == "Бытовые платежи")
async def start_household_payments(message: Message, state: FSMContext) -> None:
    """Start household payments flow."""

    user_id = message.from_user.id
    db = FinanceDatabase()

    await reset_household_cycle_if_needed(user_id, db)
    db.ensure_household_items_seeded(user_id)
    items = db.list_active_household_items(user_id)
    month = current_month_str()
    unpaid_codes = await db.get_unpaid_household_questions(user_id, month)
    unpaid_set: set[str] = set(unpaid_codes)
    first_item = _get_first_unpaid_item(items, unpaid_set)

    if first_item is None:
        await state.clear()
        sent = await message.answer(
            "Все бытовые платежи на этот месяц уже учтены.",
            reply_markup=await build_main_menu_for_user(user_id),
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)
        LOGGER.info("User %s has no unpaid household questions for month %s", user_id, month)
        return

    await state.set_state(HouseholdPaymentsState.waiting_for_answer)
    await state.update_data(current_code=first_item["code"], month=month)

    await message.answer(
        "Используй кнопку ⏪ На главную, чтобы выйти.", reply_markup=back_to_main_keyboard()
    )
    await message.answer(
        str(first_item.get("text", "")),
        reply_markup=household_yes_no_keyboard(str(first_item.get("code", ""))),
    )
    LOGGER.info("User %s started household payments for month %s", user_id, month)


@router.message(F.text == "Проверить быт")
async def trigger_household_notifications(message: Message, state: FSMContext) -> None:
    """Trigger BYT purchases check (household wishlist) as if timer fired."""

    user_id = message.from_user.id
    db = FinanceDatabase()

    db.ensure_byt_timer_defaults(user_id)
    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    times = db.list_active_byt_timer_times(user_id)
    simulated_time = None
    if times:
        first_time = times[0]
        try:
            simulated_time = dt_time(
                hour=int(first_time.get("hour", 0)),
                minute=int(first_time.get("minute", 0)),
            )
        except Exception:
            simulated_time = None

    await run_byt_timer_check(
        message.bot, db, user_id=user_id, simulated_time=simulated_time
    )


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
    current_code = data.get("current_code")
    user_id = callback.from_user.id
    db = FinanceDatabase()
    db.ensure_household_items_seeded(user_id)
    question = db.get_household_item_by_code(user_id, question_code)

    if not month or question is None:
        await state.clear()
        sent = await callback.message.answer(
            "Что-то пошло не так. Вернёмся в главное меню.",
            reply_markup=await build_main_menu_for_user(user_id),
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)
        return

    if answer == "yes":
        db.update_saving(user_id, "быт", -float(question["amount"]))
        await db.mark_household_question_paid(user_id, month, question_code)
        LOGGER.info("User %s answered YES for household question %s", user_id, question_code)
    else:
        LOGGER.info("User %s answered NO for household question %s", user_id, question_code)

    unpaid_codes = await db.get_unpaid_household_questions(user_id, month)
    unpaid_set: set[str] = set(unpaid_codes)
    items = db.list_active_household_items(user_id)
    next_question = _get_next_unpaid_item(items, current_code or question_code, unpaid_set)

    if next_question is None:
        await state.clear()
        savings = db.get_user_savings(user_id)
        summary = format_savings_summary(savings)
        sent = await callback.message.answer(
            f"Текущие накопления:\n{summary}",
            reply_markup=await build_main_menu_for_user(user_id),
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)
        LOGGER.info(
            "User %s completed household payments for month %s", user_id, month
        )
        return

    await state.update_data(current_code=next_question["code"])
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        LOGGER.debug("Failed to clear inline keyboard for household question", exc_info=True)
    await callback.message.answer(
        str(next_question.get("text", "")),
        reply_markup=household_yes_no_keyboard(str(next_question.get("code", ""))),
    )
