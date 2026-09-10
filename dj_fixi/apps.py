"""App configuration. Its only job is to register the system checks."""

from django.apps import AppConfig


class DjFixiConfig(AppConfig):
    """
    Auto-discovered by ``INSTALLED_APPS = ["dj_fixi"]``.

    Django's ``AppConfig.create()`` picks up the single AppConfig subclass in an
    app's ``apps`` submodule automatically (since 3.2; dj-fixi requires >= 4.2),
    so adding this file does not change how anyone lists the app.

    Keep ``ready()`` to the one import. Anything that raises here kills
    ``django.setup()`` for every management command, and any Django access at
    import time in the checks package runs before the app registry is populated.
    """

    name = "dj_fixi"
    label = "dj_fixi"
    verbose_name = "dj-fixi"

    def ready(self):
        from . import checks  # noqa: F401  (registration side effect)
