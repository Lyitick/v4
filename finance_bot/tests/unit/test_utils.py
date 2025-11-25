"""Utility tests."""
from Bot.utils.logging import init_logging


def test_init_logging_returns_logger() -> None:
    """init_logging should return a logger instance."""

    logger = init_logging()
    assert logger.name == "Bot.utils.logging"
