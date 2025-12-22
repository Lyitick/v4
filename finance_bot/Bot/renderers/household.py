"""Renderers for household payments UI."""
from __future__ import annotations

import html
from typing import Dict, List

from aiogram.types import InlineKeyboardMarkup

from Bot.keyboards.household import household_payments_inline_keyboard


def render_household_questions_text(
    month: str,
    questions: list[dict],
    answers: dict[str, str],
    current_index: int | None,
) -> str:
    header = f"<b>БЫТОВЫЕ ПЛАТЕЖИ — {html.escape(month)}</b>"
    lines = [header]
    for index, question in enumerate(questions, start=1):
        code = str(question.get("code", ""))
        text = html.escape(str(question.get("text", "")).strip())
        text = text.rstrip("?").strip()
        suffix = ""
        answer = answers.get(code)
        if answer == "yes":
            suffix = " ✅"
        elif answer == "no":
            suffix = " ❌"
        display = text
        if current_index is not None and index - 1 == current_index:
            display = f"<b>{display.upper()}</b>"
        lines.append(f"{index}) {display}{suffix}")
    return "\n".join(lines)


def format_household_items(
    items: List[Dict[str, int | str]],
    unpaid_set: set[str],
) -> str:
    if not items:
        return "Текущий список платежей: (пусто)"

    lines = ["Текущий список платежей:"]
    for index, item in enumerate(items, start=1):
        title = str(item.get("text", "")).rstrip("?")
        amount = item.get("amount")
        code = str(item.get("code", ""))
        status = "❌" if code in unpaid_set else "✅"
        if amount is not None:
            lines.append(f"{index}) {status} {title} — {amount}")
        else:
            lines.append(f"{index}) {status} {title}")
    return "\n".join(lines)


def build_household_question_keyboard(
    question_code: str | None, show_back: bool
) -> InlineKeyboardMarkup:
    return household_payments_inline_keyboard(
        show_back=show_back, question_code=question_code
    )
