from typing import Any, Dict


class FSMContext:
    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._state: Any = None

    async def update_data(self, **kwargs: Any) -> None:
        self._data.update(kwargs)

    async def get_data(self) -> Dict[str, Any]:
        return dict(self._data)

    async def set_state(self, state: Any) -> None:
        self._state = state

    async def clear(self) -> None:
        self._data.clear()
        self._state = None

    @property
    def state(self) -> Any:  # pragma: no cover - compatibility
        return self._state
