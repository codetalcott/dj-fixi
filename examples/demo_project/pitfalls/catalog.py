"""
The pitfalls, as data.

Each one is a mistake that is easy to make with Fixi and Django, shown twice:
the naive markup, and what dj-fixi has you write instead. Both are Django
template source, rendered live on the pitfalls page.

The snippets live here as strings, not as ``.html`` files, on purpose: the
naive halves are wrong by design, and ``manage.py fixi_lint`` (which CI runs
over every template file in this project) must stay clean.

``lint`` is the set of ``dj_fixi.L***`` ids the lint reports for the naive
markup. ``tests/test_pitfalls.py`` holds every entry to that, and to the fixed
markup being clean; ``tests/test_pitfalls_browser.py`` drives each pair in a
real browser and asserts the naive one fails the way ``problem`` says.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pitfall:
    slug: str
    title: str
    problem: str
    naive: str
    fixed: str
    fix: str
    caught_by: str
    lint: tuple[str, ...] = ()


PITFALLS = [
    Pitfall(
        slug="full-page",
        title="A whole page lands inside a div",
        problem=(
            "The view always renders its full template. A Fixi request gets the page, "
            "layout and all, and fixi swaps it into the target."
        ),
        naive="""\
<button fx-action="{% url 'pitfalls:details_page_only' %}"
        fx-target="#full-page-naive-out" fx-swap="innerHTML">Load details</button>
<div id="full-page-naive-out" class="out"></div>""",
        fixed="""\
<button fx-action="{% url 'pitfalls:details' %}"
        fx-target="#full-page-fixed-out" fx-swap="innerHTML">Load details</button>
<div id="full-page-fixed-out" class="out"></div>""",
        fix=(
            "render_fx(request, fragment, page) serves the fragment to Fixi requests and the "
            "page to everything else, from one URL, and sets Vary: FX-Request."
        ),
        caught_by=(
            "FxTestClient reports dj_fixi.L111 on the response; FxMiddleware logs it under DEBUG."
        ),
    ),
    Pitfall(
        slug="htmx",
        title="htmx attributes, written from habit",
        problem="fixi reads only fx-* attributes. The button renders, and clicking it does nothing.",
        naive="""\
<button hx-get="{% url 'pitfalls:details' %}"
        hx-target="#htmx-naive-out" hx-swap="innerHTML">Load details</button>
<div id="htmx-naive-out" class="out"></div>""",
        fixed="""\
<button {% fx_attrs action=details_url target="#htmx-fixed-out" swap="innerHTML" %}>Load details</button>
<div id="htmx-fixed-out" class="out"></div>""",
        fix="{% fx_attrs %} writes the fx-* attributes and refuses values fixi cannot use.",
        caught_by="The lint names each attribute and its Fixi translation.",
        lint=("dj_fixi.L101",),
    ),
    Pitfall(
        slug="swap-case",
        title="fx-swap in the wrong case",
        problem=(
            "fixi assigns the swap name as a DOM property, so innerhtml is not innerHTML. "
            "The request is sent, fixi throws afterwards, and nothing changes."
        ),
        naive="""\
<button fx-action="{% url 'pitfalls:details' %}"
        fx-target="#swap-case-naive-out" fx-swap="innerhtml">Load details</button>
<div id="swap-case-naive-out" class="out"></div>""",
        fixed="""\
<button {% fx_attrs action=details_url target="#swap-case-fixed-out" swap="innerhtml" %}>Load details</button>
<div id="swap-case-fixed-out" class="out"></div>""",
        fix='{% fx_attrs %} normalises the case, so swap="innerhtml" comes out as innerHTML.',
        caught_by="The lint, and a console error from {% fixi_events %} at click time.",
        lint=("dj_fixi.L103",),
    ),
    Pitfall(
        slug="trigger",
        title="Trigger modifiers, written from habit",
        problem=(
            "fixi hands fx-trigger to addEventListener as it is. With a delay modifier it "
            'waits for an event named "input delay:250ms", which never fires. Type in the box.'
        ),
        naive="""\
<input type="search" name="q" placeholder="Type here"
       fx-action="{% url 'pitfalls:echo' %}" fx-trigger="input delay:250ms"
       fx-target="#trigger-naive-out" fx-swap="innerHTML">
<div id="trigger-naive-out" class="out"></div>""",
        fixed="""\
<input type="search" name="q" placeholder="Type here"
       {% fx_attrs action=echo_url target="#trigger-fixed-out" swap="innerHTML" trigger="input" debounce=250 %}>
<div id="trigger-fixed-out" class="out"></div>""",
        fix=(
            'One event name in fx-trigger, and debounce=250 (ext-fx-debounce="250") for the '
            "pause. A newer request also replaces an unanswered older one. Needs {% fixi_scripts %}."
        ),
        caught_by="The lint; {% fx_attrs %} refuses the modifier at render.",
        lint=("dj_fixi.L105",),
    ),
    Pitfall(
        slug="redirect",
        title="A form that redirects on success",
        problem=(
            "A normal Django form view answers a valid POST with a redirect. fetch follows it "
            "before fixi sees anything, and the page it leads to replaces the form. Add a note "
            "on each side: both save it, and only one leaves you with a form and a list."
        ),
        naive="""\
{% include "pitfalls/note_form.html" with action=note_naive_url %}""",
        fixed="""\
{% include "pitfalls/note_form.html" with action=note_fixed_url %}""",
        fix=(
            "FxResponseMixin answers a Fixi POST with the fragment: the form (blank after a "
            "create, with errors and a 422 when invalid), the list via fx_collection, and an "
            "FX-Trigger event."
        ),
        caught_by="FxTestClient raises FxRedirectError when a Fixi request is answered with a redirect.",
    ),
    Pitfall(
        slug="events",
        title="FX-Trigger with nobody listening",
        problem=(
            "fixi reads no response headers. The server sends FX-Trigger and the page never "
            "hears about it."
        ),
        naive="""\
<iframe title="fixi.js alone" src="{% url 'pitfalls:frame' 'events' %}?scripts=bare"></iframe>""",
        fixed="""\
<iframe title="With fixi_scripts" src="{% url 'pitfalls:frame' 'events' %}?scripts=full"></iframe>""",
        fix=(
            "{% fixi_scripts %} in place of {% fixi_js %}. It loads the shim that turns the "
            "header into a DOM event, after the swap. The two frames differ in that one tag."
        ),
        caught_by="Nothing can see this from the server; the tag is the fix.",
    ),
    Pitfall(
        slug="confirm",
        title="Cancel that does not cancel",
        problem=(
            "Returning false from onclick only prevents the default action. fixi's own "
            "listener never checks, so choosing Cancel still sends the request."
        ),
        naive="""\
<button fx-action="{% url 'pitfalls:hit' token 'confirm-naive' %}"
        fx-target="#confirm-naive-out" fx-swap="innerHTML"
        onclick="return confirm('Delete the record?')">Delete</button>
<span id="confirm-naive-out" class="out">The server has received 0 requests.</span>""",
        fixed="""\
<button fx-action="{% url 'pitfalls:hit' token 'confirm-fixed' %}"
        fx-target="#confirm-fixed-out" fx-swap="innerHTML"
        ext-fx-confirm="Delete the record?">Delete</button>
<span id="confirm-fixed-out" class="out">The server has received 0 requests.</span>""",
        fix=(
            'ext-fx-confirm="...", or confirm= on {% fx_attrs %}. It sets cfg.confirm, which '
            "fixi awaits, and sends nothing when the answer is Cancel. Needs {% fixi_scripts %}."
        ),
        caught_by="The lint.",
        lint=("dj_fixi.L112",),
    ),
    Pitfall(
        slug="csrf",
        title="An unsafe request with no CSRF token",
        problem=(
            "A button that POSTs carries no token. Django answers 403, and fixi swaps the "
            "error page into the target, stylesheet included."
        ),
        naive="""\
<iframe title="fixi.js alone" src="{% url 'pitfalls:frame' 'csrf' %}?scripts=bare"></iframe>""",
        fixed="""\
<iframe title="With fixi_scripts" src="{% url 'pitfalls:frame' 'csrf' %}?scripts=full"></iframe>""",
        fix=(
            "{% fixi_scripts %} in place of {% fixi_js %}. Every unsafe same-origin request "
            "then carries Django's token in a header. The button in the two frames is identical."
        ),
        caught_by="Nothing static can know which requests are unsafe; the tag is the fix.",
    ),
]

BY_SLUG = {p.slug: p for p in PITFALLS}
