"""Inline settings handlers for a single-page experience."""
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from Bot.database.crud import FinanceDatabase
from Bot.handlers.common import build_main_menu_for_user
from Bot.keyboards.settings import (
    income_categories_select_keyboard,
    income_settings_inline_keyboard,
    settings_home_inline_keyboard,
    settings_stub_inline_keyboard,
)
from Bot.states.money_states import IncomeSettingsState

router = Router()


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


def _format_income_text(categories: list[dict], error_message: str | None = None) -> str:
    lines: list[str] = ["📊 ДОХОД — категории и проценты", ""]
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
        text=_format_income_text(categories, error_message),
        reply_markup=income_settings_inline_keyboard(),
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


@router.callback_query(F.data == "inc:add")
async def income_add_category(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(IncomeSettingsState.waiting_for_category_title)
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
    db.create_income_category(message.from_user.id, title)
    await state.set_state(None)
    await _render_income_settings(
        state=state, message=message, db=db, user_id=message.from_user.id
    )


@router.callback_query(F.data == "inc:del_menu")
async def income_delete_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    db = FinanceDatabase()
    categories = db.list_active_income_categories(callback.from_user.id)
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Что удалить?",
        reply_markup=income_categories_select_keyboard(
            categories, "inc:del", back_callback="st:income"
        ),
    )


@router.callback_query(F.data.startswith("inc:del:"))
async def income_delete_category(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return

    db = FinanceDatabase()
    categories = db.list_active_income_categories(callback.from_user.id)
    if len([cat for cat in categories if cat.get("is_active", 1)]) <= 1:
        await _render_income_settings(
            state=state,
            message=callback.message,
            db=db,
            user_id=callback.from_user.id,
            error_message="Нельзя удалить последнюю категорию.",
        )
        return

    db.deactivate_income_category(callback.from_user.id, category_id)
    await _render_income_settings(
        state=state, message=callback.message, db=db, user_id=callback.from_user.id
    )


@router.callback_query(F.data == "inc:pct_menu")
async def income_percent_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    db = FinanceDatabase()
    categories = db.list_active_income_categories(callback.from_user.id)
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Какой категории меняем процент?",
        reply_markup=income_categories_select_keyboard(
            categories, "inc:pct", back_callback="st:income"
        ),
    )


@router.callback_query(F.data.startswith("inc:pct:"))
async def income_percent_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return

    db = FinanceDatabase()
    category = db.get_income_category_by_id(callback.from_user.id, category_id)
    if not category:
        await _render_income_settings(
            state=state, message=callback.message, db=db, user_id=callback.from_user.id
        )
        return

    await state.update_data(
        editing_category_id=category_id,
        previous_percent=category.get("percent", 0),
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


@router.message(IncomeSettingsState.waiting_for_percent)
async def income_percent_value(message: Message, state: FSMContext) -> None:
    raw_value = (message.text or "").strip()
    if not raw_value.isdigit():
        await message.answer("Нужно ввести число от 0 до 100.")
        return

    percent = int(raw_value)
    if percent < 0 or percent > 100:
        await message.answer("Процент должен быть в диапазоне 0–100.")
        return

    data = await state.get_data()
    category_id = data.get("editing_category_id")
    previous_percent = int(data.get("previous_percent", 0))
    if category_id is None:
        await state.set_state(None)
        return

    db = FinanceDatabase()
    db.update_income_category_percent(message.from_user.id, category_id, percent)
    total = db.sum_income_category_percents(message.from_user.id)
    if total != 100:
        db.update_income_category_percent(
            message.from_user.id, category_id, previous_percent
        )
        await state.set_state(None)
        await _render_income_settings(
            state=state,
            message=message,
            db=db,
            user_id=message.from_user.id,
            error_message=f"Сумма процентов должна быть 100%. Сейчас: {total}%",
        )
        return

    await state.set_state(None)
    await _render_income_settings(
        state=state, message=message, db=db, user_id=message.from_user.id
    )
