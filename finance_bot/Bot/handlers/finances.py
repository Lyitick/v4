"""Handlers for income calculation and savings."""
import logging
from contextlib import suppress
from typing import Any, Dict, List, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from database.crud import FinanceDatabase
from keyboards.main import (
    back_to_main_keyboard,
    main_menu_keyboard,
    purchase_confirmation_keyboard,
    yes_no_inline_keyboard,
)
from states.money_states import MoneyState
from handlers.wishlist import WISHLIST_CATEGORY_TO_SAVINGS_CATEGORY, humanize_wishlist_category

LOGGER = logging.getLogger(__name__)

router = Router()

distribution_scheme = [
    {"label": "Убил боль?", "category": "долги", "percent": 30},
    {"label": "Покушал?", "category": "быт", "percent": 20},
    {"label": "Инвестиции", "category": "инвестиции", "percent": 20},
    {"label": "Сбережения", "category": "сбережения", "percent": 20},
    {"label": "Ну и на хуйню?", "category": "спонтанные траты", "percent": 10},
]


def _to_float(value: Any) -> float:
    """Safely convert value to float."""

    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _format_savings_summary(savings: Dict[str, Dict[str, Any]]) -> str:
    """Format savings summary for user message."""

    if not savings:
        return "Пока нет накоплений."

    lines = []
    for category, data in savings.items():
        current = data.get("current", 0)
        goal = data.get("goal", 0)
        purpose = data.get("purpose", "")
        line = f"{category}: {current:.2f}"
        if goal and goal > 0:
            progress = min(current / goal * 100, 100)
            extra = f" (цель {goal:.2f} для '{purpose}', прогресс {progress:.1f}%)"
            line = f"{line}{extra}"
        lines.append(line)
    return "\n".join(lines)


def _find_reached_goal(savings: Dict[str, Dict[str, Any]]) -> tuple[str, Dict[str, Any]] | tuple[None, None]:
    """Find category where goal is reached."""

    for category, data in savings.items():
        current = data.get("current", 0)
        goal = data.get("goal", 0)
        if goal and current >= goal:
            return category, data
    return None, None


async def _ask_allocation_confirmation(message: Message, allocation: Dict[str, Any]) -> None:
    """Ask user to confirm allocation for a specific category.

    Args:
        message: Aiogram message object used for sending prompts.
        allocation: Allocation details with label and amount.
    """

    await message.answer(
        f"На категорию {allocation['label']} можно направить {allocation['amount']:.2f}. Перевести?",
        reply_markup=yes_no_inline_keyboard(),
    )


async def _remove_reply_keyboard_silently(message: Message) -> None:
    """Временная заглушка: больше не отправляет сообщения и не скрывает клавиатуру."""

    return None


@router.message(F.text == "Рассчитать доход")
async def start_income_flow(message: Message, state: FSMContext) -> None:
    """Start income calculation workflow with calculator keyboard."""

    await state.clear()
    await state.set_state(MoneyState.waiting_for_amount)

    confirm_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Получено",
                    callback_data="income_received",
                )
            ]
        ]
    )

    sum_message = await message.answer("Сумма:", reply_markup=confirm_markup)

    income_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="7"), KeyboardButton(text="8"), KeyboardButton(text="9")],
            [KeyboardButton(text="4"), KeyboardButton(text="5"), KeyboardButton(text="6")],
            [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3")],
            [KeyboardButton(text="0"), KeyboardButton(text="Очистить")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

    await message.answer(
        "Когда будет нужная сумма, нажми кнопку ниже:",
        reply_markup=income_keyboard,
    )

    await state.update_data(income_str="", sum_message_id=sum_message.message_id)
    LOGGER.info("User %s started income calculation", message.from_user.id if message.from_user else "unknown")


async def _process_income_amount_value(
    message: Message,
    state: FSMContext,
    amount: float,
) -> None:
    """Validate amount and process income allocation."""

    if amount <= 0 or amount > 10_000_000:
        await message.answer("Сумма должна быть положительной и не больше 10 000 000. Попробуй снова.")
        return

    allocations: List[Dict[str, Any]] = []
    for item in distribution_scheme:
        allocated = amount * item["percent"] / 100
        allocations.append({"label": item["label"], "category": item["category"], "amount": allocated})

    await state.update_data(income_amount=amount, allocations=allocations, index=0)
    await state.set_state(MoneyState.confirm_category)
    current = allocations[0]
    await _ask_allocation_confirmation(message=message, allocation=current)


@router.message(
    MoneyState.waiting_for_amount,
    F.text.in_("0 1 2 3 4 5 6 7 8 9 Очистить".split()),
)
async def handle_income_digit(message: Message, state: FSMContext) -> None:
    """Handle digit and clear input for income calculator."""

    data = await state.get_data()
    current_str = data.get("income_str", "")
    sum_message_id = data.get("sum_message_id")

    if message.text == "Очистить":
        new_str = ""
    else:
        new_str = current_str + message.text

    await state.update_data(income_str=new_str)

    if sum_message_id is not None:
        new_text = "Сумма:" if not new_str else f"Сумма: {new_str}"
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=sum_message_id,
            text=new_text,
        )
    else:
        await message.answer("Сумма:" if not new_str else f"Сумма: {new_str}")

    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(MoneyState.waiting_for_amount, F.data == "income_received")
async def handle_income_received(query: CallbackQuery, state: FSMContext) -> None:
    """Handle confirmation of entered income amount."""

    await query.answer()

    data = await state.get_data()
    amount_str = data.get("income_str", "").strip()

    if not amount_str:
        await query.answer("Сначала набери сумму с помощью кнопок.", show_alert=True)
        return

    normalized = amount_str.replace(",", ".")
    try:
        amount = float(normalized)
    except ValueError:
        await query.answer("Некорректная сумма. Попробуй ещё раз.", show_alert=True)
        return

    if amount <= 0:
        await query.answer("Сумма должна быть больше нуля.", show_alert=True)
        return

    await query.message.answer(
        "Принял сумму, считаю и распределяю по категориям...",
        reply_markup=ReplyKeyboardRemove(),
    )

    await _process_income_amount_value(
        message=query.message,
        state=state,
        amount=amount,
    )

    await _process_income_amount_value(
        message=query.message,
        state=state,
        amount=amount,
    )

@router.callback_query(MoneyState.confirm_category, F.data.in_({"confirm_yes", "confirm_no"}))
async def handle_category_confirmation(query: CallbackQuery, state: FSMContext) -> None:
    """Handle user confirmation for category allocation via inline buttons."""

    await query.answer()

    data = await state.get_data()
    allocations: List[Dict[str, Any]] = data.get("allocations", [])
    index: int = data.get("index", 0)

    if not allocations or index >= len(allocations):
        await query.message.answer("Нет категорий для обработки.", reply_markup=main_menu_keyboard())
        await state.clear()
        return

    current = allocations[index]
    await query.message.edit_reply_markup(reply_markup=None)

    if query.data == "confirm_yes":
        FinanceDatabase().update_saving(
            user_id=query.from_user.id if query.from_user else None,
            category=current["category"],
            amount_delta=current["amount"],
        )
        await query.message.answer(f"Добавлено {current['amount']:.2f} в категорию {current['category']}.")
    else:
        await query.message.answer("Пропускаем категорию.")

    index += 1
    if index < len(allocations):
        next_item = allocations[index]
        await state.update_data(index=index)
        await _ask_allocation_confirmation(message=query.message, allocation=next_item)
    else:
        await _send_summary_and_goal_prompt(query.message, state)


async def _send_summary_and_goal_prompt(message: Message, state: FSMContext) -> None:
    """Send savings summary and suggest purchase if goal reached."""

    await state.clear()
    db = FinanceDatabase()
    savings = db.get_user_savings(message.from_user.id)
    summary = _format_savings_summary(savings)
    await message.answer(f"Текущие накопления:\n{summary}", reply_markup=main_menu_keyboard())

    category, data = _find_reached_goal(savings)
    if category:
        goal = data.get("goal", 0)
        purpose = data.get("purpose", "цель")
        current = data.get("current", 0)
        await message.answer(
            f"🎯 Цель достигнута по категории {category}. На цели {purpose} накоплено {current:.2f} из {goal:.2f}.",
            reply_markup=purchase_confirmation_keyboard(),
        )
        await state.update_data(category=category, goal=goal)
        await state.set_state(MoneyState.waiting_for_purchase_confirmation)
        return

    await show_affordable_wishes(message=message, user_id=message.from_user.id, db=db)


def _build_affordable_wishes_keyboard(wishes: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Build inline keyboard with purchase buttons for affordable wishes."""

    buttons = [
        [InlineKeyboardButton(text=f"Купил: {wish['name']}", callback_data=f"wish_buy_{wish['id']}")]
        for wish in wishes
    ]
    buttons.append([InlineKeyboardButton(text="Потом", callback_data="affordable_wishes_later")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_affordable_wishes(
    message: Message,
    user_id: int | None = None,
    db: FinanceDatabase | None = None,
) -> None:
    """Show all wishes that are affordable with current savings."""

    if message is None:
        return

    if user_id is None:
        user_id = message.from_user.id if message.from_user else None

    if user_id is None:
        return

    db = db or FinanceDatabase()
    savings_map = db.get_user_savings_map(user_id)
    wishes = db.get_wishes_by_user(user_id)

    affordable: List[Dict[str, Any]] = []
    for wish in wishes:
        if wish.get("is_purchased"):
            continue

        wishlist_category = humanize_wishlist_category(wish.get("category", ""))
        savings_category = WISHLIST_CATEGORY_TO_SAVINGS_CATEGORY.get(wishlist_category)
        if not savings_category:
            continue

        price = _to_float(wish.get("price"))
        available = _to_float(savings_map.get(savings_category))
        if price <= 0 or available < price:
            continue

        wish_copy: Dict[str, Any] = dict(wish)
        wish_copy["price"] = price
        wish_copy["wishlist_category"] = wishlist_category
        affordable.append(wish_copy)

    if not affordable:
        return

    lines = ["Ты уже можешь купить:"]
    for wish in affordable:
        lines.append(
            f"• {wish['name']} — {wish['price']:.2f} ₽ (категория: {wish['wishlist_category']})"
        )
    lines.append("Нажми на кнопку под нужным товаром, если купил.")

    keyboard = _build_affordable_wishes_keyboard(affordable)
    await message.answer("\n".join(lines), reply_markup=keyboard)


async def suggest_available_wish(message: Message) -> None:
    """Backward-compatible wrapper to show affordable wishes."""

    await show_affordable_wishes(message=message, user_id=message.from_user.id if message.from_user else None)


@router.message(MoneyState.waiting_for_purchase_confirmation, F.text.in_({"✅ Купил", "🔄 Продолжить копить"}))
async def handle_goal_purchase(message: Message, state: FSMContext) -> None:
    """Handle decision after reaching savings goal."""

    data = await state.get_data()
    category = data.get("category")
    goal_amount = data.get("goal", 0)
    db = FinanceDatabase()

    if message.text == "✅ Купил" and category:
        db.update_saving(message.from_user.id, category, -goal_amount)
        db.set_goal(message.from_user.id, category, 0, "")
        await message.answer(
            f"Поздравляю с покупкой по категории {category}! Сумма {goal_amount:.2f} списана.",
            reply_markup=main_menu_keyboard(),
        )
        savings = db.get_user_savings(message.from_user.id)
        summary = _format_savings_summary(savings)
        await message.answer(f"Обновлённые накопления:\n{summary}")
    else:
        await message.answer("Продолжаем копить!", reply_markup=main_menu_keyboard())

    await state.clear()
    LOGGER.info("User %s handled goal decision for category %s", message.from_user.id, category)


@router.message(MoneyState.confirm_category)
async def unexpected_confirmation_input(message: Message) -> None:
    """Handle unexpected text in confirmation state."""

    await message.answer("Используй кнопки Да/Нет для выбора.")


@router.message(MoneyState.waiting_for_purchase_confirmation)
async def unexpected_purchase_input(message: Message) -> None:
    """Handle unexpected text in purchase confirmation state."""

    await message.answer("Выбери вариант на клавиатуре: Купил или Продолжить копить.")
