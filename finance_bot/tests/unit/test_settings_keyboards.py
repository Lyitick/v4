"""Tests for settings keyboards."""
from Bot.constants.ui_labels import NAV_BACK, NAV_HOME
from Bot.keyboards.settings import settings_back_reply_keyboard, timezone_inline_keyboard


def _flatten_reply_keyboard_texts(keyboard) -> set[str]:
    return {button.text for row in keyboard.keyboard for button in row}


def _flatten_inline_keyboard_data(keyboard) -> list[tuple[str, str]]:
    return [(button.text, button.callback_data) for row in keyboard.inline_keyboard for button in row]


def test_settings_back_reply_keyboard_has_back_only() -> None:
    keyboard = settings_back_reply_keyboard()
    texts = _flatten_reply_keyboard_texts(keyboard)
    assert NAV_BACK in texts
    assert NAV_HOME not in texts


def test_timezone_inline_keyboard_back_only() -> None:
    keyboard = timezone_inline_keyboard()
    button_data = _flatten_inline_keyboard_data(keyboard)
    assert any(text == NAV_BACK and callback == "st:home" for text, callback in button_data)
    assert all(text != NAV_HOME for text, _ in button_data)
