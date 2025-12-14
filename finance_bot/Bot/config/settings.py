"""Bot settings module."""
from dataclasses import dataclass
from zoneinfo import ZoneInfo


BOT_TOKEN: str = "8440100118:AAFm5TCYx0vaXAaJD9jaDKkDAxfTcb9BWoY"
ADMIN_ID: int = 838347504
TIMEZONE = ZoneInfo("Europe/Moscow")


@dataclass
class Settings:
    """Container for application settings."""

    bot_token: str = BOT_TOKEN
    admin_id: int = ADMIN_ID
    timezone: ZoneInfo = TIMEZONE


def get_settings() -> Settings:
    """Get current settings.

    Returns:
        Settings: Dataclass with bot settings.
    """

    return Settings()
