"""
The shim in a real browser: events after the swap, on a node that exists, and
the console guards. Opt-in:

    pip install playwright && playwright install chromium
    pytest -m browser
"""

import os

import pytest

pytestmark = pytest.mark.browser
sync_api = pytest.importorskip("playwright.sync_api")

# Playwright's sync API runs an event loop in this thread, and Django refuses
# database work from a thread with a running loop. Test-only, and the reason
# pytest-django documents this variable for exactly this situation.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

PAGE = """{% load fixi_tags %}<!doctype html><html><head>{% fixi_js %}{% fixi_events %}</head><body>
<div id="out">OLD</div>
<button id="b1" fx-action="/b/frag/" fx-target="#out" fx-swap="innerHTML">into #out</button>
<button id="b2" fx-action="/b/frag-target/" fx-target="#out" fx-swap="innerHTML">targeted event</button>
<button id="b3" fx-action="/b/frag/">replaces itself</button>
<button id="b4" fx-action="/b/frag/" fx-target="#missing">bad target</button>
<button id="b5" fx-action="/b/frag/" fx-target="#out" fx-swap="outerhtml">bad swap</button>
<script>
window.__seen = []; window.__errors = [];
document.addEventListener("ping", (e) => __seen.push({
  detail: e.detail,
  out: document.getElementById("out") && document.getElementById("out").textContent,
  on: e.target === document.body ? "BODY" : e.target.tagName + "#" + e.target.id,
}));
const original = console.error;
console.error = (...args) => { __errors.push(args.map(String).join(" ")); original(...args); };
</script></body></html>"""

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {"loaders": [("django.template.loaders.locmem.Loader", {"browser/page.html": PAGE})]},
    }
]


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


@pytest.mark.django_db(transaction=True)
def test_events_fire_after_the_swap_on_a_node_that_exists(live_server, settings, page):
    settings.ROOT_URLCONF = "tests.urlconfs.browser"
    settings.TEMPLATES = TEMPLATES
    page.goto(live_server.url + "/b/page/")

    page.click("#b1")
    page.wait_for_function("window.__seen.length >= 1")
    page.click("#b2")
    page.wait_for_function("window.__seen.length >= 2")
    page.click("#b3")
    page.wait_for_function("window.__seen.length >= 3")
    seen = page.evaluate("window.__seen")

    # after the swap: the handler sees the new DOM; the requester is still there
    assert seen[0] == {"detail": {"x": 1}, "out": "NEW", "on": "BUTTON#b1"}
    # a `target` key in the detail chooses the node
    assert seen[1]["on"] == "DIV#out" and seen[1]["out"] == "NEWER" and seen[1]["detail"]["x"] == 2
    # the default outerHTML swap replaced the requester, so the event lands on body
    assert seen[2]["on"] == "BODY"
    assert page.evaluate("document.getElementById('b3')") is None


@pytest.mark.django_db(transaction=True)
def test_the_console_guards_report_what_fixi_swallows(live_server, settings, page):
    settings.ROOT_URLCONF = "tests.urlconfs.browser"
    settings.TEMPLATES = TEMPLATES
    page.goto(live_server.url + "/b/page/")

    page.click("#b4")
    page.wait_for_function("window.__errors.length >= 1")
    page.wait_for_function("window.__seen.length >= 1")
    page.click("#b5")
    page.wait_for_function("window.__errors.length >= 2")
    errors = page.evaluate("window.__errors")

    assert any('fx-target="#missing" matches nothing' in e for e in errors)
    # ... and fixi did exactly that: the button swapped itself away, so the event landed on body
    assert page.evaluate("window.__seen")[0]["on"] == "BODY"
    assert page.evaluate("document.getElementById('b4')") is None
    assert any('fx-swap="outerhtml" is nothing fixi can do' in e for e in errors)
    # the bad swap throws inside fixi, so no fx:swapped and no event for it
    assert page.evaluate("window.__seen.length") == 1
    assert page.evaluate("document.getElementById('out').textContent") == "OLD"
