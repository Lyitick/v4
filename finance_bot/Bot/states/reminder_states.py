"""FSM states for scheduled reminders."""

from aiogram.fsm.state import State, StatesGroup


class HabitSettingsState(StatesGroup):
    """States for habit CRUD in settings."""

    waiting_for_habit_title = State()
    waiting_for_habit_times = State()
    waiting_for_habit_removal = State()


class MotivationSettingsState(StatesGroup):
    """States for motivation reminder settings (Phase 3)."""

    waiting_for_schedule_type = State()
    waiting_for_interval = State()
    waiting_for_times = State()
    waiting_for_window_from = State()
    waiting_for_window_to = State()


class FoodSettingsState(StatesGroup):
    """States for food & supplements settings (Phase 2)."""

    waiting_for_meal_time = State()
    waiting_for_supplement_title = State()
    waiting_for_supplement_time = State()
    waiting_for_supplement_removal = State()
