"""Bot settings module."""
from dataclasses import dataclass


BOT_TOKEN: str = "<YOUR_BOT_TOKEN_HERE>"
ADMIN_ID: int = 123456789


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
