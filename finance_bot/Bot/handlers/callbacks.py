"""Callback query handlers."""
import logging
from typing import Dict

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from database.crud import FinanceDatabase
from keyboards.main import wishlist_categories_keyboard
from states.wishlist_states import WishlistState
from handlers.wishlist import WISHLIST_CATEGORY_TO_SAVINGS_CATEGORY

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
    savings_map = db.get_user_savings_map(callback.from_user.id)
    filtered = [wish for wish in wishes if wish.get("category") == category and not wish.get("is_purchased")]

    if not filtered:
        await callback.message.edit_text("Желаний в этой категории пока нет.", reply_markup=wishlist_categories_keyboard())
        return

    for wish in filtered:
        savings_category = WISHLIST_CATEGORY_TO_SAVINGS_CATEGORY.get(wish.get("category", ""), "")
        saved_amount = savings_map.get(savings_category, 0)
        text = f"{wish['name']} — {wish['price']:.2f}. Накоплено: {saved_amount:.2f}"
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

    wishlist_category = wish.get("category")
    savings_category = WISHLIST_CATEGORY_TO_SAVINGS_CATEGORY.get(wishlist_category)

    if not savings_category:
        LOGGER.error(
            "No savings mapping for wishlist category %s (wish_id=%s, user_id=%s)",
            wishlist_category,
            wish_id,
            callback.from_user.id,
        )
        await callback.answer(
            "Эта категория не привязана к накоплениям, настрой её позже.",
            show_alert=True,
        )
        return

    savings_map = db.get_user_savings_map(callback.from_user.id)
    category_savings = savings_map.get(savings_category, 0.0)
    price = float(wish.get("price", 0) or 0.0)

    if category_savings < price:
        await callback.answer(
            (
                "Недостаточно средств в накоплениях для этой категории.\n"
                f"Нужно: {price:.2f}, доступно: {category_savings:.2f}."
            ),
            show_alert=True,
        )
        return

    db.update_saving(callback.from_user.id, savings_category, -price)
    db.mark_wish_purchased(wish_id)
    db.add_purchase(callback.from_user.id, wish["name"], price, wishlist_category)

    await callback.message.edit_text(f"🎉 Поздравляю, ты купил {wish['name']} за {price:.2f}!")
    LOGGER.info(
        "User %s purchased wish %s (wishlist_category=%s, savings_category=%s, price=%.2f, savings_before=%.2f)",
        callback.from_user.id,
        wish_id,
        wishlist_category,
        savings_category,
        price,
        category_savings,
    )
