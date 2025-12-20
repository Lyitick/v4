"""Handlers for household payments scenario."""
from datetime import datetime, time as dt_time
import html
import logging
import time
from typing import Dict, List

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from Bot.config import settings
from Bot.database.crud import FinanceDatabase
from Bot.handlers.common import build_main_menu_for_user
from Bot.handlers.wishlist import run_byt_timer_check
from Bot.keyboards.calculator import income_calculator_keyboard
from Bot.keyboards.household import household_payments_inline_keyboard
from Bot.keyboards.settings import (
    household_remove_keyboard,
    household_settings_inline_keyboard,
    settings_menu_keyboard,
)
from Bot.states.money_states import HouseholdPaymentsState, HouseholdSettingsState
from Bot.utils.datetime_utils import current_month_str
from Bot.utils.savings import format_savings_summary
from Bot.utils.ui_cleanup import (
    ui_cleanup_messages,
    ui_register_message,
    ui_register_user_message,
)

LOGGER = logging.getLogger(__name__)

router = Router(name="household_payments")


async def _send_main_menu_summary(
    bot, state: FSMContext, chat_id: int, user_id: int
) -> None:
    db = FinanceDatabase()
    savings = db.get_user_savings(user_id)
    summary = format_savings_summary(savings)
    menu = await build_main_menu_for_user(user_id)
    sent = await bot.send_message(
        chat_id=chat_id, text=f"Текущие накопления:\n{summary}", reply_markup=menu
    )
    await ui_register_message(state, chat_id, sent.message_id)


async def reset_household_cycle_if_needed(
    user_id: int, db: FinanceDatabase, now: datetime | None = None
) -> None:
    """Lazily reset household payments cycle after 6th of month at noon."""

    current = now or datetime.now(tz=settings.TIMEZONE)
    month = current_month_str(current)

    threshold = datetime(current.year, current.month, 6, 12, 0, tzinfo=settings.TIMEZONE)
    if current >= threshold:
        await db.init_household_questions_for_month(user_id, month)


def _render_household_questions_text(
    month: str,
    questions: list[dict],
    answers: dict[str, str],
    current_index: int | None,
) -> str:
    header = f"<b>БЫТОВЫЕ ПЛАТЕЖИ — {html.escape(month)}</b>"
    lines = [header]
    for index, question in enumerate(questions, start=1):
        code = str(question.get("code", ""))
        text = html.escape(str(question.get("text", "")).strip())
        text = text.rstrip("?").strip()
        suffix = ""
        answer = answers.get(code)
        if answer == "yes":
            suffix = " ✅"
        elif answer == "no":
            suffix = " ❌"
        display = text
        if current_index is not None and index - 1 == current_index:
            display = f"<b>{display.upper()}</b>"
        lines.append(f"{index}) {display}{suffix}")
    return "\n".join(lines)


def _format_household_items(
    items: List[Dict[str, int | str]],
    unpaid_set: set[str],
) -> str:
    if not items:
        return "Текущий список платежей: (пусто)"

    lines = ["Текущий список платежей:"]
    for index, item in enumerate(items, start=1):
        title = str(item.get("text", "")).rstrip("?")
        amount = item.get("amount")
        code = str(item.get("code", ""))
        status = "❌" if code in unpaid_set else "✅"
        if amount is not None:
            lines.append(f"{index}) {status} {title} — {amount}")
        else:
            lines.append(f"{index}) {status} {title}")
    return "\n".join(lines)


async def _send_household_settings_overview(
    message: Message, db: FinanceDatabase, user_id: int
) -> None:
    items = db.list_active_household_items(user_id)
    month = current_month_str()
    unpaid_codes = await db.get_unpaid_household_questions(user_id, month)
    unpaid_set: set[str] = set(unpaid_codes)
    LOGGER.info(
        "Household settings overview (user_id=%s, month=%s, items_count=%s, unpaid_count=%s)",
        user_id,
        month,
        len(items),
        len(unpaid_set),
    )
    if not items:
        LOGGER.info(
            "Household settings overview items empty (user_id=%s, source=list_active_household_items)",
            user_id,
        )
    await message.answer(
        _format_household_items(items, unpaid_set),
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

    await ui_register_user_message(state, message.chat.id, message.message_id)
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        LOGGER.debug(
            "Failed to delete user menu message (Бытовые платежи)", exc_info=True
        )

    user_id = message.from_user.id
    db = FinanceDatabase()

    await reset_household_cycle_if_needed(user_id, db)
    db.ensure_household_items_seeded(user_id)
    items = db.list_active_household_items(user_id)
    if not items:
        await ui_cleanup_messages(message.bot, state)
        await state.clear()
        sent = await message.answer(
            "Список бытовых платежей не настроен.",
            reply_markup=await build_main_menu_for_user(user_id),
        )
        await ui_register_message(state, message.chat.id, sent.message_id)
        return

    month = current_month_str()
    await db.init_household_questions_for_month(user_id, month)
    status_map = await db.get_household_payment_status_map(user_id, month)
    questions = [
        {
            "code": item.get("code", ""),
            "text": item.get("text", ""),
            "amount": item.get("amount"),
        }
        for item in items
    ]
    all_paid = all(
        status_map.get(str(question.get("code", "")), 0) == 1
        for question in questions
    )
    unpaid_codes = await db.get_unpaid_household_questions(user_id, month)
    unpaid_set: set[str] = set(unpaid_codes)
    hh_questions = [
        {
            "code": item.get("code", ""),
            "text": item.get("text", ""),
            "amount": item.get("amount"),
        }
        for item in items
        if item.get("code") in unpaid_set
    ]

    if all_paid:
        answers = {}
        for question in questions:
            code = str(question.get("code", ""))
            answers[code] = "yes" if status_map.get(code, 0) == 1 else "no"
        text = _render_household_questions_text(
            month,
            questions,
            answers,
            current_index=None,
        )
        lines = text.splitlines()
        if lines:
            lines[0] = f"✅ Все бытовые платежи оплачены за {html.escape(month)}"
        text = "\n".join(lines)
        await ui_cleanup_messages(message.bot, state)
        await state.clear()
        sent = await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=await build_main_menu_for_user(user_id),
        )
        await ui_register_message(state, message.chat.id, sent.message_id)
        LOGGER.info("User %s has no unpaid household questions for month %s", user_id, month)
        return

    await state.set_state(HouseholdPaymentsState.waiting_for_answer)
    await state.update_data(
        hh_month=month,
        hh_questions=hh_questions,
        hh_index=0,
        hh_answers={},
        hh_ui_message_id=0,
    )
    text = _render_household_questions_text(month, hh_questions, {}, current_index=0)
    sent = await message.answer(
        text,
        reply_markup=household_payments_inline_keyboard(show_back=False),
        parse_mode="HTML",
    )
    await state.update_data(hh_ui_message_id=sent.message_id)
    await ui_register_message(state, message.chat.id, sent.message_id)
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


@router.callback_query(
    HouseholdPaymentsState.waiting_for_answer,
    F.data.in_({"hh_pay:yes", "hh_pay:no", "hh_pay:back"}),
)
async def handle_household_answer(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle Yes/No/Back answers for household questions."""

    data = await state.get_data()
    month = data.get("hh_month")
    questions = list(data.get("hh_questions") or [])
    index = int(data.get("hh_index") or 0)
    answers = dict(data.get("hh_answers") or {})
    ui_message_id = data.get("hh_ui_message_id")
    user_id = callback.from_user.id

    if callback.message is None or callback.message.message_id != ui_message_id:
        await callback.answer("Сообщение устарело", show_alert=False)
        return

    if callback.data == "hh_pay:back" and index == 0:
        await callback.answer("Назад нельзя — это первый вопрос", show_alert=True)
        return

    await callback.answer()

    if not month or not questions:
        await ui_cleanup_messages(callback.bot, state)
        await state.clear()
        await _send_main_menu_summary(
            callback.bot, state, callback.message.chat.id, user_id
        )
        return

    if callback.data == "hh_pay:back":
        index -= 1
        await state.update_data(hh_index=index)
        text = _render_household_questions_text(
            month,
            questions,
            answers,
            current_index=index,
        )
        await callback.message.edit_text(
            text,
            reply_markup=household_payments_inline_keyboard(show_back=True),
            parse_mode="HTML",
        )
        return

    if index >= len(questions):
        final_text = _render_household_questions_text(
            month,
            questions,
            answers,
            current_index=None,
        )
        await callback.message.edit_text(
            final_text,
            reply_markup=None,
            parse_mode="HTML",
        )
        await ui_cleanup_messages(callback.bot, state)
        await state.clear()
        await _send_main_menu_summary(
            callback.bot, state, callback.message.chat.id, user_id
        )
        return

    question = questions[index]
    code = str(question.get("code", ""))
    amount = question.get("amount")
    amount_value = float(amount) if amount is not None else 0.0
    db = FinanceDatabase()

    if callback.data == "hh_pay:yes":
        if answers.get(code) != "yes":
            if amount is not None:
                db.update_saving(user_id, "быт", -amount_value)
            await db.mark_household_question_paid(user_id, month, code)
        answers[code] = "yes"
        LOGGER.info("User %s answered YES for household question %s", user_id, code)
    elif callback.data == "hh_pay:no":
        if answers.get(code) == "yes":
            if amount is not None:
                db.update_saving(user_id, "быт", amount_value)
            await db.mark_household_question_unpaid(user_id, month, code)
        answers[code] = "no"
        LOGGER.info("User %s answered NO for household question %s", user_id, code)

    index += 1
    await state.update_data(hh_answers=answers, hh_index=index)
    if index < len(questions):
        text = _render_household_questions_text(
            month,
            questions,
            answers,
            current_index=index,
        )
        await callback.message.edit_text(
            text,
            reply_markup=household_payments_inline_keyboard(show_back=True),
            parse_mode="HTML",
        )
        return

    final_text = _render_household_questions_text(
        month,
        questions,
        answers,
        current_index=None,
    )
    await callback.message.edit_text(
        final_text,
        reply_markup=None,
        parse_mode="HTML",
    )
    await ui_cleanup_messages(callback.bot, state)
    await state.clear()
    await _send_main_menu_summary(callback.bot, state, callback.message.chat.id, user_id)
