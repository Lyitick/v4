"""Text sanitizers for user-facing labels."""
from __future__ import annotations

import re


_TAIL_PATTERNS = [
    r"на\s+тиньк",
    r"на\s+альфу",
    r"на\s+сбер",
    r"на\s+яндекс",
]


def sanitize_income_title(text: str) -> str:
    value = str(text or "")
    for pattern in _TAIL_PATTERNS:
        value = re.sub(rf"\s*(?:—|-|:)?\s*{pattern}", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*\(\s*озон\s*\)", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\(\s*\)", "", value)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip(" -—:\t\n")
