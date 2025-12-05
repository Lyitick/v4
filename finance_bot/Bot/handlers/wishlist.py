"""Handlers for wishlist flow."""

import logging
from collections import defaultdict
from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from Bot.database.crud import FinanceDatabase
from Bot.keyboards.main import (
    main_menu_keyboard,
    wishlist_categories_keyboard,
    wishlist_reply_keyboard,
    wishlist_reply_keyboard_no_add,
)
from Bot.keyboards.calculator import income_calculator_keyboard
from Bot.states.wishlist_states import WishlistState

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
    }
    return mapping.get(category, category)


@router.message(F.text == "📋 Вишлист")
async def open_wishlist(message: Message, state: FSMContext) -> None:
    """Open wishlist menu."""

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
        await message.answer("Список покупок пуст.", reply_markup=main_menu_keyboard())
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

    await message.answer("\n".join(lines), reply_markup=main_menu_keyboard())


@router.message(WishlistState.waiting_for_price)
async def invalid_price(message: Message) -> None:
    """Handle invalid price input."""

    await message.answer("Используй кнопки калькулятора ниже для ввода цены.")


@router.message(WishlistState.waiting_for_category)
async def waiting_category_text(message: Message) -> None:
    """Prompt to use inline keyboard for category."""

    await message.answer("Выбери категорию через кнопки ниже.", reply_markup=wishlist_categories_keyboard())
