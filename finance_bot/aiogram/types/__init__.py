from typing import Any, Callable, List, Optional


class _Base:
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class Message(_Base):
    def __init__(self, text: str | None = None, chat: Any | None = None, bot: Any | None = None, message_id: int | None = None, **kwargs: Any) -> None:
        super().__init__(text=text, chat=chat, bot=bot, message_id=message_id, **kwargs)

    async def answer(self, text: str, reply_markup: Any | None = None) -> "Message":
        return Message(text=text, chat=getattr(self, "chat", None), bot=getattr(self, "bot", None))

    async def delete(self) -> None:  # pragma: no cover - stub
        return None


class CallbackQuery(_Base):
    def __init__(self, data: str | None = None, message: Message | None = None, **kwargs: Any) -> None:
        super().__init__(data=data, message=message, **kwargs)

    async def answer(self, *args: Any, **kwargs: Any) -> None:
        return None


class InlineKeyboardButton(_Base):
    def __init__(self, text: str, callback_data: str | None = None, **kwargs: Any) -> None:
        super().__init__(text=text, callback_data=callback_data, **kwargs)


class InlineKeyboardMarkup(_Base):
    def __init__(self, inline_keyboard: List[List[InlineKeyboardButton]] | None = None, **kwargs: Any) -> None:
        super().__init__(inline_keyboard=inline_keyboard or [], **kwargs)


class KeyboardButton(_Base):
    def __init__(self, text: str, **kwargs: Any) -> None:
        super().__init__(text=text, **kwargs)


class ReplyKeyboardMarkup(_Base):
    def __init__(self, keyboard: List[List[KeyboardButton]] | None = None, resize_keyboard: bool | None = None, one_time_keyboard: bool | None = None, **kwargs: Any) -> None:
        super().__init__(keyboard=keyboard or [], resize_keyboard=resize_keyboard, one_time_keyboard=one_time_keyboard, **kwargs)


class ReplyKeyboardRemove(_Base):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


action_type = Callable[..., Any]
__all__ = [
    "Message",
    "CallbackQuery",
    "InlineKeyboardButton",
    "InlineKeyboardMarkup",
    "KeyboardButton",
    "ReplyKeyboardMarkup",
    "ReplyKeyboardRemove",
]
