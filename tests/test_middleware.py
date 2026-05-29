"""Tests for FxMiddleware"""

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from dj_fixi.middleware import FxMiddleware


@pytest.fixture
def middleware():
    def get_response(request):
        return HttpResponse("OK")

    return FxMiddleware(get_response)


@pytest.fixture
def rf():
    return RequestFactory()


def test_middleware_detects_fx_request(middleware, rf):
    """Test that middleware detects Fixi requests"""
    request = rf.get("/", HTTP_FX_REQUEST="true")
    response = middleware(request)

    assert request.is_fx is True
    assert response["X-FX-Response"] == "true"


def test_middleware_detects_non_fx_request(middleware, rf):
    """Test that middleware detects regular requests"""
    request = rf.get("/")
    response = middleware(request)

    assert request.is_fx is False
    assert "X-FX-Response" not in response


def test_middleware_does_not_set_target_swap_trigger(middleware, rf):
    """Fixi.js never sends FX-Target/FX-Swap/FX-Trigger request headers (target
    and swap are client-side concerns), so the middleware must not invent
    request attributes for them. Only is_fx is real."""
    request = rf.get(
        "/",
        HTTP_FX_REQUEST="true",
        # These headers are not part of Fixi's wire protocol; even if present
        # they must be ignored rather than surfaced as request attributes.
        HTTP_FX_TARGET="#content",
        HTTP_FX_SWAP="outerHTML",
        HTTP_FX_TRIGGER="myButton",
    )
    middleware(request)

    assert request.is_fx is True
    assert not hasattr(request, "fx_target")
    assert not hasattr(request, "fx_swap")
    assert not hasattr(request, "fx_trigger")


@override_settings(DEBUG=True)
def test_middleware_adds_execution_time_header_in_debug(middleware, rf):
    """Test that middleware records per-request timing when DEBUG is on"""
    request = rf.get("/")
    response = middleware(request)

    assert "X-Execution-Time" in response
    assert response["X-Execution-Time"].endswith("ms")


@override_settings(DEBUG=False)
def test_middleware_omits_execution_time_when_not_debug(middleware, rf):
    """Timing header is suppressed outside DEBUG to avoid leaking timing"""
    request = rf.get("/")
    response = middleware(request)

    assert "X-Execution-Time" not in response


def test_middleware_no_longer_sets_mcp_attributes(middleware, rf):
    """The removed MCP cargo-cult should leave no trace on requests/responses."""
    request = rf.get("/", HTTP_X_MCP_SESSION="test-123")
    response = middleware(request)

    assert not hasattr(request, "is_mcp")
    assert not hasattr(request, "mcp_session")
    assert "X-MCP-Compatible" not in response
