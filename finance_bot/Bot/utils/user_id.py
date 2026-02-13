"""Utilities for extracting user IDs from Telegram objects."""
from aiogram.types import CallbackQuery, Message


def get_user_id_from_message(message: Message) -> int:
    """Extract user ID from a message object.

    Args:
        message: Telegram message object.

    Returns:
        User ID from message.from_user or fallback to chat.id.
    """
    return message.from_user.id if message.from_user else message.chat.id


def get_user_id_from_callback(callback: CallbackQuery) -> int:
    """Extract user ID from a callback query object.

    Args:
        callback: Telegram callback query object.

    Returns:
        User ID from callback.from_user or fallback to callback.message.chat.id.
    """
    if callback.from_user:
        return callback.from_user.id
    if callback.message:
        return callback.message.chat.id
    raise ValueError("Cannot extract user ID from callback: both from_user and message are None")
