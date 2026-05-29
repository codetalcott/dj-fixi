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


def test_middleware_extracts_fx_headers(middleware, rf):
    """Test that middleware extracts Fixi headers"""
    request = rf.get(
        "/",
        HTTP_FX_REQUEST="true",
        HTTP_FX_TARGET="#content",
        HTTP_FX_SWAP="outerHTML",
        HTTP_FX_TRIGGER="myButton",
    )
    middleware(request)

    assert request.is_fx is True
    assert request.fx_target == "#content"
    assert request.fx_swap == "outerHTML"
    assert request.fx_trigger == "myButton"


def test_middleware_sets_defaults_for_missing_headers(middleware, rf):
    """Test that middleware sets defaults when headers are missing"""
    request = rf.get("/", HTTP_FX_REQUEST="true")
    middleware(request)

    assert request.is_fx is True
    assert request.fx_target is None
    assert request.fx_swap == "innerHTML"
    assert request.fx_trigger is None


def test_middleware_handles_non_fx_request_attributes(middleware, rf):
    """Test that non-Fixi requests get default attributes"""
    request = rf.get("/")
    middleware(request)

    assert request.is_fx is False
    assert request.fx_target is None
    assert request.fx_swap == "innerHTML"
    assert request.fx_trigger is None


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
