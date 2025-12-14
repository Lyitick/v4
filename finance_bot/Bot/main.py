"""Entry point for finance bot."""
import asyncio
import contextlib
import logging
import sys
from datetime import datetime, timedelta
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
from Bot.handlers import callbacks, common, finances, household_payments, start, wishlist
from Bot.handlers.wishlist import run_byt_wishlist_reminders, set_reminder_dispatcher
from Bot.utils.logging import init_logging


def register_routers(dispatcher: Dispatcher) -> None:
    """Register all routers to dispatcher."""

    dispatcher.include_router(start.router)
    dispatcher.include_router(finances.router)
    dispatcher.include_router(household_payments.router)
    dispatcher.include_router(wishlist.router)
    dispatcher.include_router(callbacks.router)
    dispatcher.include_router(common.router)


def _seconds_until_next_reminder(now: datetime) -> float:
    """Calculate seconds until next 12:00 or 18:00 run."""

    today_times = [
        now.replace(hour=12, minute=0, second=0, microsecond=0),
        now.replace(hour=18, minute=0, second=0, microsecond=0),
    ]
    candidates = [time for time in today_times if time > now]
    if not candidates:
        tomorrow = now + timedelta(days=1)
        candidates = [
            tomorrow.replace(hour=12, minute=0, second=0, microsecond=0),
            tomorrow.replace(hour=18, minute=0, second=0, microsecond=0),
        ]
    next_run = min(candidates)
    return (next_run - now).total_seconds()


async def _run_byt_scheduler(bot: Bot, db: FinanceDatabase, timezone: ZoneInfo) -> None:
    """Background scheduler for BYT reminders."""

    while True:
        now = datetime.now(tz=timezone)
        sleep_for = _seconds_until_next_reminder(now)
        await asyncio.sleep(sleep_for)
        await run_byt_wishlist_reminders(bot, db)


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
    set_reminder_dispatcher(dp)
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
