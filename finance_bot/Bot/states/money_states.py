"""FSM states for money flow."""
from aiogram.fsm.state import State, StatesGroup


class MoneyState(StatesGroup):
    """State machine for income distribution."""

    waiting_for_amount = State()
    confirm_category = State()
    waiting_for_purchase_confirmation = State()
