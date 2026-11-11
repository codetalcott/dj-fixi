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
        slug="redirect",
        title="A form that redirects on success",
        problem=(
            "A normal Django form view answers a valid POST with a redirect. fetch follows it "
            "before fixi sees anything, and the page it leads to replaces the form."
        ),
        naive="""\
{% include "pitfalls/note_form.html" with action=note_naive_url %}""",
        fixed="""\
{% include "pitfalls/note_form.html" with action=note_fixed_url %}""",
        fix=(
            "FxResponseMixin answers a Fixi POST with the form fragment (blank after a create, "
            "with errors and a 422 when invalid) and an FX-Trigger event."
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
<iframe title="Without the shim" src="{% url 'pitfalls:events_frame' %}?shim=0"></iframe>""",
        fixed="""\
<iframe title="With the shim" src="{% url 'pitfalls:events_frame' %}?shim=1"></iframe>""",
        fix="{% fixi_events %} after {% fixi_js %} turns the header into a DOM event, after the swap.",
        caught_by="Nothing can see this from the server; the shim is the fix.",
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
        data-confirm="Delete the record?">Delete</button>
<span id="confirm-fixed-out" class="out">The server has received 0 requests.</span>""",
        fix=(
            "Set cfg.confirm in an fx:config listener (this page reads it from data-confirm). "
            "fixi awaits it and sends nothing when it resolves false."
        ),
        caught_by="The lint.",
        lint=("dj_fixi.L112",),
    ),
    Pitfall(
        slug="csrf",
        title="An unsafe request with no CSRF token",
        problem=(
            "A button that POSTs carries no token. Django answers 403, and fixi swaps the "
            "error page into the target, stylesheet included, so it restyles this page too."
        ),
        naive="""\
<button fx-action="{% url 'pitfalls:save' %}" fx-method="POST"
        fx-target="#csrf-naive-out" fx-swap="innerHTML">Save</button>
<div id="csrf-naive-out" class="out"></div>""",
        fixed="""\
<form fx-action="{% url 'pitfalls:save' %}" fx-method="POST"
      fx-target="#csrf-fixed-out" fx-swap="innerHTML">
  {% fx_csrf_token %}
  <button type="submit">Save</button>
</form>
<div id="csrf-fixed-out" class="out"></div>""",
        fix=(
            "Put the control in a form with {% fx_csrf_token %}; FxForm does this for you. For "
            "controls outside a form, set the X-CSRFToken header in an fx:config listener."
        ),
        caught_by="Nothing static can know which requests are unsafe; the token tag is the fix.",
    ),
]

BY_SLUG = {p.slug: p for p in PITFALLS}
