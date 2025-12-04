from typing import Any, Callable


class Command:
    def __init__(self, *commands: str) -> None:
        self.commands = commands

    def __call__(self, *args: Any, **kwargs: Any) -> bool:  # pragma: no cover - stub
        return True


def or_filt(*filters: Any) -> Callable:  # pragma: no cover - stub
    def wrapper(*args: Any, **kwargs: Any) -> bool:
        return True

    return wrapper


__all__ = ["Command", "or_filt"]
