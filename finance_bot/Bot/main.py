"""Entry point for finance bot."""
import asyncio
import contextlib
import logging
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramUnauthorizedError

from Bot.config.settings import get_settings
from Bot.database.get_db import get_db
from Bot.handlers import (
    callbacks,
    common,
    finances,
    household_payments,
    settings,
    start,
    wishlist,
)
from Bot.handlers.wishlist import run_byt_timer_check
from Bot.utils.logging import init_logging
from Bot.utils.time import now_for_user


def register_routers(dispatcher: Dispatcher) -> None:
    """Register all routers to dispatcher."""

    dispatcher.include_router(start.router)
    dispatcher.include_router(finances.router)
    dispatcher.include_router(household_payments.router)
    dispatcher.include_router(settings.router)
    dispatcher.include_router(wishlist.router)
    dispatcher.include_router(callbacks.router)
    dispatcher.include_router(common.router)


def _token_fingerprint(token: str) -> str:
    if not token:
        return "empty"
    if len(token) <= 8:
        return f"{token[:2]}…{token[-2:]}"
    return f"{token[:4]}…{token[-4:]}"


def _validate_token(token: str) -> list[str]:
    if not token.strip():
        return ["BOT_TOKEN пустой или не загружен"]

    errors = []
    if ":" not in token:
        errors.append("BOT_TOKEN не похож на токен (нет ':')")
    if len(token) < 20:
        errors.append("BOT_TOKEN слишком короткий (ожидается > 20 символов)")
    return errors


def _format_token_context(token_source: str, fingerprint: str, env_path: Path) -> str:
    if token_source == ".env":
        return f"token_source={token_source}, fingerprint={fingerprint}, env_path={env_path}"
    return f"token_source={token_source}, fingerprint={fingerprint}"


async def _run_byt_scheduler(bot: Bot, db, default_tz: str) -> None:
    """Background scheduler for BYT reminders."""

    while True:
        user_ids = set(db.get_users_with_byt_reminder_times()) | set(
            db.get_users_with_active_byt_wishes()
        )
        now_values: dict[int, datetime] = {}
        for uid in user_ids:
            now_values[uid] = now_for_user(db, uid, default_tz)
            await run_byt_timer_check(bot, db, user_id=uid, run_time=now_values[uid])
        reference = now_values[min(now_values)] if now_values else now_for_user(db, 0, default_tz)
        sleep_for = 60 - reference.second - reference.microsecond / 1_000_000
        await asyncio.sleep(max(sleep_for, 1))


async def main() -> None:
    """Run bot polling."""

    init_logging()
    settings = get_settings()
    logger = logging.getLogger(__name__)
    token = (settings.bot_token or "").strip()
    token_source = settings.bot_token_source
    fingerprint = _token_fingerprint(token)
    token_context = _format_token_context(token_source, fingerprint, project_root / ".env")

    errors = _validate_token(token)
    for error in errors:
        logger.error("%s (%s)", error, token_context)
    if errors:
        return

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()

    db = get_db()
    register_routers(dp)

    try:
        await bot.me()
    except TelegramUnauthorizedError:
        logger.error(
            "Unauthorized: токен неверный/отозван/бот удалён. "
            "Проверь BotFather и переменные окружения. "
            "(%s)",
            token_context,
        )
        await bot.session.close()
        return

    reminder_task = asyncio.create_task(
        _run_byt_scheduler(
            bot,
            db,
            settings.timezone.key if hasattr(settings.timezone, "key") else str(settings.timezone),
        )
    )
    try:
        logger.info(
            "Starting bot polling (%s)",
            token_context,
        )
        await dp.start_polling(bot)
    except TelegramUnauthorizedError:
        logger.error(
            "Unauthorized: токен неверный/отозван/бот удалён. "
            "Проверь BotFather и переменные окружения. "
            "(%s)",
            token_context,
        )
    except Exception as error:  # noqa: BLE001
        logger.exception("Bot stopped due to error: %s", error)
    finally:
        reminder_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reminder_task
        await bot.session.close()
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
