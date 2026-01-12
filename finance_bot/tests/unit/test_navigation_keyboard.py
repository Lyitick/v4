"""Tests for navigation keyboard."""
from Bot.keyboards.navigation import nav_back_home


def test_nav_back_home_buttons() -> None:
    keyboard = nav_back_home("back_cb", "home_cb")
    buttons = keyboard.inline_keyboard[0]
    assert buttons[0].callback_data == "back_cb"
    assert buttons[1].callback_data == "home_cb"
