"""Callback query handlers."""
import logging
from typing import Dict

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from Bot.database.crud import FinanceDatabase
from Bot.keyboards.main import wishlist_categories_keyboard
from Bot.states.wishlist_states import WishlistState

LOGGER = logging.getLogger(__name__)

router = Router()

CATEGORY_MAP: Dict[str, str] = {
    "wishlist_cat_tools": "Инструменты",
    "wishlist_cat_currency": "Финансы",
    "wishlist_cat_magic": "Разное",
}


@router.callback_query(F.data.in_(CATEGORY_MAP.keys()))
async def handle_category_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle category selection for viewing or adding wishes."""

    category = CATEGORY_MAP.get(callback.data, "")
    data = await state.get_data()
    current_state = await state.get_state()

    if current_state == WishlistState.waiting_for_category.state:
        await _finalize_wish(callback, state, category)
        return

    await _send_wishes_list(callback, category)


async def _finalize_wish(callback: CallbackQuery, state: FSMContext, category: str) -> None:
    """Finalize wish creation after category selection."""

    db = FinanceDatabase()
    data = await state.get_data()
    wish_id = db.add_wish(
        user_id=callback.from_user.id,
        name=data.get("name", ""),
        price=float(data.get("price", 0)),
        url=data.get("url"),
        category=category,
    )
    await callback.message.edit_text(
        f"✅ Желание добавлено: {data.get('name')} за {data.get('price')} ({category}). ID: {wish_id}"
    )
    await state.clear()
    LOGGER.info("User %s added wish %s", callback.from_user.id, wish_id)


async def _send_wishes_list(callback: CallbackQuery, category: str) -> None:
    """Send wishlist items for selected category."""

    db = FinanceDatabase()
    wishes = db.get_wishes_by_user(callback.from_user.id)
    filtered = [wish for wish in wishes if wish.get("category") == category and not wish.get("is_purchased")]

    if not filtered:
        await callback.message.edit_text("Желаний в этой категории пока нет.", reply_markup=wishlist_categories_keyboard())
        return

    for wish in filtered:
        text = f"{wish['name']} — {wish['price']:.2f}. Накоплено: {wish.get('saved_amount', 0):.2f}"
        if wish.get("url"):
            text += f"\nСсылка: {wish['url']}"
        inline_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Купил", callback_data=f"wish_buy_{wish['id']}")]]
        )
        await callback.message.answer(text, reply_markup=inline_kb)


@router.callback_query(F.data.startswith("wish_buy_"))
async def handle_wish_purchase(callback: CallbackQuery) -> None:
    """Handle purchase of a wish."""

    wish_id = int(callback.data.split("wish_buy_")[-1])
    db = FinanceDatabase()
    wish = db.get_wish(wish_id)

    if not wish:
        await callback.answer("Желание не найдено.", show_alert=True)
        return

    savings = db.get_user_savings(callback.from_user.id)
    category = wish.get("category")
    category_savings = savings.get(category, {}).get("current", 0)

    if category_savings < wish.get("price", 0):
        await callback.answer("Недостаточно средств в накоплениях для этой категории.", show_alert=True)
        return

    db.update_saving(callback.from_user.id, category, -wish["price"])
    db.mark_wish_purchased(wish_id)
    db.add_purchase(callback.from_user.id, wish["name"], wish["price"], category)

    await callback.message.edit_text(f"Поздравляю, ты купил {wish['name']} за {wish['price']:.2f}!")
    LOGGER.info("User %s purchased wish %s", callback.from_user.id, wish_id)
