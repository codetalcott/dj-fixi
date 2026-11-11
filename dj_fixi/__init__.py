"""
dj-fixi: Django integration for Fixi.js
"""

__version__ = "0.5.1"

from .middleware import FxMiddleware
from .mixins import FxResponseMixin
from .request import is_fx
from .shortcuts import render_fx
from .views import FxTemplateView, FxView

__all__ = [
    "FxMiddleware",
    "FxView",
    "FxTemplateView",
    "FxResponseMixin",
    "render_fx",
    "is_fx",
]
