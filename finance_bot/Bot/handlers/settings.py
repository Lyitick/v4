"""Inline settings handlers for a single-page experience."""
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from Bot.database.crud import FinanceDatabase
from Bot.handlers.common import build_main_menu_for_user
from Bot.keyboards.settings import (
    expense_categories_select_keyboard,
    expense_settings_inline_keyboard,
    income_categories_select_keyboard,
    income_settings_inline_keyboard,
    settings_home_inline_keyboard,
    settings_stub_inline_keyboard,
)
from Bot.keyboards.calculator import income_calculator_keyboard
from Bot.states.money_states import IncomeSettingsState

router = Router()
LOGGER = logging.getLogger(__name__)
PERCENT_DIGITS = {str(i) for i in range(10)}
PERCENT_INPUT_BUTTONS = PERCENT_DIGITS | {"Очистить", "✅ Газ"}


async def _store_settings_message(state: FSMContext, chat_id: int, message_id: int) -> None:
    await state.update_data(settings_chat_id=chat_id, settings_message_id=message_id)


async def _get_settings_message_ids(
    state: FSMContext, fallback_message: Message
) -> tuple[int, int]:
    data = await state.get_data()
    chat_id = data.get("settings_chat_id") or fallback_message.chat.id
    message_id = data.get("settings_message_id") or fallback_message.message_id
    return int(chat_id), int(message_id)


async def _edit_settings_page(
    *,
    bot,
    state: FSMContext,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup,
) -> int:
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup
        )
        new_message_id = message_id
    except TelegramBadRequest:
        new_message = await bot.send_message(
            chat_id=chat_id, text=text, reply_markup=reply_markup
        )
        new_message_id = new_message.message_id
    await _store_settings_message(state, chat_id, new_message_id)
    return new_message_id


async def _render_settings_home(message: Message, state: FSMContext) -> None:
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="⚙️ НАСТРОЙКИ",
        reply_markup=settings_home_inline_keyboard(),
    )


def _format_category_text(
    title: str, categories: list[dict], error_message: str | None = None
) -> str:
    lines: list[str] = [title, ""]
    for category in categories:
        lines.append(f"{category['title']} — {category['percent']}%")
    total = sum(category.get("percent", 0) for category in categories)
    lines.append("")
    lines.append(f"Сумма: {total}%")
    if error_message:
        lines.append("")
        lines.append(error_message)
    return "\n".join(lines)


async def _render_income_settings(
    *,
    state: FSMContext,
    message: Message,
    db: FinanceDatabase,
    user_id: int,
    error_message: str | None = None,
) -> list[dict]:
    db.ensure_income_categories_seeded(user_id)
    categories = db.list_active_income_categories(user_id)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=_format_category_text("📊 ДОХОД — категории и проценты", categories, error_message),
        reply_markup=income_settings_inline_keyboard(),
    )
    return categories


async def _render_expense_settings(
    *,
    state: FSMContext,
    message: Message,
    db: FinanceDatabase,
    user_id: int,
    error_message: str | None = None,
) -> list[dict]:
    db.ensure_expense_categories_seeded(user_id)
    categories = db.list_active_expense_categories(user_id)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=_format_category_text(
            "💸 РАСХОД — категории и проценты", categories, error_message
        ),
        reply_markup=expense_settings_inline_keyboard(),
    )
    return categories


@router.message(F.text == "⚙️")
async def open_settings(message: Message, state: FSMContext) -> None:
    """Open settings entry point with inline navigation."""

    await state.clear()
    sent = await message.answer(
        "⚙️ НАСТРОЙКИ", reply_markup=settings_home_inline_keyboard()
    )
    await _store_settings_message(state, sent.chat.id, sent.message_id)


@router.callback_query(F.data == "st:home")
async def back_to_settings_home(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _render_settings_home(callback.message, state)


@router.callback_query(F.data == "st:income")
async def open_income_settings(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    db = FinanceDatabase()
    await _render_income_settings(
        state=state, message=callback.message, db=db, user_id=callback.from_user.id
    )


@router.callback_query(F.data == "st:expense")
async def open_expense_settings(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    db = FinanceDatabase()
    await _render_expense_settings(
        state=state, message=callback.message, db=db, user_id=callback.from_user.id
    )


@router.callback_query(F.data.in_({"st:wishlist", "st:byt_rules", "st:byt_timer"}))
async def settings_stubs(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="В разработке",
        reply_markup=settings_stub_inline_keyboard(),
    )


@router.callback_query(F.data == "st:back_main")
async def settings_back_to_main(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.answer(
        "Главное меню",
        reply_markup=await build_main_menu_for_user(callback.from_user.id),
    )


@router.callback_query(F.data.in_({"inc:add", "exp:add"}))
async def category_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    scope = "income" if callback.data == "inc:add" else "expense"
    await state.set_state(IncomeSettingsState.waiting_for_category_title)
    await state.update_data(category_scope=scope)
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Введи название новой категории",
        reply_markup=None,
    )


@router.message(IncomeSettingsState.waiting_for_category_title)
async def income_add_category_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title or len(title) > 32:
        await message.answer("Название должно быть от 1 до 32 символов.")
        return

    db = FinanceDatabase()
    data = await state.get_data()
    scope = data.get("category_scope", "income")
    if scope == "expense":
        db.create_expense_category(message.from_user.id, title)
        await _render_expense_settings(
            state=state, message=message, db=db, user_id=message.from_user.id
        )
    else:
        db.create_income_category(message.from_user.id, title)
        await _render_income_settings(
            state=state, message=message, db=db, user_id=message.from_user.id
        )
    await state.set_state(None)


@router.callback_query(F.data.in_({"inc:del_menu", "exp:del_menu"}))
async def category_delete_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    scope = "income" if callback.data == "inc:del_menu" else "expense"
    db = FinanceDatabase()
    categories = (
        db.list_active_income_categories(callback.from_user.id)
        if scope == "income"
        else db.list_active_expense_categories(callback.from_user.id)
    )
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    keyboard_builder = income_categories_select_keyboard
    back_callback = "st:income"
    if scope == "expense":
        keyboard_builder = expense_categories_select_keyboard
        back_callback = "st:expense"
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Что удалить?",
        reply_markup=keyboard_builder(categories, f"{scope[:3]}:del", back_callback=back_callback),
    )


@router.callback_query(F.data.startswith("inc:del:") | F.data.startswith("exp:del:"))
async def category_delete(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return

    db = FinanceDatabase()
    scope = "income" if callback.data.startswith("inc:") else "expense"
    categories = (
        db.list_active_income_categories(callback.from_user.id)
        if scope == "income"
        else db.list_active_expense_categories(callback.from_user.id)
    )
    if len([cat for cat in categories if cat.get("is_active", 1)]) <= 1:
        render_func = _render_income_settings if scope == "income" else _render_expense_settings
        await render_func(
            state=state,
            message=callback.message,
            db=db,
            user_id=callback.from_user.id,
            error_message="Нельзя удалить последнюю категорию.",
        )
        return

    if scope == "income":
        db.deactivate_income_category(callback.from_user.id, category_id)
        await _render_income_settings(
            state=state, message=callback.message, db=db, user_id=callback.from_user.id
        )
    else:
        db.deactivate_expense_category(callback.from_user.id, category_id)
        await _render_expense_settings(
            state=state, message=callback.message, db=db, user_id=callback.from_user.id
        )


@router.callback_query(F.data.in_({"inc:pct_menu", "exp:pct_menu"}))
async def category_percent_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    scope = "income" if callback.data == "inc:pct_menu" else "expense"
    db = FinanceDatabase()
    categories = (
        db.list_active_income_categories(callback.from_user.id)
        if scope == "income"
        else db.list_active_expense_categories(callback.from_user.id)
    )
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    keyboard_builder = income_categories_select_keyboard
    back_callback = "st:income"
    if scope == "expense":
        keyboard_builder = expense_categories_select_keyboard
        back_callback = "st:expense"
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Какой категории меняем процент?",
        reply_markup=keyboard_builder(categories, f"{scope[:3]}:pct", back_callback=back_callback),
    )


@router.callback_query(F.data.startswith("inc:pct:") | F.data.startswith("exp:pct:"))
async def category_percent_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return

    db = FinanceDatabase()
    scope = "income" if callback.data.startswith("inc:") else "expense"
    category = (
        db.get_income_category_by_id(callback.from_user.id, category_id)
        if scope == "income"
        else db.get_expense_category_by_id(callback.from_user.id, category_id)
    )
    if not category:
        render_func = _render_income_settings if scope == "income" else _render_expense_settings
        await render_func(
            state=state, message=callback.message, db=db, user_id=callback.from_user.id
        )
        return

    await state.update_data(
        edit_scope=scope,
        editing_category_id=category_id,
        previous_percent=category.get("percent", 0),
        percent_str="0",
    )
    await state.set_state(IncomeSettingsState.waiting_for_percent)
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=f"Введи процент (0–100) для: {category['title']}",
        reply_markup=None,
    )

    percent_message = await callback.message.answer(
        ": 0", reply_markup=income_calculator_keyboard()
    )
    await state.update_data(
        percent_display_chat_id=percent_message.chat.id,
        percent_display_message_id=percent_message.message_id,
    )
    LOGGER.info(
        "Percent edit start: user=%s scope=%s category_id=%s",
        callback.from_user.id,
        scope,
        category_id,
    )


@router.message(IncomeSettingsState.waiting_for_percent)
async def income_percent_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (message.text or "").strip()
    if text not in PERCENT_INPUT_BUTTONS:
        await message.answer("Используй кнопки калькулятора.")
        return

    percent_str = data.get("percent_str", "0")
    display_chat_id = data.get("percent_display_chat_id", message.chat.id)
    display_message_id = data.get("percent_display_message_id")

    if text in PERCENT_DIGITS:
        percent_str = percent_str.lstrip("0") if percent_str != "0" else ""
        percent_str = f"{percent_str}{text}" or "0"
        LOGGER.info(
            "Percent input: user=%s scope=%s value=%s",
            message.from_user.id,
            data.get("edit_scope", "income"),
            percent_str,
        )
        try:
            await message.bot.edit_message_text(
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {percent_str}",
            )
        except Exception:
            fallback = await message.bot.send_message(
                chat_id=display_chat_id, text=f": {percent_str}"
            )
            display_message_id = fallback.message_id
        await state.update_data(
            percent_str=percent_str,
            percent_display_chat_id=display_chat_id,
            percent_display_message_id=display_message_id,
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    if text == "Очистить":
        percent_str = "0"
        try:
            await message.bot.edit_message_text(
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=": 0",
            )
        except Exception:
            fallback = await message.bot.send_message(chat_id=display_chat_id, text=": 0")
            display_message_id = fallback.message_id
        await state.update_data(
            percent_str=percent_str,
            percent_display_chat_id=display_chat_id,
            percent_display_message_id=display_message_id,
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    if text == "✅ Газ":
        try:
            percent = int(percent_str or "0")
        except ValueError:
            await message.answer("Процент должен быть числом.")
            return
        if percent < 0 or percent > 100:
            await message.answer("Процент должен быть в диапазоне 0–100.")
            return

        category_id = data.get("editing_category_id")
        previous_percent = int(data.get("previous_percent", 0))
        scope = data.get("edit_scope", "income")
        if category_id is None:
            await state.set_state(None)
            return

        db = FinanceDatabase()
        if scope == "expense":
            db.update_expense_category_percent(message.from_user.id, category_id, percent)
            total = db.sum_expense_category_percents(message.from_user.id)
        else:
            db.update_income_category_percent(message.from_user.id, category_id, percent)
            total = db.sum_income_category_percents(message.from_user.id)

        if total != 100:
            if scope == "expense":
                db.update_expense_category_percent(
                    message.from_user.id, category_id, previous_percent
                )
            else:
                db.update_income_category_percent(
                    message.from_user.id, category_id, previous_percent
                )
            await state.set_state(None)
            render_func = (
                _render_expense_settings if scope == "expense" else _render_income_settings
            )
            await render_func(
                state=state,
                message=message,
                db=db,
                user_id=message.from_user.id,
                error_message=f"Сумма процентов должна быть 100%. Сейчас: {total}%",
            )
            return

        LOGGER.info(
            "Percent saved: user=%s scope=%s category_id=%s value=%s",
            message.from_user.id,
            scope,
            category_id,
            percent,
        )
        display_message_id = data.get("percent_display_message_id")
        if display_message_id:
            try:
                await message.bot.delete_message(
                    chat_id=data.get("percent_display_chat_id", message.chat.id),
                    message_id=int(display_message_id),
                )
            except Exception:
                pass
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer("Готово", reply_markup=ReplyKeyboardRemove())
        await state.set_state(None)
        render_func = (
            _render_expense_settings if scope == "expense" else _render_income_settings
        )
        await render_func(
            state=state, message=message, db=db, user_id=message.from_user.id
        )
