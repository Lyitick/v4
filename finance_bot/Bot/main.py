"""Entry point for finance bot."""
import asyncio
import contextlib
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from rich.traceback import install
install()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from Bot.config.settings import get_settings
from Bot.database.crud import FinanceDatabase
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


def register_routers(dispatcher: Dispatcher) -> None:
    """Register all routers to dispatcher."""

    dispatcher.include_router(start.router)
    dispatcher.include_router(finances.router)
    dispatcher.include_router(household_payments.router)
    dispatcher.include_router(settings.router)
    dispatcher.include_router(wishlist.router)
    dispatcher.include_router(callbacks.router)
    dispatcher.include_router(common.router)


async def _run_byt_scheduler(bot: Bot, db: FinanceDatabase, timezone: ZoneInfo) -> None:
    """Background scheduler for BYT reminders."""

    while True:
        now = datetime.now(tz=timezone)
        user_ids = set(db.get_users_with_byt_timer_times()) | set(
            db.get_users_with_active_byt_wishes()
        )
        for uid in user_ids:
            await run_byt_timer_check(bot, db, user_id=uid, run_time=now)
        sleep_for = 60 - now.second - now.microsecond / 1_000_000
        await asyncio.sleep(max(sleep_for, 1))


async def main() -> None:
    """Run bot polling."""

    init_logging()
    settings = get_settings()
    logger = logging.getLogger(__name__)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()

    db = FinanceDatabase()
    register_routers(dp)

    reminder_task = asyncio.create_task(
        _run_byt_scheduler(bot, db, settings.timezone)
    )
    try:
        logger.info("Starting bot polling")
        await dp.start_polling(bot)
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
