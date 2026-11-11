# dj-fixi

Django integration for [Fixi.js](https://github.com/bigskysoftware/fixi), a lightweight HTMX alternative for server-side rendering with hypermedia.

## Features

- **Fragment or page from one view.** `FxView` and `render_fx` serve a fragment to Fixi requests and the full page to everything else.
- **Form and delete views that answer Fixi.** `FxResponseMixin` makes Django's generic create, update and delete views respond with fragments.
- **Template tags.** `{% fixi_scripts %}` loads the vendored `fixi.js` and dj-fixi's two small companions, and `{% fx_attrs %}` writes validated Fixi attributes.
- **Two extension attributes, and CSRF for free.** `ext-fx-confirm` asks before sending, `ext-fx-debounce` gives search-as-you-type, and every unsafe request carries Django's CSRF token (see [Extension attributes](#extension-attributes)).
- **Form helpers.** `FxForm` and `FxModelForm` render Django forms with Fixi attributes.
- **A test client that lints.** `FxTestClient` checks every response for what fixi.js would silently ignore, and refuses to guess about redirects.
- **Lint.** `dj_fixi.lint` knows the six attributes fixi reads and the htmx ones it does not (see [Lint](#lint)).
- **System checks.** `manage.py check` catches the misconfigurations that would otherwise fail silently (see [System checks](#system-checks)).

## Installation

Not on PyPI yet. Install from this repository:

```bash
pip install git+https://github.com/codetalcott/dj-fixi.git
```

## Quick Start

### 1. Install the app (and, optionally, the middleware)

```python
# settings.py
INSTALLED_APPS = [
    ...
    'dj_fixi',
]

MIDDLEWARE = [
    ...
    'dj_fixi.middleware.FxMiddleware',   # optional since 0.3.0
]
```

`dj_fixi` in `INSTALLED_APPS` is required: it is what serves the vendored
`fixi.js`, registers the template tags, and runs the system checks.

The middleware is **optional as of 0.3.0**. dj-fixi reads the `FX-Request` header
directly, so fragment selection works without it. Add it anyway if you want
`request.is_fx` in your own view code, or `Vary: FX-Request` on responses dj-fixi
does not build itself.

### 2. Write a view

```python
# views.py
from django.views.generic import ListView

from dj_fixi.views import FxView


class ProductListView(FxView, ListView):
    model = Product
    context_object_name = "products"
    template_name = "products/list.html"
    partial_template = "products/list_partial.html"
```

Two things the checks will hold you to. **dj-fixi classes come first** in the base
list, because Django's generic mixins do not call `super()` in the hooks dj-fixi
overrides. And `FxView` supplies **no HTTP handlers** — compose it with a generic
view as above, or subclass `FxTemplateView`, which provides `get()`. A subclass
with neither answers `405` forever.

### 3. Create templates

```django
{# products/list.html - Full page #}
{% load fixi_tags %}
<!DOCTYPE html>
<html>
<head>
    {% fixi_scripts %}  {# fixi.js, the FX-Trigger shim and the extensions (needs staticfiles) #}
</head>
<body>
    <div id="product-list">
        {% include "products/list_partial.html" %}
    </div>
</body>
</html>
```

```django
{# products/list_partial.html - Fragment for Fixi requests #}
{% for product in products %}
    <div class="product">{{ product.name }}</div>
{% endfor %}
```

## Fixi is not HTMX

**Fixi** is deliberately minimal, and this matters for what the server can assume:
- Request header: it sends **only** `FX-Request: true` (plus anything you add via
  `window.fixiCfg.headers`). It does **not** send target/swap/trigger headers — those are
  client-side concerns — so that one header is the only signal the server gets. Read it
  with `dj_fixi.is_fx(request)`, which works with or without `FxMiddleware`.
- Attributes: `fx-action`, `fx-method`, `fx-target`, `fx-swap`, `fx-trigger`.
- Default swap is **`outerHTML`** (HTMX defaults to `innerHTML`). `{% fx_attrs %}` follows
  Fixi here: it omits `fx-swap` for `outerHTML` and emits it for anything else.
- Events: `fx:init`, `fx:config`, `fx:before`, `fx:after`, `fx:swapped`, etc. Fixi core
  reads **no response headers** (see "Client-side events" below).

**HTMX** sends `HX-Request`/`HX-Target`/…, reads response headers (`HX-Trigger`,
`HX-Retarget`, …), and ships history/indicators/OOB swaps. If you want that richer
server-driven protocol, use HTMX with [django-htmx](https://django-htmx.readthedocs.io)
rather than expecting Fixi to behave the same way.

## Client-side events (FX-Trigger)

`FxResponseMixin` sets an `FX-Trigger` response header on form success/error (e.g.
`{"formSuccess": {"object_id": "7"}}`). **Fixi core does not read response headers**, so
this header does nothing on its own. Enable it one of two ways:

- **Shipped shim (zero-config):** `{% fixi_scripts %}` loads it (on its own it is
  `{% fixi_events %}` after `{% fixi_js %}`). It turns
  the header into a bubbling `CustomEvent` **after the swap**, dispatched on the element
  that made the request if it is still in the document and on `<body>` otherwise (a
  delete's `outerHTML` swap removes the element that asked). A string `target` key in
  the detail names a selector to dispatch on instead. Listen with
  `document.addEventListener("formSuccess", (e) => …)`. The same file logs to the console
  the three mistakes fixi swallows: an `fx-target` that matches nothing (fixi swaps into
  the element itself), a swap spelled so fixi cannot perform it, and a failed request.
- **moxi.js:** if you already use [moxi](https://fixiproject.org), write the equivalent
  `on-fx:swapped` handler that reads `evt.detail.cfg.response.headers.get('FX-Trigger')`.

## Extension attributes

Fixi is deliberately minimal and expects you to add behaviour through its events.
dj-fixi ships the few that nearly every Django project needs, in a 60-line file
loaded by `{% fixi_scripts %}`, using fixi's own `ext-fx-` naming convention:

```django
{# Ask first. Cancel sends nothing. #}
<button {% fx_attrs action=item.delete_url method="DELETE" confirm="Delete this item?" %}>Delete</button>

{# Search as you type: wait for a 250 ms pause; the newest request wins. #}
<input type="search" name="q"
       {% fx_attrs action="/items/" target="#results" swap="innerHTML" trigger="input" debounce=250 %}>
```

which render `ext-fx-confirm="Delete this item?"` and `ext-fx-debounce="250"`.

**CSRF needs nothing.** With `{% fixi_scripts %}` on the page, every non-GET,
same-origin Fixi request carries Django's token in the `X-CSRFToken` header. The
token is written onto the script element, so this works with
`CSRF_COOKIE_HTTPONLY` and `CSRF_USE_SESSIONS`. `{% fx_csrf_token %}` in a form is
only needed when the form must also work without JavaScript.

**Loading on arrival** is fixi's own: `fx-trigger="fx:inited"`.

An attribute that silently does nothing is the failure dj-fixi exists to prevent,
so these are checked like everything else: the lint flags a typo'd name, a bad
value, a debounced click or submit, and a page that uses one without loading the
script; `dj_fixi.W303` does the last at startup.

**This list is closed by design.** dj-fixi is not growing into htmx. An attribute
is added only if it closes a silent failure or data loss, fixi's own README
already sketches it, and its value is a single message or number. History,
boosting, out-of-band swaps, inheritance, polling and response headers that
retarget are out of scope; if you need them, use htmx with django-htmx.

## Lint

fixi.js reads six attributes and ignores everything else, so `hx-get` written from habit,
`fx-swap="outerhtml"`, `fx-trigger="keyup delay:200ms"` and an `fx-target` that matches
nothing all render a 200 and do nothing in the browser. `dj_fixi.lint` makes them loud on
the surface a test sees:

```python
from dj_fixi.testing import FxTestClient

client = FxTestClient()  # every text/html response is linted; errors raise
client.fx_get("/products/")  # a redirect here raises too: pass follow=True or False
```

Each finding names the element, the line, and the line of `fixi.js` that explains it, and
`dj_fixi.lint.FINDING_IDS` lists them all. `python manage.py fixi_lint` runs the same rules
over template source, for a person at the command line. `FxMiddleware` logs the same findings under
`DEBUG` and never raises. `{% fx_attrs %}` and `FxForm` refuse the same mistakes at render
time, before there is anything to lint.

## System checks

dj-fixi's failure modes were almost all silent: a wrong base-class order, a
typo'd template name, or a forgotten setting produced a `200` with the wrong body
and no exception anywhere. Most of those root causes are gone as of 0.3.0. What
remains lives in your project's settings, URLconf, or filesystem, where the
library cannot fix it — so `manage.py check` reports it at startup instead.

| ID | Level | Fires when |
| --- | --- | --- |
| `dj_fixi.E101` | Error | A Django class earlier in the MRO shadows a dj-fixi hook, e.g. `class V(ListView, FxView)` |
| `dj_fixi.W102` | Warning | Same, but your own class is the one that does not call `super()` |
| `dj_fixi.E103` | Error | A routed `FxView` subclass defines no HTTP handler, so it answers `405` forever |
| `dj_fixi.E104` | Error | A routed `FxView` subclass has no way to name a template |
| `dj_fixi.W001` | Warning | `FxMiddleware` is not installed (advisory) |
| `dj_fixi.W002` | Warning | No template engine enables `context_processors.request` |
| `dj_fixi.W201` | Warning | A declared `template_name`/`partial_template` resolves to nothing |
| `dj_fixi.W202` | Warning | A routed dj-fixi view declares no `partial_template` |
| `dj_fixi.W203` | Warning | A project template uses htmx attributes, which fixi ignores |
| `dj_fixi.E301` | Error | `staticfiles` is installed but `fixi.js` is unfindable |
| `dj_fixi.W302` | Warning | `django.contrib.staticfiles` is not installed |
| `dj_fixi.W303` | Warning | Templates use `ext-fx-*` but nothing loads `ext-fixi.js` |

Checks only inspect views reachable from your URLconf, and stay silent on a
project that is not using the feature in question — a `render_fx`-only project
with function-based views triggers none of them. Silence any individually:

```python
SILENCED_SYSTEM_CHECKS = ["dj_fixi.W202"]
```

### Running them under pytest

Django runs system checks on `runserver`, on `migrate`, and inside its own test
runner — but **not** under pytest, which is what most Django projects use. Add
this one test so your suite catches these too:

```python
from dj_fixi.testing import assert_no_fixi_check_issues


def test_dj_fixi_is_configured_correctly():
    assert_no_fixi_check_issues()
```

The failure output carries each message and its hint verbatim, so it says what to
change rather than just that something is wrong. `fixi_check_messages()` returns
the same messages if you want to inspect them, and both honor
`SILENCED_SYSTEM_CHECKS`.

**Why `E101` exists.** Django's generic view mixins do not call `super()` in
`get_template_names` or `get_context_data`, so anything listed after them in the
MRO is dead code. `class V(ListView, FxView)` still renders, still returns `200`,
and silently serves the full page to every Fixi request with `is_fx` missing from
the context. Put dj-fixi classes first:

```python
class ProductListView(FxView, ListView):   # correct
class ProductListView(ListView, FxView):   # dj_fixi.E101
```

## Tables

`dj-fixi` deliberately stays small — it's the request/response/template adapter for
Fixi. Declarative, inline-editable tables (server-rendered, with Fixi row swaps) live
in a separate companion package, **dj-fixi-tables**, which builds on `dj-fixi`.
That package is not published yet.

> Earlier releases shipped two half-finished table systems (a server-rendered
> `ModelTable` and a JSON `FxCRUDView` for a client plugin). Both were removed in favor
> of the focused `dj-fixi-tables` package.

## Documentation

- [llms.txt](llms.txt): complete API reference in one file, written for coding
  agents. Point your agent at it and it should not need to read the source.
- [CHANGELOG.md](CHANGELOG.md): what changed in each release, and why
- [CLAUDE.md](CLAUDE.md): development guide

## License

MIT. The vendored `dj_fixi/static/dj_fixi/fixi.js` is Fixi.js, by Big Sky
Software, under the Zero-Clause BSD license.
