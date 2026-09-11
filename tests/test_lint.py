"""One positive per lint rule, each tied to the fixi.js behaviour it reports."""

from django.http import HttpResponse, JsonResponse, StreamingHttpResponse

from dj_fixi.lint import Finding, format_findings, lint_html, lint_response, translate_htmx


def ids(findings, level=None):
    return [f.id for f in findings if level is None or f.level == level]


FIXI_PAGE = '<!doctype html><html><head><script src="/static/dj_fixi/fixi.js"></script></head><body>{}</body></html>'


def test_htmx_attributes_are_a_warning_on_fragments_and_an_error_on_a_fixi_page():
    fragment = lint_html('<button hx-get="/x" hx-target="#r">x</button>')
    assert ids(fragment) == ["dj_fixi.L101", "dj_fixi.L101"] and {f.level for f in fragment} == {"warning"}
    page = lint_html(FIXI_PAGE.format('<button hx-post="/x">x</button><div id="r"></div>'))
    assert ids(page, "error") == ["dj_fixi.L101"]
    assert 'fx-action="..." fx-method="POST"' in page[0].message
    both = FIXI_PAGE.replace("</head>", '<script src="/js/htmx.min.js"></script></head>')
    assert ids(lint_html(both.format('<button hx-get="/x">x</button>')), "error") == []


def test_htmx_translations_say_what_to_write_or_that_there_is_nothing():
    assert "fx-target" in translate_htmx("hx-target") and "closest" in translate_htmx("hx-target")
    assert "no fixi equivalent" in translate_htmx("hx-boost")
    assert "no fixi equivalent" in translate_htmx("hx-push-url")
    assert "fx:config" in translate_htmx("hx-confirm")
    assert "addEventListener" in translate_htmx("hx-on:click")
    assert translate_htmx("data-hx-get").startswith("hx-get ->")


def test_typos_of_control_attributes_on_a_control():
    f = lint_html('<a fx-action="/x" fx-targt="#r">x</a>')
    assert ids(f) == ["dj_fixi.L102"] and "did you mean fx-target?" in f[0].message
    assert lint_html('<a fx-action="/x" fx-swpa="innerHTML">x</a>')[0].id == "dj_fixi.L102"


def test_swap_case_is_an_error_and_htmx_styles_are_warnings():
    f = lint_html('<a fx-action="/x" fx-swap="outerhtml">x</a>')
    assert ids(f) == ["dj_fixi.L103"] and "outerHTML" in f[0].message and f[0].fixi_line == "fixi.js:63-65"
    assert ids(lint_html('<a fx-action="/x" fx-swap="innerHTML swap:1s">x</a>'), "error") == ["dj_fixi.L104"]
    assert ids(lint_html('<a fx-action="/x" fx-swap="delete">x</a>'), "warning") == ["dj_fixi.L104"]
    assert ids(lint_html('<a fx-action="/x" fx-swap="outerMorph">x</a>'), "warning") == ["dj_fixi.L104"]


def test_trigger_with_modifiers_method_fetch_refuses_empty_action():
    assert ids(lint_html('<input fx-action="/x" fx-trigger="keyup delay:200ms">')) == ["dj_fixi.L105"]
    assert ids(lint_html('<a fx-action="/x" fx-trigger="click, change">x</a>')) == ["dj_fixi.L105"]
    assert ids(lint_html('<a fx-action="/x" fx-method="TRACE">x</a>')) == ["dj_fixi.L106"]
    f = lint_html('<a fx-action="">x</a>')
    assert ids(f) == ["dj_fixi.L107"] and "./undefined" in f[0].message


def test_targets_that_match_nothing_on_a_page():
    page = FIXI_PAGE.format('<button fx-action="/x" fx-target="#gone">x</button><div id="r"></div>')
    f = lint_html(page)
    assert ids(f) == ["dj_fixi.L108"] and "element itself" in f[0].message
    forgot_hash = FIXI_PAGE.format('<button fx-action="/x" fx-target="r">x</button><div id="r"></div>')
    f = lint_html(forgot_hash)
    assert ids(f) == ["dj_fixi.L108"] and 'did you mean "#r"' in f[0].message
    htmx_selector = FIXI_PAGE.format('<button fx-action="/x" fx-target="closest tr">x</button>')
    assert ids(lint_html(htmx_selector)) == ["dj_fixi.L108"]
    # a fragment cannot know what the page holds
    assert lint_html('<button fx-action="/x" fx-target="#gone">x</button>') == []


def test_duplicate_ids_only_when_a_target_points_at_them():
    page = FIXI_PAGE.format('<div id="r"></div><div id="r"></div><a fx-action="/x" fx-target="#r">x</a>')
    f = lint_html(page)
    assert ids(f) == ["dj_fixi.L109"] and "first one only" in f[0].message
    unreferenced = FIXI_PAGE.format('<img id="spinner"><img id="spinner"><a fx-action="/x">x</a>')
    assert lint_html(unreferenced) == []


def test_control_attributes_without_an_action():
    f = lint_html('<button fx-method="POST" fx-target="#r">x</button>')
    assert ids(f) == ["dj_fixi.L110"] and "fx-method, fx-target" in f[0].message
    assert lint_html('<div fx-ignore><a href="/x">x</a></div>') == []


def test_a_full_page_answering_a_fixi_request():
    f = lint_html(FIXI_PAGE.format("<p>hi</p>"), is_fx=True)
    assert ids(f) == ["dj_fixi.L111"] and f[0].level == "warning"
    assert lint_html(FIXI_PAGE.format("<p>hi</p>"), is_fx=False) == []


def test_ignore_and_formatting():
    html = '<a fx-action="/x" fx-swap="outerhtml" fx-trigger="a b">x</a>'
    assert ids(lint_html(html, ignore=["dj_fixi.L103"])) == ["dj_fixi.L105"]
    text = format_findings(lint_html(html), "GET /x/")
    assert text.startswith("dj-fixi lint found 2 issue(s) in GET /x/:")
    assert '(dj_fixi.L103) <a fx-action="/x"> line 1:0:' in text and "SILENCED_SYSTEM_CHECKS" in text
    assert str(Finding("dj_fixi.L101", "warning", "m", 3, 4, "div", "fixi.js:21")).endswith("(fixi.js:21)")


def test_lint_response_skips_what_it_cannot_judge():
    assert lint_response(JsonResponse({"hx-get": 1})) == []
    assert lint_response(HttpResponse(status=204)) == []
    assert lint_response(StreamingHttpResponse([b"<a hx-get='/x'>"], content_type="text/html")) == []
    assert lint_response(HttpResponse("<a hx-get='/x'>x</a>", status=500)) == []
    assert ids(lint_response(HttpResponse("<a hx-get='/x'>x</a>"))) == ["dj_fixi.L101"]
