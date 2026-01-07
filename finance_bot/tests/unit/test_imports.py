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


def test_register_routers_smoke() -> None:
    """Ensure register_routers includes key routers."""

    from aiogram import Dispatcher

    from Bot.handlers import household_payments, settings, start, wishlist
    from Bot.main import register_routers

    dp = Dispatcher()
    register_routers(dp)
    routers = list(getattr(dp, "sub_routers", []))

    assert start.router in routers
    assert household_payments.router in routers
    assert settings.router in routers
    assert wishlist.router in routers
