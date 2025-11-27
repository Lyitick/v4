"""Handlers for wishlist flow."""
import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database.crud import FinanceDatabase
from keyboards.main import (
    main_menu_keyboard,
    wishlist_categories_keyboard,
    wishlist_reply_keyboard,
    wishlist_url_keyboard,
)
from states.wishlist_states import WishlistState

LOGGER = logging.getLogger(__name__)

router = Router()

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
    await message.answer("Введи название желания.")


@router.message(WishlistState.waiting_for_name)
async def add_wish_name(message: Message, state: FSMContext) -> None:
    """Save wish name and request price."""

    await state.update_data(name=message.text)
    await state.set_state(WishlistState.waiting_for_price)
    await message.answer("Введи цену (только цифры).")


@router.message(WishlistState.waiting_for_price)
async def add_wish_price(message: Message, state: FSMContext) -> None:
    """Validate and save price."""

    try:
        price = float(message.text.replace(",", "."))
    except (TypeError, ValueError):
        await message.answer("Нужно ввести число. Попробуй снова.")
        return

    if price <= 0:
        await message.answer("Цена должна быть больше нуля. Попробуй снова.")
        return

    await state.update_data(price=price)
    await state.set_state(WishlistState.waiting_for_url)
    await message.answer("Дай ссылку", reply_markup=wishlist_url_keyboard())


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
        raw_category = purchase.get("category", "")
        human_category = humanize_wishlist_category(raw_category)
        groups[human_category].append(purchase)

    # Заголовки категорий с эмодзи
    CATEGORY_HEADERS: dict[str, str] = {
        "инвестиции в работу": "💼💼💼 Инвестиции в работу 💼💼💼",
        "вклад в себя": "📚📚📚 Вклад в себя 📚📚📚",
        "кайфы": "🎉🎉🎉 Кайфы 🎉🎉🎉",
    }

    def format_date(purchased_at: str) -> str:
        """Преобразовать дату к виду ДД.ММ.ГГГГ без времени."""
        if not purchased_at:
            return ""
        # Пытаемся распарсить ISO-формат: '2025-11-27 12:34:56' или '2025-11-27'
        try:
            # Обрезаем время, если есть
            base = purchased_at.split()[0]
            dt = datetime.fromisoformat(base)
            return dt.strftime("%d.%m.%Y")
        except Exception:
            # Фолбэк: если формат неожиданно другой — возвращаем как есть
            return purchased_at

    def format_price(value: float) -> str:
        """Формат цены: 3000.00 -> '3 000.00'."""
        # Используем английский формат с запятой и заменяем запятые на пробелы
        return f"{value:,.2f}".replace(",", " ")

    lines: list[str] = []

    # Фиксированный порядок категорий
    ordered_categories = ["инвестиции в работу", "вклад в себя", "кайфы"]

    for category_key in ordered_categories:
        items = groups.get(category_key)
        if not items:
            continue

        # Заголовок категории
        header = CATEGORY_HEADERS.get(category_key, category_key)
        lines.append(header)

        # Перебираем покупки внутри категории
        for purchase in items:
            name = purchase.get("wish_name", "Без названия")
            price_raw = purchase.get("price", 0) or 0
            try:
                price = float(price_raw)
            except (TypeError, ValueError):
                price = 0.0

            price_str = format_price(price)

            # URL может отсутствовать в таблице purchases — в этом случае считаем, что ссылки нет.
            url = purchase.get("url") or ""
            url_part = url if url else "---"

            date_str = format_date(purchase.get("purchased_at", ""))

            # Итоговая строка:
            # • Имя — 1 234.00 ₽ — ссылка/без ссылки — 21.11.2025
            line_parts = [
                f"• {name}",
                f"{price_str} ₽",
                url_part,
            ]
            if date_str:
                line_parts.append(date_str)

            lines.append(" — ".join(line_parts))

        # Пустая строка между категориями
        lines.append("")

    # Если по каким-то причинам ни одна категория не попала (например, нестандартные категории),
    # делаем фолбэк к простому списку.
    if not lines:
        fallback_lines: list[str] = []
        for purchase in purchases:
            category = humanize_wishlist_category(purchase.get("category", ""))
            price_raw = purchase.get("price", 0) or 0
            try:
                price = float(price_raw)
            except (TypeError, ValueError):
                price = 0.0
            price_str = format_price(price)
            date_str = format_date(purchase.get("purchased_at", ""))
            fallback_lines.append(
                f"{purchase.get('wish_name', 'Без названия')} — {price_str} ₽ ({category}) куплено {date_str}"
            )

        await message.answer("\n".join(fallback_lines), reply_markup=main_menu_keyboard())
        return

    # Отправляем красиво отформатированный список
    await message.answer("\n".join(lines).strip(), reply_markup=main_menu_keyboard())


@router.message(WishlistState.waiting_for_price)
async def invalid_price(message: Message) -> None:
    """Handle invalid price input."""

    await message.answer("Нужно ввести число. Попробуй снова.")


@router.message(WishlistState.waiting_for_category)
async def waiting_category_text(message: Message) -> None:
    """Prompt to use inline keyboard for category."""

    await message.answer("Выбери категорию через кнопки ниже.", reply_markup=wishlist_categories_keyboard())
