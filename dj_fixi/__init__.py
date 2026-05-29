"""
dj-fixi: Django integration for Fixi.js
"""

__version__ = "0.2.0"

from .middleware import FxMiddleware
from .mixins import (
    ContextPersistenceMixin,
    FxResponseMixin,
    OptimizedQueryMixin,
)
from .shortcuts import render_fx
from .views import FxView

__all__ = [
    "FxMiddleware",
    "FxView",
    "FxResponseMixin",
    "ContextPersistenceMixin",
    "OptimizedQueryMixin",
    "render_fx",
]
