"""Safe wrappers for Telegram API operations."""
from __future__ import annotations

import asyncio
import logging

from aiohttp import ClientConnectionError, ClientOSError
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

LOGGER = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT = 30


def _get_logger(logger: logging.Logger | None) -> logging.Logger:
    return logger or LOGGER


def _is_network_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            TelegramNetworkError,
            ClientOSError,
            ClientConnectionError,
            asyncio.TimeoutError,
            TimeoutError,
        ),
    )


def _log_network_error(
    logger: logging.Logger,
    action: str,
    exc: Exception,
    attempt: int,
    retries: int,
) -> None:
    logger.warning(
        "NETWORK_RETRY action=%s attempt=%s/%s error=%s",
        action,
        attempt,
        retries + 1,
        exc,
    )
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Network error details for %s", action, exc_info=True)


async def safe_delete_message(
    bot,
    chat_id: int,
    message_id: int,
    *,
    retries: int = 2,
    base_delay: float = 0.3,
    logger: logging.Logger | None = None,
    request_timeout: int | None = DEFAULT_REQUEST_TIMEOUT,
) -> bool:
    """Safely delete a message without raising exceptions."""

    log = _get_logger(logger)
    for attempt in range(retries + 1):
        try:
            await bot.delete_message(
                chat_id=chat_id,
                message_id=message_id,
                request_timeout=request_timeout,
            )
            return True
        except TelegramBadRequest as exc:
            text = str(exc).lower()
            if (
                "message to delete not found" in text
                or "message can't be deleted" in text
                or "message can’t be deleted" in text
            ):
                log.debug(
                    "Safe delete skipped (chat_id=%s, message_id=%s): %s",
                    chat_id,
                    message_id,
                    exc,
                )
                return False
            log.warning(
                "Safe delete failed (chat_id=%s, message_id=%s): %s",
                chat_id,
                message_id,
                exc,
            )
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Safe delete failure details", exc_info=True)
            return False
        except Exception as exc:  # noqa: BLE001
            if _is_network_error(exc):
                _log_network_error(log, "delete_message", exc, attempt + 1, retries)
                if attempt < retries:
                    await asyncio.sleep(base_delay * 2**attempt)
                    continue
                return False
            log.warning(
                "Safe delete unexpected error (chat_id=%s, message_id=%s): %s",
                chat_id,
                message_id,
                exc,
            )
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Safe delete unexpected error details", exc_info=True)
            return False
    return False


async def safe_edit_message_text(
    bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup=None,
    *,
    parse_mode: str | None = None,
    retries: int = 2,
    base_delay: float = 0.3,
    logger: logging.Logger | None = None,
    request_timeout: int | None = DEFAULT_REQUEST_TIMEOUT,
) -> bool:
    """Safely edit a message text without raising exceptions."""

    log = _get_logger(logger)
    if isinstance(reply_markup, (ReplyKeyboardMarkup, ReplyKeyboardRemove)):
        log.warning("Safe edit skipped due to reply keyboard markup")
        return False

    for attempt in range(retries + 1):
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                request_timeout=request_timeout,
            )
            return True
        except TelegramBadRequest as exc:
            lowered = str(exc).lower()
            if "message is not modified" in lowered:
                return True
            if "message to edit not found" in lowered:
                log.debug(
                    "Safe edit skipped (chat_id=%s, message_id=%s): %s",
                    chat_id,
                    message_id,
                    exc,
                )
                return False
            log.warning(
                "Safe edit failed (chat_id=%s, message_id=%s): %s",
                chat_id,
                message_id,
                exc,
            )
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Safe edit failure details", exc_info=True)
            return False
        except Exception as exc:  # noqa: BLE001
            if _is_network_error(exc):
                _log_network_error(log, "edit_message_text", exc, attempt + 1, retries)
                if attempt < retries:
                    await asyncio.sleep(base_delay * 2**attempt)
                    continue
                return False
            log.warning(
                "Safe edit unexpected error (chat_id=%s, message_id=%s): %s",
                chat_id,
                message_id,
                exc,
            )
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Safe edit unexpected error details", exc_info=True)
            return False
    return False


async def safe_send_message(
    bot,
    chat_id: int,
    text: str,
    reply_markup=None,
    *,
    parse_mode: str | None = None,
    retries: int = 2,
    base_delay: float = 0.3,
    logger: logging.Logger | None = None,
    request_timeout: int | None = DEFAULT_REQUEST_TIMEOUT,
):
    """Safely send a message using bot.send_message without raising exceptions."""

    log = _get_logger(logger)
    for attempt in range(retries + 1):
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                request_timeout=request_timeout,
            )
        except TelegramBadRequest as exc:
            log.warning("Safe send failed: %s", exc)
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Safe send failure details", exc_info=True)
            return None
        except Exception as exc:  # noqa: BLE001
            if _is_network_error(exc):
                _log_network_error(log, "send_message", exc, attempt + 1, retries)
                if attempt < retries:
                    await asyncio.sleep(base_delay * 2**attempt)
                    continue
                return None
            log.warning("Safe send unexpected error: %s", exc)
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Safe send unexpected error details", exc_info=True)
            return None
    return None


async def safe_answer(
    message_or_callback,
    text: str,
    reply_markup=None,
    *,
    parse_mode: str | None = None,
    retries: int = 2,
    base_delay: float = 0.3,
    logger: logging.Logger | None = None,
    request_timeout: int | None = DEFAULT_REQUEST_TIMEOUT,
) -> int | None:
    """Safely send a message using .answer without raising exceptions."""

    log = _get_logger(logger)
    for attempt in range(retries + 1):
        try:
            sent = await message_or_callback.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                request_timeout=request_timeout,
            )
            return int(sent.message_id)
        except TelegramBadRequest as exc:
            log.warning("Safe answer failed: %s", exc)
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Safe answer failure details", exc_info=True)
            return None
        except Exception as exc:  # noqa: BLE001
            if _is_network_error(exc):
                _log_network_error(log, "answer", exc, attempt + 1, retries)
                if attempt < retries:
                    await asyncio.sleep(base_delay * 2**attempt)
                    continue
                return None
            log.warning("Safe answer unexpected error: %s", exc)
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Safe answer unexpected error details", exc_info=True)
            return None
    return None


async def safe_callback_answer(
    callback,
    text: str | None = None,
    *,
    show_alert: bool | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Safely answer a callback query without raising exceptions."""

    log = _get_logger(logger)
    try:
        await callback.answer(text=text, show_alert=show_alert)
    except Exception as exc:  # noqa: BLE001
        if _is_network_error(exc):
            log.warning("Safe callback answer failed due to network error: %s", exc)
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Safe callback answer network details", exc_info=True)
            return
        log.warning("Safe callback answer unexpected error: %s", exc)
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Safe callback answer unexpected error details", exc_info=True)
