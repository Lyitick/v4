"""Handlers for wishlist flow."""

import asyncio
import logging
from collections import defaultdict
from datetime import timedelta
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from Bot.database.crud import FinanceDatabase
from Bot.handlers.common import build_main_menu_for_user
from Bot.keyboards.main import (
    wishlist_categories_keyboard,
    wishlist_reply_keyboard,
    wishlist_reply_keyboard_no_add,
    wishlist_url_keyboard,
)
from Bot.keyboards.calculator import income_calculator_keyboard
from Bot.states.wishlist_states import BytDeferState, WishlistState
from Bot.utils.datetime_utils import now_tz

LOGGER = logging.getLogger(__name__)

router = Router()


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


@router.message(F.text == "➕")
async def add_wish_start(message: Message, state: FSMContext) -> None:
    """Start adding wish."""

    await state.set_state(WishlistState.waiting_for_name)
    await message.answer(
        "Введи название желания.",
        reply_markup=wishlist_reply_keyboard_no_add(),
    )


@router.message(WishlistState.waiting_for_name)
async def add_wish_name(message: Message, state: FSMContext) -> None:
    """Save wish name and request price."""

    await state.update_data(name=message.text)
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
        await message.answer("дай", reply_markup=ReplyKeyboardRemove())
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


@router.message(WishlistState.waiting_for_url)
async def add_wish_url(message: Message, state: FSMContext) -> None:
    """Save URL and request category selection."""

    text = message.text.strip() if message.text else ""
    url: Optional[str] = None if text in {"-", ""} else text
    await state.update_data(url=url)
    await state.set_state(WishlistState.waiting_for_category)
    db = FinanceDatabase()
    categories = _get_user_wishlist_categories(db, message.from_user.id)
    await message.answer(
        "Выбери категорию желания.", reply_markup=wishlist_categories_keyboard(categories)
    )


@router.message(F.text == "Купленное")
async def show_purchases(message: Message) -> None:
    """Show purchased items grouped by category with pretty headers."""

    db = FinanceDatabase()
    purchases = db.get_purchases_by_user(message.from_user.id)

    # Если покупок нет — сразу выходим
    if not purchases:
        await message.answer(
            "Список покупок пуст.",
            reply_markup=await build_main_menu_for_user(message.from_user.id),
        )
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

    await message.answer(
        "\n".join(lines),
        reply_markup=await build_main_menu_for_user(message.from_user.id),
    )


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
        rows.append(
            [InlineKeyboardButton(text="ОТЛОЖИТЬ", callback_data="byt_defer_menu")]
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


async def run_byt_wishlist_reminders(
    bot: Bot,
    db: FinanceDatabase,
    user_id: int | None = None,
    forced: bool = False,
    run_time=None,
) -> None:
    """Run BYT reminders for users with active BYT wishes."""

    await asyncio.sleep(0)
    now_dt = run_time or now_tz()
    db.cleanup_old_byt_purchases(now_dt)
    user_ids = [user_id] if user_id else db.get_users_with_active_byt_wishes()
    if not user_ids:
        return

    is_evening = now_dt.hour == 18

    for uid in user_ids:
        settings_row = db.get_user_settings(uid)
        if not bool(settings_row.get("byt_reminders_enabled", 1)):
            continue
        items = db.list_active_byt_items_for_reminder(uid, now_dt)
        if not items:
            continue

        allow_defer = bool(settings_row.get("byt_defer_enabled", 1))
        keyboard = _build_byt_items_keyboard(items, allow_defer=allow_defer)
        await bot.send_message(uid, "Что ты купил?", reply_markup=keyboard)


@router.message(F.text == "12:00")
async def trigger_byt_reminder_test(message: Message) -> None:
    """Trigger BYT reminder sequence for current user (test button)."""

    db = FinanceDatabase()
    await run_byt_wishlist_reminders(
        message.bot, db, user_id=message.from_user.id, forced=True, run_time=now_tz()
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


@router.callback_query(F.data == "byt_defer_menu")
async def handle_byt_defer_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Show BYT items to choose which to defer."""

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


@router.callback_query(F.data == "byt_defer_menu")
async def handle_byt_defer_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Show BYT items to choose which to defer."""

    db = FinanceDatabase()
    settings_row = db.get_user_settings(callback.from_user.id)
    if not bool(settings_row.get("byt_defer_enabled", 1)):
        await callback.answer("Отключено в настройках", show_alert=True)
        return
    now_dt = now_tz()
    items = db.list_active_byt_items_for_reminder(callback.from_user.id, now_dt)
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
    if len(data) != 2:
        await callback.answer("Некорректный выбор.", show_alert=True)
        return

    try:
        item_id = int(data[1])
    except ValueError:
        await callback.answer("Некорректный выбор.", show_alert=True)
        return

    db = FinanceDatabase()
    wish = db.get_wish(item_id)
    if not wish or humanize_wishlist_category(wish.get("category", "")) != "БЫТ":
        await callback.answer("Элемент не найден.", show_alert=True)
        return
    settings_row = db.get_user_settings(callback.from_user.id)
    if not bool(settings_row.get("byt_defer_enabled", 1)):
        await callback.answer("Отключено в настройках", show_alert=True)
        await state.clear()
        return

    await state.set_state(BytDeferState.waiting_for_days)
    await state.update_data(
        defer_item_id=item_id,
        defer_days_str="0",
        reminder_message_id=callback.message.message_id if callback.message else None,
    )

    await callback.answer()
    await callback.message.answer("На сколько дней отложить?")
    prompt = await callback.message.answer(": 0", reply_markup=income_calculator_keyboard())
    await state.update_data(
        defer_display_chat_id=callback.message.chat.id
        if callback.message
        else callback.from_user.id,
        defer_display_message_id=prompt.message_id,
    )


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

    if message.text == "Очистить":
        new_sum = "0"
    elif message.text == "✅ Газ":
        amount_str = current_sum.strip()
        try:
            days = int(amount_str)
        except (TypeError, ValueError):
            await message.answer("Нужно ввести число. Попробуй снова.")
            try:
                await message.delete()
            except Exception:
                pass
            return

        settings_row = db.get_user_settings(message.from_user.id)
        max_days = int(settings_row.get("byt_defer_max_days", 365) or 365)
        if days < 1 or days > max_days:
            await message.answer(f"Количество дней должно быть от 1 до {max_days}.")
            try:
                await message.delete()
            except Exception:
                pass
            return

        defer_item_id = data.get("defer_item_id")
        reminder_message_id = data.get("reminder_message_id")
        deferred_until = now_tz() + timedelta(days=days)

        db = FinanceDatabase()
        db.set_wishlist_item_deferred_until(
            message.from_user.id, int(defer_item_id), deferred_until.isoformat()
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
