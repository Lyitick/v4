"""Handlers for wishlist flow."""

import asyncio
import logging
from collections import defaultdict
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram import Dispatcher

from Bot.database.crud import FinanceDatabase
from Bot.handlers.common import build_main_menu_for_user
from Bot.keyboards.main import (
    wishlist_categories_keyboard,
    wishlist_reply_keyboard,
    wishlist_reply_keyboard_no_add,
)
from Bot.keyboards.calculator import income_calculator_keyboard
from Bot.states.wishlist_states import WishlistBytReminderState, WishlistState
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

_reminder_dispatcher: Dispatcher | None = None


def set_reminder_dispatcher(dispatcher: Dispatcher) -> None:
    """Store dispatcher for reminder FSM usage."""

    global _reminder_dispatcher
    _reminder_dispatcher = dispatcher


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


async def _get_byt_reminder_state(bot: Bot, user_id: int) -> FSMContext:
    """Return FSM context for BYT reminder processing."""

    if _reminder_dispatcher is None:
        raise RuntimeError("Reminder dispatcher is not configured")
    return _reminder_dispatcher.fsm.get_context(bot=bot, chat_id=user_id, user_id=user_id)


@router.message(F.text == "📋 Вишлист")
async def open_wishlist(message: Message, state: FSMContext) -> None:
    """Open wishlist menu."""

    await delete_welcome_message_if_exists(message, state)
    await state.clear()
    db = FinanceDatabase()
    wishes = db.get_wishes_by_user(message.from_user.id)
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
        reply_markup=wishlist_categories_keyboard(),
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
        await message.answer(
            "Дай ссылку на желание.\n"
            "Если ссылки нет — просто напиши «-».",
            reply_markup=wishlist_reply_keyboard_no_add(),
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
    await message.answer("Выбери категорию желания.", reply_markup=wishlist_categories_keyboard())


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

    await message.answer("Выбери категорию через кнопки ниже.", reply_markup=wishlist_categories_keyboard())


def _byt_reminder_keyboard(item_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard for BYT reminder yes/no."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да", callback_data=f"byt_reminder_yes_{item_id}"
                ),
                InlineKeyboardButton(
                    text="Нет", callback_data=f"byt_reminder_no_{item_id}"
                ),
            ]
        ]
    )


async def _ask_next_byt_item(
    bot: Bot, db: FinanceDatabase, state: FSMContext, user_id: int
) -> None:
    """Ask next BYT wishlist question or finish."""

    data = await state.get_data()
    queue = data.get("reminder_queue", []) or []
    if not queue:
        await state.clear()
        await bot.send_message(
            chat_id=user_id,
            text="Напоминания по БЫТ завершены.",
            reply_markup=await build_main_menu_for_user(user_id),
        )
        return

    item_id = queue.pop(0)
    wish = db.get_wish(item_id)
    if not wish or humanize_wishlist_category(wish.get("category", "")) != "БЫТ":
        await state.update_data(reminder_queue=queue)
        await _ask_next_byt_item(bot, db, state, user_id)
        return

    await state.update_data(reminder_queue=queue, current_item_id=item_id)
    await bot.send_message(
        chat_id=user_id,
        text=f"Ты купил({wish.get('name', '')})?",
        reply_markup=_byt_reminder_keyboard(item_id),
    )


async def run_byt_wishlist_reminders(
    bot: Bot, db: FinanceDatabase, user_id: int | None = None, forced: bool = False
) -> None:
    """Run BYT reminders for users with active BYT wishes."""

    await asyncio.sleep(0)
    db.cleanup_old_byt_purchases(now_tz())
    user_ids = [user_id] if user_id else db.get_users_with_active_byt_wishes()
    if not user_ids:
        return

    for uid in user_ids:
        state = await _get_byt_reminder_state(bot, uid)
        state_name = await state.get_state()
        if state_name:
            if not forced:
                continue
            await state.clear()
        wishes = db.get_active_byt_wishes(uid)
        if not wishes:
            continue
        queue = [wish["id"] for wish in wishes]
        await state.set_state(WishlistBytReminderState.waiting_answer)
        await state.update_data(reminder_queue=queue, current_item_id=None)
        await _ask_next_byt_item(bot, db, state, uid)


@router.message(F.text == "12:00")
async def trigger_byt_reminder_test(message: Message) -> None:
    """Trigger BYT reminder sequence for current user (test button)."""

    db = FinanceDatabase()
    await run_byt_wishlist_reminders(
        message.bot, db, user_id=message.from_user.id, forced=True
    )


async def _handle_byt_reminder_response(
    callback: CallbackQuery, state: FSMContext, is_confirmed: bool
) -> None:
    """Process BYT reminder response and move to next item."""

    current_state = await state.get_state()
    if current_state != WishlistBytReminderState.waiting_answer:
        await callback.answer()
        return

    data = await state.get_data()
    current_item_id = data.get("current_item_id")
    if current_item_id is None:
        await callback.answer()
        return

    db = FinanceDatabase()
    wish = db.get_wish(int(current_item_id))
    user_id = callback.from_user.id

    if not wish or humanize_wishlist_category(wish.get("category", "")) != "БЫТ":
        await callback.answer("Элемент не найден.", show_alert=True)
        await _ask_next_byt_item(callback.bot, db, state, user_id)
        return

    if is_confirmed:
        price = float(wish.get("price", 0) or 0)
        purchase_time = now_tz()
        db.decrease_savings(user_id, "быт", price)
        db.mark_wish_purchased(int(current_item_id), purchased_at=purchase_time)
        db.add_purchase(
            user_id,
            wish.get("name", ""),
            price,
            humanize_wishlist_category(wish.get("category", "")),
            purchased_at=purchase_time,
        )
        await callback.message.answer(
            f"Отметил покупку {wish.get('name', '')} за {price:.2f} ₽."
        )

    await callback.answer()
    await _ask_next_byt_item(callback.bot, db, state, user_id)


@router.callback_query(F.data.startswith("byt_reminder_yes_"))
async def handle_byt_reminder_yes(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle affirmative answer for BYT reminder."""

    await _handle_byt_reminder_response(callback, state, is_confirmed=True)


@router.callback_query(F.data.startswith("byt_reminder_no_"))
async def handle_byt_reminder_no(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle negative answer for BYT reminder."""

    await _handle_byt_reminder_response(callback, state, is_confirmed=False)
