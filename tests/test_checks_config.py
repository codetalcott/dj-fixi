"""
Tests for the remaining checks: E103, E104, W001, W002, W201, W202, E301, W302,
plus the one integration test that proves registration actually happens.
"""

from django.core.checks import run_checks
from django.test import override_settings

from .checks_support import TEMPLATES, TEMPLATES_NO_PARTIAL, check_ids

NO_MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]
NO_REQUEST_PROCESSOR = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {"good/list.html": "x", "good/list_partial.html": "y"},
                )
            ],
            "context_processors": [],
        },
    }
]


def hint_for(check_id):
    return next(m.hint for m in run_checks(tags=["dj_fixi"]) if m.id == check_id)


# --------------------------------------------------------------------------- #
# E103 / E104 -- views that cannot answer a request
# --------------------------------------------------------------------------- #


def test_e103_view_with_no_http_handler():
    with override_settings(ROOT_URLCONF="tests.urlconfs.no_handler", TEMPLATES=TEMPLATES):
        assert "dj_fixi.E103" in check_ids()
        assert "FxTemplateView" in hint_for("dj_fixi.E103")


def test_e103_silent_for_views_that_have_a_handler():
    with override_settings(ROOT_URLCONF="tests.urlconfs.good", TEMPLATES=TEMPLATES):
        assert "dj_fixi.E103" not in check_ids()


def test_e104_view_with_no_template_source():
    with override_settings(ROOT_URLCONF="tests.urlconfs.no_template", TEMPLATES=TEMPLATES):
        assert "dj_fixi.E104" in check_ids()


def test_e104_silent_when_the_urlconf_supplies_the_template():
    """as_view(template_name=...) counts; reading the class alone would not."""
    with override_settings(ROOT_URLCONF="tests.urlconfs.nested", TEMPLATES=TEMPLATES):
        assert "dj_fixi.E104" not in check_ids()


# --------------------------------------------------------------------------- #
# W001 / W002 -- settings, gated on a routed dj-fixi view existing
# --------------------------------------------------------------------------- #


def test_w001_middleware_missing():
    with override_settings(
        ROOT_URLCONF="tests.urlconfs.good", TEMPLATES=TEMPLATES, MIDDLEWARE=NO_MIDDLEWARE
    ):
        assert "dj_fixi.W001" in check_ids()


def test_w001_accepts_a_subclass_of_the_middleware():
    """Import-and-issubclass, not string equality."""
    with override_settings(
        ROOT_URLCONF="tests.urlconfs.good",
        TEMPLATES=TEMPLATES,
        MIDDLEWARE=[*NO_MIDDLEWARE, "tests.checks_support_middleware.CustomFxMiddleware"],
    ):
        assert "dj_fixi.W001" not in check_ids()


def test_w001_silent_when_installed():
    with override_settings(ROOT_URLCONF="tests.urlconfs.good", TEMPLATES=TEMPLATES):
        assert "dj_fixi.W001" not in check_ids()


def test_w002_request_context_processor_missing():
    with override_settings(ROOT_URLCONF="tests.urlconfs.good", TEMPLATES=NO_REQUEST_PROCESSOR):
        assert "dj_fixi.W002" in check_ids()


def test_w002_silent_when_enabled():
    with override_settings(ROOT_URLCONF="tests.urlconfs.good", TEMPLATES=TEMPLATES):
        assert "dj_fixi.W002" not in check_ids()


# --------------------------------------------------------------------------- #
# W201 / W202 -- template resolution
# --------------------------------------------------------------------------- #


def test_w201_typoed_partial_template():
    with override_settings(ROOT_URLCONF="tests.urlconfs.templates", TEMPLATES=TEMPLATES):
        assert "dj_fixi.W201" in check_ids()


def test_w201_hint_explains_the_silent_fall_through():
    with override_settings(ROOT_URLCONF="tests.urlconfs.templates", TEMPLATES=TEMPLATES):
        assert "never falls through" in hint_for("dj_fixi.W201")


def test_w201_silent_when_every_template_resolves():
    with override_settings(ROOT_URLCONF="tests.urlconfs.good", TEMPLATES=TEMPLATES):
        assert "dj_fixi.W201" not in check_ids()


def test_w202_when_no_partial_exists_anywhere():
    with override_settings(ROOT_URLCONF="tests.urlconfs.templates", TEMPLATES=TEMPLATES_NO_PARTIAL):
        found = check_ids()
        assert "dj_fixi.W202" in found
        assert "SILENCED_SYSTEM_CHECKS" in hint_for("dj_fixi.W202")


def test_w202_silent_when_partial_template_is_declared():
    with override_settings(ROOT_URLCONF="tests.urlconfs.good", TEMPLATES=TEMPLATES):
        assert "dj_fixi.W202" not in check_ids()


def test_w202_fires_even_when_a_conventionally_named_file_exists():
    """0.5: nothing is derived, so an unnamed good/list_partial.html does not count."""
    with override_settings(ROOT_URLCONF="tests.urlconfs.templates", TEMPLATES=TEMPLATES):
        assert "dj_fixi.W202" in check_ids()
        assert "partial_template = 'good/list_partial.html'" in hint_for("dj_fixi.W202")


# --------------------------------------------------------------------------- #
# E301 / W302 -- the vendored fixi.js being reachable
# --------------------------------------------------------------------------- #


def test_e301_when_no_finder_can_see_fixi_js():
    with override_settings(
        ROOT_URLCONF="tests.urlconfs.good",
        TEMPLATES=TEMPLATES,
        STATICFILES_FINDERS=["django.contrib.staticfiles.finders.FileSystemFinder"],
    ):
        assert "dj_fixi.E301" in check_ids()


def test_e301_silent_with_the_default_finders():
    with override_settings(ROOT_URLCONF="tests.urlconfs.good", TEMPLATES=TEMPLATES):
        assert "dj_fixi.E301" not in check_ids()


def test_w302_when_staticfiles_is_not_installed():
    with override_settings(
        ROOT_URLCONF="tests.urlconfs.good",
        TEMPLATES=TEMPLATES,
        INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth", "dj_fixi"],
    ):
        found = check_ids()
        assert "dj_fixi.W302" in found and "dj_fixi.E301" not in found


# --------------------------------------------------------------------------- #
# Registration -- the only test that proves apps.py -> ready() actually runs
# --------------------------------------------------------------------------- #


def test_checks_are_registered_by_the_app_config():
    from django.core.checks import registry

    registered = {
        getattr(c, "__name__", "")
        for c in registry.registry.get_checks(include_deployment_checks=False)
    }
    assert "check_view_mro" in registered


def test_app_config_is_auto_discovered():
    from django.apps import apps

    assert type(apps.get_app_config("dj_fixi")).__name__ == "DjFixiConfig"


# --------------------------------------------------------------------------- #
# 0.4.0: W203 (htmx attributes in project templates) and the W201 hint for
# Django 6 partial syntax
# --------------------------------------------------------------------------- #


def test_w203_names_the_htmx_attributes_and_their_translations(tmp_path):
    from .checks_support import GOOD_FILES, fs_templates

    files = {**GOOD_FILES, "mixed.html": '<button hx-get="/x/" hx-target="#r" hx-boost="true">x</button>'}
    with override_settings(TEMPLATES=fs_templates(tmp_path, files), ROOT_URLCONF="tests.urlconfs.good"):
        assert "dj_fixi.W203" in check_ids()
        hint = hint_for("dj_fixi.W203")
    assert "fx-action" in hint and "no fixi equivalent" in hint and "SILENCED_SYSTEM_CHECKS" in hint


@override_settings(TEMPLATES=TEMPLATES, ROOT_URLCONF="tests.urlconfs.templates")
def test_w201_explains_django_6_partial_syntax():
    hints = [m.hint for m in run_checks(tags=["dj_fixi"]) if m.id == "dj_fixi.W201" and "#nope" in m.msg]
    assert hints and ("partialdef" in hints[0] or "django-template-partials" in hints[0])
