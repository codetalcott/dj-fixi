"""
Each pitfall in a real browser: the naive side fails the way the page says,
and the dj-fixi side works. Opt-in, like the package's own browser tests:

    pip install playwright && playwright install chromium
    pytest -m browser          (from examples/demo_project)

Set PLAYWRIGHT_CHANNEL=chrome to drive an installed Chrome instead.
"""

import os

import pytest

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]
sync_api = pytest.importorskip("playwright.sync_api")

# See tests/test_browser.py in the package for why.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

DETAILS = "Widget 42: in stock, ships tomorrow."
PAGE_CHROME = "Details: the full page"


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch(channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
        yield b
        b.close()


@pytest.fixture
def page(browser, live_server):
    context = browser.new_context()
    page = context.new_page()
    page.requests_seen = []
    page.console_errors = []
    page.on("request", lambda r: page.requests_seen.append((r.method, r.url)))
    page.on("console", lambda m: m.type == "error" and page.console_errors.append(m.text))
    page.goto(live_server.url + "/pitfalls/")
    yield page
    context.close()


def fetches(page, fragment):
    return [r for r in page.requests_seen if fragment in r[1]]


def test_full_page(page):
    page.click("#full-page-naive button")
    page.wait_for_selector("#full-page-naive-out >> text=" + DETAILS)
    assert PAGE_CHROME in page.inner_text("#full-page-naive-out")  # the layout came too

    page.click("#full-page-fixed button")
    page.wait_for_selector("#full-page-fixed-out >> text=" + DETAILS)
    assert page.inner_text("#full-page-fixed-out").strip() == DETAILS


def test_htmx_attributes(page):
    page.click("#htmx-naive button")
    page.click("#htmx-fixed button")
    page.wait_for_selector("#htmx-fixed-out >> text=" + DETAILS)
    # the fixed button went second and has answered, so the naive one had its chance
    assert page.inner_text("#htmx-naive-out") == ""
    assert len(fetches(page, "/pitfalls/details/")) == 1


def test_swap_in_the_wrong_case(page):
    with page.expect_response("**/pitfalls/details/"):
        page.click("#swap-case-naive button")
    page.click("#swap-case-fixed button")
    page.wait_for_selector("#swap-case-fixed-out >> text=" + DETAILS)
    assert page.inner_text("#swap-case-naive-out") == ""  # requested, answered, not swapped
    assert any('fx-swap="innerhtml" is nothing fixi can do' in e for e in page.console_errors)


def test_form_that_redirects(page):
    # dj-fixi first: the naive form is about to put a second copy of this page on the page.
    page.fill("#redirect-fixed input[name=text]", "from the dj-fixi form")
    page.click("#redirect-fixed button[type=submit]")
    page.wait_for_function("document.getElementById('events-count').textContent === '1'")
    assert page.locator("#redirect-fixed .live .note-form").count() == 1
    assert page.input_value("#redirect-fixed input[name=text]") == ""  # blank, ready for the next

    assert page.locator("section.pitfall").count() == 8
    page.fill("#redirect-naive input[name=text]", "from the naive form")
    page.click("#redirect-naive button[type=submit]")
    # the redirect's target, the whole pitfalls page, replaced the form
    page.wait_for_selector("#redirect-naive .live h1 >> text=Pitfalls")
    assert page.locator("#redirect-naive .live section.pitfall").count() == 8
    assert page.locator("section.pitfall").count() == 16


def test_fx_trigger_needs_the_shim(page):
    without = page.frame_locator("#events-naive iframe")
    with_shim = page.frame_locator("#events-fixed iframe")
    for frame in (without, with_shim):
        frame.locator("button").click()
        frame.locator("#out >> text=The server answered").wait_for()
    with_shim.locator("#heard >> text=1").wait_for()
    assert without.locator("#heard").inner_text() == "0"


def test_cancel_that_does_not_cancel(page):
    page.on("dialog", lambda d: d.dismiss())  # the user chooses Cancel, both times

    page.click("#confirm-naive button")
    page.wait_for_selector("#confirm-naive-out >> text=received 1 request.")

    page.click("#confirm-fixed button")
    page.wait_for_timeout(400)
    assert page.inner_text("#confirm-fixed-out") == "The server has received 0 requests."
    assert len(fetches(page, "/confirm-fixed/")) == 0


def test_confirm_accepted_still_sends(page):
    page.on("dialog", lambda d: d.accept())
    page.click("#confirm-fixed button")
    page.wait_for_selector("#confirm-fixed-out >> text=received 1 request.")


def test_unsafe_request_without_a_token(page):
    """The two frames hold the same button; only the script tag differs."""
    bare = page.frame_locator("#csrf-naive iframe")
    with page.expect_response("**/pitfalls/save/") as naive:
        bare.locator("button").click()
    assert naive.value.status == 403
    bare.locator("#out >> text=CSRF").wait_for()

    full = page.frame_locator("#csrf-fixed iframe")
    with page.expect_response("**/pitfalls/save/") as fixed:
        full.locator("button").click()
    assert fixed.value.status == 200
    full.locator("#out >> text=Saved.").wait_for()


def test_trigger_modifiers(page):
    page.locator("#trigger-naive input").press_sequentially("anvil", delay=20)
    page.locator("#trigger-fixed input").press_sequentially("anvil", delay=20)
    page.wait_for_selector("#trigger-fixed-out >> text=You searched for: anvil")

    # the fixed box went second and has answered, so the naive one had its chance
    assert page.inner_text("#trigger-naive-out") == ""
    assert [r[1].split("?")[1] for r in fetches(page, "/pitfalls/echo/")] == ["q=anvil"]
