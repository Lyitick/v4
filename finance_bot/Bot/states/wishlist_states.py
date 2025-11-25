"""FSM states for wishlist."""
from aiogram.fsm.state import State, StatesGroup


class WishlistState(StatesGroup):
    """State machine for wishlist management."""

    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_url = State()
    waiting_for_category = State()
