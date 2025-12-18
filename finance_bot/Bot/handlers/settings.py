"""Inline settings handlers for a single-page experience."""
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from Bot.database.crud import FinanceDatabase
from Bot.handlers.common import build_main_menu_for_user
from Bot.keyboards.settings import (
    byt_rules_inline_keyboard,
    byt_timer_inline_keyboard,
    byt_timer_times_select_keyboard,
    income_categories_select_keyboard,
    income_settings_inline_keyboard,
    settings_home_inline_keyboard,
    wishlist_categories_select_keyboard,
    wishlist_settings_inline_keyboard,
)
from Bot.keyboards.calculator import income_calculator_keyboard
from Bot.states.money_states import IncomeSettingsState
from Bot.states.wishlist_states import (
    BytSettingsState,
    BytTimerState,
    WishlistSettingsState,
)

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


def _format_wishlist_text(
    categories: list[dict], purchased_days: int, error_message: str | None = None
) -> str:
    lines: list[str] = ["🧾 ВИШЛИСТ — настройки", "", "Категории:", ""]
    if categories:
        for category in categories:
            lines.append(category.get("title", ""))
    lines.append("")
    lines.append(f'Показывать "Купленное": {purchased_days} дней')
    if error_message:
        lines.append("")
        lines.append(error_message)
    return "\n".join(lines)


def _format_byt_rules_text(settings: dict, error_message: str | None = None) -> str:
    on_off = {True: "ДА", False: "НЕТ", 1: "ДА", 0: "НЕТ"}
    lines = [
        "🧺 БЫТ — условия напоминаний",
        "",
        f"Напоминания включены: {on_off.get(settings.get('byt_reminders_enabled', 1), 'НЕТ')}",
        "Слать если список пуст: НЕТ",
        'Формат: "Что ты купил?" (кнопки-товары)',
        f"ОТЛОЖИТЬ: {on_off.get(settings.get('byt_defer_enabled', 1), 'НЕТ')}",
        f"Макс. дней отложить: {settings.get('byt_defer_max_days', 365)}",
    ]
    if error_message:
        lines.append("")
        lines.append(error_message)
    return "\n".join(lines)


def _format_byt_timer_text(times: list[dict], error_message: str | None = None) -> str:
    lines = ["⏰ БЫТ — таймер напоминаний", "Текущие времена:", ""]
    if times:
        for timer in times:
            lines.append(f"{int(timer.get('hour', 0)):02d}:{int(timer.get('minute', 0)):02d}")
    else:
        lines.append("(пусто)")
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


async def _render_wishlist_settings(
    *,
    state: FSMContext,
    message: Message,
    db: FinanceDatabase,
    user_id: int,
    error_message: str | None = None,
) -> list[dict]:
    db.ensure_wishlist_categories_seeded(user_id)
    db.ensure_user_settings(user_id)
    categories = db.list_active_wishlist_categories(user_id)
    settings_row = db.get_user_settings(user_id)
    purchased_days = int(settings_row.get("purchased_keep_days", 30) or 30)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=_format_wishlist_text(categories, purchased_days, error_message),
        reply_markup=wishlist_settings_inline_keyboard(),
    )
    return categories


async def _render_byt_rules_settings(
    *,
    state: FSMContext,
    message: Message,
    db: FinanceDatabase,
    user_id: int,
    error_message: str | None = None,
) -> dict:
    db.ensure_user_settings(user_id)
    settings_row = db.get_user_settings(user_id)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=_format_byt_rules_text(settings_row, error_message),
        reply_markup=byt_rules_inline_keyboard(),
    )
    return settings_row


async def _render_byt_timer_settings(
    *,
    state: FSMContext,
    message: Message,
    db: FinanceDatabase,
    user_id: int,
    error_message: str | None = None,
) -> list[dict]:
    db.ensure_byt_timer_defaults(user_id)
    times = db.list_active_byt_timer_times(user_id)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=_format_byt_timer_text(times, error_message),
        reply_markup=byt_timer_inline_keyboard(),
    )
    return times


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
    db = FinanceDatabase()
    if callback.data == "st:wishlist":
        await _render_wishlist_settings(
            state=state, message=callback.message, db=db, user_id=callback.from_user.id
        )
        return
    if callback.data == "st:byt_rules":
        await _render_byt_rules_settings(
            state=state, message=callback.message, db=db, user_id=callback.from_user.id
        )
        return
    await _render_byt_timer_settings(
        state=state, message=callback.message, db=db, user_id=callback.from_user.id
    )


@router.callback_query(F.data == "st:back_main")
async def settings_back_to_main(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.answer(
        "Главное меню",
        reply_markup=await build_main_menu_for_user(callback.from_user.id),
    )


@router.callback_query(F.data == "byt:toggle_enabled")
async def toggle_byt_enabled(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    db = FinanceDatabase()
    settings_row = db.get_user_settings(callback.from_user.id)
    current = bool(settings_row.get("byt_reminders_enabled", 1))
    db.set_byt_reminders_enabled(callback.from_user.id, not current)
    await _render_byt_rules_settings(
        state=state, message=callback.message, db=db, user_id=callback.from_user.id
    )


@router.callback_query(F.data == "byt:toggle_defer")
async def toggle_byt_defer(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    db = FinanceDatabase()
    settings_row = db.get_user_settings(callback.from_user.id)
    current = bool(settings_row.get("byt_defer_enabled", 1))
    db.set_byt_defer_enabled(callback.from_user.id, not current)
    await _render_byt_rules_settings(
        state=state, message=callback.message, db=db, user_id=callback.from_user.id
    )


@router.callback_query(F.data == "byt:edit_max_defer_days")
async def edit_byt_max_defer_days(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(BytSettingsState.waiting_for_max_defer_days)
    db = FinanceDatabase()
    settings_row = db.get_user_settings(callback.from_user.id)
    await state.update_data(
        byt_max_days_str="0", previous_byt_max_days=settings_row.get("byt_defer_max_days", 365)
    )
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Максимум дней отложки?",
        reply_markup=None,
    )
    prompt = await callback.message.answer(": 0", reply_markup=income_calculator_keyboard())
    await state.update_data(
        byt_max_display_chat_id=prompt.chat.id,
        byt_max_display_message_id=prompt.message_id,
    )


@router.callback_query(F.data == "bt:add_time_hour")
async def byt_timer_add_hour(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(BytTimerState.waiting_for_hour)
    await state.update_data(bt_hour_str="0")
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Введи ЧАС (0–23)",
        reply_markup=None,
    )
    prompt = await callback.message.answer(": 0", reply_markup=income_calculator_keyboard())
    await state.update_data(
        bt_hour_display_chat_id=prompt.chat.id,
        bt_hour_display_message_id=prompt.message_id,
    )


@router.callback_query(F.data == "bt:del_time_menu")
async def byt_timer_delete_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    db = FinanceDatabase()
    times = db.list_active_byt_timer_times(callback.from_user.id)
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Что удалить?",
        reply_markup=byt_timer_times_select_keyboard(
            times, "bt:del_time", back_callback="st:byt_timer"
        ),
    )


@router.callback_query(F.data.startswith("bt:del_time:"))
async def byt_timer_delete(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        timer_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return

    db = FinanceDatabase()
    times = db.list_active_byt_timer_times(callback.from_user.id)
    if len(times) <= 1:
        await _render_byt_timer_settings(
            state=state,
            message=callback.message,
            db=db,
            user_id=callback.from_user.id,
            error_message="Нельзя удалить последнее время.",
        )
        return

    db.deactivate_byt_timer_time(callback.from_user.id, timer_id)
    await _render_byt_timer_settings(
        state=state, message=callback.message, db=db, user_id=callback.from_user.id
    )


@router.callback_query(F.data == "bt:reset_default")
async def byt_timer_reset(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    db = FinanceDatabase()
    db.reset_byt_timer_times(callback.from_user.id)
    await _render_byt_timer_settings(
        state=state, message=callback.message, db=db, user_id=callback.from_user.id
    )


@router.callback_query(F.data == "inc:add")
async def category_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(IncomeSettingsState.waiting_for_category_title)
    await state.update_data(category_scope="income")
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Введи название новой категории",
        reply_markup=None,
    )


@router.callback_query(F.data == "wl:add_cat")
async def wishlist_category_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(WishlistSettingsState.waiting_for_category_title)
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Введи название категории",
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
    db.create_income_category(message.from_user.id, title)
    await _render_income_settings(
        state=state, message=message, db=db, user_id=message.from_user.id
    )
    await state.set_state(None)


@router.message(WishlistSettingsState.waiting_for_category_title)
async def wishlist_add_category_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title or len(title) > 32:
        await message.answer("Название должно быть от 1 до 32 символов.")
        return

    db = FinanceDatabase()
    db.create_wishlist_category(message.from_user.id, title)
    await _render_wishlist_settings(
        state=state, message=message, db=db, user_id=message.from_user.id
    )
    await state.set_state(None)


@router.callback_query(F.data == "inc:del_menu")
async def category_delete_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    scope = "income"
    db = FinanceDatabase()
    categories = db.list_active_income_categories(callback.from_user.id)
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    keyboard_builder = income_categories_select_keyboard
    back_callback = "st:income"
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Что удалить?",
        reply_markup=keyboard_builder(categories, f"{scope[:3]}:del", back_callback=back_callback),
    )


@router.callback_query(F.data == "wl:del_cat_menu")
async def wishlist_delete_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    db = FinanceDatabase()
    categories = db.list_active_wishlist_categories(callback.from_user.id)
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Что удалить?",
        reply_markup=wishlist_categories_select_keyboard(
            categories, "wl:del_cat", back_callback="st:wishlist"
        ),
    )


@router.callback_query(F.data.startswith("inc:del:"))
async def category_delete(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return

    db = FinanceDatabase()
    scope = "income"
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


@router.callback_query(F.data.startswith("wl:del_cat:"))
async def wishlist_category_delete(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return

    db = FinanceDatabase()
    categories = db.list_active_wishlist_categories(callback.from_user.id)
    if len(categories) <= 1:
        await _render_wishlist_settings(
            state=state,
            message=callback.message,
            db=db,
            user_id=callback.from_user.id,
            error_message="Нельзя удалить последнюю категорию.",
        )
        return

    db.deactivate_wishlist_category(callback.from_user.id, category_id)
    await _render_wishlist_settings(
        state=state, message=callback.message, db=db, user_id=callback.from_user.id
    )


@router.callback_query(F.data == "inc:pct_menu")
async def category_percent_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    scope = "income"
    db = FinanceDatabase()
    categories = db.list_active_income_categories(callback.from_user.id)
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    keyboard_builder = income_categories_select_keyboard
    back_callback = "st:income"
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Какой категории меняем процент?",
        reply_markup=keyboard_builder(categories, f"{scope[:3]}:pct", back_callback=back_callback),
    )


@router.callback_query(F.data.startswith("inc:pct:"))
async def category_percent_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return

    db = FinanceDatabase()
    scope = "income"
    category = db.get_income_category_by_id(callback.from_user.id, category_id)
    if not category:
        await _render_income_settings(
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


@router.callback_query(F.data == "wl:edit_purchased_days")
async def wishlist_edit_purchased_days(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(WishlistSettingsState.waiting_for_purchased_days)
    db = FinanceDatabase()
    settings_row = db.get_user_settings(callback.from_user.id)
    await state.update_data(purchased_days_str="0", previous_purchased_days=settings_row.get("purchased_keep_days", 30))
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text='На сколько дней показывать "Купленное"?',
        reply_markup=None,
    )
    prompt = await callback.message.answer(": 0", reply_markup=income_calculator_keyboard())
    await state.update_data(
        purchased_display_chat_id=prompt.chat.id,
        purchased_display_message_id=prompt.message_id,
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

        LOGGER.info(
            "Percent saved: user=%s scope=%s category_id=%s value=%s",
            message.from_user.id,
            "income",
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
        await _render_income_settings(
            state=state, message=message, db=db, user_id=message.from_user.id
        )


@router.message(WishlistSettingsState.waiting_for_purchased_days)
async def wishlist_purchased_days_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (message.text or "").strip()
    if text not in PERCENT_INPUT_BUTTONS:
        await message.answer("Используй кнопки калькулятора.")
        return

    days_str = data.get("purchased_days_str", "0")
    display_chat_id = data.get("purchased_display_chat_id", message.chat.id)
    display_message_id = data.get("purchased_display_message_id")

    if text in PERCENT_DIGITS:
        days_str = days_str.lstrip("0") if days_str != "0" else ""
        days_str = f"{days_str}{text}" or "0"
        try:
            await message.bot.edit_message_text(
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {days_str}",
            )
        except Exception:
            fallback = await message.bot.send_message(chat_id=display_chat_id, text=f": {days_str}")
            display_message_id = fallback.message_id
        await state.update_data(
            purchased_days_str=days_str,
            purchased_display_chat_id=display_chat_id,
            purchased_display_message_id=display_message_id,
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    if text == "Очистить":
        days_str = "0"
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
            purchased_days_str=days_str,
            purchased_display_chat_id=display_chat_id,
            purchased_display_message_id=display_message_id,
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    if text == "✅ Газ":
        try:
            days = int(days_str or "0")
        except ValueError:
            await message.answer("Нужно ввести число дней.")
            return
        if days < 1 or days > 365:
            await message.answer("Количество дней должно быть от 1 до 365.")
            return

        db = FinanceDatabase()
        db.update_purchased_keep_days(message.from_user.id, days)
        display_message_id = data.get("purchased_display_message_id")
        if display_message_id:
            try:
                await message.bot.delete_message(
                    chat_id=data.get("purchased_display_chat_id", message.chat.id),
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
    await _render_wishlist_settings(
        state=state, message=message, db=db, user_id=message.from_user.id
    )


@router.message(BytSettingsState.waiting_for_max_defer_days)
async def byt_max_defer_days_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (message.text or "").strip()
    if text not in PERCENT_INPUT_BUTTONS:
        await message.answer("Используй кнопки калькулятора.")
        return

    days_str = data.get("byt_max_days_str", "0")
    display_chat_id = data.get("byt_max_display_chat_id", message.chat.id)
    display_message_id = data.get("byt_max_display_message_id")

    if text in PERCENT_DIGITS:
        days_str = days_str.lstrip("0") if days_str != "0" else ""
        days_str = f"{days_str}{text}" or "0"
        try:
            await message.bot.edit_message_text(
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {days_str}",
            )
        except Exception:
            fallback = await message.bot.send_message(chat_id=display_chat_id, text=f": {days_str}")
            display_message_id = fallback.message_id
        await state.update_data(
            byt_max_days_str=days_str,
            byt_max_display_chat_id=display_chat_id,
            byt_max_display_message_id=display_message_id,
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    if text == "Очистить":
        days_str = "0"
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
            byt_max_days_str=days_str,
            byt_max_display_chat_id=display_chat_id,
            byt_max_display_message_id=display_message_id,
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    if text == "✅ Газ":
        try:
            days = int(days_str or "0")
        except ValueError:
            await message.answer("Нужно ввести число дней.")
            return
        if days < 1 or days > 3650:
            await message.answer("Количество дней должно быть от 1 до 3650.")
            return

        db = FinanceDatabase()
        db.set_byt_defer_max_days(message.from_user.id, days)
        display_message_id = data.get("byt_max_display_message_id")
        if display_message_id:
            try:
                await message.bot.delete_message(
                    chat_id=data.get("byt_max_display_chat_id", message.chat.id),
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
        await _render_byt_rules_settings(
            state=state, message=message, db=db, user_id=message.from_user.id
        )


@router.message(BytTimerState.waiting_for_hour, F.text.in_(PERCENT_INPUT_BUTTONS))
async def byt_timer_hour_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (message.text or "").strip()
    hour_str = data.get("bt_hour_str", "0")
    display_chat_id = data.get("bt_hour_display_chat_id", message.chat.id)
    display_message_id = data.get("bt_hour_display_message_id")

    if text in PERCENT_DIGITS:
        hour_str = hour_str.lstrip("0") if hour_str != "0" else ""
        hour_str = f"{hour_str}{text}" or "0"
        try:
            await message.bot.edit_message_text(
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {hour_str}",
            )
        except Exception:
            prompt = await message.bot.send_message(chat_id=display_chat_id, text=f": {hour_str}")
            display_message_id = prompt.message_id
        await state.update_data(
            bt_hour_str=hour_str,
            bt_hour_display_chat_id=display_chat_id,
            bt_hour_display_message_id=display_message_id,
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    if text == "Очистить":
        hour_str = "0"
        try:
            await message.bot.edit_message_text(
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=": 0",
            )
        except Exception:
            prompt = await message.bot.send_message(chat_id=display_chat_id, text=": 0")
            display_message_id = prompt.message_id
        await state.update_data(
            bt_hour_str=hour_str,
            bt_hour_display_chat_id=display_chat_id,
            bt_hour_display_message_id=display_message_id,
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    if text == "✅ Газ":
        try:
            hour = int(hour_str or "0")
        except ValueError:
            await message.answer("Нужно ввести число.")
            return
        if hour < 0 or hour > 23:
            await message.answer("Часы должны быть 0–23.")
            return
        db = FinanceDatabase()
        display_message_id = data.get("bt_hour_display_message_id")
        if display_message_id:
            try:
                await message.bot.delete_message(
                    chat_id=data.get("bt_hour_display_chat_id", message.chat.id),
                    message_id=int(display_message_id),
                )
            except Exception:
                pass
        await state.set_state(BytTimerState.waiting_for_minute)
        await state.update_data(selected_hour=hour, bt_minute_str="0")
        await message.answer("Введи МИНУТЫ (0–59)")
        prompt = await message.answer(": 0", reply_markup=income_calculator_keyboard())
        await state.update_data(
            bt_min_display_chat_id=prompt.chat.id,
            bt_min_display_message_id=prompt.message_id,
        )
        try:
            await message.delete()
        except Exception:
            pass


@router.message(BytTimerState.waiting_for_minute, F.text.in_(PERCENT_INPUT_BUTTONS))
async def byt_timer_minute_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (message.text or "").strip()
    minute_str = data.get("bt_minute_str", "0")
    display_chat_id = data.get("bt_min_display_chat_id", message.chat.id)
    display_message_id = data.get("bt_min_display_message_id")

    if text in PERCENT_DIGITS:
        minute_str = minute_str.lstrip("0") if minute_str != "0" else ""
        minute_str = f"{minute_str}{text}" or "0"
        try:
            await message.bot.edit_message_text(
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {minute_str}",
            )
        except Exception:
            prompt = await message.bot.send_message(chat_id=display_chat_id, text=f": {minute_str}")
            display_message_id = prompt.message_id
        await state.update_data(
            bt_minute_str=minute_str,
            bt_min_display_chat_id=display_chat_id,
            bt_min_display_message_id=display_message_id,
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    if text == "Очистить":
        minute_str = "0"
        try:
            await message.bot.edit_message_text(
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=": 0",
            )
        except Exception:
            prompt = await message.bot.send_message(chat_id=display_chat_id, text=": 0")
            display_message_id = prompt.message_id
        await state.update_data(
            bt_minute_str=minute_str,
            bt_min_display_chat_id=display_chat_id,
            bt_min_display_message_id=display_message_id,
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    if text == "✅ Газ":
        try:
            minute = int(minute_str or "0")
        except ValueError:
            await message.answer("Нужно ввести число.")
            return
        if minute < 0 or minute > 59:
            await message.answer("Минуты должны быть 0–59.")
            return
        db = FinanceDatabase()
        selected_hour = int(data.get("selected_hour", 0))
        db.add_byt_timer_time(message.from_user.id, selected_hour, minute)
        display_message_id = data.get("bt_min_display_message_id")
        if display_message_id:
            try:
                await message.bot.delete_message(
                    chat_id=data.get("bt_min_display_chat_id", message.chat.id),
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
        await _render_byt_timer_settings(
            state=state, message=message, db=db, user_id=message.from_user.id
        )
