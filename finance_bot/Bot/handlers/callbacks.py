"""Callback query handlers."""
import logging
from typing import Dict
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from Bot.database.get_db import get_db
from Bot.handlers.common import build_main_menu_for_user
from Bot.handlers.finances import (
    _format_savings_summary,
    show_affordable_wishes,
)
from Bot.keyboards.main import back_only_keyboard, wishlist_categories_keyboard
from Bot.states.wishlist_states import WishlistState
from Bot.handlers.wishlist import (
    _get_user_wishlist_categories,
    humanize_wishlist_category,
)
from Bot.utils.telegram_safe import (
    safe_answer,
    safe_callback_answer,
    safe_delete_message,
    safe_edit_message_text,
)
from Bot.utils.ui_cleanup import ui_register_message

LOGGER = logging.getLogger(__name__)

router = Router()

@router.callback_query(F.data.startswith("wlcat:"))
async def handle_category_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle category selection for viewing or adding wishes."""

    await safe_callback_answer(callback, logger=LOGGER)
    try:
        category_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await safe_callback_answer(callback, "Некорректная категория", show_alert=True, logger=LOGGER)
        return

    db = get_db()
    category_row = db.get_wishlist_category_by_id(callback.from_user.id, category_id)
    if not category_row:
        await safe_callback_answer(callback, "Категория не найдена", show_alert=True, logger=LOGGER)
        return

    category_code = category_row.get("title", "")
    category = humanize_wishlist_category(category_code)
    category_code_norm = "byt" if category == "БЫТ" else category_code
    data = await state.get_data()
    current_state = await state.get_state()

    if current_state == WishlistState.waiting_for_category.state:
        await _finalize_wish(callback, state, category_code_norm, category)
        return

    await _send_wishes_list(callback, category)


@router.callback_query(F.data == "wishlist_skip_url")
async def skip_wishlist_url(callback: CallbackQuery, state: FSMContext) -> None:
    """Skip wishlist URL step via inline button."""

    await safe_callback_answer(callback, logger=LOGGER)
    current_state = await state.get_state()
    if current_state != WishlistState.waiting_for_url.state:
        return

    await state.update_data(url=None)
    await state.set_state(WishlistState.waiting_for_category)
    data = await state.get_data()
    stack = list(data.get("wl_add_step_stack") or [])
    if not stack or stack[-1] != "category":
        stack.append("category")
    await state.update_data(wl_add_step_stack=stack)
    if callback.message:
        await safe_delete_message(
            callback.message.bot,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            logger=LOGGER,
        )
        categories = _get_user_wishlist_categories(get_db(), callback.from_user.id)
        if not categories:
            await safe_answer(
                callback.message,
                "Категорий вишлиста пока нет. Добавь их в настройках.",
                reply_markup=back_only_keyboard(),
                logger=LOGGER,
            )
            await state.clear()
            return
        await safe_answer(
            callback.message,
            "Выбери категорию желания.",
            reply_markup=wishlist_categories_keyboard(
                categories
            ),
            logger=LOGGER,
        )
        await safe_answer(
            callback.message,
            "Если нужно, нажми ⬅️ Назад.",
            reply_markup=back_only_keyboard(),
            logger=LOGGER,
        )


async def _finalize_wish(
    callback: CallbackQuery,
    state: FSMContext,
    category_code: str,
    humanized_category: str,
) -> None:
    """Finalize wish creation after category selection."""

    db = get_db()
    data = await state.get_data()
    wish_id = db.add_wish(
        user_id=callback.from_user.id,
        name=data.get("name", ""),
        price=float(data.get("price", 0)),
        url=data.get("url"),
        category=category_code,
    )
    lines = [
        f"Категория: {humanized_category}",
        f"Название: {data.get('name')}",
        f"Цена: {data.get('price')}",
        f"ID: {wish_id}",
    ]
    url = data.get("url")
    if url:
        lines.insert(3, f"Ссылка: {url}")
    if callback.message:
        info_id = await safe_answer(callback.message, "\n".join(lines), logger=LOGGER)
        if info_id:
            await ui_register_message(state, callback.message.chat.id, info_id)
        sent_id = await safe_answer(
            callback.message,
            "✅ Желание добавлено",
            reply_markup=await build_main_menu_for_user(callback.from_user.id),
            logger=LOGGER,
        )
        if sent_id:
            await ui_register_message(state, callback.message.chat.id, sent_id)
    await state.clear()
    LOGGER.info("User %s added wish %s", callback.from_user.id, wish_id)


async def _send_wishes_list(callback: CallbackQuery, category: str) -> None:
    """Send wishlist items for selected category."""

    db = get_db()
    wishes = db.get_wishes_by_user(callback.from_user.id)
    savings_map = db.get_user_savings_map(callback.from_user.id)
    debit_category = db.get_wishlist_debit_category(callback.from_user.id)
    saved_amount = (
        float(savings_map.get(debit_category, 0.0) or 0.0) if debit_category else 0.0
    )
    filtered = [
        wish
        for wish in wishes
        if (
            humanize_wishlist_category(wish.get("category", ""))
            == humanize_wishlist_category(category)
        )
        and not wish.get("is_purchased")
    ]

    if not filtered:
        if callback.message:
            edited = await safe_edit_message_text(
                callback.message.bot,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text="Желаний в этой категории пока нет.",
                reply_markup=wishlist_categories_keyboard(
                    _get_user_wishlist_categories(db, callback.from_user.id)
                ),
                logger=LOGGER,
            )
            if not edited:
                await safe_answer(
                    callback.message,
                    "Желаний в этой категории пока нет.",
                    reply_markup=wishlist_categories_keyboard(
                        _get_user_wishlist_categories(db, callback.from_user.id)
                    ),
                    logger=LOGGER,
                )
        return

    for wish in filtered:
        wishlist_category = humanize_wishlist_category(wish.get("category", ""))
        price = float(wish.get("price", 0) or 0.0)

        if price > 0:
            progress = min(saved_amount / price, 1.0)
        else:
            progress = 0.0
        total_blocks = 10
        filled_blocks = int(progress * total_blocks)
        bar = "■" * filled_blocks + "□" * (total_blocks - filled_blocks)
        remaining = max(price - saved_amount, 0.0)
        progress_percent = round(progress * 100)

        lines = [
            f"{wish['name']} — {price:.2f} ({wishlist_category})",
            f"Прогресс: {bar} {progress_percent}%",
            f"Накоплено: {saved_amount:.2f}, осталось: {remaining:.2f}",
        ]
        if wish.get("url"):
            lines.append(f"Ссылка: {wish['url']}")
        text = "\n".join(lines)
        inline_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Купил", callback_data=f"wish_buy_{wish['id']}")]]
        )
        if callback.message:
            await safe_answer(callback.message, text, reply_markup=inline_kb, logger=LOGGER)


@router.callback_query(F.data.startswith("wish_buy_"))
async def handle_wish_purchase(callback: CallbackQuery) -> None:
    """Handle purchase of a wish."""

    await safe_callback_answer(callback, logger=LOGGER)
    wish_id = int(callback.data.split("wish_buy_")[-1])
    db = get_db()
    wish = db.get_wish(wish_id)

    if not wish:
        await safe_callback_answer(callback, "Желание не найдено.", show_alert=True, logger=LOGGER)
        return
    if wish.get("is_purchased") or wish.get("debited_at"):
        await safe_callback_answer(callback, "Уже отмечено как купленное.", logger=LOGGER)
        return

    wishlist_category = humanize_wishlist_category(wish.get("category"))
    price = float(wish.get("price", 0) or 0.0)
    LOGGER.info(
        "USER=%s ACTION=WISHLIST_PURCHASE META=item_id=%s price=%.2f",
        callback.from_user.id,
        wish_id,
        price,
    )
    debit_category = db.get_wishlist_debit_category(callback.from_user.id)

    if debit_category is not None:
        income_category = db.get_income_category_by_code(callback.from_user.id, debit_category)
        if not income_category:
            await safe_callback_answer(
                "Не удалось списать: категория не найдена/удалена. Выберите категорию списания в настройках Wishlist.",
                show_alert=True,
                logger=LOGGER,
            )
            return

    result = db.purchase_wish(callback.from_user.id, wish_id, debit_category)
    status = result.get("status")
    if status == "not_found":
        await safe_callback_answer(callback, "Желание не найдено.", show_alert=True, logger=LOGGER)
        return
    if status == "already":
        await safe_callback_answer(callback, "Уже отмечено как купленное.", logger=LOGGER)
        return
    if status == "insufficient":
        await safe_callback_answer(
            (
                "Недостаточно средств в накоплениях для этой категории.\n"
                f"Нужно: {price:.2f}, доступно: {float(result.get('available', 0.0)):.2f}."
            ),
            show_alert=True,
            logger=LOGGER,
        )
        return
    if status == "error":
        await safe_callback_answer(
            "Не удалось списать: ошибка базы данных.",
            show_alert=True,
            logger=LOGGER,
        )
        return

    if callback.message:
        await safe_edit_message_text(
            callback.message.bot,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=f"🎉 Поздравляю, ты купил {wish['name']} за {price:.2f}!",
            logger=LOGGER,
        )
    if status == "debited":
        LOGGER.info(
            "USER=%s ACTION=WISHLIST_DEBIT META=category=%s amount=%.2f item_id=%s",
            callback.from_user.id,
            debit_category,
            price,
            wish_id,
        )
        savings = db.get_user_savings(callback.from_user.id)
        categories_map = db.get_income_categories_map(callback.from_user.id)
        summary = _format_savings_summary(savings, categories_map)
        if callback.message:
            await safe_answer(
                callback.message, f"Обновлённые накопления:\n{summary}", logger=LOGGER
            )
            await show_affordable_wishes(
                message=callback.message, user_id=callback.from_user.id, db=db
            )


@router.callback_query(F.data == "affordable_wishes_later")
async def handle_affordable_wishes_later(callback: CallbackQuery, state: FSMContext) -> None:
    """Close affordable wish suggestions and return to main menu."""

    await safe_callback_answer(callback, logger=LOGGER)
    await state.clear()
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            LOGGER.debug("Failed to clear inline keyboard for affordable wishes", exc_info=True)
        sent_id = await safe_answer(
            callback.message,
            "Хорошо, вернёмся к покупкам позже. Главное меню.",
            reply_markup=await build_main_menu_for_user(callback.from_user.id),
            logger=LOGGER,
        )
        if sent_id:
            await ui_register_message(state, callback.message.chat.id, sent_id)
