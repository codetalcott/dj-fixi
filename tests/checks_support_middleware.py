"""A user subclass of FxMiddleware, to prove W001 accepts subclasses."""

from dj_fixi.middleware import FxMiddleware


class CustomFxMiddleware(FxMiddleware):
    pass
