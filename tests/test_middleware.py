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
    middleware(request)

    assert request.is_fx is True


def test_middleware_detects_non_fx_request(middleware, rf):
    """Test that middleware detects regular requests"""
    request = rf.get("/")
    middleware(request)

    assert request.is_fx is False


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


def test_middleware_no_longer_sets_mcp_attributes(middleware, rf):
    """The removed MCP cargo-cult should leave no trace on requests/responses."""
    request = rf.get("/", HTTP_X_MCP_SESSION="test-123")
    response = middleware(request)

    assert not hasattr(request, "is_mcp")
    assert not hasattr(request, "mcp_session")
    assert "X-MCP-Compatible" not in response


# ------------------------------------------------------------------ 0.4.0
# Under DEBUG the middleware says what fixi would do silently. Never raises.

LOCMEM = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {"m/page.html": "PAGE", "m/page_partial.html": "PART"},
                )
            ]
        },
    }
]


@override_settings(DEBUG=True)
def test_debug_logs_lint_findings_for_fixi_responses_only(rf, caplog):
    mw = FxMiddleware(lambda r: HttpResponse('<a fx-action="/x/" fx-swap="outerhtml">x</a>'))
    with caplog.at_level("WARNING", logger="dj_fixi.middleware"):
        response = mw(rf.get("/x/", HTTP_FX_REQUEST="true"))
    assert response.status_code == 200  # logged, never raised
    assert any("dj_fixi.L103" in m and "GET /x/" in m for m in caplog.messages)
    caplog.clear()
    with caplog.at_level("WARNING", logger="dj_fixi.middleware"):
        mw(rf.get("/x/"))
    assert caplog.messages == []


@override_settings(DEBUG=False)
def test_nothing_is_logged_outside_debug(rf, caplog):
    mw = FxMiddleware(lambda r: HttpResponse('<a fx-action="/x/" fx-swap="outerhtml">x</a>'))
    with caplog.at_level("WARNING", logger="dj_fixi.middleware"):
        mw(rf.get("/x/", HTTP_FX_REQUEST="true"))
    assert caplog.messages == []


@override_settings(DEBUG=True)
def test_debug_logs_the_redirects_fetch_mishandles_and_not_prg(rf, caplog):
    from django.http import HttpResponseRedirect

    mw = FxMiddleware(lambda r: HttpResponseRedirect("/list/"))
    with caplog.at_level("WARNING", logger="dj_fixi.middleware"):
        mw(rf.delete("/things/3/", HTTP_FX_REQUEST="true"))
    assert any("DELETE /things/3/" in m and "follows redirects" in m for m in caplog.messages)
    caplog.clear()
    with caplog.at_level("WARNING", logger="dj_fixi.middleware"):
        mw(rf.post("/things/", HTTP_FX_REQUEST="true"))  # post-redirect-get is idiomatic
    assert caplog.messages == []

    slash = FxMiddleware(lambda r: HttpResponseRedirect("/things/"))
    with caplog.at_level("WARNING", logger="dj_fixi.middleware"):
        slash(rf.get("/things", HTTP_FX_REQUEST="true"))
    assert any("APPEND_SLASH" in m for m in caplog.messages)


@override_settings(DEBUG=True, TEMPLATES=LOCMEM)
def test_debug_names_the_template_a_fixi_response_came_from(rf):
    from django.template.response import TemplateResponse

    def view(request):
        return TemplateResponse(request, ["m/page_partial.html", "m/page.html"]).render()

    response = FxMiddleware(view)(rf.get("/x/", HTTP_FX_REQUEST="true"))
    assert response["X-FX-Template"] == "m/page_partial.html"
    assert "X-FX-Template" not in FxMiddleware(view)(rf.get("/x/"))


@override_settings(DEBUG=True)
def test_streaming_and_non_html_responses_are_left_alone(rf, caplog):
    from django.http import JsonResponse, StreamingHttpResponse

    for factory in (
        lambda r: StreamingHttpResponse([b'<a fx-swap="outerhtml">'], content_type="text/html"),
        lambda r: JsonResponse({"hx-get": 1}),
    ):
        with caplog.at_level("WARNING", logger="dj_fixi.middleware"):
            FxMiddleware(factory)(rf.get("/x/", HTTP_FX_REQUEST="true"))
    assert caplog.messages == []


# ------------------------------------------------------------------ 0.6.1


INCLUDES = {
    "outer.html": '{% include "inner.html" %}',
    "inner.html": "<p>fragment</p>",
}
CACHED = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    [("django.template.loaders.locmem.Loader", INCLUDES)],
                )
            ]
        },
    }
]


@override_settings(DEBUG=True, TEMPLATES=CACHED)
def test_every_header_is_an_exact_str_even_when_an_include_loaded_the_template_first(rf):
    """
    wsgiref (runserver) asserts ``type(value) is str`` and answers 500 otherwise.

    ``{% include "inner.html" %}`` loads the template under a SafeString name,
    and the cached loader hands that object to the next request for it.
    """
    from django.template.loader import render_to_string
    from django.template.response import TemplateResponse

    from dj_fixi.shortcuts import render_fx

    render_to_string("outer.html")  # the include gets there first

    def view(request):
        return TemplateResponse(request, "inner.html").render()

    for answer in (
        FxMiddleware(view)(rf.get("/x/", HTTP_FX_REQUEST="true")),
        FxMiddleware(lambda r: render_fx(r, "inner.html"))(rf.get("/x/", HTTP_FX_REQUEST="true")),
    ):
        assert answer["X-FX-Template"] == "inner.html"
        assert all(type(k) is str and type(v) is str for k, v in answer.items())
