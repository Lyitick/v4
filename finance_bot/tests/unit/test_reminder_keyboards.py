"""Tests for reminder keyboard builders."""

from Bot.keyboards.reminders import (
    food_delete_inline_keyboard,
    food_settings_keyboard,
    habit_delete_inline_keyboard,
    habit_list_inline_keyboard,
    motivation_delete_inline_keyboard,
    motivation_schedule_inline_keyboard,
    motivation_settings_keyboard,
    reminder_action_keyboard_habits,
    reminder_action_keyboard_motivation,
    reminder_categories_keyboard,
    snooze_duration_keyboard,
    wishlist_delete_inline_keyboard,
    wishlist_list_inline_keyboard,
    wishlist_settings_keyboard,
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


# ------------------------------------------------------------------ #
#  Phase 2: Food keyboards                                            #
# ------------------------------------------------------------------ #


def test_food_settings_keyboard_has_buttons() -> None:
    kb = food_settings_keyboard()
    texts = [btn.text for row in kb.keyboard for btn in row]
    assert "🍽 Добавить приём пищи" in texts
    assert "💊 Добавить БАД" in texts
    assert "➖ Удалить" in texts
    assert "📊 Статистика питания" in texts


def test_food_delete_inline_keyboard() -> None:
    items = [
        {"id": 1, "title": "Обед", "text": "meal"},
        {"id": 2, "title": "Витамин D", "text": "supplement"},
    ]
    kb = food_delete_inline_keyboard(items)
    assert len(kb.inline_keyboard) == 3  # 2 items + back
    assert kb.inline_keyboard[0][0].callback_data == "rem:food_del:1"
    assert "🍽" in kb.inline_keyboard[0][0].text
    assert kb.inline_keyboard[1][0].callback_data == "rem:food_del:2"
    assert "💊" in kb.inline_keyboard[1][0].text
    assert kb.inline_keyboard[2][0].callback_data == "rem:food_back"


# ------------------------------------------------------------------ #
#  Phase 3: Motivation keyboards                                       #
# ------------------------------------------------------------------ #


def test_motivation_settings_keyboard_has_buttons() -> None:
    kb = motivation_settings_keyboard()
    texts = [btn.text for row in kb.keyboard for btn in row]
    assert "➕ Добавить контент" in texts
    assert "➖ Удалить контент" in texts
    assert "⏰ Расписание" in texts
    assert "🔁 Вкл/Выкл" in texts


def test_motivation_delete_inline_keyboard() -> None:
    items = [
        {"id": 1, "title": "Верь!", "media_type": None},
        {"id": 2, "title": "Фото", "media_type": "photo"},
    ]
    kb = motivation_delete_inline_keyboard(items)
    assert len(kb.inline_keyboard) == 3  # 2 items + back
    assert kb.inline_keyboard[0][0].callback_data == "rem:motiv_del:1"
    assert "📝" in kb.inline_keyboard[0][0].text  # text emoji
    assert kb.inline_keyboard[1][0].callback_data == "rem:motiv_del:2"
    assert "🖼" in kb.inline_keyboard[1][0].text  # photo emoji
    assert kb.inline_keyboard[2][0].callback_data == "rem:motiv_back"


def test_motivation_schedule_inline_keyboard() -> None:
    kb = motivation_schedule_inline_keyboard()
    all_buttons = [b for row in kb.inline_keyboard for b in row]
    assert len(all_buttons) == 3
    data_values = [b.callback_data for b in all_buttons]
    assert "rem:motiv_sched:interval" in data_values
    assert "rem:motiv_sched:times" in data_values
    assert "rem:motiv_back" in data_values


# ------------------------------------------------------------------ #
#  Wishlist keyboard tests                                             #
# ------------------------------------------------------------------ #


def test_wishlist_settings_keyboard_has_buttons() -> None:
    kb = wishlist_settings_keyboard()
    texts = [btn.text for row in kb.keyboard for btn in row]
    assert "➕ Добавить напоминание" in texts
    assert "➖ Удалить напоминание" in texts
    assert "📊 Статистика" in texts


def test_wishlist_list_inline_keyboard() -> None:
    items = [
        {"id": 1, "title": "Покупки", "is_enabled": 1},
        {"id": 2, "title": "Подарки", "is_enabled": 0},
    ]
    kb = wishlist_list_inline_keyboard(items)
    assert len(kb.inline_keyboard) == 2
    assert kb.inline_keyboard[0][0].callback_data == "rem:wish_toggle:1"
    assert "✅" in kb.inline_keyboard[0][0].text
    assert kb.inline_keyboard[1][0].callback_data == "rem:wish_toggle:2"
    assert "❌" in kb.inline_keyboard[1][0].text


def test_wishlist_delete_inline_keyboard() -> None:
    items = [
        {"id": 1, "title": "Покупки"},
        {"id": 2, "title": "Подарки"},
    ]
    kb = wishlist_delete_inline_keyboard(items)
    assert len(kb.inline_keyboard) == 3  # 2 items + back
    assert kb.inline_keyboard[0][0].callback_data == "rem:wish_del:1"
    assert kb.inline_keyboard[1][0].callback_data == "rem:wish_del:2"
    assert kb.inline_keyboard[2][0].callback_data == "rem:wish_back"
