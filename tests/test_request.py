"""
Tests for Fixi request detection and the Vary header (dj-fixi 0.3.0, F1/F2).

The point of dj_fixi.request is that detection no longer depends on FxMiddleware
being installed. Before 0.3.0 every call site read
``getattr(request, "is_fx", False)``, so a forgotten middleware entry meant
``is_fx`` was False forever: full HTML pages served into swap targets, 302s that
fixi followed, and 200s where a 422 was expected -- none of it raising.
"""

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from dj_fixi.request import FX_REQUEST_HEADER, is_fx, vary_on_fx


@pytest.fixture
def rf():
    return RequestFactory()


class TestIsFx:
    def test_detects_header_without_middleware(self, rf):
        """The whole point of F1: no middleware, still detected."""
        assert is_fx(rf.get("/", HTTP_FX_REQUEST="true")) is True

    def test_plain_request_is_not_fx(self, rf):
        assert is_fx(rf.get("/")) is False

    def test_wrong_header_value_is_not_fx(self, rf):
        assert is_fx(rf.get("/", HTTP_FX_REQUEST="yes")) is False

    def test_middleware_set_attribute_wins(self, rf):
        request = rf.get("/")
        request.is_fx = True
        assert is_fx(request) is True

    def test_explicit_false_is_honored_over_the_header(self, rf):
        """Deliberately forcing a full-page render must not be overridden."""
        request = rf.get("/", HTTP_FX_REQUEST="true")
        request.is_fx = False
        assert is_fx(request) is False


class TestVaryOnFx:
    def test_adds_the_header(self):
        assert FX_REQUEST_HEADER in vary_on_fx(HttpResponse("x"))["Vary"]

    def test_preserves_an_existing_vary(self):
        response = HttpResponse("x")
        response["Vary"] = "Accept-Encoding"
        vary = vary_on_fx(response)["Vary"]
        assert "Accept-Encoding" in vary and FX_REQUEST_HEADER in vary

    def test_does_not_duplicate(self):
        response = vary_on_fx(vary_on_fx(HttpResponse("x")))
        assert response["Vary"].lower().count("fx-request") == 1

    def test_returns_the_response_for_chaining(self):
        response = HttpResponse("x")
        assert vary_on_fx(response) is response
