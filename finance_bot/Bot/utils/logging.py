"""Logging utilities."""
import logging

from Bot.config.logging_config import setup_logging


def init_logging() -> logging.Logger:
    """Initialize logging and return module logger.

    Returns:
        logging.Logger: Configured logger instance.
    """

    setup_logging()
    return logging.getLogger(__name__)
