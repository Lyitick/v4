"""Service layer shared types."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ManualCheckResult:
    time_str: str
    categories: list[str]
    total: int
    due: int
    deferred: int


@dataclass
class WishlistPurchaseResult:
    ok: bool
    already_done: bool
    message: str
    balance_before: int | None
    balance_after: int | None


@dataclass
class ServiceError:
    code: str
    message: str
