"""Settings-level checks. Each requires a routed dj-fixi view before it speaks."""

from django.core.checks import Tags, Warning, register

from ._utils import fx_views, should_run

REQUEST_PROCESSOR = "django.template.context_processors.request"


def _contains_subclass(dotted_path: str, candidates) -> bool:
    """
    True when any entry in ``candidates`` is that class or a subclass of it.

    Import-and-issubclass rather than string equality, so ``dj_fixi.FxMiddleware``
    (the package re-export) and user subclasses both count. Mirrors the helper
    django.contrib.admin.checks uses for the same job.
    """
    from django.utils.module_loading import import_string

    try:
        target = import_string(dotted_path)
    except ImportError:
        return False
    for entry in candidates:
        try:
            candidate = import_string(entry)
        except Exception:
            continue
        if isinstance(candidate, type) and issubclass(candidate, target):
            return True
    return False


@register("dj_fixi")
def check_middleware_installed(app_configs=None, **kwargs):
    """
    Advisory since 0.3.0: detection no longer depends on the middleware.

    dj-fixi reads the FX-Request header directly, so a missing middleware entry
    is no longer a silent breakage. It still costs you ``request.is_fx`` in your
    own code, and the Vary header on responses dj-fixi does not itself build.
    """
    if not should_run(app_configs) or not fx_views():
        return []

    from django.conf import settings

    if _contains_subclass("dj_fixi.middleware.FxMiddleware", settings.MIDDLEWARE):
        return []

    return [
        Warning(
            "dj_fixi.middleware.FxMiddleware is not in MIDDLEWARE, so request.is_fx is never set.",
            hint=(
                "dj-fixi's own views and shortcuts read the FX-Request header "
                "directly, so template selection still works. But 'request.is_fx' "
                "in your own view code will raise AttributeError, and responses "
                "built outside dj-fixi will not carry 'Vary: FX-Request', which "
                "lets a shared cache serve a full page into a swap target. Add "
                "'dj_fixi.middleware.FxMiddleware' to MIDDLEWARE."
            ),
            id="dj_fixi.W001",
        )
    ]


@register("dj_fixi", Tags.templates)
def check_request_context_processor(app_configs=None, **kwargs):
    """``{{ request }}`` is unavailable, which most dj-fixi templates rely on."""
    if not should_run(app_configs) or not fx_views():
        return []

    from django.conf import settings

    engines = [
        engine
        for engine in settings.TEMPLATES
        if engine.get("BACKEND") == "django.template.backends.django.DjangoTemplates"
    ]
    if not engines:
        return []
    if any(
        REQUEST_PROCESSOR in engine.get("OPTIONS", {}).get("context_processors", [])
        for engine in engines
    ):
        return []

    return [
        Warning(
            f"{REQUEST_PROCESSOR!r} is not enabled in any DjangoTemplates engine.",
            hint=(
                "dj-fixi templates commonly build fx-action from {{ request.path }}, "
                "and dj-fixi-tables requires it outright. Add it to "
                "TEMPLATES[0]['OPTIONS']['context_processors']. (Note {% fx_csrf_token %} "
                "no longer needs it: csrf_token is a builtin context processor.)"
            ),
            id="dj_fixi.W002",
        )
    ]
