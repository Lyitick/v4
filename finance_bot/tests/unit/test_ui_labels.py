"""Tests for UI label constants."""
from Bot.constants.ui_labels import NAV_BACK


def test_nav_back_has_expected_format() -> None:
    assert "⏪" in NAV_BACK
    assert "⟪Back⟫" in NAV_BACK
