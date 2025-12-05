"""Entry point for finance bot."""
import asyncio
import logging
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from rich.traceback import install
install()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from Bot.config.settings import get_settings
from Bot.database.crud import FinanceDatabase
from Bot.handlers import callbacks, common, finances, start, wishlist
from Bot.utils.logging import init_logging


def register_routers(dispatcher: Dispatcher) -> None:
    """Register all routers to dispatcher."""

    dispatcher.include_router(start.router)
    dispatcher.include_router(finances.router)
    dispatcher.include_router(wishlist.router)
    dispatcher.include_router(callbacks.router)
    dispatcher.include_router(common.router)


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

    FinanceDatabase()
    register_routers(dp)

    try:
        logger.info("Starting bot polling")
        await dp.start_polling(bot)
    except Exception as error:  # noqa: BLE001
        logger.exception("Bot stopped due to error: %s", error)
    finally:
        await bot.session.close()
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
