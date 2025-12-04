"""Lightweight stubs for aiogram to satisfy tests without external dependency."""
from typing import Any, Callable


class _F:
    def __getattr__(self, name: str) -> "_F":  # pragma: no cover - stub
        return self

    def __eq__(self, other: Any) -> "_F":  # pragma: no cover - stub
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> "_F":  # pragma: no cover - stub
        return self

    def in_(self, values: Any) -> "_F":  # pragma: no cover - stub
        return self

    def startswith(self, prefix: Any) -> "_F":  # pragma: no cover - stub
        return self


F = _F()


class Router:
    def message(self, *args: Any, **kwargs: Any) -> Callable:
        def decorator(func: Callable) -> Callable:
            return func

        return decorator

    def callback_query(self, *args: Any, **kwargs: Any) -> Callable:
        def decorator(func: Callable) -> Callable:
            return func

        return decorator

    def __init__(self) -> None:
        self.handlers = []

    def include_router(self, router: "Router") -> None:  # pragma: no cover - stub
        self.handlers.append(router)


class Bot:
    def __init__(self, token: str = "", default: Any | None = None) -> None:
        self.token = token
        self.default = default

    async def session(self) -> None:  # pragma: no cover - stub
        return None

    async def close(self) -> None:  # pragma: no cover - stub
        return None


class Dispatcher:
    def __init__(self) -> None:
        self.routers = []

    def include_router(self, router: Router) -> None:
        self.routers.append(router)

    async def start_polling(self, bot: Bot) -> None:  # pragma: no cover - stub
        return None


__all__ = ["F", "Router", "Bot", "Dispatcher"]
