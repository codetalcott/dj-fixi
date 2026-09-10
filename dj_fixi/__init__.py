"""
dj-fixi: Django integration for Fixi.js
"""

__version__ = "0.3.0"

from .middleware import FxMiddleware
from .mixins import (
    ContextPersistenceMixin,
    FxResponseMixin,
    OptimizedQueryMixin,
)
from .request import is_fx
from .shortcuts import render_fx
from .views import FxTemplateView, FxView

__all__ = [
    "FxMiddleware",
    "FxView",
    "FxTemplateView",
    "FxResponseMixin",
    "ContextPersistenceMixin",
    "OptimizedQueryMixin",
    "render_fx",
    "is_fx",
]
