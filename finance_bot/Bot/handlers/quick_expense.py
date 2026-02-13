"""Quick expense entry handler.

Allows users to add expenses by sending messages like:
  500 такси
  200 кофе обед с коллегой
  1500.50 еда

Parses: <amount> <category/description> [optional note]
"""
import logging
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from Bot.database.get_db import get_db

LOGGER = logging.getLogger(__name__)

router = Router()

# Match: number (possibly with decimal) followed by text
EXPENSE_PATTERN = re.compile(
    r"^(\d+(?:[.,]\d{1,2})?)\s+(.+)$", re.DOTALL
)


def _match_category(text: str, categories: list[dict]) -> tuple[str | None, str]:
    """Try to match input text to an expense category.

    Returns (matched_category_title, remaining_note).
    """
    text_lower = text.strip().lower()

    # Try exact match on category title
    for cat in categories:
        if text_lower == cat["title"].lower():
            return cat["title"], ""

    # Try prefix match (first word matches category)
    first_word = text_lower.split()[0] if text_lower else ""
    for cat in categories:
        cat_lower = cat["title"].lower()
        if first_word == cat_lower or cat_lower.startswith(first_word):
            rest = text.strip()[len(first_word):].strip()
            return cat["title"], rest

    # Try code match
    for cat in categories:
        if first_word == cat["code"].lower():
            rest = text.strip()[len(first_word):].strip()
            return cat["title"], rest

    # No match — return None, full text as note
    return None, text.strip()


@router.message(F.text.regexp(EXPENSE_PATTERN))
async def quick_expense_handler(message: Message) -> None:
    """Handle quick expense entry like '500 еда' or '200 такси'."""
    if not message.text:
        return

    match = EXPENSE_PATTERN.match(message.text.strip())
    if not match:
        return

    amount_str = match.group(1).replace(",", ".")
    description = match.group(2).strip()

    try:
        amount = float(amount_str)
    except ValueError:
        return

    if amount <= 0 or amount > 10_000_000:
        return

    user_id = message.from_user.id
    db = get_db()

    # Ensure categories exist
    db.ensure_expense_categories_seeded(user_id)
    categories = db.list_active_expense_categories(user_id)

    if not categories:
        return

    matched_category, note = _match_category(description, categories)

    if matched_category:
        # Direct match found — ask for confirmation
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да",
                    callback_data=f"qexp_ok:{amount}:{matched_category}:{note[:50]}",
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data="qexp_cancel",
                ),
            ],
        ])
        await message.reply(
            f"Записать расход?\n\n"
            f"<b>{amount:,.2f} ₽</b> — {matched_category}"
            + (f"\nЗаметка: {note}" if note else ""),
            reply_markup=keyboard,
        )
    else:
        # No match — offer category selection
        buttons = []
        for cat in categories:
            buttons.append([
                InlineKeyboardButton(
                    text=cat["title"],
                    callback_data=f"qexp_cat:{amount}:{cat['title']}:{note[:50]}",
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="Отмена", callback_data="qexp_cancel"),
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.reply(
            f"<b>{amount:,.2f} ₽</b> — выберите категорию:",
            reply_markup=keyboard,
        )


@router.callback_query(F.data.startswith("qexp_ok:"))
async def confirm_quick_expense(callback: CallbackQuery) -> None:
    """Confirm and save a quick expense."""
    parts = callback.data.split(":", 3)
    if len(parts) < 3:
        return

    amount = float(parts[1])
    category = parts[2]
    note = parts[3] if len(parts) > 3 else ""

    db = get_db()
    db.add_expense(callback.from_user.id, amount, category, note)

    await callback.message.edit_text(
        f"Записано: <b>{amount:,.2f} ₽</b> — {category}"
        + (f"\n{note}" if note else ""),
    )
    await callback.answer("Расход записан!")


@router.callback_query(F.data.startswith("qexp_cat:"))
async def select_category_quick_expense(callback: CallbackQuery) -> None:
    """Save expense with selected category."""
    parts = callback.data.split(":", 3)
    if len(parts) < 3:
        return

    amount = float(parts[1])
    category = parts[2]
    note = parts[3] if len(parts) > 3 else ""

    db = get_db()
    db.add_expense(callback.from_user.id, amount, category, note)

    await callback.message.edit_text(
        f"Записано: <b>{amount:,.2f} ₽</b> — {category}"
        + (f"\n{note}" if note else ""),
    )
    await callback.answer("Расход записан!")


@router.callback_query(F.data == "qexp_cancel")
async def cancel_quick_expense(callback: CallbackQuery) -> None:
    """Cancel quick expense."""
    await callback.message.edit_text("Отменено.")
    await callback.answer()
