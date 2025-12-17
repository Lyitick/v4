"""FSM states for wishlist."""
from aiogram.fsm.state import State, StatesGroup


class WishlistState(StatesGroup):
    """State machine for wishlist management."""

    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_url = State()
    waiting_for_category = State()


class WishlistBytReminderState(StatesGroup):
    """State machine for BYT reminder flow."""

    waiting_answer = State()


class BytDeferState(StatesGroup):
    """State machine for deferring BYT wishlist items."""

    waiting_for_days = State()
