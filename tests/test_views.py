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
    """Test that FxView selects partial template for Fixi requests"""

    class TestView(FxView):
        template_name = "test.html"
        partial_template = "test_partial.html"

    request = rf.get("/", HTTP_FX_REQUEST="true")
    request.is_fx = True

    view_instance = TestView()
    view_instance.setup(request)
    view_instance.dispatch(request)

    templates = view_instance.get_template_names()

    assert "test_partial.html" in templates
    assert "test.html" in templates


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
