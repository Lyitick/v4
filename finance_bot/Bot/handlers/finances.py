"""Handlers for income calculation and savings."""
import logging
from typing import Any, Dict, List, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from Bot.database.crud import FinanceDatabase
from Bot.database.get_db import get_db
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
from Bot.utils.telegram_safe import safe_delete_message, safe_edit_message_text
from Bot.utils.ui_cleanup import ui_register_message

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


def _build_allocations(categories: List[Dict[str, Any]], amount: float) -> List[Dict[str, Any]]:
    """Build allocation list from income categories."""

    allocations: List[Dict[str, Any]] = []
    for category in categories:
        percent = float(category.get("percent", 0))
        allocated = amount * percent / 100
        allocations.append(
            {
                "label": category.get("title", ""),
                "category": category.get("code", ""),
                "amount": allocated,
            }
        )
    return allocations


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

    edited = await safe_edit_message_text(
        message.bot,
        chat_id=message.chat.id,
        message_id=income_message_id,
        text=text,
        logger=LOGGER,
    )
    if edited:
        return income_message_id

    await safe_delete_message(
        message.bot,
        chat_id=message.chat.id,
        message_id=income_message_id,
        logger=LOGGER,
    )

    new_message = await message.answer(text)
    return new_message.message_id


def _to_float(value: Any) -> float:
    """Safely convert value to float."""

    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _format_savings_summary(
    savings: Dict[str, Dict[str, Any]],
    categories_map: Dict[str, str] | None = None,
) -> str:
    """Format savings summary for user message."""

    return format_savings_summary(savings, categories_map)


def _find_reached_goal(
    savings: Dict[str, Dict[str, Any]]
) -> tuple[str, Dict[str, Any]] | tuple[None, None]:
    """Find category where goal is reached."""

    return find_reached_goal(savings)


async def _ask_allocation_confirmation(
    message: Message, state: FSMContext, allocation: Dict[str, Any]
) -> None:
    """Ask user to confirm allocation for a specific category.

    Args:
        message: Aiogram message object used for sending prompts.
        allocation: Allocation details with label and amount.
    """

    text = (
        f"На категорию {allocation['label']} можно направить "
        f"{allocation['amount']:.2f}. Перевести?"
    )
    data = await state.get_data()
    existing_id: Optional[int] = data.get("allocation_question_message_id")
    if existing_id:
        edited = await safe_edit_message_text(
            message.bot,
            chat_id=message.chat.id,
            message_id=existing_id,
            text=text,
            reply_markup=yes_no_inline_keyboard(),
            logger=LOGGER,
        )
        if edited:
            return

    sent = await message.answer(text, reply_markup=yes_no_inline_keyboard())
    await state.update_data(allocation_question_message_id=sent.message_id)


@router.message(F.text == "Рассчитать доход")
async def start_income_flow(message: Message, state: FSMContext) -> None:
    """Start income calculation workflow with calculator keyboard."""

    await delete_welcome_message_if_exists(message, state)
    await state.clear()
    user_id = message.from_user.id
    categories = get_db().list_active_income_categories(user_id)
    if not categories:
        sent = await message.answer(
            'Категории дохода не настроены. Открой "Настройки → Доход" и добавь хотя бы одну категорию.',
            reply_markup=await build_main_menu_for_user(_message_user_id(message)),
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)
        try:
            await safe_delete_message(
                message.bot,
                chat_id=message.chat.id,
                message_id=message.message_id,
                logger=LOGGER,
            )
        except Exception:  # noqa: BLE001
            LOGGER.warning("Failed to delete user command message", exc_info=True)
        LOGGER.info("USER=%s ACTION=INCOME_START_NO_CATEGORIES", user_id)
        return
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
        await safe_delete_message(
        message.bot,
        chat_id=message.chat.id,
        message_id=message.message_id,
        logger=LOGGER,
    )
    except Exception:  # noqa: BLE001
        LOGGER.warning("Failed to delete user command message", exc_info=True)

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
        await safe_delete_message(
            message.bot,
            chat_id=message.chat.id,
            message_id=income_question_message_id,
            logger=LOGGER,
        )

    if income_message_id:
        await safe_delete_message(
            message.bot,
            chat_id=message.chat.id,
            message_id=income_message_id,
            logger=LOGGER,
        )

    db = get_db()
    categories = db.list_active_income_categories(message.from_user.id)
    total_percent = db.sum_income_category_percents(message.from_user.id)
    if total_percent != 100:
        sent = await message.answer(
            f"Сумма процентов должна быть 100%. Сейчас: {total_percent}%. Исправь настройки через ⚙️ → 📊 Доход.",
            reply_markup=await build_main_menu_for_user(_message_user_id(message)),
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)
        await state.clear()
        return

    allocations: List[Dict[str, Any]] = _build_allocations(categories, amount)

    if not allocations:
        sent = await message.answer(
            "Нет категорий для распределения.",
            reply_markup=await build_main_menu_for_user(_message_user_id(message)),
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)
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
        state=state,
        allocation=current,
    )

    try:
        await safe_delete_message(
        message.bot,
        chat_id=message.chat.id,
        message_id=message.message_id,
        logger=LOGGER,
    )
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
        await safe_delete_message(
        message.bot,
        chat_id=message.chat.id,
        message_id=message.message_id,
        logger=LOGGER,
    )
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
            await safe_delete_message(
        message.bot,
        chat_id=message.chat.id,
        message_id=message.message_id,
        logger=LOGGER,
    )
        except Exception:
            pass
        return

    normalized = amount_str.replace(",", ".")
    try:
        amount = float(normalized)
    except ValueError:
        await message.answer("Некорректная сумма. Попробуй ещё раз.")
        try:
            await safe_delete_message(
        message.bot,
        chat_id=message.chat.id,
        message_id=message.message_id,
        logger=LOGGER,
    )
        except Exception:
            pass
        return

    if amount <= 0 or amount > 10_000_000:
        await message.answer(
            "Сумма должна быть положительной и не больше 10 000 000. Попробуй снова."
        )
        try:
            await safe_delete_message(
        message.bot,
        chat_id=message.chat.id,
        message_id=message.message_id,
        logger=LOGGER,
    )
        except Exception:
            pass
        return

    await _process_income_amount_value(
        message=message,
        state=state,
        amount=amount,
    )

    try:
        await safe_delete_message(
        message.bot,
        chat_id=message.chat.id,
        message_id=message.message_id,
        logger=LOGGER,
    )
    except Exception:
        pass


@router.callback_query(MoneyState.confirm_category, F.data.in_({"confirm_yes", "confirm_no"}))
async def handle_category_confirmation(query: CallbackQuery, state: FSMContext) -> None:
    """Handle user confirmation for category allocation via inline buttons."""

    await query.answer()

    data = await state.get_data()
    allocations: List[Dict[str, Any]] = data.get("allocations", [])
    index: int = int(data.get("index", 0))
    # Если категорий нет или индекс вышел за пределы — выходим в главное меню
    if not allocations or index >= len(allocations):
        sent = await query.message.answer(
            "Нет категорий для обработки.",
            reply_markup=await build_main_menu_for_user(_callback_user_id(query)),
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)
        await state.clear()
        return

    current = allocations[index]

    # --- Пользователь нажал "Да" ---
    if query.data == "confirm_yes":
        # Обновляем накопления
        get_db().update_saving(
            user_id=query.from_user.id if query.from_user else None,
            category=current["category"],
            amount_delta=current["amount"],
        )

        # Переходим к следующей категории
        index += 1

    # --- Пользователь нажал "Нет" ---
    else:
        await query.answer("Ты что про жизнь забыл?", show_alert=True)

    # Если ещё есть категории — задаём следующий вопрос
    if index < len(allocations):
        await state.update_data(
            index=index,
        )
        next_allocation = allocations[index]
        await _ask_allocation_confirmation(
            message=query.message,
            state=state,
            allocation=next_allocation,
        )
    else:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
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
    db = get_db()

    # Читаем накопления по реальному user_id пользователя
    savings = db.get_user_savings(user_id)
    categories_map = db.get_income_categories_map(user_id)
    summary = _format_savings_summary(savings, categories_map)

    # Формируем текст: сначала "Получено бабок", затем текущие накопления
    lines: List[str] = []
    if income_amount:
        lines.append(f"Получено бабок: {income_amount:.2f}")
        lines.append("")  # пустая строка для читаемости

    lines.append("Текущие накопления:")
    lines.append(summary)

    sent = await message.answer(
        "\n".join(lines),
        reply_markup=await build_main_menu_for_user(user_id),
    )
    await ui_register_message(state, sent.chat.id, sent.message_id)

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
        [InlineKeyboardButton(text=f"{wish['name']}", callback_data=f"wish_buy_{wish['id']}")]
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

    db = db or get_db()
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
    db = get_db()

    if message.text == "✅ Купил" and category:
        db.update_saving(message.from_user.id, category, -goal_amount)
        db.set_goal(message.from_user.id, category, 0, "")
        sent = await message.answer(
            f"Поздравляю с покупкой по категории {category}! Сумма {goal_amount:.2f} списана.",
            reply_markup=await build_main_menu_for_user(_message_user_id(message)),
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)
        savings = db.get_user_savings(message.from_user.id)
        categories_map = db.get_income_categories_map(message.from_user.id)
        summary = _format_savings_summary(savings, categories_map)
        await message.answer(f"Обновлённые накопления:\n{summary}")
    else:
        sent = await message.answer(
            "Продолжаем копить!",
            reply_markup=await build_main_menu_for_user(_message_user_id(message)),
        )
        await ui_register_message(state, sent.chat.id, sent.message_id)

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
