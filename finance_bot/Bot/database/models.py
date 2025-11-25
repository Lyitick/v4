"""Database model helpers."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Saving:
    """Saving record representation."""

    id: int
    user_id: int
    category: str
    current: float
    goal: float
    purpose: str


@dataclass
class Wish:
    """Wish record representation."""

    id: int
    user_id: int
    name: str
    price: float
    url: Optional[str]
    category: str
    is_purchased: bool
    saved_amount: float


@dataclass
class Purchase:
    """Purchase record representation."""

    id: int
    user_id: int
    wish_name: str
    price: float
    category: str
    purchased_at: str
