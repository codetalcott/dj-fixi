"""
The products list in a real browser. Opt-in, like the other browser tests:

    pytest -m browser          (from examples/demo_project)
"""

import os

import pytest

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]
sync_api = pytest.importorskip("playwright.sync_api")

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch(channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
        yield b
        b.close()


@pytest.fixture
def page(browser, live_server):
    from django.core.management import call_command

    call_command("seed", verbosity=0)
    context = browser.new_context()
    page = context.new_page()
    page.searches = []
    page.problems = []
    page.on("request", lambda r: "q=" in r.url and page.searches.append(r.url.split("?", 1)[1]))
    page.on("console", lambda m: m.type == "error" and page.problems.append(m.text))
    page.goto(live_server.url + "/")
    yield page
    assert page.problems == []
    context.close()


def shown(page):
    return page.locator("#product-container tbody tr td:first-child").all_inner_texts()


def test_the_list_filters_as_you_type(page):
    page.locator("input[name=q]").press_sequentially("vis", delay=30)
    page.wait_for_function("document.querySelectorAll('#product-container tbody tr').length === 1")

    assert shown(page) == ["Vise"]
    assert page.searches == ["q=vis"]  # one request for three keystrokes
    assert page.evaluate("document.activeElement.name") == "q"  # still typing


def test_clearing_the_box_brings_the_list_back(page):
    box = page.locator("input[name=q]")
    box.press_sequentially("vis", delay=30)
    page.wait_for_function("document.querySelectorAll('#product-container tbody tr').length === 1")
    box.fill("")
    page.wait_for_function("document.querySelectorAll('#product-container tbody tr').length === 10")


def test_paging_keeps_the_search(page):
    page.locator("input[name=q]").press_sequentially("a", delay=30)
    page.locator("#product-container .pagination >> text=Page 1 of 2").wait_for()
    page.locator("#product-container").get_by_role("link", name="Next").click()
    page.locator("#product-container .pagination >> text=Page 2 of 2").wait_for()
    assert all("a" in name.lower() for name in shown(page))


def test_the_newest_keystroke_wins_over_a_slow_answer(page):
    """
    The first search is still unanswered when the second is typed.

    fixi would drop the second (a request from the same element is in flight);
    the demo aborts the first instead. The fixture's console check is part of
    this test: an abort made on purpose must not be reported as a failure.
    """
    held = []

    def hold_the_first(route):
        if route.request.url.endswith("q=v"):
            held.append(route)  # leave it pending
        else:
            route.continue_()

    page.route("**/?q=*", hold_the_first)
    box = page.locator("input[name=q]")
    box.press_sequentially("v")
    page.wait_for_function("true")
    for _ in range(40):
        if held:
            break
        page.wait_for_timeout(50)
    assert held, "the first search never left the browser"

    box.press_sequentially("is", delay=30)
    page.wait_for_function("document.querySelectorAll('#product-container tbody tr').length === 1")
    assert shown(page) == ["Vise"]
    assert page.searches == ["q=v", "q=vis"]

    try:
        held[0].continue_()  # the slow answer arrives at last, to nobody
    except Exception:
        pass  # already aborted, which is the point
    page.wait_for_timeout(400)
    assert shown(page) == ["Vise"]


def test_enter_still_submits_the_form(page):
    box = page.locator("input[name=q]")
    box.fill("")
    box.type("yok")
    box.press("Enter")
    page.wait_for_function("document.querySelectorAll('#product-container tbody tr').length === 1")
    assert shown(page) == ["Yoke"]
