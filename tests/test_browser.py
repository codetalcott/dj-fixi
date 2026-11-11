"""
The shim in a real browser: events after the swap, on a node that exists, and
the console guards. Opt-in:

    pip install playwright && playwright install chromium
    pytest -m browser

Set PLAYWRIGHT_CHANNEL=chrome to drive an installed Chrome instead of the
Chromium that ``playwright install`` downloads.
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
<button id="b6" fx-action="/b/frag/" fx-target="#b6">names itself</button>
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

EXT_PAGE = """{% load fixi_tags %}<!doctype html><html><head>{% fixi_scripts %}</head><body>
<div id="out">OLD</div>
<button id="ask" fx-action="/b/echo/?q=asked" fx-target="#out" fx-swap="innerHTML"
        ext-fx-confirm="Really?">confirm</button>
<input id="search" name="q" fx-action="/b/echo/" fx-trigger="input" fx-target="#out" fx-swap="innerHTML"
       ext-fx-debounce="150">
<button id="post" fx-action="/b/unsafe/" fx-method="POST" fx-target="#out" fx-swap="innerHTML">post</button>
<button id="delete" fx-action="/b/unsafe/" fx-method="DELETE" fx-target="#out" fx-swap="innerHTML">delete</button>
<button id="get" fx-action="/b/echo/?q=got" fx-target="#out" fx-swap="innerHTML">get</button>
<button id="elsewhere" fx-action="http://elsewhere.test/collect" fx-method="POST" fx-target="#out"
        fx-swap="innerHTML">cross-origin</button>
<script>
window.__errors = [];
const original = console.error;
console.error = (...args) => { __errors.push(args.map(String).join(" ")); original(...args); };
</script></body></html>"""

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "context_processors": ["django.template.context_processors.request"],
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {"browser/page.html": PAGE, "browser/ext.html": EXT_PAGE},
                )
            ],
        },
    }
]


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch(channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
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


@pytest.mark.django_db(transaction=True)
def test_an_element_that_targets_itself_is_not_reported(live_server, settings, page):
    """fx-target="#own-id" resolves to the element, exactly like a missing target does."""
    settings.ROOT_URLCONF = "tests.urlconfs.browser"
    settings.TEMPLATES = TEMPLATES
    page.goto(live_server.url + "/b/page/")

    page.click("#b6")
    page.wait_for_function("window.__seen.length >= 1")

    assert page.evaluate("window.__errors") == []
    assert page.evaluate("document.getElementById('b6')") is None  # it did swap itself


# ------------------------------------------------------------------ ext-fixi.js


@pytest.fixture
def ext(live_server, settings, page):
    settings.ROOT_URLCONF = "tests.urlconfs.browser"
    settings.TEMPLATES = TEMPLATES
    page.sent = []
    page.on("request", lambda r: "/b/" in r.url and "/b/ext/" not in r.url and page.sent.append(r))
    page.goto(live_server.url + "/b/ext/")
    yield page
    assert page.evaluate("window.__errors") == []


@pytest.mark.django_db(transaction=True)
def test_confirm_cancel_sends_nothing_and_ok_sends_once(ext):
    ext.once("dialog", lambda d: d.dismiss())
    ext.click("#ask")
    ext.wait_for_timeout(300)
    assert ext.sent == [] and ext.inner_text("#out") == "OLD"

    asked = []
    ext.once("dialog", lambda d: (asked.append(d.message), d.accept()))
    ext.click("#ask")
    ext.wait_for_selector("#out >> text=q=asked")
    assert asked == ["Really?"] and len(ext.sent) == 1


@pytest.mark.django_db(transaction=True)
def test_debounce_sends_one_request_for_a_burst_of_typing(ext):
    ext.locator("#search").press_sequentially("anvil", delay=20)
    ext.wait_for_selector("#out >> text=q=anvil")
    assert [r.url.split("?")[1] for r in ext.sent] == ["q=anvil"]


@pytest.mark.django_db(transaction=True)
def test_debounce_lets_the_newest_request_replace_an_unanswered_one(ext):
    held = []

    def hold_the_first(route):
        if route.request.url.endswith("q=a"):
            held.append(route)  # never answered while the test types on
        else:
            route.continue_()

    ext.route("**/b/echo/?q=*", hold_the_first)
    ext.locator("#search").press_sequentially("a")
    for _ in range(40):
        if held:
            break
        ext.wait_for_timeout(50)
    assert held, "the first request never left the browser"

    ext.locator("#search").press_sequentially("nvil", delay=20)
    ext.wait_for_selector("#out >> text=q=anvil")  # not dropped, though one was in flight
    assert [r.url.split("?")[1] for r in ext.sent] == ["q=a", "q=anvil"]


@pytest.mark.django_db(transaction=True)
def test_unsafe_same_origin_requests_carry_the_csrf_token(ext):
    for control, method in (("#post", "POST"), ("#delete", "DELETE")):
        ext.click(control)
        ext.wait_for_selector(f"#out >> text={method} accepted")  # a 403 would not say this
    assert all(r.headers.get("x-csrftoken") for r in ext.sent)

    ext.sent.clear()
    ext.click("#get")
    ext.wait_for_selector("#out >> text=q=got")
    assert "x-csrftoken" not in ext.sent[0].headers  # safe methods do not need it


@pytest.mark.django_db(transaction=True)
def test_the_csrf_token_is_never_sent_to_another_origin(ext):
    seen = []

    def collect(route):
        seen.append(route.request.headers)
        route.fulfill(status=200, body="collected", headers={"Access-Control-Allow-Origin": "*"})

    ext.route("http://elsewhere.test/**", collect)
    ext.click("#elsewhere")
    ext.wait_for_selector("#out >> text=collected")
    assert seen and all("x-csrftoken" not in headers for headers in seen)
