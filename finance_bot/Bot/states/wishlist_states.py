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


class WishlistSettingsState(StatesGroup):
    """States for wishlist settings inputs."""

    waiting_for_category_title = State()
    waiting_for_removal = State()
    waiting_for_purchased_category = State()
    waiting_for_purchased_mode = State()
    waiting_for_purchased_days = State()


class BytSettingsState(StatesGroup):
    """States for BYT settings inputs."""

    waiting_for_max_defer_days = State()


class BytTimerState(StatesGroup):
    """States for BYT timer settings inputs."""

    waiting_for_removal = State()
    waiting_for_hour = State()
    waiting_for_minute = State()
