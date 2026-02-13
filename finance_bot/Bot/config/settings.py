"""Bot settings module."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


def _load_env_file(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}

    data: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        data[key.strip()] = value.strip().strip("\"'")
    return data


def _resolve_bot_token() -> tuple[str, str]:
    if "BOT_TOKEN" in os.environ:
        return os.environ.get("BOT_TOKEN", ""), "env"

    env_path = Path(__file__).resolve().parents[2] / ".env"
    env_values = _load_env_file(env_path)
    if "BOT_TOKEN" in env_values:
        os.environ.setdefault("BOT_TOKEN", env_values["BOT_TOKEN"])
        return env_values["BOT_TOKEN"], ".env"

    return "", "missing"


BOT_TOKEN, BOT_TOKEN_SOURCE = _resolve_bot_token()
ADMIN_ID: int = 838347504
TIMEZONE = ZoneInfo("Europe/Moscow")

_env_path = Path(__file__).resolve().parents[2] / ".env"
_env_values = _load_env_file(_env_path)
WEBAPP_URL: str = os.environ.get("WEBAPP_URL", _env_values.get("WEBAPP_URL", ""))


@dataclass
class Settings:
    """Container for application settings."""

    bot_token: str = BOT_TOKEN
    bot_token_source: str = BOT_TOKEN_SOURCE
    admin_id: int = ADMIN_ID
    timezone: ZoneInfo = TIMEZONE
    webapp_url: str = WEBAPP_URL


def get_settings() -> Settings:
    """Get current settings.

    Returns:
        Settings: Dataclass with bot settings.
    """

    return Settings()
