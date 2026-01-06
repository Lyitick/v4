"""Tests for income text sanitizer."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Bot.utils.text_sanitizer import sanitize_income_title  # noqa: E402


def test_sanitize_income_title_removes_bank_suffixes() -> None:
    text = "бытовые расходы на тиньк (озон)"
    assert sanitize_income_title(text) == "бытовые расходы"


def test_sanitize_income_title_trims_separators() -> None:
    text = "Инвестиции — на Альфу"
    assert sanitize_income_title(text) == "Инвестиции"
