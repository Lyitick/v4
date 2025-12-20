"""Handlers for wishlist flow."""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from Bot.database.crud import FinanceDatabase
from Bot.handlers.common import build_main_menu_for_user
from Bot.keyboards.main import (
    back_only_keyboard,
    wishlist_categories_keyboard,
    wishlist_reply_keyboard,
    wishlist_url_keyboard,
)
from Bot.keyboards.calculator import income_calculator_keyboard
from Bot.states.wishlist_states import BytDeferState, WishlistState
from Bot.utils.datetime_utils import now_tz
from Bot.utils.ui_cleanup import ui_register_message

LOGGER = logging.getLogger(__name__)

router = Router()


async def _push_wl_step(state: FSMContext, step: str) -> None:
    data = await state.get_data()
    stack = list(data.get("wl_add_step_stack") or [])
    if not stack or stack[-1] != step:
        stack.append(step)
    await state.update_data(wl_add_step_stack=stack)


async def _set_wl_steps(state: FSMContext, steps: list[str]) -> None:
    await state.update_data(wl_add_step_stack=steps)


async def delete_welcome_message_if_exists(message: Message, state: FSMContext) -> None:
    """Legacy no-op to keep compatibility when welcome cleanup is referenced."""

    return None

WISHLIST_CATEGORY_TO_SAVINGS_CATEGORY = {
    "Инструменты": "инвестиции",
    "Финансы": "сбережения",
    "Разное": "спонтанные траты",
    "инвестиции в работу": "инвестиции",
    "вклад в себя": "сбережения",
    "кайфы": "спонтанные траты",
    "БЫТ": "быт",
}

def humanize_wishlist_category(category: str) -> str:
    """Return user-facing category name supporting legacy values."""

    mapping = {
        "Инструменты": "инвестиции в работу",
        "Финансы": "вклад в себя",
        "Разное": "кайфы",
        "инвестиции в работу": "инвестиции в работу",
        "вклад в себя": "вклад в себя",
        "кайфы": "кайфы",
        "byt": "БЫТ",
        "БЫТ": "БЫТ",
    }
    return mapping.get(category, category)


def _get_user_wishlist_categories(db: FinanceDatabase, user_id: int) -> list[dict]:
    """Return active wishlist categories ensuring defaults exist."""

    db.ensure_wishlist_categories_seeded(user_id)
    return db.list_active_wishlist_categories(user_id)


@router.message(F.text == "📋 Вишлист")
async def open_wishlist(message: Message, state: FSMContext) -> None:
    """Open wishlist menu."""

    await delete_welcome_message_if_exists(message, state)
    await state.clear()
    db = FinanceDatabase()
    wishes = db.get_wishes_by_user(message.from_user.id)
    categories = _get_user_wishlist_categories(db, message.from_user.id)
    has_active_wishes = any(not wish.get("is_purchased") for wish in wishes)

    if not has_active_wishes:
        await message.answer(
            "В твоём вишлисте пока пусто.\nДавай добавим что-то новое в наши категории ✨",
            reply_markup=wishlist_reply_keyboard(),
        )
        LOGGER.info("User %s opened empty wishlist", message.from_user.id if message.from_user else "unknown")
        return

    await message.answer("Раздел вишлиста.", reply_markup=wishlist_reply_keyboard())
    await message.answer(
        "Выбери категорию для просмотра или добавь новое желание.",
        reply_markup=wishlist_categories_keyboard(categories),
    )
    LOGGER.info("User %s opened wishlist", message.from_user.id if message.from_user else "unknown")


@router.message(F.text.in_({"➕", "+"}))
async def add_wish_start(message: Message, state: FSMContext) -> None:
    """Start adding wish."""

    await state.set_state(WishlistState.waiting_for_name)
    await _set_wl_steps(state, ["name"])
    await message.answer(
        "Введи название желания.",
        reply_markup=back_only_keyboard(),
    )

@router.message(WishlistState.waiting_for_name, F.text != "⬅️ Назад")
async def add_wish_name(message: Message, state: FSMContext) -> None:
    """Save wish name and request price."""

    await state.update_data(name=message.text)
    await state.set_state(WishlistState.waiting_for_price)
    await _push_wl_step(state, "amount")

    question = await message.answer(
        "Введи цену (используй кнопки ниже).",
        reply_markup=income_calculator_keyboard(),
    )
    prompt = await message.answer(": 0")

    await state.update_data(
        price_sum="0",
        price_question_message_id=question.message_id,
        price_message_id=prompt.message_id,
    )


@router.message(
    WishlistState.waiting_for_price,
    F.text.in_(
        {
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "Очистить",
            "✅ Газ",
        }
    ),
)
async def add_wish_price_calc(message: Message, state: FSMContext) -> None:
    """Handle price input via calculator buttons."""

    data = await state.get_data()
    current_sum = str(data.get("price_sum", "0"))
    price_message_id = data.get("price_message_id")

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

        normalized = amount_str.replace(",", ".")
        try:
            price = float(normalized)
        except (TypeError, ValueError):
            await message.answer("Нужно ввести число. Попробуй снова.")
            try:
                await message.delete()
            except Exception:
                pass
            return

        if price <= 0:
            await message.answer("Цена должна быть больше нуля. Попробуй снова.")
            try:
                await message.delete()
            except Exception:
                pass
            return

        await state.update_data(price=price)
        await state.set_state(WishlistState.waiting_for_url)
        await _push_wl_step(state, "pre_url")
        await message.answer("дай", reply_markup=back_only_keyboard())
        await _push_wl_step(state, "url")
        await message.answer("ссылочку", reply_markup=wishlist_url_keyboard())

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

    if price_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=price_message_id,
                text=f": {new_sum}",
            )
        except Exception:
            pass

    await state.update_data(price_sum=new_sum, price_message_id=price_message_id)

    try:
        await message.delete()
    except Exception:
        pass


@router.message(WishlistState.waiting_for_url, F.text != "⬅️ Назад")
async def add_wish_url(message: Message, state: FSMContext) -> None:
    """Save URL and request category selection."""

    text = message.text.strip() if message.text else ""
    url: Optional[str] = None if text in {"-", ""} else text
    await state.update_data(url=url)
    await state.set_state(WishlistState.waiting_for_category)
    await _push_wl_step(state, "category")
    db = FinanceDatabase()
    categories = _get_user_wishlist_categories(db, message.from_user.id)
    await message.answer(
        "Выбери категорию желания.", reply_markup=wishlist_categories_keyboard(categories)
    )
    await message.answer("Если нужно, нажми ⬅️ Назад.", reply_markup=back_only_keyboard())


@router.message(F.text == "Купленное")
async def show_purchases(message: Message, state: FSMContext | None = None) -> None:
    """Show purchased items grouped by category with pretty headers."""

    db = FinanceDatabase()
    purchases = db.get_purchases_by_user(message.from_user.id)

    # Если покупок нет — сразу выходим
    if not purchases:
        sent = await message.answer(
            "Список покупок пуст.",
            reply_markup=await build_main_menu_for_user(message.from_user.id),
        )
        if state:
            await ui_register_message(state, sent.chat.id, sent.message_id)
        return

    # Группируем покупки по "очеловеченным" категориям
    groups: dict[str, list[dict]] = defaultdict(list)
    for purchase in purchases:
        category_key = humanize_wishlist_category(purchase.get("category", ""))
        groups[category_key].append(purchase)

    lines: list[str] = ["Купленные желания:"]
    for category, items in groups.items():
        lines.append(f"\n💡 {category}:")
        for purchase in items:
            lines.append(
                f"• {purchase['wish_name']} — {purchase['price']:.2f} ₽ "
                f"(куплено {purchase['purchased_at']})"
            )

    sent = await message.answer(
        "\n".join(lines),
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )
    if state:
        await ui_register_message(state, sent.chat.id, sent.message_id)


@router.message(
    F.text == "⬅️ Назад",
    StateFilter(
        WishlistState.waiting_for_name,
        WishlistState.waiting_for_price,
        WishlistState.waiting_for_url,
        WishlistState.waiting_for_category,
    ),
)
async def wishlist_add_back(message: Message, state: FSMContext) -> None:
    """Handle back navigation in wishlist add flow."""

    data = await state.get_data()
    stack = list(data.get("wl_add_step_stack") or [])
    current = stack[-1] if stack else None

    if current == "name":
        await state.clear()
        await open_wishlist(message, state)
        return

    if current == "amount":
        await state.update_data(
            price=None,
            price_sum=None,
            price_question_message_id=None,
            price_message_id=None,
        )
        await state.set_state(WishlistState.waiting_for_name)
        await _set_wl_steps(state, ["name"])
        await message.answer(
            "Введи название желания.",
            reply_markup=back_only_keyboard(),
        )
        return

    if current == "url":
        stack.pop()
        await state.update_data(url=None, wl_add_step_stack=stack)
        await message.answer("дай", reply_markup=back_only_keyboard())
        await message.answer("ссылочку", reply_markup=wishlist_url_keyboard())
        return

    if current == "pre_url":
        stack.pop()
        await state.update_data(
            price=None,
            price_sum=None,
            price_question_message_id=None,
            price_message_id=None,
            wl_add_step_stack=stack,
        )
        await state.set_state(WishlistState.waiting_for_price)
        question = await message.answer(
            "Введи цену (используй кнопки ниже).",
            reply_markup=income_calculator_keyboard(),
        )
        prompt = await message.answer(": 0")
        await state.update_data(
            price_sum="0",
            price_question_message_id=question.message_id,
            price_message_id=prompt.message_id,
        )
        await _push_wl_step(state, "amount")
        return

    if current == "category":
        stack.pop()
        await state.update_data(wl_add_step_stack=stack)
        await state.set_state(WishlistState.waiting_for_url)
        await message.answer("дай", reply_markup=back_only_keyboard())
        await message.answer("ссылочку", reply_markup=wishlist_url_keyboard())
        return


@router.message(WishlistState.waiting_for_price)
async def invalid_price(message: Message) -> None:
    """Handle invalid price input."""

    await message.answer("Используй кнопки калькулятора ниже для ввода цены.")


@router.message(WishlistState.waiting_for_category)
async def waiting_category_text(message: Message) -> None:
    """Prompt to use inline keyboard for category."""

    db = FinanceDatabase()
    categories = _get_user_wishlist_categories(db, message.from_user.id)
    await message.answer(
        "Выбери категорию через кнопки ниже.",
        reply_markup=wishlist_categories_keyboard(categories),
    )
    await message.answer("Если нужно, нажми ⬅️ Назад.", reply_markup=back_only_keyboard())


def _build_byt_items_keyboard(items: list[dict], allow_defer: bool = True) -> InlineKeyboardMarkup:
    """Build inline keyboard for BYT items with optional two-column layout."""

    rows: list[list[InlineKeyboardButton]] = []
    per_row = 2 if len(items) > 3 else 1
    for index in range(0, len(items), per_row):
        row_items = items[index : index + per_row]
        row: list[InlineKeyboardButton] = []
        for item in row_items:
            row.append(
                InlineKeyboardButton(
                    text=item.get("name", ""), callback_data=f"byt_buy:{item.get('id')}"
                )
            )
        rows.append(row)
    if allow_defer:
        defer_callback = "byt_defer_menu"
        if len(items) == 1:
            try:
                defer_id = int(items[0].get("id"))
            except (TypeError, ValueError):
                defer_id = None
            else:
                defer_callback = f"byt_defer_menu:{defer_id}"
        rows.append(
            [InlineKeyboardButton(text="ОТЛОЖИТЬ", callback_data=defer_callback)]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_byt_defer_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    """Build inline keyboard for selecting BYT item to defer."""

    rows: list[list[InlineKeyboardButton]] = []
    per_row = 2 if len(items) > 3 else 1
    for index in range(0, len(items), per_row):
        row_items = items[index : index + per_row]
        row: list[InlineKeyboardButton] = []
        for item in row_items:
            row.append(
                InlineKeyboardButton(
                    text=item.get("name", ""),
                    callback_data=f"byt_defer_pick:{item.get('id')}",
                )
            )
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _refresh_byt_reminder_message(
    bot: Bot, chat_id: int, message_id: int, user_id: int
) -> None:
    """Refresh reminder message with current BYT items."""

    db = FinanceDatabase()
    items = db.list_active_byt_items_for_reminder(user_id, now_tz())
    settings_row = db.get_user_settings(user_id)
    allow_defer = bool(settings_row.get("byt_defer_enabled", 1))
    if not items:
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text="Ок."
            )
        except Exception:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=chat_id, message_id=message_id, reply_markup=None
                )
            except Exception:
                pass
        return


async def _start_byt_defer_flow(
    callback: CallbackQuery, state: FSMContext, wish_id: int
) -> bool:
    """Validate and start BYT defer input flow for specific item."""

    db = FinanceDatabase()
    wish = db.get_wish(wish_id)
    if not wish or humanize_wishlist_category(wish.get("category", "")) != "БЫТ":
        await callback.answer("Элемент не найден.", show_alert=True)
        return False

    settings_row = db.get_user_settings(callback.from_user.id)
    if not bool(settings_row.get("byt_defer_enabled", 1)):
        await callback.answer("Отключено в настройках", show_alert=True)
        await state.clear()
        return False

    await state.set_state(BytDeferState.waiting_for_days)
    await state.update_data(
        defer_item_id=wish_id,
        defer_days_str="0",
        reminder_message_id=callback.message.message_id if callback.message else None,
    )

    await callback.answer()
    target_chat_id = callback.message.chat.id if callback.message else callback.from_user.id
    question_message = await callback.bot.send_message(
        target_chat_id, "На сколько дней отложить?"
    )
    prompt = await callback.bot.send_message(
        target_chat_id, ": 0", reply_markup=income_calculator_keyboard()
    )
    await state.update_data(
        defer_display_chat_id=question_message.chat.id,
        defer_display_message_id=prompt.message_id,
    )
    return True

    keyboard = _build_byt_items_keyboard(items, allow_defer=allow_defer)
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="Что ты купил?",
            reply_markup=keyboard,
        )
    except Exception:
        try:
            await bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=message_id, reply_markup=keyboard
            )
        except Exception:
            pass


async def run_byt_timer_check(
    bot: Bot,
    db: FinanceDatabase,
    user_id: int | None = None,
    simulated_time: time | None = None,
    run_time: datetime | None = None,
) -> None:
    """Run BYT reminders using timer configuration for the user."""

    await asyncio.sleep(0)
    trigger_dt = run_time or now_tz()
    if simulated_time:
        trigger_dt = trigger_dt.replace(
            hour=simulated_time.hour,
            minute=simulated_time.minute,
            second=0,
            microsecond=0,
        )

    db.cleanup_old_byt_purchases(trigger_dt)
    user_ids = (
        [user_id]
        if user_id is not None
        else list(
            set(db.get_users_with_active_byt_wishes())
            | set(db.get_users_with_byt_timer_times())
        )
    )
    if not user_ids:
        return

    for uid in user_ids:
        db.ensure_byt_timer_defaults(uid)
        settings_row = db.get_user_settings(uid)
        if not bool(settings_row.get("byt_reminders_enabled", 1)):
            continue

        times = db.list_active_byt_timer_times(uid)
        simulated = simulated_time is not None
        trigger_label = trigger_dt.strftime("%H:%M")
        LOGGER.info(
            "BYT timer check triggered (user_id=%s, simulated=%s, time=%s)",
            uid,
            simulated,
            trigger_label,
        )
        if not times:
            LOGGER.info(
                "BYT timer check: no active times (user_id=%s)",
                uid,
            )
            continue

        should_run = any(
            int(timer.get("hour", -1)) == trigger_dt.hour
            and int(timer.get("minute", -1)) == trigger_dt.minute
            for timer in times
        )
        if not should_run:
            continue

        items = db.list_active_byt_items_for_reminder(uid, trigger_dt)
        if not items:
            LOGGER.info("BYT timer: no items, skip (user_id=%s)", uid)
            continue

        allow_defer = bool(settings_row.get("byt_defer_enabled", 1))
        keyboard = _build_byt_items_keyboard(items, allow_defer=allow_defer)
        await bot.send_message(uid, "Что ты купил?", reply_markup=keyboard)
        LOGGER.info(
            "BYT timer: sending checklist, items=%s, user_id=%s", len(items), uid
        )


async def run_byt_wishlist_reminders(
    bot: Bot,
    db: FinanceDatabase,
    user_id: int | None = None,
    forced: bool = False,
    run_time=None,
) -> None:
    """Backward-compatible wrapper for BYT reminders."""

    await run_byt_timer_check(
        bot,
        db,
        user_id=user_id,
        simulated_time=None,
        run_time=run_time,
    )


@router.callback_query(F.data.startswith("byt_buy:"))
async def handle_byt_buy(callback: CallbackQuery) -> None:
    """Handle purchase confirmation from BYT reminder list."""

    data = callback.data.split(":", maxsplit=1)
    if len(data) != 2:
        await callback.answer("Некорректный формат.", show_alert=True)
        return

    try:
        item_id = int(data[1])
    except ValueError:
        await callback.answer("Некорректный элемент.", show_alert=True)
        return

    db = FinanceDatabase()
    wish = db.get_wish(item_id)
    if not wish or humanize_wishlist_category(wish.get("category", "")) != "БЫТ":
        await callback.answer("Элемент не найден.", show_alert=True)
        return

    price = float(wish.get("price", 0) or 0)
    purchase_time = now_tz()
    db.decrease_savings(callback.from_user.id, "быт", price)
    db.mark_wish_purchased(item_id, purchased_at=purchase_time)
    db.add_purchase(
        callback.from_user.id,
        wish.get("name", ""),
        price,
        humanize_wishlist_category(wish.get("category", "")),
        purchased_at=purchase_time,
    )

    await callback.answer()
    if callback.message:
        await _refresh_byt_reminder_message(
            callback.bot,
            callback.message.chat.id,
            callback.message.message_id,
            callback.from_user.id,
        )


@router.callback_query(F.data.startswith("byt_defer_menu"))
async def handle_byt_defer_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Show BYT items to choose which to defer."""

    wish_id: int | None = None
    if callback.data and ":" in callback.data:
        parts = callback.data.split(":", maxsplit=1)
        if len(parts) == 2:
            try:
                wish_id = int(parts[1])
            except ValueError:
                wish_id = None
    if wish_id is None:
        data = await state.get_data()
        stored_id = data.get("current_byt_item_id")
        try:
            wish_id = int(stored_id) if stored_id is not None else None
        except (TypeError, ValueError):
            wish_id = None

    db = FinanceDatabase()
    settings_row = db.get_user_settings(callback.from_user.id)
    if not bool(settings_row.get("byt_defer_enabled", 1)):
        await callback.answer("Отключено в настройках", show_alert=True)
        return
    now_dt = now_tz()
    items = db.list_active_byt_items_for_reminder(callback.from_user.id, now_dt)
    if wish_id is not None:
        await state.update_data(current_byt_item_id=wish_id)
        started = await _start_byt_defer_flow(callback, state, wish_id)
        if not started:
            await state.clear()
        return
    if not items:
        await state.clear()
        if callback.message:
            await callback.message.answer("Нет бытовых покупок для отложки.")
        else:
            await callback.bot.send_message(
                callback.from_user.id, "Нет бытовых покупок для отложки."
            )
        await callback.answer()
        return

    keyboard = _build_byt_defer_keyboard(items)
    await state.clear()
    if callback.message:
        try:
            await callback.message.edit_text("ЧТО?", reply_markup=keyboard)
        except Exception:
            await callback.message.answer("ЧТО?", reply_markup=keyboard)
    else:
        await callback.bot.send_message(callback.from_user.id, "ЧТО?", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("byt_defer_pick:"))
async def handle_byt_defer_pick(callback: CallbackQuery, state: FSMContext) -> None:
    """Start deferring selected BYT item."""

    data = callback.data.split(":", maxsplit=1)
    wish_id: int | None = None
    if len(data) == 2:
        try:
            wish_id = int(data[1])
        except ValueError:
            wish_id = None
    if wish_id is None:
        state_data = await state.get_data()
        try:
            wish_id = (
                int(state_data.get("defer_item_id"))
                if state_data.get("defer_item_id") is not None
                else None
            )
        except (TypeError, ValueError):
            wish_id = None
    if wish_id is None:
        await callback.answer("Ошибка: не найден item_id", show_alert=True)
        return

    started = await _start_byt_defer_flow(callback, state, wish_id)
    if not started:
        await state.clear()


@router.message(
    BytDeferState.waiting_for_days,
    F.text.in_(
        {
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "Очистить",
            "✅ Газ",
        }
    ),
)
async def handle_byt_defer_days(message: Message, state: FSMContext) -> None:
    """Handle calculator input for BYT defer days."""

    data = await state.get_data()
    current_sum = str(data.get("defer_days_str", "0"))
    display_chat_id = data.get("defer_display_chat_id", message.chat.id)
    display_message_id = data.get("defer_display_message_id")
    db = FinanceDatabase()

    if message.text == "Очистить":
        new_sum = "0"
    elif message.text == "✅ Газ":
        amount_str = current_sum.strip()
        if not amount_str:
            LOGGER.warning(
                "BYT defer submit missing entered_days user_id=%s",
                message.from_user.id if message.from_user else "unknown",
            )
            await message.answer("Нужно ввести число дней. Попробуй снова.")
            try:
                await message.delete()
            except Exception:
                pass
            return
        try:
            days = int(amount_str)
        except (TypeError, ValueError):
            LOGGER.warning(
                "BYT defer submit invalid days user_id=%s value=%s",
                message.from_user.id if message.from_user else "unknown",
                amount_str,
            )
            await message.answer("Нужно ввести число. Попробуй снова.")
            try:
                await message.delete()
            except Exception:
                pass
            return

        if days <= 0:
            LOGGER.warning(
                "BYT defer submit non-positive days user_id=%s value=%s",
                message.from_user.id if message.from_user else "unknown",
                days,
            )
            await message.answer("Нужно ввести число дней. Попробуй снова.")
            try:
                await message.delete()
            except Exception:
                pass
            return

        try:
            settings_row = db.get_user_settings(message.from_user.id)
        except Exception as exc:
            LOGGER.error(
                "Failed to load user settings for BYT defer user_id=%s",
                message.from_user.id if message.from_user else "unknown",
                exc_info=exc,
            )
            await message.answer("Ошибка БД")
            try:
                await message.delete()
            except Exception:
                pass
            return
        max_days = int(settings_row.get("byt_defer_max_days", 365) or 365)
        if days < 1 or days > max_days:
            await message.answer(f"Количество дней должно быть от 1 до {max_days}.")
            try:
                await message.delete()
            except Exception:
                pass
            return

        raw_defer_item_id = data.get("defer_item_id")
        try:
            defer_item_id = int(raw_defer_item_id) if raw_defer_item_id is not None else None
        except (TypeError, ValueError):
            defer_item_id = None
        if defer_item_id is None:
            LOGGER.warning(
                "BYT defer submit missing item_id user_id=%s",
                message.from_user.id if message.from_user else "unknown",
            )
            await message.answer("Не выбран товар для отсрочки.")
            await state.clear()
            try:
                await message.delete()
            except Exception:
                pass
            return
        reminder_message_id = data.get("reminder_message_id")
        deferred_until = now_tz() + timedelta(days=days)

        try:
            db.set_wishlist_item_deferred_until(
                message.from_user.id, defer_item_id, deferred_until.isoformat()
            )
        except Exception as exc:
            LOGGER.error(
                "Failed to set BYT defer days user_id=%s item_id=%s days=%s",
                message.from_user.id if message.from_user else "unknown",
                defer_item_id,
                days,
                exc_info=exc,
            )
            await message.answer("Ошибка БД")
            try:
                await message.delete()
            except Exception:
                pass
            return

        LOGGER.info(
            "BYT defer days submit user_id=%s item_id=%s days=%s",
            message.from_user.id if message.from_user else "unknown",
            defer_item_id,
            days,
        )

        await state.clear()
        await message.answer(
            f"Отложено на {days} дн.", reply_markup=ReplyKeyboardRemove()
        )

        if reminder_message_id:
            await _refresh_byt_reminder_message(
                message.bot,
                message.chat.id,
                int(reminder_message_id),
                message.from_user.id,
            )

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

    new_display_message_id = display_message_id
    new_display_chat_id = display_chat_id
    if display_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=display_chat_id,
                message_id=int(display_message_id),
                text=f": {new_sum}",
            )
        except Exception:
            try:
                prompt = await message.answer(f": {new_sum}")
                new_display_message_id = prompt.message_id
                new_display_chat_id = message.chat.id
            except Exception:
                pass
    else:
        try:
            prompt = await message.answer(f": {new_sum}")
            new_display_message_id = prompt.message_id
            new_display_chat_id = message.chat.id
        except Exception:
            pass

    await state.update_data(
        defer_days_str=new_sum,
        defer_display_message_id=new_display_message_id,
        defer_display_chat_id=new_display_chat_id,
    )

    try:
        await message.delete()
    except Exception:
        pass


@router.message(BytDeferState.waiting_for_days)
async def handle_byt_defer_days_invalid(message: Message) -> None:
    """Prompt to use calculator buttons for defer days."""

    await message.answer("Используй кнопки калькулятора ниже.")
