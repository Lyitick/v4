"""Handlers for household payments scenario."""
from datetime import datetime, time as dt_time
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
from Bot.keyboards.settings import (
    household_remove_keyboard,
    household_settings_inline_keyboard,
    settings_menu_keyboard,
)
from Bot.renderers.household import (
    build_household_question_keyboard,
    format_household_items,
    render_household_questions_text,
)
from Bot.services.household import (
    build_answers_from_status,
    build_household_questions,
    filter_unpaid_questions,
    get_current_question,
    get_next_index,
    get_previous_index,
    should_ignore_answer,
    update_flow_state,
)
from Bot.states.money_states import HouseholdPaymentsState, HouseholdSettingsState
from Bot.utils.datetime_utils import current_month_str, now_tz
from Bot.utils.savings import format_savings_summary
from Bot.utils.ui_cleanup import (
    ui_cleanup_messages,
    ui_register_message,
    ui_register_user_message,
)

LOGGER = logging.getLogger(__name__)

router = Router(name="household_payments")


def _format_meta(meta: dict) -> str:
    if not meta:
        return "-"
    return " ".join(f"{key}={value}" for key, value in meta.items())


async def _log_state_transition(
    state: FSMContext, user_id: int, to_state: str | None
) -> None:
    from_state = await state.get_state()
    LOGGER.info(
        "USER=%s ACTION=STATE_TRANSITION STATE=%s->%s META=-",
        user_id,
        from_state,
        to_state,
    )


def _log_event(user_id: int, action: str, state: str | None, **meta: str) -> None:
    LOGGER.info(
        "USER=%s ACTION=%s STATE=%s META=%s",
        user_id,
        action,
        state,
        _format_meta(meta),
    )


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


def _format_household_items(
    items: List[Dict[str, int | str]],
    unpaid_set: set[str],
) -> str:
    return format_household_items(items, unpaid_set)


async def _send_household_settings_overview(
    message: Message, db: FinanceDatabase, user_id: int
) -> None:
    items = db.list_active_household_items(user_id)
    month = current_month_str()
    unpaid_codes = await db.get_unpaid_household_questions(user_id, month)
    unpaid_set: set[str] = set(unpaid_codes)
    _log_event(
        user_id,
        "HOUSEHOLD_SETTINGS_OVERVIEW",
        None,
        month=month,
        items_count=str(len(items)),
        unpaid_count=str(len(unpaid_set)),
    )
    if not items:
        _log_event(
            user_id,
            "HOUSEHOLD_SETTINGS_EMPTY",
            None,
            source="list_active_household_items",
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
                LOGGER.warning("Failed to delete amount prompt message", exc_info=True)
            return

        try:
            amount = int(amount_str)
        except (TypeError, ValueError):
            await message.answer("Нужно ввести число. Попробуй снова.")
            try:
                await message.delete()
            except Exception:
                LOGGER.warning("Failed to delete amount prompt message", exc_info=True)
            return

        if amount <= 0:
            await message.answer("Сумма должна быть больше нуля. Попробуй снова.")
            try:
                await message.delete()
            except Exception:
                LOGGER.warning("Failed to delete amount prompt message", exc_info=True)
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
            LOGGER.warning("Failed to delete amount confirmation message", exc_info=True)
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
            LOGGER.warning("Failed to edit amount message", exc_info=True)

    await state.update_data(amount_sum=new_sum, amount_message_id=amount_message_id)

    try:
        await message.delete()
    except Exception:
        LOGGER.warning("Failed to delete calculator message", exc_info=True)


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
        LOGGER.warning(
            "Failed to delete user menu message (Бытовые платежи)", exc_info=True
        )

    user_id = message.from_user.id
    db = FinanceDatabase()

    await reset_household_cycle_if_needed(user_id, db)
    db.ensure_household_items_seeded(user_id)
    items = db.list_active_household_items(user_id)
    if not items:
        await ui_cleanup_messages(message.bot, state)
        await _log_state_transition(state, user_id, None)
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
    questions = build_household_questions(items)
    answers = build_answers_from_status(status_map)
    all_paid = all(status_map.get(str(question.get("code", "")), 0) == 1 for question in questions)
    unpaid_codes = await db.get_unpaid_household_questions(user_id, month)
    hh_questions = filter_unpaid_questions(questions, unpaid_codes)

    if all_paid or not hh_questions:
        text = render_household_questions_text(
            month, questions, answers, current_index=None
        )
        lines = text.splitlines()
        if lines:
            lines[0] = f"✅ Все бытовые платежи оплачены за {month}"
        text = "\n".join(lines)
        await ui_cleanup_messages(message.bot, state)
        await _log_state_transition(state, user_id, None)
        await state.clear()
        sent = await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=await build_main_menu_for_user(user_id),
        )
        await ui_register_message(state, message.chat.id, sent.message_id)
        _log_event(
            user_id,
            "HOUSEHOLD_ALL_PAID",
            None,
            month=month,
        )
        return

    await _log_state_transition(state, user_id, HouseholdPaymentsState.waiting_for_answer.state)
    await state.set_state(HouseholdPaymentsState.waiting_for_answer)
    flow_state = update_flow_state(
        month=month,
        questions=hh_questions,
        current_step_index=0,
        answers=answers,
        processed_steps=[],
    )
    await state.update_data(
        hh_month=month,
        hh_questions=hh_questions,
        hh_index=0,
        hh_answers=answers,
        hh_ui_message_id=0,
        current_step_index=flow_state.current_step_index,
        current_question_code=flow_state.current_question_code,
        processed_steps=[],
    )
    text = render_household_questions_text(
        month, hh_questions, answers, current_index=0
    )
    sent = await message.answer(
        text,
        reply_markup=build_household_question_keyboard(
            flow_state.current_question_code, show_back=False
        ),
        parse_mode="HTML",
    )
    await state.update_data(hh_ui_message_id=sent.message_id)
    await ui_register_message(state, message.chat.id, sent.message_id)
    _log_event(
        user_id,
        "HOUSEHOLD_START",
        await state.get_state(),
        month=month,
    )


@router.message(F.text == "Проверить быт")
async def trigger_household_notifications(message: Message, state: FSMContext) -> None:
    """Trigger BYT purchases check (household wishlist) as if timer fired."""

    user_id = message.from_user.id
    db = FinanceDatabase()
    _log_event(user_id, "BYT_MANUAL_CHECK", None)

    db.ensure_byt_timer_defaults(user_id)
    data = await state.get_data()
    last_ts = data.get("byt_manual_check_ts")
    current_ts = time.time()
    if last_ts is not None and current_ts - float(last_ts) < 2:
        sent = await message.answer(
            "Уже проверил. Попробуй ещё раз через пару секунд.",
            reply_markup=await build_main_menu_for_user(user_id),
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)
        return
    await state.update_data(byt_manual_check_ts=current_ts)
    try:
        await message.delete()
    except TelegramBadRequest:
        LOGGER.warning("Failed to delete BYT manual check message", exc_info=True)

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

    now_dt = now_tz()
    total_items = db.get_active_byt_wishes(user_id)
    due_items = db.list_active_byt_items_for_reminder(user_id, now_dt)
    due_ids = {int(item.get("id")) for item in due_items if item.get("id") is not None}
    deferred_items = [
        item
        for item in total_items
        if item.get("id") is not None and int(item.get("id")) not in due_ids
    ]
    nearest_deferred = None
    for item in deferred_items:
        deferred_until = item.get("deferred_until")
        if not deferred_until:
            continue
        try:
            deferred_dt = datetime.fromisoformat(str(deferred_until))
        except ValueError:
            continue
        if nearest_deferred is None or deferred_dt < nearest_deferred:
            nearest_deferred = deferred_dt
    _log_event(
        user_id,
        "BYT_MANUAL_CHECK_SUMMARY",
        None,
        total_items=str(len(total_items)),
        due_items=str(len(due_items)),
        deferred_items=str(len(deferred_items)),
        nearest_deferred=nearest_deferred.isoformat() if nearest_deferred else "None",
    )
    if not due_items:
        text = "✅ Сейчас покупать ничего не нужно. Список пуст или всё отложено."
        if deferred_items:
            if nearest_deferred:
                nearest_label = nearest_deferred.strftime("%d.%m.%Y %H:%M")
                text = (
                    f"{text}\nЕсть отложенные покупки: {len(deferred_items)} шт. "
                    f"(ближайшая — {nearest_label})"
                )
            else:
                text = (
                    f"{text}\nЕсть отложенные покупки: {len(deferred_items)} шт."
                )
        sent = await message.answer(
            text, reply_markup=await build_main_menu_for_user(user_id)
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)
        return

    await run_byt_timer_check(
        message.bot, db, user_id=user_id, simulated_time=simulated_time
    )


@router.callback_query(
    HouseholdPaymentsState.waiting_for_answer,
    F.data.startswith("hh_pay:"),
)
async def handle_household_answer(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle Yes/No/Back answers for household questions."""

    data = await state.get_data()
    month = data.get("hh_month")
    questions = list(data.get("hh_questions") or [])
    index = int(data.get("current_step_index") or data.get("hh_index") or 0)
    answers = dict(data.get("hh_answers") or {})
    ui_message_id = data.get("hh_ui_message_id")
    processed_steps = set(data.get("processed_steps") or [])
    user_id = callback.from_user.id

    if callback.message is None or callback.message.message_id != ui_message_id:
        await callback.answer("Сообщение устарело", show_alert=False)
        return

    callback_parts = callback.data.split(":") if callback.data else []
    if len(callback_parts) < 2:
        await callback.answer("Сообщение устарело", show_alert=False)
        return
    action = callback_parts[1]
    callback_code = callback_parts[2] if len(callback_parts) > 2 else None

    if action == "back" and index == 0:
        await callback.answer("Назад нельзя — это первый вопрос", show_alert=True)
        return

    await callback.answer()

    if not month or not questions:
        await ui_cleanup_messages(callback.bot, state)
        await _log_state_transition(state, user_id, None)
        await state.clear()
        await _send_main_menu_summary(
            callback.bot, state, callback.message.chat.id, user_id
        )
        return

    current_question = get_current_question(questions, index)
    current_code = str(current_question.get("code")) if current_question else None
    target_code = callback_code or current_code

    if action == "back":
        index = get_previous_index(index)
        current_question = get_current_question(questions, index)
        current_code = str(current_question.get("code")) if current_question else None
        await state.update_data(
            hh_index=index,
            current_step_index=index,
            current_question_code=current_code,
        )
        text = render_household_questions_text(
            month, questions, answers, current_index=index
        )
        await callback.message.edit_text(
            text,
            reply_markup=build_household_question_keyboard(
                current_code, show_back=index > 0
            ),
            parse_mode="HTML",
        )
        _log_event(
            user_id,
            "HOUSEHOLD_BACK",
            await state.get_state(),
            month=str(month),
            index=str(index),
            question_code=str(current_code),
        )
        return

    if index >= len(questions):
        final_text = render_household_questions_text(
            month, questions, answers, current_index=None
        )
        await callback.message.edit_text(
            final_text,
            reply_markup=None,
            parse_mode="HTML",
        )
        await ui_cleanup_messages(callback.bot, state)
        await _log_state_transition(state, user_id, None)
        await state.clear()
        await _send_main_menu_summary(
            callback.bot, state, callback.message.chat.id, user_id
        )
        return

    if target_code and target_code != current_code:
        if target_code in processed_steps:
            await callback.answer("Уже учтено", show_alert=False)
            return
        await callback.answer("Сообщение устарело", show_alert=False)
        return

    question = current_question
    if not question:
        await callback.answer("Сообщение устарело", show_alert=False)
        return

    code = str(question.get("code", ""))
    amount = question.get("amount")
    amount_value = float(amount) if amount is not None else 0.0
    db = FinanceDatabase()

    if action not in {"yes", "no"}:
        await callback.answer("Сообщение устарело", show_alert=False)
        return

    if should_ignore_answer(answers, processed_steps, code, action):
        await callback.answer("Уже учтено", show_alert=False)
        return

    db.apply_household_payment_answer(
        user_id=user_id,
        month=str(month),
        question_code=code,
        amount=amount_value if amount is not None else None,
        answer=action,
    )
    answers[code] = "yes" if action == "yes" else "no"
    processed_steps.add(code)

    _log_event(
        user_id,
        "HOUSEHOLD_ANSWER",
        await state.get_state(),
        month=str(month),
        question_code=code,
        answer=action,
    )

    index = get_next_index(index, questions)
    next_question = get_current_question(questions, index)
    next_code = str(next_question.get("code")) if next_question else None
    await state.update_data(
        hh_answers=answers,
        hh_index=index,
        current_step_index=index,
        current_question_code=next_code,
        processed_steps=list(processed_steps),
    )
    if index < len(questions):
        text = render_household_questions_text(
            month, questions, answers, current_index=index
        )
        await callback.message.edit_text(
            text,
            reply_markup=build_household_question_keyboard(
                next_code, show_back=index > 0
            ),
            parse_mode="HTML",
        )
        return

    final_text = render_household_questions_text(
        month, questions, answers, current_index=None
    )
    await callback.message.edit_text(
        final_text,
        reply_markup=None,
        parse_mode="HTML",
    )
    await ui_cleanup_messages(callback.bot, state)
    await _log_state_transition(state, user_id, None)
    await state.clear()
    await _send_main_menu_summary(callback.bot, state, callback.message.chat.id, user_id)
