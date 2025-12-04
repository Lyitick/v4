class State:
    def __init__(self, name: str = "") -> None:
        self.name = name

    def __str__(self) -> str:  # pragma: no cover - stub
        return self.name


class StatesGroup:
    pass
