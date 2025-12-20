"""Handlers for household payments scenario."""
from datetime import datetime, time as dt_time
import asyncio
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
from Bot.keyboards.calculator import income_calculator_keyboard
from Bot.keyboards.household import household_payments_answer_keyboard
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


async def _delete_message_safely(bot, chat_id: int, message_id: int | None) -> None:
    if message_id is None:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest as exc:
        description = str(exc)
        if "message to delete not found" in description or "message can't be deleted" in description:
            LOGGER.warning(
                "Failed to delete message (chat_id=%s, message_id=%s): %s",
                chat_id,
                message_id,
                description,
            )
        else:
            LOGGER.exception(
                "Unexpected TelegramBadRequest deleting message (chat_id=%s, message_id=%s)",
                chat_id,
                message_id,
                exc_info=True,
            )
    except Exception:
        LOGGER.exception(
            "Unexpected error deleting message (chat_id=%s, message_id=%s)",
            chat_id,
            message_id,
            exc_info=True,
        )


async def _send_main_menu_summary(bot, chat_id: int, user_id: int) -> None:
    db = FinanceDatabase()
    savings = db.get_user_savings(user_id)
    summary = format_savings_summary(savings)
    menu = await build_main_menu_for_user(user_id)
    await bot.send_message(chat_id=chat_id, text=f"Текущие накопления:\n{summary}", reply_markup=menu)


async def _ask_next_household_question(
    message: Message,
    state: FSMContext,
    pending_codes: list[str],
    asked_stack: list[str],
    month: str,
) -> None:
    if not pending_codes:
        countdown = await message.answer("КРАСАВА 5", reply_markup=ReplyKeyboardRemove())
        ui_ids = list((await state.get_data()).get("household_ui_message_ids") or [])
        ui_ids.append(countdown.message_id)
        await state.update_data(household_ui_message_ids=ui_ids)
        try:
            await asyncio.sleep(1)
            await countdown.edit_text("КРАСАВА 4")
            await asyncio.sleep(1)
            await countdown.edit_text("КРАСАВА 3")
            await asyncio.sleep(1)
            await countdown.edit_text("КРАСАВА 2")
            await asyncio.sleep(1)
            await countdown.edit_text("КРАСАВА 1")
            await asyncio.sleep(1)
        except Exception:
            pass
        await _delete_message_safely(message.bot, message.chat.id, countdown.message_id)
        data = await state.get_data()
        cleanup_ids = list(data.get("household_ui_message_ids") or [])
        LOGGER.info(
            "Household cleanup ids (count=%s): %s",
            len(cleanup_ids),
            cleanup_ids,
        )
        for msg_id in cleanup_ids:
            await _delete_message_safely(message.bot, message.chat.id, msg_id)
        await state.clear()
        await _send_main_menu_summary(message.bot, message.chat.id, message.from_user.id)
        return

    next_code = pending_codes.pop(0)
    db = FinanceDatabase()
    question = db.get_household_item_by_code(message.from_user.id, next_code)
    if question is None:
        await state.clear()
        await _send_main_menu_summary(message.bot, message.chat.id, message.from_user.id)
        return

    question_message = await message.answer(
        str(question.get("text", "")),
        reply_markup=household_payments_answer_keyboard(),
    )
    ui_ids = list((await state.get_data()).get("household_ui_message_ids") or [])
    ui_ids.append(question_message.message_id)
    LOGGER.info(
        "Household question sent (code=%s, message_id=%s, ui_count=%s)",
        next_code,
        question_message.message_id,
        len(ui_ids),
    )
    await state.update_data(
        pending_codes=pending_codes,
        asked_stack=asked_stack + [next_code],
        current_code=next_code,
        last_question_message_id=question_message.message_id,
        month=month,
        household_ui_message_ids=ui_ids,
    )


async def reset_household_cycle_if_needed(
    user_id: int, db: FinanceDatabase, now: datetime | None = None
) -> None:
    """Lazily reset household payments cycle after 6th of month at noon."""

    current = now or datetime.now(tz=settings.TIMEZONE)
    month = current_month_str(current)

    threshold = datetime(current.year, current.month, 6, 12, 0, tzinfo=settings.TIMEZONE)
    if current >= threshold:
        await db.init_household_questions_for_month(user_id, month)


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
    pending_codes = [item.get("code", "") for item in items if item.get("code") in unpaid_set]

    if not pending_codes:
        await state.clear()
        sent = await message.answer(
            "На этот месяц всё оплачено ✅",
            reply_markup=ReplyKeyboardRemove(),
        )
        await asyncio.sleep(2)
        await _delete_message_safely(message.bot, message.chat.id, sent.message_id)
        await _send_main_menu_summary(message.bot, message.chat.id, user_id)
        LOGGER.info("User %s has no unpaid household questions for month %s", user_id, month)
        return

    await state.set_state(HouseholdPaymentsState.waiting_for_answer)
    await state.update_data(
        pending_codes=pending_codes,
        asked_stack=[],
        current_code=None,
        last_question_message_id=None,
        month=month,
        household_ui_message_ids=[],
    )
    await _ask_next_household_question(
        message,
        state,
        pending_codes,
        [],
        month,
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


@router.message(
    HouseholdPaymentsState.waiting_for_answer,
    F.text.in_({"✅ Да", "❌ Нет", "⬅️ Назад"}),
)
async def handle_household_answer(message: Message, state: FSMContext) -> None:
    """Handle Yes/No/Back answers for household questions."""

    data = await state.get_data()
    month = data.get("month")
    pending_codes = list(data.get("pending_codes") or [])
    asked_stack = list(data.get("asked_stack") or [])
    current_code = data.get("current_code")
    last_question_message_id = data.get("last_question_message_id")
    user_id = message.from_user.id
    db = FinanceDatabase()
    db.ensure_household_items_seeded(user_id)

    await _delete_message_safely(message.bot, message.chat.id, message.message_id)

    if not month:
        await state.clear()
        await _send_main_menu_summary(message.bot, message.chat.id, user_id)
        return

    if message.text == "⬅️ Назад":
        if len(asked_stack) <= 1:
            await state.clear()
            await _send_main_menu_summary(message.bot, message.chat.id, user_id)
            return
        asked_stack.pop()
        previous_code = asked_stack[-1]
        await state.update_data(
            asked_stack=asked_stack,
            current_code=previous_code,
            last_question_message_id=None,
        )
        question = db.get_household_item_by_code(user_id, previous_code)
        if question is None:
            await state.clear()
            await _send_main_menu_summary(message.bot, message.chat.id, user_id)
            return
        question_message = await message.answer(
            str(question.get("text", "")),
            reply_markup=household_payments_answer_keyboard(),
        )
        ui_ids = list((await state.get_data()).get("household_ui_message_ids") or [])
        ui_ids.append(question_message.message_id)
        LOGGER.info(
            "Household back question sent (code=%s, message_id=%s, ui_count=%s)",
            previous_code,
            question_message.message_id,
            len(ui_ids),
        )
        await state.update_data(
            last_question_message_id=question_message.message_id,
            household_ui_message_ids=ui_ids,
        )
        return

    if current_code:
        question = db.get_household_item_by_code(user_id, current_code)
    else:
        question = None

    if question is None:
        await state.clear()
        await _send_main_menu_summary(message.bot, message.chat.id, user_id)
        return

    if message.text == "✅ Да":
        db.update_saving(user_id, "быт", -float(question["amount"]))
        await db.mark_household_question_paid(user_id, month, current_code)
        LOGGER.info("User %s answered YES for household question %s", user_id, current_code)
    else:
        LOGGER.info("User %s answered NO for household question %s", user_id, current_code)

    if last_question_message_id is None:
        LOGGER.warning("Household question message id missing for code=%s", current_code)
    else:
        question_text = str(question.get("text", "")).rstrip()
        if question_text.endswith("?"):
            question_text = question_text[:-1].rstrip()
        if message.text == "✅ Да":
            updated_text = f"✅ {question_text}"
        else:
            updated_text = f"❌ {question_text} !!!"
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=last_question_message_id,
                text=updated_text,
            )
        except TelegramBadRequest as exc:
            LOGGER.warning(
                "Failed to update household question text (chat_id=%s, message_id=%s): %s",
                message.chat.id,
                last_question_message_id,
                exc,
            )
        except Exception:
            LOGGER.exception(
                "Unexpected error updating household question text (chat_id=%s, message_id=%s)",
                message.chat.id,
                last_question_message_id,
                exc_info=True,
            )

    await _ask_next_household_question(
        message,
        state,
        pending_codes,
        asked_stack,
        month,
    )
