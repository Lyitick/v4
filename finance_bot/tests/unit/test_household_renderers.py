"""Tests for household renderers."""

from Bot.renderers.household import format_household_items, render_household_questions_text


def test_render_questions_text_marks_answers() -> None:
    questions = [
        {"code": "q1", "text": "Оплатил интернет?", "amount": 100},
        {"code": "q2", "text": "Оплатил свет?", "amount": 200},
    ]
    answers = {"q1": "yes", "q2": "no"}
    text = render_household_questions_text("2025-02", questions, answers, current_index=1)
    assert "✅" in text
    assert "❌" in text
    assert "2025-02" in text


def test_format_household_items() -> None:
    items = [
        {"code": "q1", "text": "Интернет?", "amount": 100},
        {"code": "q2", "text": "Свет?", "amount": 200},
    ]
    text = format_household_items(items, unpaid_set={"q2"})
    assert "✅" in text
    assert "❌" in text
    assert "Интернет" in text
