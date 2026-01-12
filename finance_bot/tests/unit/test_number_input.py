"""Tests for numeric input parsing."""

from Bot.utils.number_input import parse_int_choice, parse_positive_int


def test_parse_int_choice_basic() -> None:
    assert parse_int_choice("2") == 2
    assert parse_int_choice("  2 ") == 2
    assert parse_int_choice("+2") == 2


def test_parse_int_choice_invalid() -> None:
    assert parse_int_choice("ab") is None


def test_parse_positive_int_basic() -> None:
    assert parse_positive_int("2") == 2
    assert parse_positive_int(" +3 ") == 3


def test_parse_positive_int_invalid() -> None:
    assert parse_positive_int("0") is None
    assert parse_positive_int("-1") is None
