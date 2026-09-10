"""Checks for the vendored fixi.js actually being reachable."""

from django.core.checks import Error, Tags, Warning, register

from ._utils import should_run

FIXI_JS = "dj_fixi/fixi.js"


@register("dj_fixi", Tags.staticfiles)
def check_fixi_js_available(app_configs=None, **kwargs):
    """
    ``{% fixi_js %}`` emits a URL without verifying the file exists.

    If it 404s, every fx-action on every page becomes decorative while the server
    keeps returning 200 -- there is no server-side symptom at all.
    """
    if not should_run(app_configs):
        return []

    from django.apps import apps

    if not apps.is_installed("django.contrib.staticfiles"):
        return [
            Warning(
                "django.contrib.staticfiles is not installed, so dj-fixi cannot "
                f"confirm that {FIXI_JS!r} is served.",
                hint=(
                    "{% fixi_js %} falls back to STATIC_URL + the path, which is "
                    "fine if nginx, WhiteNoise, or a build step serves it. "
                    "Otherwise add 'django.contrib.staticfiles' to INSTALLED_APPS."
                ),
                id="dj_fixi.W302",
            )
        ]

    from django.contrib.staticfiles import finders

    try:
        found = finders.find(FIXI_JS)
    except Exception:
        return []

    if found:
        return []

    return [
        Error(
            f"{FIXI_JS!r} cannot be found by any staticfiles finder.",
            hint=(
                "{% fixi_js %} will emit a URL that 404s, and every fx-action on "
                "every page becomes decorative while the server still returns 200. "
                "Ensure 'dj_fixi' is in INSTALLED_APPS and that "
                "AppDirectoriesFinder is in STATICFILES_FINDERS."
            ),
            id="dj_fixi.E301",
        )
    ]
