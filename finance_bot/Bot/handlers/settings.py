"""Inline settings handlers for a single-page experience."""
import logging
import time

from aiogram import F, Router
from aiogram.filters import BaseFilter
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from Bot.constants.ui_labels import (
    NAV_BACK,
    NAV_HOME,
    WISHLIST_DEBIT_CATEGORY_BACK,
    WISHLIST_DEBIT_CATEGORY_BUTTON,
    WISHLIST_DEBIT_CATEGORY_NONE,
    WISHLIST_BYT_CATEGORY_BUTTON,
)
from Bot.config.settings import get_settings
from Bot.database.get_db import get_db
from Bot.handlers.common import build_main_menu_for_user
from Bot.keyboards.main import back_only_keyboard
from Bot.keyboards.settings import (
    byt_category_toggle_keyboard,
    byt_rules_reply_keyboard,
    byt_timer_categories_inline_keyboard,
    byt_timer_inline_keyboard,
    byt_timer_times_select_keyboard,
    household_debit_category_select_reply_keyboard,
    household_payments_remove_reply_keyboard,
    household_settings_reply_keyboard,
    income_categories_select_reply_keyboard,
    income_settings_reply_keyboard,
    settings_back_reply_keyboard,
    settings_home_reply_keyboard,
    timezone_inline_keyboard,
    wishlist_categories_select_reply_keyboard,
    wishlist_debit_category_select_reply_keyboard,
    wishlist_purchased_mode_reply_keyboard,
    wishlist_settings_reply_keyboard,
)
from Bot.utils.byt_render import format_byt_categories_status_text
from Bot.keyboards.calculator import income_calculator_keyboard
from Bot.states.money_states import HouseholdSettingsState, IncomeSettingsState
from Bot.states.wishlist_states import (
    BytSettingsState,
    BytTimerState,
    WishlistSettingsState,
)
from Bot.utils.datetime_utils import current_month_str
from Bot.utils.messages import ERR_INVALID_INPUT, HINT_TIME_FORMAT
from Bot.utils.number_input import parse_int_choice, parse_positive_int
from Bot.utils.time_input import normalize_time_partial
from Bot.utils.savings import format_savings_summary
from Bot.utils.telegram_safe import (
    safe_delete_message,
    safe_edit_message_text,
    safe_send_message,
)
from Bot.utils.ui_cleanup import (
    ui_cleanup_messages,
    ui_cleanup_to_context,
    ui_register_message,
    ui_render_screen,
    ui_set_screen_message,
    ui_track_message,
)

router = Router()
LOGGER = logging.getLogger(__name__)
DEFAULT_TZ = (
    get_settings().timezone.key
    if hasattr(get_settings().timezone, "key")
    else str(get_settings().timezone)
)
PERCENT_DIGITS = {str(i) for i in range(10)}
PERCENT_INPUT_BUTTONS = PERCENT_DIGITS | {"Очистить", "✅ Газ"}


class InSettingsFilter(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        data = await state.get_data()
        return bool(data.get("in_settings"))


async def _register_user_message(state: FSMContext, message: Message) -> None:
    await ui_track_message(state, message.chat.id, message.message_id)


async def _safe_edit(bot, **kwargs) -> None:
    edited = await safe_edit_message_text(bot, logger=LOGGER, **kwargs)
    if not edited:
        raise TelegramBadRequest(method="editMessageText", message="edit-failed")


async def _delete_message_safely(bot, chat_id: int | None, message_id: int | None) -> None:
    if chat_id is None or message_id is None:
        return
    await safe_delete_message(
        bot,
        chat_id=chat_id,
        message_id=int(message_id),
        logger=LOGGER,
    )


async def _delete_user_message(message: Message) -> None:
    await safe_delete_message(
        message.bot,
        chat_id=message.chat.id,
        message_id=message.message_id,
        logger=LOGGER,
    )


async def _remove_calculator_keyboard(message: Message) -> None:
    temp = await safe_send_message(
        message.bot,
        chat_id=message.chat.id,
        text=" ",
        reply_markup=ReplyKeyboardRemove(),
        logger=LOGGER,
    )
    if temp:
        await safe_delete_message(
            message.bot,
            chat_id=temp.chat.id,
            message_id=temp.message_id,
            logger=LOGGER,
        )


async def _apply_reply_keyboard(message: Message, reply_markup: ReplyKeyboardMarkup) -> None:
    temp = await safe_send_message(
        message.bot,
        chat_id=message.chat.id,
        text=" ",
        reply_markup=reply_markup,
        logger=LOGGER,
    )
    if temp:
        await safe_delete_message(
            message.bot,
            chat_id=temp.chat.id,
            message_id=temp.message_id,
            logger=LOGGER,
        )


async def _cleanup_input_ui(
    bot,
    data: dict,
    *,
    display_chat_key: str | None = None,
    display_message_key: str | None = None,
    prompt_chat_key: str | None = None,
    prompt_message_key: str | None = None,
) -> None:
    if display_chat_key and display_message_key:
        await _delete_message_safely(
            bot, data.get(display_chat_key), data.get(display_message_key)
        )
    if prompt_chat_key and prompt_message_key:
        await _delete_message_safely(
            bot, data.get(prompt_chat_key), data.get(prompt_message_key)
        )


async def _store_settings_message(state: FSMContext, chat_id: int, message_id: int) -> None:
    await state.update_data(
        settings_chat_id=chat_id, settings_message_id=message_id, in_settings=True
    )


async def _set_current_screen(state: FSMContext, screen_id: str) -> None:
    await state.update_data(settings_current_screen=screen_id, in_settings=True)


async def _reset_navigation(state: FSMContext, current_screen: str = "st:home") -> None:
    await state.update_data(settings_nav_stack=[], settings_current_screen=current_screen)


async def _push_current_screen(state: FSMContext, next_screen: str) -> None:
    data = await state.get_data()
    current_screen = data.get("settings_current_screen")
    stack = list(data.get("settings_nav_stack") or [])
    if current_screen and current_screen != next_screen:
        if not stack or stack[-1] != current_screen:
            stack.append(current_screen)
    await state.update_data(settings_nav_stack=stack, settings_current_screen=next_screen)


async def _pop_previous_screen(state: FSMContext) -> str | None:
    data = await state.get_data()
    stack = list(data.get("settings_nav_stack") or [])
    if not stack:
        return None
    previous = stack.pop()
    await state.update_data(settings_nav_stack=stack, settings_current_screen=previous)
    return previous


async def _send_and_register(
    *, message: Message, state: FSMContext, text: str, reply_markup=None
) -> Message:
    sent = await message.answer(text, reply_markup=reply_markup)
    await ui_register_message(state, sent.chat.id, sent.message_id)
    return sent


async def _send_main_menu_summary(
    *, bot, state: FSMContext, chat_id: int, user_id: int
) -> None:
    db = get_db()
    savings = db.get_user_savings(user_id)
    categories_map = db.get_income_categories_map(user_id)
    summary = format_savings_summary(savings, categories_map)
    text = f"Текущие накопления:\n{summary}"
    menu = await build_main_menu_for_user(user_id)
    sent = await safe_send_message(bot, chat_id=chat_id, text=text, reply_markup=menu)
    if sent:
        await ui_register_message(state, sent.chat.id, sent.message_id)


async def _exit_settings_to_main(
    *, bot, state: FSMContext, chat_id: int, user_id: int
) -> None:
    await ui_cleanup_messages(bot, state, chat_id=chat_id)
    await state.clear()
    await ui_render_screen(
        bot,
        state,
        chat_id,
        "Главное меню",
        reply_markup=await build_main_menu_for_user(user_id),
    )


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
        data = await state.get_data()
        if data.get("settings_current_screen") in {"st:income", "st:wishlist", "st:byt_rules"}:
            raise TelegramBadRequest(method="editMessageText", message="reply-only")
        await _safe_edit(
            bot,
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
        )
        new_message_id = message_id
    except TelegramBadRequest:
        new_message = await safe_send_message(
            bot,
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            logger=LOGGER,
        )
        new_message_id = new_message.message_id if new_message else message_id
        await ui_register_message(state, chat_id, new_message_id)
    await ui_set_screen_message(state, chat_id, new_message_id)
    await _store_settings_message(state, chat_id, new_message_id)
    return new_message_id


async def _render_reply_settings_page(
    *,
    message: Message,
    state: FSMContext,
    text: str,
    reply_markup: ReplyKeyboardMarkup,
    screen_id: str,
    force_new: bool = False,
) -> None:
    data = await state.get_data()
    chat_id = data.get("settings_chat_id")
    message_id = data.get("settings_message_id")
    current_screen = data.get("settings_current_screen")

    deleted_count = 0
    if force_new or not chat_id or not message_id or current_screen != screen_id:
        await _delete_message_safely(message.bot, chat_id, message_id)
        if message_id:
            deleted_count = 1
    sent = await safe_send_message(
        message.bot,
        chat_id=message.chat.id,
        text=text,
        reply_markup=reply_markup,
    )
    new_message_id = sent.message_id if sent else 0
    if sent:
        await ui_register_message(state, sent.chat.id, sent.message_id)
        await ui_set_screen_message(state, sent.chat.id, sent.message_id)
        await _store_settings_message(state, sent.chat.id, sent.message_id)
    await _set_current_screen(state, screen_id)
    if deleted_count:
        LOGGER.info(
            "Settings reply screen cleanup: deleted %s messages (screen_id=%s)",
            deleted_count,
            screen_id,
        )


async def _render_settings_home(message: Message, state: FSMContext) -> None:
    await _render_reply_settings_page(
        message=message,
        state=state,
        text="⚙️ НАСТРОЙКИ",
        reply_markup=settings_home_reply_keyboard(),
        screen_id="st:home",
        force_new=True,
    )


async def _render_timezone_settings(
    *,
    state: FSMContext,
    message: Message,
    db,
    user_id: int,
    error_message: str | None = None,
) -> None:
    tz_value = get_user_timezone(db, user_id, DEFAULT_TZ)
    lines = [
        "Настройки таймзоны",
        f"Текущая таймзона: {tz_value}",
        "Выбери новую таймзону:",
    ]
    if error_message:
        lines.append("")
        lines.append(error_message)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="\n".join(lines),
        reply_markup=timezone_inline_keyboard(),
    )


def _format_household_payments_text(
    items: list[dict],
    *,
    unpaid_set: set[str],
    debit_category: str,
    error_message: str | None = None,
) -> str:
    lines: list[str] = [
        "РЕЖИМ НАСТРОЕК",
        "",
        "Бытовые платежи",
        f"Категория списания: {debit_category}",
        "",
    ]
    if not items:
        lines.append("Платежей пока нет. Нажми ➕ Добавить")
    else:
        for item in items:
            title = str(item.get("text", "")).rstrip("?")
            amount = item.get("amount")
            prefix = "❌" if item.get("code") in unpaid_set else "✅"
            if amount not in (None, 0):
                lines.append(f"{prefix} {title} — {amount}")
            else:
                lines.append(f"{prefix} {title}")
    if error_message:
        lines.extend(["", error_message])
    return "\n".join(lines)


async def _render_household_payments_settings(
    *,
    state: FSMContext,
    message: Message,
    db,
    user_id: int,
    error_message: str | None = None,
    force_new_keyboard: bool = False,
) -> None:
    items = db.list_active_household_items(user_id)
    month = current_month_str(now_for_user(db, user_id, DEFAULT_TZ))
    await db.init_household_questions_for_month(user_id, month)
    unpaid = await db.get_unpaid_household_questions(user_id, month)
    unpaid_set: set[str] = set(unpaid)
    debit_code, debit_title = db.resolve_household_debit_category(user_id)
    LOGGER.info(
        "Open household payments settings (user_id=%s, month=%s, items_count=%s, unpaid_count=%s)",
        user_id,
        month,
        len(items),
        len(unpaid_set),
    )
    await _render_reply_settings_page(
        message=message,
        state=state,
        text=_format_household_payments_text(
            items,
            unpaid_set=unpaid_set,
            debit_category=debit_title or debit_code,
            error_message=error_message,
        ),
        reply_markup=household_settings_reply_keyboard(),
        screen_id="st:household_payments",
        force_new=True,
    )


async def _render_household_delete_menu(
    *, state: FSMContext, message: Message, db, user_id: int
) -> None:
    items = db.list_active_household_items(user_id)
    await _render_reply_settings_page(
        message=message,
        state=state,
        text="Что удалить?" if items else "Активных платежей нет.",
        reply_markup=household_payments_remove_reply_keyboard(items)
        if items
        else household_settings_reply_keyboard(),
        screen_id="hp:del_payment_menu",
        force_new=True,
    )
    await state.update_data(
        hp_delete_map={
            (f"{str(item.get('text', ''))}".rstrip("?")
             + (f" — {item.get('amount')}" if item.get("amount") is not None else "")
            ): item.get("code")
            for item in items
        }
    )
    if items:
        await state.set_state(HouseholdSettingsState.waiting_for_removal)


async def _render_household_debit_category_menu(
    *, state: FSMContext, message: Message, db, user_id: int, error_message: str | None = None
) -> None:
    categories = db.list_active_income_categories(user_id)
    if categories:
        text = "Выбери категорию списания"
        if error_message:
            text = f"{error_message}\n\n{text}"
    else:
        text = "Категорий дохода пока нет."
    await _render_reply_settings_page(
        message=message,
        state=state,
        text=text,
        reply_markup=household_debit_category_select_reply_keyboard(categories)
        if categories
        else household_settings_reply_keyboard(),
        screen_id="hp:debit_category_menu",
        force_new=True,
    )
    await state.update_data(
        hp_debit_map={category.get("title", ""): category.get("code") for category in categories}
    )
    if categories:
        await state.set_state(HouseholdSettingsState.waiting_for_debit_category)


async def _render_wishlist_debit_category_menu(
    *, state: FSMContext, message: Message, db, user_id: int, error_message: str | None = None
) -> None:
    categories = db.list_active_income_categories(user_id)
    selected = db.get_wishlist_debit_category(user_id)
    selected_title = "Не выбрано"
    if selected:
        income_category = db.get_income_category_by_code(user_id, selected)
        selected_title = income_category.get("title", selected) if income_category else "Категория удалена"
    if categories:
        text = (
            "Категория списания для покупок (Wishlist)\n"
            f"Текущая: {selected_title}\n\n"
            "Выбери категорию списания"
        )
        if error_message:
            text = f"{error_message}\n\n{text}"
    else:
        text = "Сначала добавь категории доходов/накоплений."
    LOGGER.info("USER=%s ACTION=WISHLIST_DEBIT_CATEGORY_MENU_OPEN", user_id)
    await _render_reply_settings_page(
        message=message,
        state=state,
        text=text,
        reply_markup=wishlist_debit_category_select_reply_keyboard(categories)
        if categories
        else back_only_keyboard(),
        screen_id="wl:debit_category_menu",
        force_new=True,
    )
    await state.update_data(
        wl_debit_map={category.get("title", ""): category.get("code") for category in categories}
    )
    if categories:
        await state.set_state(WishlistSettingsState.waiting_for_debit_category)


async def _render_wishlist_byt_category_menu(
    *,
    state: FSMContext,
    message: Message,
    db,
    user_id: int,
    error_message: str | None = None,
) -> None:
    categories = db.list_byt_reminder_categories(user_id)
    if categories:
        lines = ["Выбор категорий для напоминаний:", ""]
        for category in categories:
            status = "✅" if category.get("enabled") else "❌"
            lines.append(f"{status} {category.get('title', '')}")
        text = "\n".join(lines)
        if error_message:
            text = f"{error_message}\n\n{text}"
    else:
        text = "Категорий пока нет."
    LOGGER.info("USER=%s ACTION=BYT_CATEGORY_MENU_OPEN", user_id)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=byt_category_toggle_keyboard(categories)
        if categories
        else back_only_keyboard(),
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
    categories: list[dict],
    debit_category_title: str,
    error_message: str | None = None,
) -> str:
    lines: list[str] = ["🧾 ВИШЛИСТ — настройки", "", "Категории:", ""]
    if categories:
        for category in categories:
            mode = str(category.get("purchased_mode") or "days")
            days = int(category.get("purchased_days") or 30)
            if mode == "always":
                display = "Всегда"
            else:
                display = f"{days} дней"
            lines.append(f"{category.get('title', '')} — Купленное: {display}")
    lines.extend(
        [
            "",
            f"Категория списания: {debit_category_title}",
        ]
    )
    if error_message:
        lines.append("")
        lines.append(error_message)
    return "\n".join(lines)


def _format_byt_rules_text(
    settings: dict,
    categories: list[dict],
    error_message: str | None = None,
) -> str:
    on_off = {True: "ДА", False: "НЕТ", 1: "ДА", 0: "НЕТ"}
    lines = [
        "🔔 Напоминания — условия",
        "",
        format_byt_categories_status_text(categories),
        f"Напоминания включены: {on_off.get(settings.get('byt_reminders_enabled', 1), 'НЕТ')}",
        "Слать если список пуст: НЕТ",
        'Формат: "Что ты купил?" (кнопки-товары)',
        f"ОТЛОЖИТЬ: {on_off.get(settings.get('byt_defer_enabled', 1), 'НЕТ')}",
        f"Макс. дней отложить: {settings.get('byt_defer_max_days', 365)}",
        "",
        "Время напоминаний настраивается по категориям.",
    ]
    if error_message:
        lines.append("")
        lines.append(error_message)
    return "\n".join(lines)


def _format_byt_timer_menu_text(
    categories: list[dict], error_message: str | None = None
) -> str:
    lines = ["⏰ Время напоминаний", "", "Выбери категорию, затем выбери время(я)."]
    if not categories:
        lines.append("")
        lines.append("Категорий пока нет.")
    if error_message:
        lines.append("")
        lines.append(error_message)
    return "\n".join(lines)


def _format_byt_timer_category_text(
    category_title: str, times: list[dict], error_message: str | None = None
) -> str:
    lines = [
        "⏰ Время напоминаний",
        "",
        f"Категория: {category_title}",
        "",
        "Текущие времена:",
        "",
    ]
    if times:
        for timer in times:
            if timer.get("time_hhmm"):
                lines.append(str(timer.get("time_hhmm")))
            else:
                lines.append(
                    f"{int(timer.get('hour', 0)):02d}:{int(timer.get('minute', 0)):02d}"
                )
    else:
        lines.append("Время не задано")
    if error_message:
        lines.append("")
        lines.append(error_message)
    return "\n".join(lines)


async def _render_income_settings(
    *,
    state: FSMContext,
    message: Message,
    db,
    user_id: int,
    error_message: str | None = None,
) -> list[dict]:
    categories = db.list_active_income_categories(user_id)
    LOGGER.info("Open income settings (reply mode) user_id=%s", user_id)
    await _render_reply_settings_page(
        message=message,
        state=state,
        text=_format_category_text(
            "📊 ДОХОД — категории и проценты", categories, error_message
        ),
        reply_markup=income_settings_reply_keyboard(),
        screen_id="st:income",
    )
    return categories


async def _render_wishlist_settings(
    *,
    state: FSMContext,
    message: Message,
    db,
    user_id: int,
    error_message: str | None = None,
) -> list[dict]:
    categories = db.list_active_wishlist_categories(user_id)
    debit_category = db.get_wishlist_debit_category(user_id)
    debit_title = "Не выбрано"
    if debit_category:
        income_category = db.get_income_category_by_code(user_id, debit_category)
        debit_title = income_category.get("title", debit_category) if income_category else "Категория удалена"
    LOGGER.info("Open wishlist settings (reply mode) user_id=%s", user_id)
    LOGGER.info("USER=%s ACTION=WISHLIST_SETTINGS_OPEN", user_id)
    await _render_reply_settings_page(
        message=message,
        state=state,
        text=_format_wishlist_text(categories, debit_title, error_message),
        reply_markup=wishlist_settings_reply_keyboard(),
        screen_id="st:wishlist",
    )
    return categories


async def _render_byt_rules_settings(
    *,
    state: FSMContext,
    message: Message,
    db,
    user_id: int,
    error_message: str | None = None,
) -> dict:
    db.ensure_user_settings(user_id)
    settings_row = db.get_user_settings(user_id)
    categories = db.list_byt_reminder_categories(user_id)
    LOGGER.info("Open byt conditions settings (reply mode) user_id=%s", user_id)
    await _render_reply_settings_page(
        message=message,
        state=state,
        text=_format_byt_rules_text(settings_row, categories, error_message),
        reply_markup=byt_rules_reply_keyboard(),
        screen_id="st:byt_rules",
    )
    return settings_row


async def _render_byt_timer_settings(
    *,
    state: FSMContext,
    message: Message,
    db,
    user_id: int,
    error_message: str | None = None,
) -> list[dict]:
    categories = db.list_byt_reminder_categories(user_id)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=_format_byt_timer_menu_text(categories, error_message),
        reply_markup=byt_timer_categories_inline_keyboard(
            categories, "byt:timer_category"
        )
        if categories
        else InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=NAV_BACK, callback_data="st:byt_rules"),
                    InlineKeyboardButton(text=NAV_HOME, callback_data="nav:home"),
                ]
            ]
        ),
    )
    return categories


async def _render_byt_timer_category_settings(
    *,
    state: FSMContext,
    message: Message,
    db,
    user_id: int,
    category_id: int,
    error_message: str | None = None,
) -> list[dict]:
    category = db.get_wishlist_category_by_id(user_id, category_id)
    category_title = category.get("title") if category else "категория"
    times = db.list_byt_reminder_times(user_id, category_id)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=_format_byt_timer_category_text(category_title, times, error_message),
        reply_markup=byt_timer_inline_keyboard(),
    )
    return times


async def _render_income_delete_menu(
    *, state: FSMContext, message: Message, db, user_id: int
) -> None:
    categories = db.list_active_income_categories(user_id)
    await _render_reply_settings_page(
        message=message,
        state=state,
        text="Что удалить?" if categories else "Категорий пока нет.",
        reply_markup=income_categories_select_reply_keyboard(categories)
        if categories
        else income_settings_reply_keyboard(),
        screen_id="inc:del_menu",
        force_new=True,
    )
    await state.update_data(
        inc_delete_map={
            f"{category.get('title', '')} — {category.get('percent', 0)}%": category.get(
                "id"
            )
            for category in categories
        }
    )
    if categories:
        await state.set_state(IncomeSettingsState.waiting_for_removal)


async def _render_income_percent_menu(
    *,
    state: FSMContext,
    message: Message,
    db,
    user_id: int,
    error_message: str | None = None,
) -> None:
    categories = db.list_active_income_categories(user_id)
    if categories:
        text = "Какой категории меняем процент?"
        if error_message:
            text = f"{error_message}\n\n{text}"
    else:
        text = "Категорий пока нет."
    await _render_reply_settings_page(
        message=message,
        state=state,
        text=text,
        reply_markup=income_categories_select_reply_keyboard(categories)
        if categories
        else income_settings_reply_keyboard(),
        screen_id="inc:pct_menu",
        force_new=True,
    )
    await state.update_data(
        inc_percent_map={
            f"{category.get('title', '')} — {category.get('percent', 0)}%": category.get(
                "id"
            )
            for category in categories
        }
    )
    if categories:
        await state.set_state(IncomeSettingsState.waiting_for_percent_category)


async def _render_wishlist_delete_menu(
    *, state: FSMContext, message: Message, db, user_id: int
) -> None:
    categories = db.list_active_wishlist_categories(user_id)
    await _render_reply_settings_page(
        message=message,
        state=state,
        text="Что удалить?" if categories else "Категорий пока нет.",
        reply_markup=wishlist_categories_select_reply_keyboard(categories)
        if categories
        else wishlist_settings_reply_keyboard(),
        screen_id="wl:del_cat_menu",
        force_new=True,
    )
    await state.update_data(
        wl_delete_map={category.get("title", ""): category.get("id") for category in categories}
    )
    if categories:
        await state.set_state(WishlistSettingsState.waiting_for_removal)


async def _render_wishlist_purchased_select_menu(
    *, state: FSMContext, message: Message, db, user_id: int
) -> None:
    categories = db.list_active_wishlist_categories(user_id)
    await _render_reply_settings_page(
        message=message,
        state=state,
        text="Выбери категорию вишлиста для настройки срока купленного"
        if categories
        else "Категорий пока нет.",
        reply_markup=wishlist_categories_select_reply_keyboard(categories)
        if categories
        else wishlist_settings_reply_keyboard(),
        screen_id="wl:purchased_select_category",
        force_new=True,
    )
    await state.update_data(
        wl_purchased_map={
            category.get("title", ""): category.get("id") for category in categories
        }
    )
    if categories:
        await state.set_state(WishlistSettingsState.waiting_for_purchased_category)


async def _render_wishlist_purchased_mode(
    *,
    state: FSMContext,
    message: Message,
    db,
    user_id: int,
    category_id: int,
) -> None:
    category = db.get_wishlist_category_by_id(user_id, category_id)
    await state.set_state(WishlistSettingsState.waiting_for_purchased_mode)
    await _render_reply_settings_page(
        message=message,
        state=state,
        text=(
            f'⏳ Купленное — "{category.get("title", "")}"\nКак показывать купленное?'
        ),
        reply_markup=wishlist_purchased_mode_reply_keyboard(),
        screen_id="wl:purchased_mode",
        force_new=True,
    )


async def _render_byt_timer_delete_menu(
    *, state: FSMContext, message: Message, db, user_id: int
) -> None:
    data = await state.get_data()
    category_id = data.get("byt_timer_category_id")
    if category_id is None:
        await _render_byt_timer_settings(
            state=state, message=message, db=db, user_id=user_id
        )
        return
    times = db.list_byt_reminder_times(user_id, int(category_id))
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Что удалить?" if times else "Времена пока не заданы.",
        reply_markup=byt_timer_times_select_keyboard(times, "bt:del_time")
        if times
        else byt_timer_inline_keyboard(),
    )


async def render_settings_screen(
    screen_id: str,
    *,
    message: Message,
    state: FSMContext,
    error_message: str | None = None,
    force_new: bool = False,
) -> None:
    db = get_db()
    data = await state.get_data()
    user_id = message.from_user.id
    if message.from_user.id == message.bot.id:
        user_id = data.get("settings_user_id") or message.from_user.id
    if screen_id == "st:home":
        await _render_settings_home(message, state)
    elif screen_id == "st:timezone":
        await _render_timezone_settings(
            state=state,
            message=message,
            db=db,
            user_id=user_id,
            error_message=error_message,
        )
    elif screen_id == "st:income":
        await _render_income_settings(
            state=state,
            message=message,
            db=db,
            user_id=user_id,
            error_message=error_message,
        )
    elif screen_id == "inc:del_menu":
        await _render_income_delete_menu(
            state=state, message=message, db=db, user_id=user_id
        )
    elif screen_id == "inc:pct_menu":
        await _render_income_percent_menu(
            state=state,
            message=message,
            db=db,
            user_id=user_id,
            error_message=error_message,
        )
    elif screen_id == "st:wishlist":
        await _render_wishlist_settings(
            state=state,
            message=message,
            db=db,
            user_id=user_id,
            error_message=error_message,
        )
    elif screen_id == "st:household_payments":
        await _render_household_payments_settings(
            state=state,
            message=message,
            db=db,
            user_id=user_id,
            error_message=error_message,
            force_new_keyboard=force_new,
        )
    elif screen_id == "wl:del_cat_menu":
        await _render_wishlist_delete_menu(
            state=state, message=message, db=db, user_id=user_id
        )
    elif screen_id == "wl:purchased_select_category":
        await _render_wishlist_purchased_select_menu(
            state=state, message=message, db=db, user_id=user_id
        )
    elif screen_id == "wl:purchased_mode":
        data = await state.get_data()
        category_id = data.get("editing_wl_category_id")
        if category_id is not None:
            await _render_wishlist_purchased_mode(
                state=state,
                message=message,
                db=db,
                user_id=user_id,
                category_id=int(category_id),
            )
        else:
            await _render_wishlist_settings(
                state=state,
                message=message,
                db=db,
                user_id=user_id,
            )
    elif screen_id == "wl:debit_category_menu":
        await _render_wishlist_debit_category_menu(
            state=state,
            message=message,
            db=db,
            user_id=user_id,
            error_message=error_message,
        )
    elif screen_id == "wl:byt_category_menu":
        await _render_wishlist_byt_category_menu(
            state=state,
            message=message,
            db=db,
            user_id=user_id,
            error_message=error_message,
        )
    elif screen_id == "st:byt_rules":
        await _render_byt_rules_settings(
            state=state,
            message=message,
            db=db,
            user_id=user_id,
            error_message=error_message,
        )
    elif screen_id == "byt:timer_menu":
        await _render_byt_timer_settings(
            state=state,
            message=message,
            db=db,
            user_id=user_id,
            error_message=error_message,
        )
    elif screen_id == "byt:timer_category":
        data = await state.get_data()
        category_id = data.get("byt_timer_category_id")
        if category_id is not None:
            await _render_byt_timer_category_settings(
                state=state,
                message=message,
                db=db,
                user_id=user_id,
                category_id=int(category_id),
                error_message=error_message,
            )
        else:
            await _render_byt_timer_settings(
                state=state,
                message=message,
                db=db,
                user_id=user_id,
                error_message=error_message,
            )
    elif screen_id == "bt:del_time_menu":
        await _render_byt_timer_delete_menu(
            state=state, message=message, db=db, user_id=user_id
        )
    elif screen_id == "hp:del_payment_menu":
        await _render_household_delete_menu(
            state=state, message=message, db=db, user_id=user_id
        )
    elif screen_id == "hp:debit_category_menu":
        await _render_household_debit_category_menu(
            state=state,
            message=message,
            db=db,
            user_id=user_id,
            error_message=error_message,
        )
    else:
        await _render_settings_home(message, state)
    await _set_current_screen(state, screen_id)


async def _navigate_to_screen(
    screen_id: str,
    *,
    message: Message,
    state: FSMContext,
    error_message: str | None = None,
    force_new: bool = False,
) -> None:
    await _push_current_screen(state, screen_id)
    await render_settings_screen(
        screen_id,
        message=message,
        state=state,
        error_message=error_message,
        force_new=force_new,
    )


async def _render_previous_screen_or_exit(
    message: Message, state: FSMContext
) -> None:
    previous = await _pop_previous_screen(state)
    if previous:
        await render_settings_screen(previous, message=message, state=state)
    else:
        await _exit_settings_to_main(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )


async def handle_settings_back_action(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    data = await state.get_data()

    await _register_user_message(state, message)
    await _delete_user_message(message)

    numeric_cleanup_map = {
        IncomeSettingsState.waiting_for_percent.state: {
            "display_chat_key": "percent_display_chat_id",
            "display_message_key": "percent_display_message_id",
        },
        IncomeSettingsState.waiting_for_new_category_percent.state: {
            "display_chat_key": "new_income_display_chat_id",
            "display_message_key": "new_income_display_message_id",
        },
        WishlistSettingsState.waiting_for_purchased_days.state: {
            "display_chat_key": "purchased_display_chat_id",
            "display_message_key": "purchased_display_message_id",
        },
        HouseholdSettingsState.waiting_for_amount.state: {
            "display_chat_key": "hp_amount_display_chat_id",
            "display_message_key": "hp_amount_display_message_id",
        },
        BytSettingsState.waiting_for_max_defer_days.state: {
            "display_chat_key": "byt_max_display_chat_id",
            "display_message_key": "byt_max_display_message_id",
        },
    }

    cleanup_params = numeric_cleanup_map.get(current_state)
    if cleanup_params:
        await _cleanup_input_ui(message.bot, data, **cleanup_params)
        await _remove_calculator_keyboard(message)
        await state.set_state(None)
        await _render_previous_screen_or_exit(message, state)
        return

    await state.set_state(None)
    await _render_previous_screen_or_exit(message, state)


@router.message(F.text == "⚙️")
async def open_settings(message: Message, state: FSMContext) -> None:
    """Open settings entry point with inline navigation."""

    await ui_track_message(state, message.chat.id, message.message_id)
    await _delete_user_message(message)
    await ui_cleanup_to_context(message.bot, state, message.chat.id, "SETTINGS_MENU")
    await state.update_data(settings_user_id=message.from_user.id)
    screen_id = await ui_render_screen(
        message.bot,
        state,
        message.chat.id,
        "⚙️ НАСТРОЙКИ",
        reply_markup=settings_home_reply_keyboard(),
    )
    await _store_settings_message(state, message.chat.id, screen_id)
    await _set_current_screen(state, "st:home")
    await _reset_navigation(state)


@router.callback_query(F.data == "st:home")
async def back_to_settings_home(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _reset_navigation(state)
    await render_settings_screen("st:home", message=callback.message, state=state)


@router.message(F.text == "⚙️ НАСТРОЙКИ")
async def back_to_settings_home_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("in_settings"):
        return
    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    await _reset_navigation(state)
    await render_settings_screen("st:home", message=message, state=state)


@router.callback_query(F.data == "st:income")
async def open_income_settings(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _navigate_to_screen("st:income", message=callback.message, state=state)


@router.message(F.text == "📊 Доход")
async def open_income_settings_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("in_settings"):
        return
    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    await _navigate_to_screen("st:income", message=message, state=state)


@router.callback_query(F.data == "st:timezone")
async def open_timezone_settings(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _navigate_to_screen("st:timezone", message=callback.message, state=state)


@router.message(F.text == "Таймзона")
async def open_timezone_settings_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("in_settings"):
        return
    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    await _navigate_to_screen("st:timezone", message=message, state=state)


@router.callback_query(F.data.startswith("st:tz:"))
async def update_timezone(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.message:
        return
    tz_value = callback.data.split("st:tz:", maxsplit=1)[-1]
    db = get_db()
    set_user_timezone(db, callback.from_user.id, tz_value, DEFAULT_TZ)
    await render_settings_screen("st:timezone", message=callback.message, state=state)


@router.message(F.text.in_({NAV_BACK, "Назад", "⬅ Назад", "⬅️ Назад", "⏪ Назад"}))
async def settings_exit_via_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("in_settings"):
        return
    await handle_settings_back_action(message, state)


@router.callback_query(F.data == "st:wishlist")
async def open_wishlist(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _navigate_to_screen("st:wishlist", message=callback.message, state=state)


@router.message(F.text == "🧾 Вишлист")
async def open_wishlist_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("in_settings"):
        return
    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    await _navigate_to_screen("st:wishlist", message=message, state=state)


@router.callback_query(F.data == "st:household_payments")
async def open_household_payments(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _navigate_to_screen(
        "st:household_payments", message=callback.message, state=state, force_new=True
    )


@router.message(F.text == "🧾 Бытовые платежи")
async def open_household_payments_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("in_settings"):
        return
    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    await _navigate_to_screen(
        "st:household_payments", message=message, state=state, force_new=True
    )


@router.message(F.text == "Напоминания")
async def open_byt_rules_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("in_settings"):
        return
    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    await _navigate_to_screen("st:byt_rules", message=message, state=state)


@router.message(F.text == "➕ Добавить")
async def household_payment_add_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") != "st:household_payments":
        return
    await _register_user_message(state, message)
    await _delete_user_message(message)
    await _push_current_screen(state, "hp:add_payment")
    await state.set_state(HouseholdSettingsState.waiting_for_title)
    await state.update_data(hp_amount_str="0", hp_new_title=None)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Напиши платёж",
        reply_markup=back_only_keyboard(),
    )


@router.message(F.text == "➖ Удалить")
async def household_payment_delete_menu_reply(
    message: Message, state: FSMContext
) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") != "st:household_payments":
        return
    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    await _navigate_to_screen(
        "hp:del_payment_menu", message=message, state=state, force_new=True
    )


@router.message(F.text == "💰 Категория списания")
async def household_debit_category_menu_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") != "st:household_payments":
        return
    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    await _navigate_to_screen(
        "hp:debit_category_menu", message=message, state=state, force_new=True
    )


@router.message(F.text == "🧹 Обнулить")
async def household_reset_questions_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") != "st:household_payments":
        return
    await _register_user_message(state, message)
    await _delete_user_message(message)
    db = get_db()
    month = current_month_str(now_for_user(db, message.from_user.id, DEFAULT_TZ))
    await db.reset_household_questions_for_month(message.from_user.id, month)
    LOGGER.info(
        "Reset household payment statuses (user_id=%s, month=%s)",
        message.from_user.id,
        month,
    )
    await render_settings_screen(
        "st:household_payments", message=message, state=state, force_new=False
    )


@router.message(F.text == "🔄 Обновить")
async def household_refresh_questions_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") != "st:household_payments":
        return
    await _register_user_message(state, message)
    await _delete_user_message(message)
    await _send_and_register(
        message=message,
        state=state,
        text="Эта кнопка устарела. Открой настройки заново.",
    )
    await render_settings_screen(
        "st:household_payments", message=message, state=state, force_new=False
    )


@router.message(
    InSettingsFilter(),
    F.text.in_(
        {
            "➕",
            "➕ Добавить категорию дохода",
            "➕ Добавить категорию вишлиста",
            "➕ Добавить время напоминания",
        }
    ),
)
async def settings_add_action_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("in_settings"):
        return
    screen = data.get("settings_current_screen")
    if screen not in {"st:income", "st:wishlist", "st:byt_rules"}:
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)

    if screen == "st:income":
        await _push_current_screen(state, "inc:add_category")
        await state.set_state(IncomeSettingsState.waiting_for_category_title)
        prompt = "Название новой категории дохода?"
        next_screen = "inc:add_category"
    elif screen == "st:wishlist":
        await _push_current_screen(state, "wl:add_category")
        await state.set_state(WishlistSettingsState.waiting_for_category_title)
        prompt = "Название новой категории вишлиста?"
        next_screen = "wl:add_category"
    else:
        await _push_current_screen(state, "bt:add_time_text")
        await state.set_state(BytTimerState.waiting_for_time_add)
        prompt = "Введи время в формате ЧЧ:ММ (например 12:00)"
        next_screen = "bt:add_time_text"

    await _render_reply_settings_page(
        message=message,
        state=state,
        text=prompt,
        reply_markup=back_only_keyboard(),
        screen_id=next_screen,
        force_new=True,
    )


@router.message(
    InSettingsFilter(),
    F.text.in_(
        {
            "➖",
            "➖ Удалить категорию дохода",
            "➖ Удалить категорию вишлиста",
            "➖ Удалить время напоминания",
        }
    ),
)
async def settings_delete_action_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("in_settings"):
        return
    screen = data.get("settings_current_screen")
    if screen not in {"st:income", "st:wishlist", "st:byt_rules"}:
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)

    if screen == "st:income":
        await _navigate_to_screen("inc:del_menu", message=message, state=state, force_new=True)
        return
    if screen == "st:wishlist":
        await _navigate_to_screen("wl:del_cat_menu", message=message, state=state, force_new=True)
        return
    await _navigate_to_screen("bt:del_time_menu", message=message, state=state, force_new=True)


@router.message(F.text.in_({"%", "⚙️ Проценты доходов"}))
async def income_percent_menu_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("in_settings"):
        return
    if data.get("settings_current_screen") != "st:income":
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)

    db = get_db()
    total = db.sum_income_category_percents(message.from_user.id)
    if total == 100:
        await render_settings_screen(
            "st:income",
            message=message,
            state=state,
            error_message="Сумма процентов 100%. ОК.",
        )
        return

    await _navigate_to_screen(
        "inc:pct_menu",
        message=message,
        state=state,
        force_new=True,
        error_message=f"Сумма процентов сейчас {total}%. Нужно 100%.",
    )


@router.message(F.text == "🕒 Настроить купленное")
async def wishlist_purchased_menu_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("in_settings"):
        return
    if data.get("settings_current_screen") != "st:wishlist":
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    await _navigate_to_screen(
        "wl:purchased_select_category", message=message, state=state, force_new=True
    )


@router.message(F.text == WISHLIST_DEBIT_CATEGORY_BUTTON)
async def wishlist_debit_category_menu_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    current_state = await state.get_state()
    LOGGER.info(
        "USER=%s ACTION=WISHLIST_DEBIT_CATEGORY_MENU_CLICK STATE=%s META=current_screen=%s in_settings=%s",
        message.from_user.id,
        current_state,
        data.get("settings_current_screen"),
        data.get("in_settings"),
    )
    if not data.get("in_settings"):
        return
    if data.get("settings_current_screen") != "st:wishlist":
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    await _navigate_to_screen(
        "wl:debit_category_menu", message=message, state=state, force_new=True
    )


@router.message(F.text == WISHLIST_BYT_CATEGORY_BUTTON)
async def wishlist_byt_category_menu_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("in_settings"):
        return
    if data.get("settings_current_screen") != "st:byt_rules":
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    await _navigate_to_screen(
        "wl:byt_category_menu", message=message, state=state, force_new=True
    )


@router.message(F.text == "🔁 Вкл/Выкл напоминания")
async def byt_toggle_enabled_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") != "st:byt_rules":
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    db = get_db()
    settings_row = db.get_user_settings(message.from_user.id)
    current = bool(settings_row.get("byt_reminders_enabled", 1))
    db.set_byt_reminders_enabled(message.from_user.id, not current)
    await render_settings_screen("st:byt_rules", message=message, state=state)


@router.message(F.text == "🔁 ОТЛОЖИТЬ Вкл/Выкл")
async def byt_toggle_defer_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") != "st:byt_rules":
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    db = get_db()
    settings_row = db.get_user_settings(message.from_user.id)
    current = bool(settings_row.get("byt_defer_enabled", 1))
    db.set_byt_defer_enabled(message.from_user.id, not current)
    await render_settings_screen("st:byt_rules", message=message, state=state)


@router.message(F.text == "⏳ Макс. дни отложить")
async def edit_byt_max_defer_days_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") != "st:byt_rules":
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    await _push_current_screen(state, "byt:edit_max_defer_days")
    await state.set_state(BytSettingsState.waiting_for_max_defer_days)
    db = get_db()
    settings_row = db.get_user_settings(message.from_user.id)
    await state.update_data(
        byt_max_days_str="0",
        previous_byt_max_days=settings_row.get("byt_defer_max_days", 365),
    )
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Максимум дней отложки?",
        reply_markup=None,
    )
    prompt = await _send_and_register(
        message=message,
        state=state,
        text=": 0",
        reply_markup=income_calculator_keyboard(),
    )
    await state.update_data(
        byt_max_display_chat_id=prompt.chat.id,
        byt_max_display_message_id=prompt.message_id,
    )


@router.message(F.text.in_({"⏰ Время напоминаний", "⏰ Таймер", "⏱ Таймер"}))
async def open_byt_timer_menu_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") != "st:byt_rules":
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    try:
        LOGGER.info(
            "USER=%s ACTION=BYT_TIMER_MENU_OPEN STATE=%s META=-",
            message.from_user.id,
            await state.get_state(),
        )
        await _navigate_to_screen("byt:timer_menu", message=message, state=state)
    except Exception:  # noqa: BLE001
        LOGGER.error(
            "Failed to open BYT timer menu (reply) user_id=%s",
            message.from_user.id,
            exc_info=True,
        )
        error_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=NAV_BACK, callback_data="st:byt_rules")]
            ]
        )
        await safe_send_message(
            message.bot,
            message.chat.id,
            "⚠️ Не удалось открыть настройки времени напоминаний. Попробуй ещё раз.",
            reply_markup=error_keyboard,
            logger=LOGGER,
        )


@router.message(F.text == "⚙ Условия")
async def open_byt_rules_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") not in {
        "st:byt_rules",
        "byt:timer_menu",
        "byt:timer_category",
        "bt:del_time_menu",
    }:
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    if data.get("settings_current_screen") == "st:byt_rules":
        await render_settings_screen("st:byt_rules", message=message, state=state)
        return
    await _navigate_to_screen("st:byt_rules", message=message, state=state)


@router.message(F.text == "➕ Добавить время")
async def byt_timer_add_time_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") != "byt:timer_category":
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    await _push_current_screen(state, "bt:add_time")
    await state.set_state(BytTimerState.waiting_for_time_add)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Введи время в формате HH:MM",
        reply_markup=None,
    )


@router.message(F.text == "🗑 Удалить время")
async def byt_timer_delete_menu_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") != "byt:timer_category":
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    await state.set_state(None)
    await _navigate_to_screen("bt:del_time_menu", message=message, state=state, force_new=True)


@router.message(F.text == "🔁 Сбросить по умолчанию")
async def byt_timer_reset_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("settings_current_screen") != "byt:timer_menu":
        return

    await _register_user_message(state, message)
    await _delete_user_message(message)
    db = get_db()
    db.reset_byt_timer_times(message.from_user.id)
    await render_settings_screen("byt:timer_menu", message=message, state=state)

@router.callback_query(F.data == "st:byt_rules")
async def open_byt_rules(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _navigate_to_screen("st:byt_rules", message=callback.message, state=state)


@router.callback_query(F.data == "wl:byt_category_menu")
async def open_byt_category_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _navigate_to_screen(
        "wl:byt_category_menu", message=callback.message, state=state, force_new=True
    )


@router.callback_query(F.data == "byt:toggle_enabled")
async def toggle_byt_enabled(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    db = get_db()
    settings_row = db.get_user_settings(callback.from_user.id)
    current = bool(settings_row.get("byt_reminders_enabled", 1))
    db.set_byt_reminders_enabled(callback.from_user.id, not current)
    await render_settings_screen(
        "st:byt_rules", message=callback.message, state=state
    )


@router.callback_query(F.data == "byt:toggle_defer")
async def toggle_byt_defer(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    db = get_db()
    settings_row = db.get_user_settings(callback.from_user.id)
    current = bool(settings_row.get("byt_defer_enabled", 1))
    db.set_byt_defer_enabled(callback.from_user.id, not current)
    await render_settings_screen(
        "st:byt_rules", message=callback.message, state=state
    )


@router.callback_query(F.data.startswith("byt:category_toggle:"))
async def toggle_byt_category(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    db = get_db()
    parts = callback.data.split(":")
    if len(parts) < 4:
        return
    try:
        category_id = int(parts[2])
        target_state = int(parts[3])
    except ValueError:
        return
    current = db.get_byt_reminder_category_enabled(callback.from_user.id, category_id)
    if int(current) == target_state:
        return
    enabled = db.toggle_byt_reminder_category(callback.from_user.id, category_id)
    LOGGER.info(
        "USER=%s ACTION=BYT_CATEGORY_TOGGLE META=category=%s enabled=%s",
        callback.from_user.id,
        category_id,
        enabled,
    )
    await render_settings_screen(
        "wl:byt_category_menu", message=callback.message, state=state
    )


@router.callback_query(F.data == "byt:edit_max_defer_days")
async def edit_byt_max_defer_days(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _push_current_screen(state, "byt:edit_max_defer_days")
    await state.set_state(BytSettingsState.waiting_for_max_defer_days)
    db = get_db()
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
    prompt = await _send_and_register(
        message=callback.message,
        state=state,
        text=": 0",
        reply_markup=income_calculator_keyboard(),
    )
    await state.update_data(
        byt_max_display_chat_id=prompt.chat.id,
        byt_max_display_message_id=prompt.message_id,
    )


@router.callback_query(F.data == "bt:add_time")
async def byt_timer_add_time(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _push_current_screen(state, "bt:add_time")
    await state.set_state(BytTimerState.waiting_for_time_add)
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Введи время в формате HH:MM",
        reply_markup=None,
    )


@router.callback_query(F.data == "bt:del_time_menu")
async def byt_timer_delete_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _navigate_to_screen("bt:del_time_menu", message=callback.message, state=state)


@router.callback_query(F.data.startswith("bt:del_time:"))
async def byt_timer_delete(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) < 3:
        return
    time_hhmm = parts[2]
    data = await state.get_data()
    category_id = data.get("byt_timer_category_id")
    if category_id is None:
        return
    db = get_db()
    db.remove_byt_reminder_time(callback.from_user.id, int(category_id), time_hhmm)
    await _render_byt_timer_category_settings(
        state=state,
        message=callback.message,
        db=db,
        user_id=callback.from_user.id,
        category_id=int(category_id),
    )


@router.callback_query(F.data == "bt:reset_default")
async def byt_timer_reset(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    db = get_db()
    db.reset_byt_timer_times(callback.from_user.id)
    await render_settings_screen(
        "byt:timer_menu", message=callback.message, state=state
    )


@router.callback_query(F.data == "byt:timer_menu")
async def open_byt_timer_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    LOGGER.info(
        "USER=%s ACTION=BYT_TIMER_MENU_OPEN STATE=%s META=-",
        callback.from_user.id,
        await state.get_state(),
    )
    await _navigate_to_screen("byt:timer_menu", message=callback.message, state=state)


@router.callback_query(F.data.startswith("byt:timer_category:"))
async def open_byt_timer_category(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) < 3:
        return
    try:
        category_id = int(parts[2])
    except ValueError:
        return
    LOGGER.info(
        "USER=%s ACTION=BYT_TIMER_CATEGORY_SELECT META=category_id=%s",
        callback.from_user.id,
        category_id,
    )
    await state.update_data(byt_timer_category_id=category_id)
    await _navigate_to_screen("byt:timer_category", message=callback.message, state=state)


@router.message(HouseholdSettingsState.waiting_for_removal)
async def household_payment_delete_choice(
    message: Message, state: FSMContext
) -> None:
    data = await state.get_data()
    await _register_user_message(state, message)
    await _delete_user_message(message)
    mapping: dict[str, str] = data.get("hp_delete_map") or {}
    choice = (message.text or "").strip()
    if choice in {NAV_BACK, "⬅ Назад", "⬅️ Назад"}:
        await state.set_state(None)
        await render_settings_screen(
            "st:household_payments", message=message, state=state, force_new=False
        )
        return

    code = mapping.get(choice)
    if not code:
        await _send_and_register(
            message=message,
            state=state,
            text="Выбери платеж из списка.",
        )
        return

    db = get_db()
    db.deactivate_household_payment_item(message.from_user.id, code)
    await db.init_household_questions_for_month(
        message.from_user.id, current_month_str(now_for_user(db, message.from_user.id, DEFAULT_TZ))
    )
    LOGGER.info(
        "Deleted household payment item (user_id=%s, code=%s)",
        message.from_user.id,
        code,
    )
    await state.set_state(None)
    await render_settings_screen(
        "st:household_payments", message=message, state=state, force_new=False
    )


@router.message(HouseholdSettingsState.waiting_for_debit_category)
async def household_debit_category_choice(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await _register_user_message(state, message)
    await _delete_user_message(message)

    choice = (message.text or "").strip()
    if choice in {NAV_BACK, "⬅ Назад", "⬅️ Назад"}:
        await state.set_state(None)
        previous_screen = await _pop_previous_screen(state) or "st:household_payments"
        await render_settings_screen(previous_screen, message=message, state=state)
        return

    mapping: dict[str, str] = data.get("hp_debit_map") or {}
    category_code = mapping.get(choice)
    if not category_code:
        await render_settings_screen(
            "hp:debit_category_menu",
            message=message,
            state=state,
            error_message="Выбери категорию из списка.",
            force_new=True,
        )
        return

    db = get_db()
    db.set_household_debit_category(message.from_user.id, str(category_code))
    LOGGER.info(
        "USER=%s ACTION=HOUSEHOLD_DEBIT_CATEGORY_SET META=category=%s",
        message.from_user.id,
        category_code,
    )
    await state.set_state(None)
    previous_screen = await _pop_previous_screen(state) or "st:household_payments"
    await render_settings_screen(previous_screen, message=message, state=state)


@router.message(WishlistSettingsState.waiting_for_debit_category)
async def wishlist_debit_category_choice(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await _register_user_message(state, message)
    await _delete_user_message(message)

    choice = (message.text or "").strip()
    if choice in {WISHLIST_DEBIT_CATEGORY_BACK, NAV_BACK, "⬅ Назад"}:
        await state.set_state(None)
        previous_screen = await _pop_previous_screen(state) or "st:wishlist"
        await render_settings_screen(previous_screen, message=message, state=state)
        return

    if choice == WISHLIST_DEBIT_CATEGORY_NONE:
        db = get_db()
        db.set_wishlist_debit_category(message.from_user.id, None)
        LOGGER.info(
            "USER=%s ACTION=WISHLIST_DEBIT_CATEGORY_SET META=category=None",
            message.from_user.id,
        )
        await _send_and_register(
            message=message,
            state=state,
            text="Категория списания обновлена.",
        )
        await state.set_state(None)
        previous_screen = await _pop_previous_screen(state) or "st:wishlist"
        await render_settings_screen(previous_screen, message=message, state=state)
        return

    mapping: dict[str, str] = data.get("wl_debit_map") or {}
    category_code = mapping.get(choice)
    if not category_code:
        await render_settings_screen(
            "wl:debit_category_menu",
            message=message,
            state=state,
            error_message="Выбери категорию из списка.",
            force_new=True,
        )
        return

    db = get_db()
    db.set_wishlist_debit_category(message.from_user.id, str(category_code))
    LOGGER.info(
        "USER=%s ACTION=WISHLIST_DEBIT_CATEGORY_SET META=category=%s",
        message.from_user.id,
        category_code,
    )
    await _send_and_register(
        message=message,
        state=state,
        text="Категория списания обновлена.",
    )
    await state.set_state(None)
    previous_screen = await _pop_previous_screen(state) or "st:wishlist"
    await render_settings_screen(previous_screen, message=message, state=state)


@router.message(IncomeSettingsState.waiting_for_removal)
async def income_category_delete_choice(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await _register_user_message(state, message)
    await _delete_user_message(message)

    choice = (message.text or "").strip()
    if choice in {NAV_BACK, "⬅ Назад", "⬅️ Назад"}:
        await state.set_state(None)
        await _render_previous_screen_or_exit(message, state)
        return

    mapping: dict[str, int] = data.get("inc_delete_map") or {}
    category_id = mapping.get(choice)
    if not category_id:
        await render_settings_screen(
            "inc:del_menu",
            message=message,
            state=state,
            error_message="Выбери категорию из списка.",
            force_new=True,
        )
        return

    db = get_db()
    categories = db.list_active_income_categories(message.from_user.id)
    if len([cat for cat in categories if cat.get("is_active", 1)]) <= 1:
        await state.set_state(None)
        await render_settings_screen(
            "st:income",
            message=message,
            state=state,
            error_message="Нельзя удалить последнюю категорию.",
        )
        return

    db.deactivate_income_category(message.from_user.id, category_id)
    await state.set_state(None)
    previous_screen = await _pop_previous_screen(state) or "st:income"
    await render_settings_screen(previous_screen, message=message, state=state)


@router.message(IncomeSettingsState.waiting_for_percent_category)
async def income_category_percent_choice(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await _register_user_message(state, message)
    await _delete_user_message(message)

    choice = (message.text or "").strip()
    if choice in {NAV_BACK, "⬅ Назад", "⬅️ Назад"}:
        await state.set_state(None)
        await _render_previous_screen_or_exit(message, state)
        return

    mapping: dict[str, int] = data.get("inc_percent_map") or {}
    category_id = mapping.get(choice)
    if not category_id:
        await render_settings_screen(
            "inc:pct_menu",
            message=message,
            state=state,
            error_message="Выбери категорию из списка.",
            force_new=True,
        )
        return

    db = get_db()
    category = db.get_income_category_by_id(message.from_user.id, category_id)
    if not category:
        await state.set_state(None)
        await render_settings_screen("st:income", message=message, state=state)
        return

    await _push_current_screen(state, "inc:pct_input")
    await state.update_data(
        edit_scope="income",
        editing_category_id=category_id,
        previous_percent=category.get("percent", 0),
        percent_str="0",
    )
    await state.set_state(IncomeSettingsState.waiting_for_percent)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=f"Введи процент (0–100) для: {category['title']}",
        reply_markup=None,
    )
    percent_message = await _send_and_register(
        message=message,
        state=state,
        text=": 0",
        reply_markup=income_calculator_keyboard(),
    )
    await state.update_data(
        percent_display_chat_id=percent_message.chat.id,
        percent_display_message_id=percent_message.message_id,
    )
    LOGGER.info(
        "Percent edit start: user=%s scope=%s category_id=%s",
        message.from_user.id,
        "income",
        category_id,
    )


@router.message(WishlistSettingsState.waiting_for_removal)
async def wishlist_category_delete_choice(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await _register_user_message(state, message)
    await _delete_user_message(message)

    choice = (message.text or "").strip()
    if choice in {NAV_BACK, "⬅ Назад", "⬅️ Назад"}:
        await state.set_state(None)
        await _render_previous_screen_or_exit(message, state)
        return

    mapping: dict[str, int] = data.get("wl_delete_map") or {}
    category_id = mapping.get(choice)
    if not category_id:
        await render_settings_screen(
            "wl:del_cat_menu",
            message=message,
            state=state,
            error_message="Выбери категорию из списка.",
            force_new=True,
        )
        return

    db = get_db()
    categories = db.list_active_wishlist_categories(message.from_user.id)
    if len(categories) <= 1:
        await state.set_state(None)
        await render_settings_screen(
            "st:wishlist",
            message=message,
            state=state,
            error_message="Нельзя удалить последнюю категорию.",
        )
        return

    db.deactivate_wishlist_category(message.from_user.id, category_id)
    await state.set_state(None)
    previous_screen = await _pop_previous_screen(state) or "st:wishlist"
    await render_settings_screen(previous_screen, message=message, state=state)


@router.message(WishlistSettingsState.waiting_for_purchased_category)
async def wishlist_purchased_category_choice(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await _register_user_message(state, message)
    await _delete_user_message(message)

    choice = (message.text or "").strip()
    if choice in {NAV_BACK, "⬅ Назад", "⬅️ Назад"}:
        await state.set_state(None)
        await _render_previous_screen_or_exit(message, state)
        return

    mapping: dict[str, int] = data.get("wl_purchased_map") or {}
    category_id = mapping.get(choice)
    if not category_id:
        await render_settings_screen(
            "wl:purchased_select_category",
            message=message,
            state=state,
            error_message="Выбери категорию из списка.",
            force_new=True,
        )
        return

    db = get_db()
    category = db.get_wishlist_category_by_id(message.from_user.id, category_id)
    if not category or not category.get("is_active", 1):
        await state.set_state(None)
        await render_settings_screen("st:wishlist", message=message, state=state)
        return

    await _push_current_screen(state, "wl:purchased_mode")
    await state.update_data(editing_wl_category_id=category_id)
    await state.set_state(WishlistSettingsState.waiting_for_purchased_mode)
    await _navigate_to_screen(
        "wl:purchased_mode", message=message, state=state, force_new=True
    )


@router.message(WishlistSettingsState.waiting_for_purchased_mode)
async def wishlist_purchased_mode_choice(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await _register_user_message(state, message)
    await _delete_user_message(message)

    choice = (message.text or "").strip()
    if choice in {NAV_BACK, "⬅ Назад", "⬅️ Назад"}:
        await state.set_state(None)
        await _render_previous_screen_or_exit(message, state)
        return

    category_id = data.get("editing_wl_category_id")
    if category_id is None:
        await state.set_state(None)
        await render_settings_screen("st:wishlist", message=message, state=state)
        return

    db = get_db()
    if choice == "Всегда":
        db.update_wishlist_category_purchased_mode(
            message.from_user.id, int(category_id), "always"
        )
        await state.set_state(None)
        await _reset_navigation(state, "st:wishlist")
        await render_settings_screen("st:wishlist", message=message, state=state)
        return
    if choice != "Настроить дни":
        await render_settings_screen(
            "wl:purchased_mode",
            message=message,
            state=state,
            error_message="Выбери вариант из списка.",
            force_new=True,
        )
        return

    category = db.get_wishlist_category_by_id(message.from_user.id, int(category_id))
    if not category:
        await state.set_state(None)
        await _reset_navigation(state, "st:wishlist")
        await render_settings_screen("st:wishlist", message=message, state=state)
        return

    await _push_current_screen(state, "wl:purchased_days")
    await state.set_state(WishlistSettingsState.waiting_for_purchased_days)
    await state.update_data(
        purchased_days_str="0",
        purchased_display_chat_id=None,
        purchased_display_message_id=None,
        editing_wl_category_id=int(category_id),
    )
    db.update_wishlist_category_purchased_mode(
        message.from_user.id, int(category_id), "days"
    )
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=(
            f'На сколько дней показывать купленное для "{category.get("title", "")}"?'
        ),
        reply_markup=None,
    )
    prompt = await _send_and_register(
        message=message,
        state=state,
        text=": 0",
        reply_markup=income_calculator_keyboard(),
    )
    await state.update_data(
        purchased_display_chat_id=prompt.chat.id,
        purchased_display_message_id=prompt.message_id,
    )


@router.message(BytTimerState.waiting_for_time_add)
async def byt_timer_add_time_value(message: Message, state: FSMContext) -> None:
    await _register_user_message(state, message)
    await _delete_user_message(message)
    text = (message.text or "").strip()
    data = await state.get_data()
    time_draft = data.get("time_draft")
    combined = None
    if time_draft and time_draft.endswith(":") and text.isdigit() and len(text) == 2:
        combined = f"{time_draft}{text}"
    normalized, is_complete = normalize_time_partial(combined or text)
    if not normalized:
        chat_id, message_id = await _get_settings_message_ids(state, message)
        await _edit_settings_page(
            bot=message.bot,
            state=state,
            chat_id=chat_id,
            message_id=message_id,
            text=f"{ERR_INVALID_INPUT} {HINT_TIME_FORMAT}",
            reply_markup=None,
        )
        return

    if not is_complete:
        await state.update_data(time_draft=normalized)
        chat_id, message_id = await _get_settings_message_ids(state, message)
        await _edit_settings_page(
            bot=message.bot,
            state=state,
            chat_id=chat_id,
            message_id=message_id,
            text=f"Введи минуты (мм). Текущее: {normalized}",
            reply_markup=None,
        )
        return

    await state.update_data(time_draft=None)
    hour, minute = [int(part) for part in normalized.split(":")]
    category_id = data.get("byt_timer_category_id")
    if category_id is None:
        await state.set_state(None)
        await render_settings_screen("byt:timer_menu", message=message, state=state)
        return
    db = get_db()
    db.add_byt_reminder_time(
        message.from_user.id, int(category_id), f"{hour:02d}:{minute:02d}"
    )
    await state.set_state(None)
    await render_settings_screen("byt:timer_category", message=message, state=state)

@router.callback_query(F.data == "inc:add")
async def category_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _push_current_screen(state, "inc:add_category")
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
    await _push_current_screen(state, "wl:add_category")
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
    await _register_user_message(state, message)
    await _delete_user_message(message)
    title = (message.text or "").strip()
    if not title or len(title) > 32:
        chat_id, message_id = await _get_settings_message_ids(state, message)
        await _edit_settings_page(
            bot=message.bot,
            state=state,
            chat_id=chat_id,
            message_id=message_id,
            text="Название должно быть от 1 до 32 символов.",
            reply_markup=None,
        )
        return

    await state.update_data(new_income_category_title=title, new_income_percent_str="0")
    await state.set_state(IncomeSettingsState.waiting_for_new_category_percent)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text="Процент для категории?",
        reply_markup=None,
    )
    prompt = await _send_and_register(
        message=message,
        state=state,
        text=": 0",
        reply_markup=income_calculator_keyboard(),
    )
    await state.update_data(
        new_income_display_chat_id=prompt.chat.id,
        new_income_display_message_id=prompt.message_id,
    )


@router.message(WishlistSettingsState.waiting_for_category_title)
async def wishlist_add_category_title(message: Message, state: FSMContext) -> None:
    await _register_user_message(state, message)
    await _delete_user_message(message)
    title = (message.text or "").strip()
    if not title or len(title) > 32:
        chat_id, message_id = await _get_settings_message_ids(state, message)
        await _edit_settings_page(
            bot=message.bot,
            state=state,
            chat_id=chat_id,
            message_id=message_id,
            text="Название должно быть от 1 до 32 символов.",
            reply_markup=None,
        )
        return

    db = get_db()
    db.create_wishlist_category(message.from_user.id, title)
    await state.set_state(None)
    previous_screen = await _pop_previous_screen(state) or "st:wishlist"
    await render_settings_screen(previous_screen, message=message, state=state)


@router.message(IncomeSettingsState.waiting_for_new_category_percent)
async def income_new_category_percent(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (message.text or "").strip()
    await _register_user_message(state, message)
    await _delete_user_message(message)
    if text in {"Назад", "⬅ Назад", "⬅️ Назад", "⏪ Назад"}:
        return

    percent_str = data.get("new_income_percent_str", "0")
    display_chat_id = data.get("new_income_display_chat_id", message.chat.id)
    display_message_id = data.get("new_income_display_message_id")

    if text not in PERCENT_INPUT_BUTTONS:
        parsed_value = parse_int_choice(text)
        if parsed_value is None:
            chat_id, message_id = await _get_settings_message_ids(state, message)
            await _edit_settings_page(
                bot=message.bot,
                state=state,
                chat_id=chat_id,
                message_id=message_id,
                text=f"{ERR_INVALID_INPUT} Введи число.",
                reply_markup=None,
            )
            return
        percent_str = str(parsed_value)
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {percent_str}",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=f": {percent_str}",
            )
            if fallback:
                display_message_id = fallback.message_id
                await ui_register_message(state, display_chat_id, display_message_id)
        await state.update_data(
            new_income_percent_str=percent_str,
            new_income_display_chat_id=display_chat_id,
            new_income_display_message_id=display_message_id,
        )
        return

    if text in PERCENT_DIGITS:
        percent_str = percent_str.lstrip("0") if percent_str != "0" else ""
        percent_str = f"{percent_str}{text}" or "0"
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {percent_str}",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=f": {percent_str}",
            )
            if fallback:
                display_message_id = fallback.message_id
                await ui_register_message(state, display_chat_id, display_message_id)
        await state.update_data(
            new_income_percent_str=percent_str,
            new_income_display_chat_id=display_chat_id,
            new_income_display_message_id=display_message_id,
        )
        return

    if text == "Очистить":
        percent_str = "0"
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=": 0",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=": 0",
            )
            if fallback:
                display_message_id = fallback.message_id
                await ui_register_message(state, display_chat_id, display_message_id)
        await state.update_data(
            new_income_percent_str=percent_str,
            new_income_display_chat_id=display_chat_id,
            new_income_display_message_id=display_message_id,
        )
        return

    if text == "✅ Газ":
        error_message = None
        try:
            percent = int(percent_str or "0")
        except ValueError:
            error_message = "Процент должен быть числом."
            percent = 0
        else:
            if percent < 0 or percent > 100:
                error_message = "Процент должен быть в диапазоне 0–100."

        title = (data.get("new_income_category_title") or "").strip()
        if not title:
            error_message = error_message or "Название категории не задано."

        if error_message is None:
            db = get_db()
            category_id = db.create_income_category(message.from_user.id, title)
            if category_id is not None:
                db.update_income_category_percent(
                    message.from_user.id, category_id, percent
                )

        await _cleanup_input_ui(
            message.bot,
            data,
            display_chat_key="new_income_display_chat_id",
            display_message_key="new_income_display_message_id",
        )
        await _remove_calculator_keyboard(message)
        await state.set_state(None)
        previous_screen = await _pop_previous_screen(state) or "st:income"
        await render_settings_screen(
            previous_screen, message=message, state=state, error_message=error_message
        )


@router.message(HouseholdSettingsState.waiting_for_title)
async def household_payment_title(message: Message, state: FSMContext) -> None:
    await _register_user_message(state, message)
    title = (message.text or "").strip()
    if not title:
        await _send_and_register(
            message=message,
            state=state,
            text=ERR_INVALID_INPUT,
        )
        return

    await state.update_data(hp_new_title=title, hp_amount_str="0")
    await state.set_state(HouseholdSettingsState.waiting_for_amount)
    chat_id, message_id = await _get_settings_message_ids(state, message)
    await _edit_settings_page(
        bot=message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=f'Сколько платить за "{title}"?',
        reply_markup=None,
    )
    prompt = await _send_and_register(
        message=message,
        state=state,
        text=": 0",
        reply_markup=income_calculator_keyboard(),
    )
    await state.update_data(
        hp_amount_display_chat_id=prompt.chat.id,
        hp_amount_display_message_id=prompt.message_id,
    )


@router.message(HouseholdSettingsState.waiting_for_amount)
async def household_payment_amount(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (message.text or "").strip()
    await _register_user_message(state, message)
    await _delete_user_message(message)
    amount_str = data.get("hp_amount_str", "0")
    display_chat_id = data.get("hp_amount_display_chat_id", message.chat.id)
    display_message_id = data.get("hp_amount_display_message_id")
    if text in {"Назад", "⬅ Назад", "⬅️ Назад", "⏪ Назад"}:
        return

    if text not in PERCENT_INPUT_BUTTONS:
        parsed_value = parse_positive_int(text)
        if parsed_value is None:
            chat_id, message_id = await _get_settings_message_ids(state, message)
            await _edit_settings_page(
                bot=message.bot,
                state=state,
                chat_id=chat_id,
                message_id=message_id,
                text=f"{ERR_INVALID_INPUT} Введи число.",
                reply_markup=None,
            )
            return
        amount_str = str(parsed_value)
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {amount_str}",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=f": {amount_str}",
            )
            if fallback:
                display_message_id = fallback.message_id
                await ui_register_message(state, display_chat_id, display_message_id)
        await state.update_data(
            hp_amount_str=amount_str,
            hp_amount_display_chat_id=display_chat_id,
            hp_amount_display_message_id=display_message_id,
        )
        return

    if text in PERCENT_DIGITS:
        amount_str = amount_str.lstrip("0") if amount_str != "0" else ""
        amount_str = f"{amount_str}{text}" or "0"
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {amount_str}",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=f": {amount_str}",
            )
            if fallback:
                display_message_id = fallback.message_id
                await ui_register_message(state, display_chat_id, display_message_id)
        await state.update_data(
            hp_amount_str=amount_str,
            hp_amount_display_chat_id=display_chat_id,
            hp_amount_display_message_id=display_message_id,
        )
        return

    if text == "Очистить":
        amount_str = "0"
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=": 0",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=": 0",
            )
            if fallback:
                display_message_id = fallback.message_id
                await ui_register_message(state, display_chat_id, display_message_id)
        await state.update_data(
            hp_amount_str=amount_str,
            hp_amount_display_chat_id=display_chat_id,
            hp_amount_display_message_id=display_message_id,
        )
        return

    if text == "✅ Газ":
        error_message = None
        try:
            amount = int(amount_str or "0")
        except ValueError:
            error_message = ERR_INVALID_INPUT
            amount = 0
        else:
            if amount <= 0:
                error_message = "Сумма должна быть больше нуля."

        title = (data.get("hp_new_title") or "").strip()
        db = get_db()

        if not title:
            error_message = error_message or "Название платежа не задано."

        if error_message is None:
            position = db.get_next_household_position(message.from_user.id)
            code = f"custom_{time.time_ns()}"
            text_value = f"{title} {amount}р?"
            db.add_household_payment_item(
                message.from_user.id, code, text_value, amount, position
            )
            await db.init_household_questions_for_month(
                message.from_user.id, current_month_str(now_for_user(db, message.from_user.id, DEFAULT_TZ))
            )
            LOGGER.info(
                "Added household payment item (user_id=%s, code=%s, amount=%s, title=%s)",
                message.from_user.id,
                code,
                amount,
                title,
            )

        await _cleanup_input_ui(
            message.bot,
            data,
            display_chat_key="hp_amount_display_chat_id",
            display_message_key="hp_amount_display_message_id",
        )
        await _remove_calculator_keyboard(message)
        await state.set_state(None)
        previous_screen = await _pop_previous_screen(state) or "st:household_payments"
        await render_settings_screen(
            previous_screen,
            message=message,
            state=state,
            error_message=error_message,
        )


@router.callback_query(F.data == "inc:del_menu")
async def category_delete_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _navigate_to_screen("inc:del_menu", message=callback.message, state=state)


@router.callback_query(F.data == "wl:del_cat_menu")
async def wishlist_delete_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _navigate_to_screen("wl:del_cat_menu", message=callback.message, state=state)


@router.callback_query(F.data.startswith("inc:del:"))
async def category_delete(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return

    db = get_db()
    scope = "income"
    categories = db.list_active_income_categories(callback.from_user.id)
    if len([cat for cat in categories if cat.get("is_active", 1)]) <= 1:
        await render_settings_screen(
            "st:income",
            message=callback.message,
            state=state,
            error_message="Нельзя удалить последнюю категорию.",
        )
        return

    db.deactivate_income_category(callback.from_user.id, category_id)
    previous_screen = await _pop_previous_screen(state) or "st:income"
    await render_settings_screen(previous_screen, message=callback.message, state=state)


@router.callback_query(F.data.startswith("wl:del_cat:"))
async def wishlist_category_delete(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return

    db = get_db()
    categories = db.list_active_wishlist_categories(callback.from_user.id)
    if len(categories) <= 1:
        await render_settings_screen(
            "st:wishlist",
            message=callback.message,
            state=state,
            error_message="Нельзя удалить последнюю категорию.",
        )
        return

    db.deactivate_wishlist_category(callback.from_user.id, category_id)
    previous_screen = await _pop_previous_screen(state) or "st:wishlist"
    await render_settings_screen(previous_screen, message=callback.message, state=state)


@router.callback_query(F.data == "inc:pct_menu")
async def category_percent_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _navigate_to_screen("inc:pct_menu", message=callback.message, state=state)


@router.callback_query(F.data.startswith("inc:pct:"))
async def category_percent_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return

    db = get_db()
    scope = "income"
    category = db.get_income_category_by_id(callback.from_user.id, category_id)
    if not category:
        await _render_income_settings(
            state=state, message=callback.message, db=db, user_id=callback.from_user.id
        )
        return

    await _push_current_screen(state, "inc:pct_input")
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

    percent_message = await _send_and_register(
        message=callback.message,
        state=state,
        text=": 0",
        reply_markup=income_calculator_keyboard(),
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


@router.callback_query(F.data == "wl:purchased_select_category")
async def wishlist_purchased_select_category(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(None)
    await _navigate_to_screen(
        "wl:purchased_select_category", message=callback.message, state=state
    )


@router.callback_query(F.data.startswith("wl:purchased_cat:"))
async def wishlist_purchased_category(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        category_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return

    db = get_db()
    category = db.get_wishlist_category_by_id(callback.from_user.id, category_id)
    if not category or not category.get("is_active", 1):
        await render_settings_screen(
            "st:wishlist", message=callback.message, state=state
        )
        return

    await _push_current_screen(state, "wl:purchased_mode")
    await state.update_data(editing_wl_category_id=category_id)
    await _navigate_to_screen(
        "wl:purchased_mode", message=callback.message, state=state
    )


@router.callback_query(F.data == "wl:purchased_mode:always")
async def wishlist_set_purchased_always(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    category_id = data.get("editing_wl_category_id")
    if category_id is None:
        await render_settings_screen("st:wishlist", message=callback.message, state=state)
        return
    db = get_db()
    db.update_wishlist_category_purchased_mode(callback.from_user.id, int(category_id), "always")
    await state.set_state(None)
    await _reset_navigation(state, "st:wishlist")
    await render_settings_screen("st:wishlist", message=callback.message, state=state)


@router.callback_query(F.data == "wl:purchased_mode:days")
async def wishlist_set_purchased_days(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    category_id = data.get("editing_wl_category_id")
    if category_id is None:
        await render_settings_screen("st:wishlist", message=callback.message, state=state)
        return
    db = get_db()
    category = db.get_wishlist_category_by_id(callback.from_user.id, int(category_id))
    if not category:
        await _reset_navigation(state, "st:wishlist")
        await render_settings_screen("st:wishlist", message=callback.message, state=state)
        return
    await _push_current_screen(state, "wl:purchased_days")
    await state.set_state(WishlistSettingsState.waiting_for_purchased_days)
    await state.update_data(
        purchased_days_str="0",
        purchased_display_chat_id=None,
        purchased_display_message_id=None,
        editing_wl_category_id=int(category_id),
    )
    db.update_wishlist_category_purchased_mode(callback.from_user.id, int(category_id), "days")
    chat_id, message_id = await _get_settings_message_ids(state, callback.message)
    await _edit_settings_page(
        bot=callback.message.bot,
        state=state,
        chat_id=chat_id,
        message_id=message_id,
        text=(
            f'На сколько дней показывать купленное для "{category.get("title", "")}"?'
        ),
        reply_markup=None,
    )
    prompt = await _send_and_register(
        message=callback.message,
        state=state,
        text=": 0",
        reply_markup=income_calculator_keyboard(),
    )
    await state.update_data(
        purchased_display_chat_id=prompt.chat.id,
        purchased_display_message_id=prompt.message_id,
    )


@router.message(IncomeSettingsState.waiting_for_percent)
async def income_percent_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (message.text or "").strip()
    await _register_user_message(state, message)
    await _delete_user_message(message)
    if text in {"Назад", "⬅ Назад", "⬅️ Назад", "⏪ Назад"}:
        return

    percent_str = data.get("percent_str", "0")
    display_chat_id = data.get("percent_display_chat_id", message.chat.id)
    display_message_id = data.get("percent_display_message_id")

    if text not in PERCENT_INPUT_BUTTONS:
        parsed_value = parse_int_choice(text)
        if parsed_value is None:
            chat_id, message_id = await _get_settings_message_ids(state, message)
            await _edit_settings_page(
                bot=message.bot,
                state=state,
                chat_id=chat_id,
                message_id=message_id,
                text=f"{ERR_INVALID_INPUT} Введи число.",
                reply_markup=None,
            )
            return
        percent_str = str(parsed_value)
        LOGGER.info(
            "Percent input: user=%s scope=%s value=%s",
            message.from_user.id,
            data.get("edit_scope", "income"),
            percent_str,
        )
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {percent_str}",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=f": {percent_str}",
            )
            display_message_id = fallback.message_id
            await ui_register_message(state, display_chat_id, display_message_id)
        await state.update_data(
            percent_str=percent_str,
            percent_display_chat_id=display_chat_id,
            percent_display_message_id=display_message_id,
        )
        return

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
            await _safe_edit(message.bot, 
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {percent_str}",
            )
        except Exception:
            fallback = await safe_send_message(message.bot, 
                chat_id=display_chat_id, text=f": {percent_str}"
            )
            display_message_id = fallback.message_id
            await ui_register_message(state, display_chat_id, display_message_id)
        await state.update_data(
            percent_str=percent_str,
            percent_display_chat_id=display_chat_id,
            percent_display_message_id=display_message_id,
        )
        return

    if text == "Очистить":
        percent_str = "0"
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=": 0",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=": 0",
            )
            if fallback:
                display_message_id = fallback.message_id
                await ui_register_message(state, display_chat_id, display_message_id)
        await state.update_data(
            percent_str=percent_str,
            percent_display_chat_id=display_chat_id,
            percent_display_message_id=display_message_id,
        )
        return

    if text == "✅ Газ":
        error_message = None
        try:
            percent = int(percent_str or "0")
        except ValueError:
            error_message = "Процент должен быть числом."
        else:
            if percent < 0 or percent > 100:
                error_message = "Процент должен быть в диапазоне 0–100."

        category_id = data.get("editing_category_id")
        if category_id is None:
            await state.set_state(None)
            await _cleanup_input_ui(
                message.bot,
                data,
                display_chat_key="percent_display_chat_id",
                display_message_key="percent_display_message_id",
            )
            await _remove_calculator_keyboard(message)
            await _render_previous_screen_or_exit(message, state)
            return

        if error_message is None:
            db = get_db()
            db.update_income_category_percent(message.from_user.id, category_id, percent)
            total = db.sum_income_category_percents(message.from_user.id)

            if total == 100:
                LOGGER.info(
                    "Percent saved: user=%s scope=%s category_id=%s value=%s",
                    message.from_user.id,
                    "income",
                    category_id,
                    percent,
                )
            else:
                error_message = f"Сумма процентов сейчас {total}%. Нужно 100%."

        await _cleanup_input_ui(
            message.bot,
            data,
            display_chat_key="percent_display_chat_id",
            display_message_key="percent_display_message_id",
        )
        await _remove_calculator_keyboard(message)
        if error_message:
            await state.set_state(IncomeSettingsState.waiting_for_percent_category)
            await _render_income_percent_menu(
                state=state,
                message=message,
                db=get_db(),
                user_id=message.from_user.id,
                error_message=error_message,
            )
            return

        await state.set_state(None)
        previous_screen = await _pop_previous_screen(state) or "st:income"
        await render_settings_screen(previous_screen, message=message, state=state)


@router.message(WishlistSettingsState.waiting_for_purchased_days)
async def wishlist_purchased_days_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (message.text or "").strip()
    await _register_user_message(state, message)
    await _delete_user_message(message)
    if text in {"Назад", "⬅ Назад", "⬅️ Назад", "⏪ Назад"}:
        return

    days_str = data.get("purchased_days_str", "0")
    display_chat_id = data.get("purchased_display_chat_id", message.chat.id)
    display_message_id = data.get("purchased_display_message_id")

    if text not in PERCENT_INPUT_BUTTONS:
        parsed_value = parse_positive_int(text)
        if parsed_value is None:
            chat_id, message_id = await _get_settings_message_ids(state, message)
            await _edit_settings_page(
                bot=message.bot,
                state=state,
                chat_id=chat_id,
                message_id=message_id,
                text=f"{ERR_INVALID_INPUT} Введи число.",
                reply_markup=None,
            )
            return
        days_str = str(parsed_value)
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {days_str}",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=f": {days_str}",
            )
            if fallback:
                display_message_id = fallback.message_id
                await ui_register_message(state, display_chat_id, display_message_id)
        await state.update_data(
            purchased_days_str=days_str,
            purchased_display_chat_id=display_chat_id,
            purchased_display_message_id=display_message_id,
        )
        return

    if text in PERCENT_DIGITS:
        days_str = days_str.lstrip("0") if days_str != "0" else ""
        days_str = f"{days_str}{text}" or "0"
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {days_str}",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=f": {days_str}",
            )
            if fallback:
                display_message_id = fallback.message_id
                await ui_register_message(state, display_chat_id, display_message_id)
        await state.update_data(
            purchased_days_str=days_str,
            purchased_display_chat_id=display_chat_id,
            purchased_display_message_id=display_message_id,
        )
        return

    if text == "Очистить":
        days_str = "0"
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=": 0",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=": 0",
            )
            if fallback:
                display_message_id = fallback.message_id
                await ui_register_message(state, display_chat_id, display_message_id)
        await state.update_data(
            purchased_days_str=days_str,
            purchased_display_chat_id=display_chat_id,
            purchased_display_message_id=display_message_id,
        )
        return

    if text == "✅ Газ":
        try:
            days = int(days_str or "0")
        except ValueError:
            chat_id, message_id = await _get_settings_message_ids(state, message)
            await _edit_settings_page(
                bot=message.bot,
                state=state,
                chat_id=chat_id,
                message_id=message_id,
                text=ERR_INVALID_INPUT,
                reply_markup=None,
            )
            return
        if days < 1 or days > 3650:
            chat_id, message_id = await _get_settings_message_ids(state, message)
            await _edit_settings_page(
                bot=message.bot,
                state=state,
                chat_id=chat_id,
                message_id=message_id,
                text="Количество дней должно быть от 1 до 3650.",
                reply_markup=None,
            )
            return

        db = get_db()
        category_id = data.get("editing_wl_category_id")
        if category_id is not None:
            db.update_wishlist_category_purchased_days(
                message.from_user.id, int(category_id), days
            )

        await _cleanup_input_ui(
            message.bot,
            data,
            display_chat_key="purchased_display_chat_id",
            display_message_key="purchased_display_message_id",
        )
        await _remove_calculator_keyboard(message)
        await state.set_state(None)
        await _reset_navigation(state, "st:wishlist")
        await render_settings_screen(
            "st:wishlist", message=message, state=state
        )


@router.message(BytSettingsState.waiting_for_max_defer_days)
async def byt_max_defer_days_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (message.text or "").strip()
    await _register_user_message(state, message)
    await _delete_user_message(message)
    if text in {"Назад", "⬅ Назад", "⬅️ Назад", "⏪ Назад"}:
        return

    days_str = data.get("byt_max_days_str", "0")
    display_chat_id = data.get("byt_max_display_chat_id", message.chat.id)
    display_message_id = data.get("byt_max_display_message_id")

    if text not in PERCENT_INPUT_BUTTONS:
        parsed_value = parse_positive_int(text)
        if parsed_value is None:
            chat_id, message_id = await _get_settings_message_ids(state, message)
            await _edit_settings_page(
                bot=message.bot,
                state=state,
                chat_id=chat_id,
                message_id=message_id,
                text=f"{ERR_INVALID_INPUT} Введи число.",
                reply_markup=None,
            )
            return
        days_str = str(parsed_value)
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {days_str}",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=f": {days_str}",
            )
            if fallback:
                display_message_id = fallback.message_id
        await state.update_data(
            byt_max_days_str=days_str,
            byt_max_display_chat_id=display_chat_id,
            byt_max_display_message_id=display_message_id,
        )
        return

    if text in PERCENT_DIGITS:
        days_str = days_str.lstrip("0") if days_str != "0" else ""
        days_str = f"{days_str}{text}" or "0"
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {days_str}",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=f": {days_str}",
            )
            if fallback:
                display_message_id = fallback.message_id
        await state.update_data(
            byt_max_days_str=days_str,
            byt_max_display_chat_id=display_chat_id,
            byt_max_display_message_id=display_message_id,
        )
        return

    if text == "Очистить":
        days_str = "0"
        try:
            await _safe_edit(
                message.bot,
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=": 0",
            )
        except Exception:
            fallback = await safe_send_message(
                message.bot,
                chat_id=display_chat_id,
                text=": 0",
            )
            if fallback:
                display_message_id = fallback.message_id
        await state.update_data(
            byt_max_days_str=days_str,
            byt_max_display_chat_id=display_chat_id,
            byt_max_display_message_id=display_message_id,
        )
        return

    if text == "✅ Газ":
        try:
            days = int(days_str or "0")
        except ValueError:
            chat_id, message_id = await _get_settings_message_ids(state, message)
            await _edit_settings_page(
                bot=message.bot,
                state=state,
                chat_id=chat_id,
                message_id=message_id,
                text=ERR_INVALID_INPUT,
                reply_markup=None,
            )
            return
        if days < 1 or days > 3650:
            chat_id, message_id = await _get_settings_message_ids(state, message)
            await _edit_settings_page(
                bot=message.bot,
                state=state,
                chat_id=chat_id,
                message_id=message_id,
                text="Количество дней должно быть от 1 до 3650.",
                reply_markup=None,
            )
            return

        db = get_db()
        settings_row = db.get_user_settings(message.from_user.id)
        previous_days = settings_row.get("byt_defer_max_days")
        db.set_byt_defer_max_days(message.from_user.id, days)
        LOGGER.info(
            "Updated BYT defer max days for user %s: %s", message.from_user.id, days
        )
        previous_max = data.get("previous_byt_max_days")
        if previous_max is not None and previous_max != days:
            LOGGER.info(
                "Max defer days changed: user=%s from=%s to=%s",
                message.from_user.id,
                previous_max,
                days,
            )

        await _cleanup_input_ui(
            message.bot,
            data,
            display_chat_key="byt_max_display_chat_id",
            display_message_key="byt_max_display_message_id",
        )
        await _remove_calculator_keyboard(message)
        await state.set_state(None)
        previous_screen = await _pop_previous_screen(state) or "st:byt_rules"
        await render_settings_screen(
            previous_screen,
            message=message,
            state=state,
        )
