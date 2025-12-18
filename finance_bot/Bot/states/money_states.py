"""FSM states for money flow."""
from aiogram.fsm.state import State, StatesGroup


class MoneyState(StatesGroup):
    """State machine for income distribution."""

    waiting_for_amount = State()
    confirm_category = State()
    waiting_for_purchase_confirmation = State()


class HouseholdPaymentsState(StatesGroup):
    """State machine for household payments flow."""

    waiting_for_answer = State()


class HouseholdSettingsState(StatesGroup):
    """State machine for household payments settings."""

    waiting_for_title = State()
    waiting_for_amount = State()


class IncomeSettingsState(StatesGroup):
    """State machine for income settings."""

    waiting_for_category_title = State()
    waiting_for_percent = State()
