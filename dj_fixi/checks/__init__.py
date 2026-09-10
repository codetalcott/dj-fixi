"""
dj-fixi's Django system checks.

Importing this module registers them; ``dj_fixi.apps.DjFixiConfig.ready()`` is
what does that. Silence any of them with, for example::

    SILENCED_SYSTEM_CHECKS = ["dj_fixi.W202"]

Errors are rationed to conditions with no legitimate configuration, because an
Error stops ``runserver``: a false positive there does not annoy someone, it
blocks them.

===========  =======  ==================================================
ID           Level    Fires when
===========  =======  ==================================================
E101         Error    A Django class earlier in the MRO shadows a hook
W102         Warning  Same, but the shadowing class is user code
E103         Error    Routed FxView subclass has no HTTP handler (405)
E104         Error    Routed FxView subclass has no template source
W001         Warning  FxMiddleware absent (advisory since 0.3.0)
W002         Warning  No engine enables context_processors.request
W201         Warning  A declared template name resolves to nothing
W202         Warning  Fixi requests can only ever render the full page
E301         Error    staticfiles installed but fixi.js is unfindable
W302         Warning  django.contrib.staticfiles is not installed
===========  =======  ==================================================
"""

from . import settings, static, templates, views  # noqa: F401

__all__ = ["settings", "static", "templates", "views"]
