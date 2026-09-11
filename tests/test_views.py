"""Tests for FxView"""

import pytest
from django.test import RequestFactory

from dj_fixi.views import FxTemplateView, FxView


@pytest.fixture
def rf():
    return RequestFactory()


def test_fx_view_detects_fx_request(rf):
    """Test that FxView detects Fixi requests"""

    class TestView(FxTemplateView):
        template_name = "test.html"
        partial_template = "test_partial.html"

    request = rf.get("/", HTTP_FX_REQUEST="true")

    # Process through middleware-like setup
    request.is_fx = True

    # Would need actual templates to test rendering
    # Just verify dispatch works
    view_instance = TestView()
    view_instance.setup(request)

    assert view_instance.is_fx is True


def test_fx_view_template_selection_for_fx_request(rf):
    """An explicit partial is the whole answer for a Fixi request: no fall-through."""

    class TestView(FxView):
        template_name = "test.html"
        partial_template = "test_partial.html"

    request = rf.get("/", HTTP_FX_REQUEST="true")
    request.is_fx = True

    view_instance = TestView()
    view_instance.setup(request)
    view_instance.dispatch(request)

    assert view_instance.get_template_names() == ["test_partial.html"]

    request = rf.get("/")
    request.is_fx = False
    view_instance.setup(request)
    assert view_instance.get_template_names() == ["test.html"]


def test_fx_view_template_fallback_with_suffix(rf):
    """Test that FxView tries _partial suffix when partial_template not set"""

    class TestView(FxView):
        template_name = "test.html"

    request = rf.get("/", HTTP_FX_REQUEST="true")
    request.is_fx = True

    view_instance = TestView()
    view_instance.setup(request)
    view_instance.dispatch(request)

    templates = view_instance.get_template_names()

    assert "test_partial.html" in templates
    assert "test.html" in templates


def test_fx_view_context_includes_fx_metadata(rf):
    """Context exposes is_fx (the one real Fixi signal) and nothing for the
    target/swap headers Fixi never sends."""

    class TestView(FxView):
        template_name = "test.html"

    request = rf.get("/", HTTP_FX_REQUEST="true")
    request.is_fx = True

    view_instance = TestView()
    view_instance.setup(request)
    view_instance.dispatch(request)

    context = view_instance.get_context_data()

    assert context["is_fx"] is True
    assert "fx_target" not in context
    assert "fx_swap" not in context


# ------------------------------------------------------------------ 0.4.0


@pytest.mark.parametrize(
    "name, expected",
    [
        ("products/list.html", "products/list_partial.html"),
        ("v1.0/list.html", "v1.0/list_partial.html"),  # .replace(".html", ...) got this wrong
        ("list.txt", "list_partial.txt"),
        ("products/list_partial.html", None),  # already a partial
        ("products/list.html#rows", None),  # a Django 6 partial reference stands alone
        ("noext", None),
        (None, None),
    ],
)
def test_derived_partial_name(name, expected):
    from dj_fixi.views import derived_partial_name

    assert derived_partial_name(name) == expected


LOCMEM = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                ("django.template.loaders.locmem.Loader", {"p/page.html": "PAGE"}),
            ],
        },
    }
]


def test_a_missing_explicit_partial_raises_at_the_first_request(rf):
    """Before 0.4.0 the typo fell through to the page, which fixi swapped into a div."""
    from django.template import TemplateDoesNotExist
    from django.test import override_settings

    class TestView(FxTemplateView):
        template_name = "p/page.html"
        partial_template = "p/typo_partail.html"

    with override_settings(TEMPLATES=LOCMEM):
        assert TestView.as_view()(rf.get("/")).render().content == b"PAGE"
        with pytest.raises(TemplateDoesNotExist, match="typo_partail"):
            TestView.as_view()(rf.get("/", HTTP_FX_REQUEST="true")).render()
