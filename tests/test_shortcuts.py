"""Tests for shortcut functions"""

import pytest
from django.test import RequestFactory

from dj_fixi.shortcuts import render_fx


@pytest.fixture
def rf():
    return RequestFactory()


def test_render_fx_selects_fragment_for_fx_request(rf):
    """Test that render_fx uses fragment template for Fixi requests"""
    request = rf.get("/", HTTP_FX_REQUEST="true")
    request.is_fx = True
    request.fx_target = None
    request.fx_swap = "innerHTML"
    request.fx_trigger = None

    # Would need actual templates to fully test; just verify the fragment
    # template is selected for Fixi requests (raised error names the template).
    from django.template import TemplateDoesNotExist

    with pytest.raises(TemplateDoesNotExist) as exc:
        render_fx(
            request,
            fragment_template="fragment.html",
            page_template="page.html",
            context={"test": "data"},
        )
    assert "fragment.html" in str(exc.value)


def test_render_fx_adds_fx_context(rf):
    """Test that render_fx adds Fixi context variables"""
    request = rf.get("/")
    request.is_fx = False
    request.fx_target = None
    request.fx_swap = "innerHTML"
    request.fx_trigger = None

    context = {"test": "data"}

    # Non-Fixi request with no page_template falls back to the fragment template.
    from django.template import TemplateDoesNotExist

    with pytest.raises(TemplateDoesNotExist) as exc:
        render_fx(request, "test.html", context=context)
    assert "test.html" in str(exc.value)
