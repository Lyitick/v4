"""Tests for manual BYT reminder check helpers."""

from Bot.utils.byt_manual_check import (
    build_byt_times_sorted,
    parse_byt_manual_cursor_index,
    select_next_byt_manual_time,
)


def test_build_byt_times_sorted_unique_sorted() -> None:
    times_by_category = {
        1: ["12:00", "18:00"],
        2: ["14:00", "12:00"],
    }
    assert build_byt_times_sorted(times_by_category) == ["12:00", "14:00", "18:00"]


def test_select_next_byt_manual_time_cycles() -> None:
    times_sorted = ["12:00", "14:00"]
    current_date = "2026-01-09"
    selected, index, notice = select_next_byt_manual_time(
        times_sorted, current_date, current_date, -1
    )
    assert selected == "12:00"
    assert index == 0
    assert notice == ""

    selected, index, notice = select_next_byt_manual_time(
        times_sorted, current_date, current_date, index
    )
    assert selected == "14:00"
    assert index == 1
    assert notice == ""

    selected, index, notice = select_next_byt_manual_time(
        times_sorted, current_date, current_date, index
    )
    assert selected == "12:00"
    assert index == 0
    assert notice == "Сегодня все времена уже проверены — начинаю заново."


def test_parse_byt_manual_cursor_index_zero_is_valid() -> None:
    assert parse_byt_manual_cursor_index(0) == 0
    assert parse_byt_manual_cursor_index("0") == 0


def test_parse_byt_manual_cursor_index_invalid_returns_minus_one() -> None:
    assert parse_byt_manual_cursor_index(None) == -1
    assert parse_byt_manual_cursor_index("") == -1
    assert parse_byt_manual_cursor_index("   ") == -1
    assert parse_byt_manual_cursor_index("abc") == -1
