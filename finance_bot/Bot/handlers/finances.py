"""Handlers for income calculation and savings."""
import logging
from typing import Any, Dict, List, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from Bot.database.crud import FinanceDatabase
from Bot.keyboards.main import (
    back_to_main_keyboard,
    purchase_confirmation_keyboard,
    yes_no_inline_keyboard,
)
from Bot.keyboards.calculator import income_calculator_keyboard
from Bot.handlers.common import build_main_menu_for_user
from Bot.states.money_states import MoneyState
from Bot.handlers.wishlist import WISHLIST_CATEGORY_TO_SAVINGS_CATEGORY, humanize_wishlist_category
from Bot.utils.savings import find_reached_goal, format_savings_summary

LOGGER = logging.getLogger(__name__)

router = Router()


def _message_user_id(message: Message) -> int:
    """Extract user id from message."""

    return message.from_user.id if message.from_user else message.chat.id


def _callback_user_id(callback: CallbackQuery) -> int:
    """Extract user id from callback."""

    if callback.from_user:
        return callback.from_user.id
    return callback.message.chat.id


async def delete_welcome_message_if_exists(message: Message, state: FSMContext) -> None:
    """Legacy no-op to keep compatibility when welcome cleanup is referenced."""

    return None

INCOME_DIGITS = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
INCOME_INPUT_BUTTONS = INCOME_DIGITS | {"Очистить"}

distribution_scheme = [
    {"label": "Убил боль?", "category": "долги", "percent": 30},
    {"label": "бытовые расходы на Тиньк", "category": "быт", "percent": 20},
    {"label": "Инвестиции на Альфу", "category": "инвестиции", "percent": 20},
    {"label": "Сбережения на Сбер", "category": "сбережения", "percent": 20},
    {"label": "спонтанные траты на Яндекс", "category": "спонтанные траты", "percent": 10},
]


def _build_income_prompt(income_sum: str) -> str:
    """Build income input prompt."""

    # Отображаем сумму в формате ": <число>"
    return f": {income_sum}"


async def _refresh_income_message(
    message: Message, income_message_id: Optional[int], income_sum: str
) -> int:
    """Update or create income prompt message with current sum.

    Редактируем уже существующее сообщение с подсказкой по сумме.
    Если id нет (например, первый запуск) — создаём новое.
    При ошибке редактирования пытаемся удалить старое сообщение и создаём новое,
    чтобы пользователь видел актуальную сумму.
    """

    text = _build_income_prompt(income_sum)

    # Если сообщения ещё не было — создаём его
    if income_message_id is None:
        new_message = await message.answer(text)
        return new_message.message_id

    # Пытаемся отредактировать существующее сообщение
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=income_message_id,
            text=text,
        )
        return income_message_id
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "Failed to edit income message %s: %s",
            income_message_id,
            exc,
        )

    try:
        await message.bot.delete_message(
            chat_id=message.chat.id,
            message_id=income_message_id,
        )
    except Exception:
        pass

    new_message = await message.answer(text)
    return new_message.message_id


def _to_float(value: Any) -> float:
    """Safely convert value to float."""

    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _format_savings_summary(savings: Dict[str, Dict[str, Any]]) -> str:
    """Format savings summary for user message."""

    return format_savings_summary(savings)


def _find_reached_goal(
    savings: Dict[str, Dict[str, Any]]
) -> tuple[str, Dict[str, Any]] | tuple[None, None]:
    """Find category where goal is reached."""

    return find_reached_goal(savings)


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


@router.message(F.text == "Рассчитать доход")
async def start_income_flow(message: Message, state: FSMContext) -> None:
    """Start income calculation workflow with calculator keyboard."""

    await delete_welcome_message_if_exists(message, state)
    await state.clear()
    await state.set_state(MoneyState.waiting_for_amount)

    income_sum = "0"
    question = await message.answer(
        "Введи сумму дохода (используй кнопки ниже).",
        reply_markup=income_calculator_keyboard(),
    )
    prompt = _build_income_prompt(income_sum)
    income_message = await message.answer(prompt)

    # Сохраняем служебные message_id и текущую сумму
    await state.update_data(
        income_sum=income_sum,
        income_question_message_id=question.message_id,
        income_message_id=income_message.message_id,
    )

    # Удаляем сообщение пользователя "Рассчитать доход"
    try:
        await message.delete()
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed to delete user command message: %s", exc)

    LOGGER.info(
        "User %s started income calculation",
        message.from_user.id if message.from_user else "unknown",
    )


async def _process_income_amount_value(
    message: Message,
    state: FSMContext,
    amount: float,
) -> None:
    """Validate amount and start category confirmation workflow."""

    # Базовая валидация суммы
    if amount <= 0 or amount > 10_000_000:
        await message.answer(
            "Сумма должна быть положительной и не больше 10 000 000. Попробуй снова."
        )
        return

    # Удаляем служебное сообщение с суммой и вопрос с клавиатурой
    data = await state.get_data()
    income_question_message_id: Optional[int] = data.get("income_question_message_id")
    income_message_id: Optional[int] = data.get("income_message_id")

    if income_question_message_id:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=income_question_message_id,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                "Failed to delete income helper message %s: %s",
                income_question_message_id,
                exc,
            )

    if income_message_id:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=income_message_id,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                "Failed to delete income helper message %s: %s",
                income_message_id,
                exc,
            )

    # Считаем распределение по категориям
    allocations: List[Dict[str, Any]] = []
    for item in distribution_scheme:
        allocated = amount * item["percent"] / 100
        allocations.append(
            {
                "label": item["label"],
                "category": item["category"],
                "amount": allocated,
            }
        )

    # Если по какой-то причине схема пустая — выходим в главное меню
    if not allocations:
        await message.answer(
            "Нет категорий для распределения.",
            reply_markup=await build_main_menu_for_user(_message_user_id(message)),
        )
        await state.clear()
        return

    # Сохраняем данные в FSM
    await state.update_data(
        income_amount=amount,
        allocations=allocations,
        index=0,
        life_message_id=None,
    )

    # Переходим в состояние подтверждения категорий
    await state.set_state(MoneyState.confirm_category)

    # Задаём вопрос ТОЛЬКО по первой категории
    current = allocations[0]
    await _ask_allocation_confirmation(
        message=message,
        allocation=current,
    )

    try:
        await message.delete()
    except Exception:
        pass


@router.message(
    MoneyState.waiting_for_amount,
    F.text.in_(INCOME_INPUT_BUTTONS),
)
async def handle_income_digit(message: Message, state: FSMContext) -> None:
    """Handle digit and clear input for income calculator."""

    data = await state.get_data()
    current_sum = str(data.get("income_sum", "0"))
    sum_message_id = data.get("income_message_id")

    if message.text == "Очистить":
        new_sum = "0"
    else:
        if current_sum == "0":
            new_sum = message.text
        else:
            new_sum = current_sum + message.text

    income_message_id = await _refresh_income_message(
        message=message,
        income_message_id=sum_message_id,
        income_sum=new_sum,
    )

    await state.update_data(income_sum=new_sum, income_message_id=income_message_id)

    try:
        await message.delete()
    except Exception:
        pass


@router.message(MoneyState.waiting_for_amount, F.text == "✅ Газ")
async def handle_income_confirm(message: Message, state: FSMContext) -> None:
    """Handle confirmation of income input via calculator button."""

    data = await state.get_data()
    amount_str = str(data.get("income_sum", "0")).strip()

    if not amount_str:
        await message.answer("Сначала набери сумму с помощью кнопок.")
        try:
            await message.delete()
        except Exception:
            pass
        return

    normalized = amount_str.replace(",", ".")
    try:
        amount = float(normalized)
    except ValueError:
        await message.answer("Некорректная сумма. Попробуй ещё раз.")
        try:
            await message.delete()
        except Exception:
            pass
        return

    if amount <= 0 or amount > 10_000_000:
        await message.answer(
            "Сумма должна быть положительной и не больше 10 000 000. Попробуй снова."
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    await _process_income_amount_value(
        message=message,
        state=state,
        amount=amount,
    )

    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(MoneyState.confirm_category, F.data.in_({"confirm_yes", "confirm_no"}))
async def handle_category_confirmation(query: CallbackQuery, state: FSMContext) -> None:
    """Handle user confirmation for category allocation via inline buttons."""

    await query.answer()

    data = await state.get_data()
    allocations: List[Dict[str, Any]] = data.get("allocations", [])
    index: int = int(data.get("index", 0))
    life_message_id: Optional[int] = data.get("life_message_id")

    # Если категорий нет или индекс вышел за пределы — выходим в главное меню
    if not allocations or index >= len(allocations):
        await query.message.answer(
            "Нет категорий для обработки.",
            reply_markup=await build_main_menu_for_user(_callback_user_id(query)),
        )
        await state.clear()
        return

    current = allocations[index]

    # Удаляем сообщение-вопрос с кнопками Да/Нет
    try:
        await query.message.delete()
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed to delete category question message: %s", exc)

    new_life_message_id: Optional[int] = life_message_id

    # --- Пользователь нажал "Да" ---
    if query.data == "confirm_yes":
        # Если было сообщение "Ты что про жизнь забыл?" — удаляем его
        if life_message_id:
            try:
                await query.message.bot.delete_message(
                    chat_id=query.message.chat.id,
                    message_id=life_message_id,
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "Failed to delete life message %s: %s",
                    life_message_id,
                    exc,
                )
        new_life_message_id = None

        # Обновляем накопления
        FinanceDatabase().update_saving(
            user_id=query.from_user.id if query.from_user else None,
            category=current["category"],
            amount_delta=current["amount"],
        )

        # Переходим к следующей категории
        index += 1

    # --- Пользователь нажал "Нет" ---
    else:
        # Перед тем как отправить новое "Ты что про жизнь забыл?" — удаляем старое, если было
        if life_message_id:
            try:
                await query.message.bot.delete_message(
                    chat_id=query.message.chat.id,
                    message_id=life_message_id,
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "Failed to delete previous life message %s: %s",
                    life_message_id,
                    exc,
                )

        life_msg = await query.message.bot.send_message(
            chat_id=query.message.chat.id,
            text="Ты что про жизнь забыл?",
        )
        new_life_message_id = life_msg.message_id

        # index НЕ меняем — задаём тот же вопрос по той же категории

    # Если ещё есть категории — задаём следующий вопрос
    if index < len(allocations):
        await state.update_data(
            index=index,
            life_message_id=new_life_message_id,
        )
        next_allocation = allocations[index]
        await _ask_allocation_confirmation(
            message=query.message,
            allocation=next_allocation,
        )
    else:
        # Категорий больше нет — life_message_id очищаем и показываем итог
        await state.update_data(life_message_id=None)
        await _send_summary_and_goal_prompt(
            message=query.message,
            state=state,
            user_id=query.from_user.id if query.from_user else None,
        )


async def _send_summary_and_goal_prompt(
    message: Message,
    state: FSMContext,
    user_id: Optional[int],
) -> None:
    """Send savings summary and suggest purchase if goal reached."""

    # Достаём сумму, которую пользователь ввёл как доход
    data = await state.get_data()
    income_amount = data.get("income_amount", 0)

    # Восстанавливаем user_id, если не передали явно
    if user_id is None:
        user_id = message.from_user.id if message.from_user else message.chat.id

    await state.clear()
    db = FinanceDatabase()

    # Читаем накопления по реальному user_id пользователя
    savings = db.get_user_savings(user_id)
    summary = _format_savings_summary(savings)

    # Формируем текст: сначала "Получено бабок", затем текущие накопления
    lines: List[str] = []
    if income_amount:
        lines.append(f"Получено бабок: {income_amount:.2f}")
        lines.append("")  # пустая строка для читаемости

    lines.append("Текущие накопления:")
    lines.append(summary)

    await message.answer(
        "\n".join(lines),
        reply_markup=await build_main_menu_for_user(user_id),
    )

    category, goal_data = _find_reached_goal(savings)
    if category:
        goal = goal_data.get("goal", 0)
        purpose = goal_data.get("purpose", "цель")
        current = goal_data.get("current", 0)
        await message.answer(
            f"🎯 Цель достигнута по категории {category}. "
            f"На цели {purpose} накоплено {current:.2f} из {goal:.2f}.",
            reply_markup=purchase_confirmation_keyboard(),
        )
        await state.update_data(category=category, goal=goal)
        await state.set_state(MoneyState.waiting_for_purchase_confirmation)
        return

    # Подбор желаний из вишлиста по тем же savings и user_id
    await show_affordable_wishes(
        message=message,
        user_id=user_id,
        db=db,
    )


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
            reply_markup=await build_main_menu_for_user(_message_user_id(message)),
        )
        savings = db.get_user_savings(message.from_user.id)
        summary = _format_savings_summary(savings)
        await message.answer(f"Обновлённые накопления:\n{summary}")
    else:
        await message.answer(
            "Продолжаем копить!",
            reply_markup=await build_main_menu_for_user(_message_user_id(message)),
        )

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
