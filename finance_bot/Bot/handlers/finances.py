"""Handlers for income calculation and savings."""
import logging
from typing import Any, Dict, List

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from Bot.database.crud import FinanceDatabase
from Bot.keyboards.main import back_to_main_keyboard, main_menu_keyboard, purchase_confirmation_keyboard, yes_no_keyboard
from Bot.states.money_states import MoneyState

LOGGER = logging.getLogger(__name__)

router = Router()

distribution_scheme = [
    {"label": "Убил боль?", "category": "долги", "percent": 30},
    {"label": "Покушал?", "category": "быт", "percent": 20},
    {"label": "Инвестиции", "category": "инвестиции", "percent": 20},
    {"label": "Сбережения", "category": "сбережения", "percent": 20},
    {"label": "Ну и на хуйню?", "category": "спонтанные траты", "percent": 10},
]


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


@router.message(F.text == "Рассчитать доход")
async def start_income_flow(message: Message, state: FSMContext) -> None:
    """Start income calculation workflow."""

    await state.clear()
    await state.set_state(MoneyState.waiting_for_amount)
    await message.answer("Введи сумму дохода числом, без пробелов и символов.", reply_markup=back_to_main_keyboard())
    LOGGER.info("User %s started income calculation", message.from_user.id if message.from_user else "unknown")


@router.message(MoneyState.waiting_for_amount)
async def process_income_amount(message: Message, state: FSMContext) -> None:
    """Validate and process entered income amount."""

    try:
        amount = float(message.text.replace(",", "."))
    except (TypeError, ValueError):
        await message.answer("Нужно ввести число. Попробуй ещё раз.")
        return

    if amount <= 0 or amount > 10_000_000:
        await message.answer("Сумма должна быть положительной и не больше 10 000 000. Попробуй снова.")
        return

    allocations: List[Dict[str, Any]] = []
    for item in distribution_scheme:
        allocated = amount * item["percent"] / 100
        allocations.append({"label": item["label"], "category": item["category"], "amount": allocated})

    await state.update_data(allocations=allocations, index=0)
    await state.set_state(MoneyState.confirm_category)
    current = allocations[0]
    await message.answer(
        f"На категорию {current['label']} можно направить {current['amount']:.2f}. Перевести?",
        reply_markup=yes_no_keyboard(),
    )


@router.message(MoneyState.confirm_category, F.text.in_({"Да", "Нет"}))
async def handle_category_confirmation(message: Message, state: FSMContext) -> None:
    """Handle user confirmation for category allocation."""

    data = await state.get_data()
    allocations: List[Dict[str, Any]] = data.get("allocations", [])
    index: int = data.get("index", 0)

    if not allocations or index >= len(allocations):
        await message.answer("Нет категорий для обработки.", reply_markup=main_menu_keyboard())
        await state.clear()
        return

    current = allocations[index]
    if message.text == "Да":
        FinanceDatabase().update_saving(user_id=message.from_user.id, category=current["category"], amount_delta=current["amount"])
        await message.answer(
            f"Добавлено {current['amount']:.2f} в категорию {current['category']}.",
            reply_markup=yes_no_keyboard(),
        )
    else:
        await message.answer("Пропускаем категорию.", reply_markup=yes_no_keyboard())

    index += 1
    if index < len(allocations):
        next_item = allocations[index]
        await state.update_data(index=index)
        await message.answer(
            f"На категорию {next_item['label']} можно направить {next_item['amount']:.2f}. Перевести?",
            reply_markup=yes_no_keyboard(),
        )
    else:
        await _send_summary_and_goal_prompt(message, state)


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
