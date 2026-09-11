"""FxTestClient: every response linted, redirects made explicit, fx_put."""

import pytest
from django.test import override_settings

from dj_fixi.lint import FxLintError, FxLintWarning
from dj_fixi.testing import FxRedirectError, FxTestClient

PAGE = """{% load fixi_tags %}<!doctype html><html><head>{% fixi_js %}{% fixi_events %}</head><body>
<div id="r"></div>
<button fx-action="/client/frag/" fx-target="#r" fx-swap="innerHTML">load</button>
<a fx-action="/client/frag/" fx-method="DELETE" fx-target="#r">del</a>
</body></html>"""
HTMX = """{% load fixi_tags %}<!doctype html><html><head>{% fixi_js %}</head><body>
<button hx-get="/client/frag/" hx-target="#r">load</button><div id="r"></div></body></html>"""
FRAGMENT = '<tr fx-action="/client/frag/"><td>row {{ is_fx }}</td></tr>'

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {"client/page.html": PAGE, "client/htmx.html": HTMX, "client/fragment.html": FRAGMENT},
                )
            ],
            "context_processors": ["django.template.context_processors.request"],
        },
    }
]



@pytest.fixture(autouse=True)
def _client_settings():
    with override_settings(ROOT_URLCONF="tests.urlconfs.client", TEMPLATES=TEMPLATES):
        yield


def test_a_clean_page_carries_no_findings():
    response = FxTestClient().get("/client/page/")
    assert response.status_code == 200 and response.fx_findings == []


def test_htmx_in_a_fixi_page_raises_with_the_translation():
    with pytest.raises(FxLintError, match=r"dj_fixi.L101.*hx-get is htmx.*fx-action") as info:
        FxTestClient().get("/client/htmx/")
    assert "GET /client/htmx/" in str(info.value)


def test_lint_can_be_switched_off_or_silenced():
    assert FxTestClient(lint=False).get("/client/htmx/").status_code == 200
    assert FxTestClient(lint_ignore=("dj_fixi.L101",)).get("/client/htmx/").fx_findings == []
    with override_settings(SILENCED_SYSTEM_CHECKS=["dj_fixi.L101"]):
        assert FxTestClient().get("/client/htmx/").fx_findings == []


def test_fragments_fetched_with_fx_get_are_linted_too():
    with pytest.raises(FxLintError, match="dj_fixi.L103"):
        FxTestClient().fx_get("/client/bad-swap/")
    with pytest.warns(FxLintWarning, match="dj_fixi.L102.*fx-target"):
        response = FxTestClient().fx_get("/client/typo/")
    assert [f.id for f in response.fx_findings] == ["dj_fixi.L102"]


def test_non_html_and_empty_responses_are_skipped():
    client = FxTestClient()
    assert client.fx_get("/client/json/").fx_findings == []
    assert client.fx_get("/client/204/").status_code == 204
    assert client.fx_get("/client/stream/").fx_findings == []


def test_a_redirect_to_a_fixi_request_must_be_chosen():
    client = FxTestClient()
    with pytest.raises(FxRedirectError, match="302.*follows redirects silently.*follow=True"):
        client.fx_get("/client/goes-away/")
    assert client.fx_get("/client/goes-away/", follow=False).status_code == 302
    # following lands on a full page as a Fixi request, which is itself a warning (L111)
    followed = FxTestClient(lint_ignore=("dj_fixi.L111",)).fx_get("/client/goes-away/", follow=True)
    assert followed.status_code == 200 and followed.redirect_chain == [("/client/page/", 302)]


def test_append_slash_is_named():
    with pytest.raises(FxRedirectError, match="APPEND_SLASH.*trailing slash"):
        FxTestClient().fx_get("/client/needs-slash")


def test_plain_get_never_raises_on_redirects():
    assert FxTestClient().get("/client/goes-away/").status_code == 302


def test_helpers_send_the_header_and_fixi_shaped_bodies():
    client = FxTestClient()
    assert client.fx_get("/client/echo/", {"a": "1"}).content == b"GET fx=true ct= a=1"
    assert client.fx_post("/client/echo/", {"a": "2"}).content.startswith(b"POST fx=true ct=multipart/form-data a=2")
    assert client.fx_put("/client/echo/", {"a": "3"}).content == b"PUT fx=true ct=application/x-www-form-urlencoded a="
    assert client.fx_patch("/client/echo/", {"a": "5"}).content == b"PATCH fx=true ct=application/x-www-form-urlencoded a="
    assert client.fx_delete("/client/echo/?a=4").content.startswith(b"DELETE fx=true") and b"a=4" in client.fx_delete("/client/echo/?a=4").content
    assert b"ct=application/json" in client.fx_post("/client/echo/", json={"a": 1}).content


def test_render_fx_page_and_fragment_both_lint_clean():
    client = FxTestClient()
    assert client.get("/client/frag/").fx_findings == []
    assert client.fx_get("/client/frag/").fx_findings == []
