"""Tests for reminder keyboard builders."""

from Bot.keyboards.reminders import (
    habit_delete_inline_keyboard,
    habit_list_inline_keyboard,
    reminder_action_keyboard_habits,
    reminder_action_keyboard_motivation,
    reminder_categories_keyboard,
    snooze_duration_keyboard,
)


def test_reminder_categories_keyboard_has_4_categories() -> None:
    kb = reminder_categories_keyboard()
    texts = [btn.text for row in kb.keyboard for btn in row]
    assert "🏃 Привычки" in texts
    assert "💡 Мотивация" in texts
    assert "🍽 Питание" in texts
    assert "📋 Вишлист (БЫТ)" in texts


def test_reminder_action_keyboard_habits_has_3_buttons() -> None:
    kb = reminder_action_keyboard_habits(42)
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 3
    texts = [b.text for b in buttons]
    assert "✅ Сделано" in texts
    assert "⏳ Отложить" in texts
    assert "🙅 Пропущено" in texts


def test_reminder_action_keyboard_habits_callback_data() -> None:
    kb = reminder_action_keyboard_habits(42)
    buttons = kb.inline_keyboard[0]
    data_values = [b.callback_data for b in buttons]
    assert "rem:done:42" in data_values
    assert "rem:snooze_menu:42" in data_values
    assert "rem:skip:42" in data_values


def test_reminder_action_keyboard_motivation_has_1_button() -> None:
    kb = reminder_action_keyboard_motivation(7)
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 1
    assert buttons[0].callback_data == "rem:seen:7"


def test_snooze_keyboard_has_4_options_plus_back() -> None:
    kb = snooze_duration_keyboard(99)
    all_buttons = [b for row in kb.inline_keyboard for b in row]
    assert len(all_buttons) == 5  # 4 durations + back

    data_values = [b.callback_data for b in all_buttons]
    assert "rem:snooze:15:99" in data_values
    assert "rem:snooze:60:99" in data_values
    assert "rem:snooze:180:99" in data_values
    assert "rem:snooze:1440:99" in data_values
    assert "rem:snooze_back:99" in data_values


def test_habit_list_inline_keyboard() -> None:
    habits = [
        {"id": 1, "title": "Бег", "is_enabled": 1},
        {"id": 2, "title": "Чтение", "is_enabled": 0},
    ]
    kb = habit_list_inline_keyboard(habits)
    assert len(kb.inline_keyboard) == 2
    assert "✅ Бег" in kb.inline_keyboard[0][0].text
    assert "❌ Чтение" in kb.inline_keyboard[1][0].text


def test_habit_delete_inline_keyboard() -> None:
    habits = [{"id": 1, "title": "Йога"}]
    kb = habit_delete_inline_keyboard(habits)
    assert len(kb.inline_keyboard) == 2  # 1 habit + back
    assert kb.inline_keyboard[0][0].callback_data == "rem:habit_del:1"
    assert kb.inline_keyboard[1][0].callback_data == "rem:habits_back"
