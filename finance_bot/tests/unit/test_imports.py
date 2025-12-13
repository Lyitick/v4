"""Basic import tests."""


def test_import_main() -> None:
    """Ensure main module is importable."""

    import Bot.main  # noqa: F401


def test_import_handlers() -> None:
    """Ensure handlers modules are importable."""

    import Bot.handlers.start  # noqa: F401
    import Bot.handlers.finances  # noqa: F401
    import Bot.handlers.household_payments  # noqa: F401
    import Bot.handlers.wishlist  # noqa: F401
    import Bot.handlers.callbacks  # noqa: F401
    import Bot.handlers.common  # noqa: F401
