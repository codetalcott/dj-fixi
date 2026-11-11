"""
The extension attributes, everywhere they are emitted or judged: the validators,
{% fx_attrs %}, FxForm, the script tags, the lint, and check W303.

The no-false-positive cases come first in each section, as they did when the
rules were written.
"""

import re

import pytest
from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.template import Context, RequestContext, Template, TemplateSyntaxError
from django.test import RequestFactory, override_settings

from dj_fixi.attrs import validate_confirm, validate_debounce
from dj_fixi.forms import FxForm
from dj_fixi.lint import lint_html

from .checks_support import GOOD_FILES, check_ids, fs_templates

SCRIPTS = (
    '<script src="/static/dj_fixi/fixi.js"></script>'
    '<script src="/static/dj_fixi/fixi-events.js"></script>'
    '<script src="/static/dj_fixi/ext-fixi.js"></script>'
)
FIXI_ONLY = '<script src="/static/dj_fixi/fixi.js"></script>'


def page(body: str, scripts: str = SCRIPTS) -> str:
    return f"<!doctype html><html><head>{scripts}</head><body>{body}</body></html>"


def render(source: str, context=None) -> str:
    return Template("{% load fixi_tags %}" + source).render(context or Context({}))


def ids(findings):
    return [f.id for f in findings]


# ------------------------------------------------------------------ validators


def test_validators_accept_what_the_script_can_use():
    assert validate_confirm("Delete it?") == "Delete it?"
    assert validate_debounce(250) == "250" and validate_debounce("250") == "250"
    assert validate_debounce(250, "input") == "250" and validate_debounce(1, "keyup") == "1"


@pytest.mark.parametrize("message", ["", "   "])
def test_an_empty_confirm_is_refused(message):
    with pytest.raises(ValueError, match="sends the request without asking"):
        validate_confirm(message)


@pytest.mark.parametrize(
    "wait", ["250ms", "0.5s", "delay:250", "fast", "", 0, -5, "2.5", " 250 ms"]
)
def test_debounce_is_whole_milliseconds_and_nothing_else(wait):
    with pytest.raises(ValueError, match="whole number of milliseconds"):
        validate_debounce(wait)


@pytest.mark.parametrize("trigger", ["click", "submit", "Click"])
def test_a_click_or_submit_cannot_be_debounced(trigger):
    with pytest.raises(ValueError, match="default action"):
        validate_debounce(250, trigger)


# ------------------------------------------------------------------- fx_attrs


def test_fx_attrs_emits_the_extension_attributes():
    html = render(
        "<input {% fx_attrs action='/s/' trigger='input' debounce=250 %}>"
        "<button {% fx_attrs action='/d/' method='DELETE' confirm=question %}>x</button>",
        Context({"question": 'Delete "Anvil" & co?'}),
    )
    assert 'ext-fx-debounce="250"' in html and 'fx-trigger="input"' in html
    assert 'ext-fx-confirm="Delete &quot;Anvil&quot; &amp; co?"' in html  # escaped
    assert lint_html(page(html)) == []


def test_fx_attrs_emits_neither_by_default():
    assert "ext-fx" not in render("<a {% fx_attrs action='/x/' %}>x</a>")


def test_fx_attrs_refuses_what_would_silently_do_nothing():
    with pytest.raises(TemplateSyntaxError, match="without asking"):
        render("<a {% fx_attrs action='/x/' confirm=missing %}>x</a>", Context({"missing": ""}))
    with pytest.raises(TemplateSyntaxError, match="whole number of milliseconds"):
        render("<input {% fx_attrs action='/x/' trigger='input' debounce='250ms' %}>")
    with pytest.raises(TemplateSyntaxError, match="default action"):
        render("<form {% fx_attrs action='/x/' trigger='submit' debounce=250 %}></form>")


def test_fxform_confirm():
    class F(forms.Form):
        name = forms.CharField()

    html = FxForm(F(), action="/x/", confirm="Really save?").render()
    assert 'ext-fx-confirm="Really save?"' in html
    assert "ext-fx" not in FxForm(F(), action="/x/").render()
    with pytest.raises(ValueError, match="without asking"):
        FxForm(F(), action="/x/", confirm="").render()


# --------------------------------------------------------------- script tags


def test_fixi_scripts_emits_all_three_in_order_with_the_csrf_token():
    request = RequestFactory().get("/")
    html = render("{% fixi_scripts %}", RequestContext(request, {}))
    srcs = re.findall(r'src="([^"]+)"', html)
    assert [s.rsplit("/", 1)[1] for s in srcs] == ["fixi.js", "fixi-events.js", "ext-fixi.js"]
    token = re.search(r'data-csrf-token="([^"]+)"', html).group(1)
    assert (
        len(token) >= 32 and 'data-csrf-header="X-CSRFTOKEN"' in html
    )  # header names are case-insensitive
    assert lint_html(page("", scripts=html)) == []


@override_settings(CSRF_HEADER_NAME="HTTP_X_MY_TOKEN")
def test_the_header_name_follows_the_setting():
    request = RequestFactory().get("/")
    assert 'data-csrf-header="X-MY-TOKEN"' in render("{% fixi_ext %}", RequestContext(request, {}))


def test_fixi_scripts_without_a_request_says_so_instead_of_emitting_no_token():
    with pytest.raises(ImproperlyConfigured, match="RequestContext"):
        render("{% fixi_scripts %}")


def test_a_csrf_exempt_context_gets_the_script_and_no_token():
    html = render("{% fixi_ext %}", Context({"csrf_token": "NOTPROVIDED"}))
    assert "ext-fixi.js" in html and "data-csrf-token" not in html


# ------------------------------------------------------------------- the lint


def test_correct_use_and_other_peoples_extensions_are_clean():
    body = (
        '<div id="r"></div>'
        '<button fx-action="/d/" fx-method="DELETE" ext-fx-confirm="Delete?">x</button>'
        '<input name="q" fx-action="/s/" fx-trigger="input" fx-target="#r" ext-fx-debounce="250">'
        '<input name="q2" fx-action="/s/" fx-target="#r" ext-fx-debounce="300">'  # default: change
        '<textarea fx-action="/s/" fx-trigger="keyup" ext-fx-debounce="1"></textarea>'
        # upstream's own sketches and a project's inventions are not ours to judge
        '<button fx-action="/x/" ext-fx-disable ext-fx-indicator="#spin">x</button>'
        '<div fx-action="/n/" fx-trigger="poll" ext-fx-poll-interval="300"></div>'
        '<a fx-action="/x/" ext-fx-push ext-fx-my-thing="1">x</a>'
        '<button fx-action="/x/" ext-fx-confirm="{{ question }}" ext-fx-debounce="{{ ms }}">t</button>'
    )
    assert lint_html(page(body)) == []
    assert lint_html(body, full_document=False) == []  # a fragment cannot know what the page loads


def test_a_page_with_its_own_script_arrangement_is_not_second_guessed():
    """No fixi.js script tag in sight (bundled, inlined, deferred): nothing to conclude."""
    body = '<button fx-action="/d/" ext-fx-confirm="Delete?">x</button>'
    assert lint_html(page(body, scripts='<script src="/static/app.bundle.js"></script>')) == []


def test_l113_a_typo_of_ours_on_a_control():
    f = lint_html('<button fx-action="/d/" ext-fx-confrim="Delete?">x</button>')
    assert ids(f) == ["dj_fixi.L113"] and "did you mean ext-fx-confirm?" in f[0].message
    assert ids(lint_html('<input fx-action="/s/" ext-fx-debouce="250">')) == ["dj_fixi.L113"]


@pytest.mark.parametrize(
    "control,reason",
    [
        ('<button fx-action="/d/" ext-fx-confirm="">x</button>', "without asking"),
        ('<button fx-action="/d/" ext-fx-confirm>x</button>', "has no value"),
        ('<input fx-action="/s/" fx-trigger="input" ext-fx-debounce="250ms">', "whole number"),
        ('<input fx-action="/s/" fx-trigger="input" ext-fx-debounce="delay:250">', "whole number"),
        ('<button fx-action="/s/" ext-fx-debounce="250">x</button>', "default action"),  # click
        ('<form fx-action="/s/" ext-fx-debounce="250"></form>', "default action"),  # submit
    ],
)
def test_l114_a_value_the_script_cannot_use(control, reason):
    f = lint_html(control, full_document=False)
    assert ids(f) == ["dj_fixi.L114"] and f[0].level == "error" and reason in f[0].message


def test_l115_the_attribute_without_the_script():
    body = (
        '<button fx-action="/d/" ext-fx-confirm="Delete?">x</button>'
        '<input fx-action="/s/" fx-trigger="input" ext-fx-debounce="250">'
    )
    f = lint_html(page(body, scripts=FIXI_ONLY))
    assert ids(f) == ["dj_fixi.L115"] and f[0].level == "error"  # once per page, not per element
    assert "sent without asking" in f[0].message and "{% fixi_scripts %}" in f[0].message


def test_l110_covers_an_extension_attribute_with_no_action():
    f = lint_html('<button ext-fx-confirm="Delete?">x</button>')
    assert ids(f) == ["dj_fixi.L110"] and "ext-fx-confirm" in f[0].message


def test_the_older_messages_now_name_the_attribute_to_write():
    confirm = lint_html("<button fx-action='/d/' onclick=\"return confirm('?')\">x</button>")
    assert "ext-fx-confirm" in confirm[0].message
    trigger = lint_html('<input fx-action="/s/" fx-trigger="keyup delay:300ms">')
    assert ids(trigger) == ["dj_fixi.L105"] and "ext-fx-debounce" in trigger[0].message


# ------------------------------------------------------------------ check W303

BASE = "{% load fixi_tags %}<html><head>{% fixi_scripts %}</head><body></body></html>"
OLD_BASE = (
    "{% load fixi_tags %}<html><head>{% fixi_js %}{% fixi_events %}</head><body></body></html>"
)
USES = '<button fx-action="/d/" ext-fx-confirm="Delete?">x</button>'
USES_VIA_TAG = (
    "{% load fixi_tags %}<input {% fx_attrs action='/s/' trigger='input' debounce=250 %}>"
)


def w303(tmp_path, files):
    with override_settings(
        TEMPLATES=fs_templates(tmp_path, {**GOOD_FILES, **files}),
        ROOT_URLCONF="tests.urlconfs.good",
    ):
        return "dj_fixi.W303" in check_ids()


@pytest.mark.parametrize(
    "files",
    [
        {},  # the extensions are not used at all
        {"base.html": OLD_BASE},
        {"base.html": BASE, "list.html": USES},
        {"base.html": BASE, "list.html": USES_VIA_TAG},
        {
            "base.html": "<script src=\"{% static 'dj_fixi/ext-fixi.js' %}\"></script>",
            "a.html": USES,
        },
        {"base.html": "{% load fixi_tags %}{% fixi_js %}{% fixi_ext %}", "a.html": USES},
        # confirm= on some other tag is not ours
        {"base.html": OLD_BASE, "a.html": "{% include 'x.html' with confirm='yes' %}"},
    ],
    ids=["unused", "old-base", "loaded", "loaded-tag-use", "static-tag", "fixi_ext", "other-tag"],
)
def test_w303_is_silent_when_it_should_be(tmp_path, files):
    assert not w303(tmp_path, files)


@pytest.mark.parametrize("use", [USES, USES_VIA_TAG], ids=["attribute", "fx_attrs"])
def test_w303_when_templates_use_an_extension_and_nothing_loads_the_script(tmp_path, use):
    assert w303(tmp_path, {"base.html": OLD_BASE, "list.html": use})
