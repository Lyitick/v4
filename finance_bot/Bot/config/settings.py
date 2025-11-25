"""Bot settings module."""
from dataclasses import dataclass


BOT_TOKEN: str = "<8440100118:AAFm5TCYx0vaXAaJD9jaDKkDAxfTcb9BWoY>"
ADMIN_ID: int =


@dataclass
class Settings:
    """Container for application settings."""

    bot_token: str = BOT_TOKEN
    admin_id: int = ADMIN_ID


def get_settings() -> Settings:
    """Get current settings.

    Returns:
        Settings: Dataclass with bot settings.
    """

    return Settings()
