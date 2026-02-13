"""Telegram Mini App authentication.

Validates initData sent by Telegram WebApp using HMAC-SHA256.
See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qs, unquote


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict[str, Any]:
    """Validate Telegram WebApp initData and return parsed user info.

    Args:
        init_data: Raw initData query string from Telegram WebApp.
        bot_token: Bot token used to compute HMAC secret.
        max_age_seconds: Max allowed age of auth_date (default 24h).

    Returns:
        Parsed user dict with at least 'id' field.

    Raises:
        ValueError: If validation fails.
    """
    if not init_data:
        raise ValueError("Empty initData")

    parsed = parse_qs(init_data, keep_blank_values=True)

    hash_value = parsed.pop("hash", [None])[0]
    if not hash_value:
        raise ValueError("Missing hash in initData")

    # Build check string: sorted key=value pairs joined by \n
    data_pairs = []
    for key in sorted(parsed.keys()):
        values = parsed[key]
        value = values[0] if values else ""
        data_pairs.append(f"{key}={value}")
    data_check_string = "\n".join(data_pairs)

    # Compute HMAC: secret_key = HMAC_SHA256("WebAppData", bot_token)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, hash_value):
        raise ValueError("Invalid initData signature")

    # Check auth_date freshness
    auth_date_str = parsed.get("auth_date", [None])[0]
    if auth_date_str:
        try:
            auth_date = int(auth_date_str)
            if time.time() - auth_date > max_age_seconds:
                raise ValueError("initData expired")
        except (TypeError, ValueError) as exc:
            if "expired" in str(exc):
                raise
            raise ValueError("Invalid auth_date") from exc

    # Parse user JSON
    user_raw = parsed.get("user", [None])[0]
    if not user_raw:
        raise ValueError("Missing user in initData")

    try:
        user = json.loads(unquote(user_raw))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Invalid user JSON in initData") from exc

    if "id" not in user:
        raise ValueError("Missing user id")

    return user
