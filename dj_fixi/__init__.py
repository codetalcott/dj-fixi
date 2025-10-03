"""
dj-fixi: Django integration for Fixi.js
"""

__version__ = "0.1.0"

from .middleware import FxMiddleware
from .mixins import (
    BulkActionMixin,
    ContextPersistenceMixin,
    FxResponseMixin,
    OptimizedQueryMixin,
    ReversibleDeleteMixin,
)
from .shortcuts import render_fx
from .views import FxView

__all__ = [
    "FxMiddleware",
    "FxView",
    "FxResponseMixin",
    "ContextPersistenceMixin",
    "BulkActionMixin",
    "ReversibleDeleteMixin",
    "OptimizedQueryMixin",
    "render_fx",
]
