"""Tests for handler utilities."""
from Bot.handlers.finances import _format_savings_summary, _find_reached_goal


def test_format_savings_summary_empty() -> None:
    """Empty savings returns default message."""

    assert _format_savings_summary({}) == "Пока нет накоплений."


def test_find_reached_goal() -> None:
    """Goal detection returns first satisfied category."""

    savings = {
        "категория": {"current": 150, "goal": 100, "purpose": "test"},
        "другая": {"current": 50, "goal": 100, "purpose": "none"},
    }
    category, data = _find_reached_goal(savings)
    assert category == "категория"
    assert data["goal"] == 100
