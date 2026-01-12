"""Tests for time input normalization."""

from Bot.utils.time_input import normalize_time_partial


def test_normalize_time_partial_hour_only() -> None:
    assert normalize_time_partial("12") == ("12:", False)
    assert normalize_time_partial("00") == ("00:", False)
    assert normalize_time_partial("23") == ("23:", False)


def test_normalize_time_partial_invalid_hour() -> None:
    assert normalize_time_partial("24") == ("", False)


def test_normalize_time_partial_compact_time() -> None:
    assert normalize_time_partial("1230") == ("12:30", True)


def test_normalize_time_partial_colon_time() -> None:
    assert normalize_time_partial("12:30") == ("12:30", True)


def test_normalize_time_partial_hour_with_colon() -> None:
    assert normalize_time_partial("12:") == ("12:", False)


def test_normalize_time_partial_invalid_minutes() -> None:
    assert normalize_time_partial("1260") == ("", False)


def test_normalize_time_partial_invalid_text() -> None:
    assert normalize_time_partial("ab") == ("", False)
