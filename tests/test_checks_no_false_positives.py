"""
The discipline file. Write changes here first.

Every configuration below is a project that legitimately is not using the feature
a check is about. All of them must produce nothing. This is the file that catches
the regression where someone "improves" a check into firing on everyone -- and it
matters more than the individual check tests, because a dj-fixi Error stops
runserver, so a false positive does not annoy a user, it blocks them.
"""

import pytest
from django.test import override_settings

from .checks_support import TEMPLATES, check_ids

NO_MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]


@override_settings(TEMPLATES=TEMPLATES)
@pytest.mark.parametrize(
    "urlconf",
    ["tests.urlconfs.good", "tests.urlconfs.nested"],
)
def test_correctly_configured_projects_are_silent(urlconf):
    with override_settings(ROOT_URLCONF=urlconf):
        assert check_ids() == []


@override_settings(TEMPLATES=TEMPLATES, MIDDLEWARE=NO_MIDDLEWARE)
def test_fbv_only_project_without_middleware_is_silent():
    """render_fx reads the header itself, so this project genuinely works."""
    with override_settings(ROOT_URLCONF="tests.urlconfs.fbv_only"):
        assert check_ids() == []


@override_settings(TEMPLATES=TEMPLATES, MIDDLEWARE=NO_MIDDLEWARE)
def test_empty_urlconf_without_middleware_is_silent():
    with override_settings(ROOT_URLCONF="tests.urlconfs.empty"):
        assert check_ids() == []


@override_settings(TEMPLATES=TEMPLATES)
def test_broken_urlconf_is_left_to_djangos_own_checks():
    with override_settings(ROOT_URLCONF="tests.urlconfs.broken"):
        assert check_ids() == []


@override_settings(TEMPLATES=TEMPLATES, ROOT_URLCONF="tests.urlconfs.bad_mro")
def test_silent_when_dj_fixi_is_not_installed():
    """Registration survives an INSTALLED_APPS override; the guards must not."""
    with override_settings(INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth"]):
        assert check_ids() == []


@override_settings(TEMPLATES=TEMPLATES, ROOT_URLCONF="tests.urlconfs.bad_mro")
def test_silent_when_checking_a_different_app():
    from django.apps import apps

    other = [apps.get_app_config("auth")]
    assert check_ids(app_configs=other) == []


@override_settings(ROOT_URLCONF="tests.urlconfs.good")
def test_jinja2_only_project_does_not_trigger_the_context_processor_check():
    with override_settings(
        TEMPLATES=[{"BACKEND": "django.template.backends.jinja2.Jinja2", "DIRS": []}]
    ):
        assert "dj_fixi.W002" not in check_ids()


@override_settings(TEMPLATES=TEMPLATES, ROOT_URLCONF="tests.urlconfs.user_shadow")
def test_user_override_is_a_warning_never_an_error():
    """A deliberate non-cooperative override must not block runserver."""
    assert "dj_fixi.E101" not in check_ids()


# ------------------------------------------------------------------ 0.4.0
# W203 (htmx in project templates) scans files a project may legitimately have;
# W202 (no partial_template) must stay quiet for views that render nothing.

from .checks_support import GOOD_FILES, fs_templates  # noqa: E402


def test_w203_silent_for_clean_templates_and_htmx_inside_comments(tmp_path):
    files = {
        **GOOD_FILES,
        "clean.html": '{% load fixi_tags %}<button {% fx_attrs action="/x/" %}>x</button><a fx-action="/y/">y</a>',
        "commented.html": '{# <a hx-get="/old/">old</a> #}{% comment %}hx-post="/y/"{% endcomment %}<b>ok</b>',
        "notes.txt": '<a hx-get="/x/">not a template</a>',
    }
    with override_settings(TEMPLATES=fs_templates(tmp_path, files), ROOT_URLCONF="tests.urlconfs.good"):
        assert check_ids() == []


def test_w203_silent_when_no_dj_fixi_view_is_routed(tmp_path):
    files = {**GOOD_FILES, "htmx.html": '<a hx-get="/x/">x</a>'}
    with override_settings(TEMPLATES=fs_templates(tmp_path, files), ROOT_URLCONF="tests.urlconfs.fbv_only"):
        assert "dj_fixi.W203" not in check_ids()


def test_w203_silent_when_django_htmx_is_installed_too(tmp_path, monkeypatch):
    from django.apps import apps

    real = apps.is_installed
    monkeypatch.setattr(apps, "is_installed", lambda name: name == "django_htmx" or real(name))
    files = {**GOOD_FILES, "htmx.html": '<a hx-get="/x/">x</a>'}
    with override_settings(TEMPLATES=fs_templates(tmp_path, files), ROOT_URLCONF="tests.urlconfs.good"):
        assert "dj_fixi.W203" not in check_ids()


def test_w203_silent_for_templates_under_site_packages(tmp_path, monkeypatch):
    files = {**GOOD_FILES, "vendored/htmx.html": '<a hx-get="/x/">x</a>'}
    templates = fs_templates(tmp_path, files)
    monkeypatch.setattr("sysconfig.get_paths", lambda: {"purelib": str(tmp_path), "platlib": str(tmp_path)})
    with override_settings(TEMPLATES=templates, ROOT_URLCONF="tests.urlconfs.good"):
        assert "dj_fixi.W203" not in check_ids()


def test_w203_silent_for_a_jinja2_only_project(tmp_path):
    (tmp_path / "htmx.html").write_text('<a hx-get="/x/">x</a>')
    jinja = [{"BACKEND": "django.template.backends.jinja2.Jinja2", "DIRS": [str(tmp_path)]}]
    with override_settings(TEMPLATES=jinja, ROOT_URLCONF="tests.urlconfs.good"):
        assert "dj_fixi.W203" not in check_ids()


@override_settings(TEMPLATES=TEMPLATES, ROOT_URLCONF="tests.urlconfs.partial_sources")
def test_w202_silent_for_deletes_and_for_partials_declared_at_the_urlconf():
    """The only two views W202 must name are the ones with no partial and a page to serve."""
    from django.core.checks import run_checks

    named = sorted(m.obj.__name__ for m in run_checks(tags=["dj_fixi"]) if m.id == "dj_fixi.W202")
    assert named == ["NoPartialCreate", "NoPartialList"]
