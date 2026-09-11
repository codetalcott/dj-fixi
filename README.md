# dj-fixi

Django integration for [Fixi.js](https://github.com/bigskysoftware/fixi) - a lightweight HTMX alternative for server-side rendering with hypermedia.

## Features

- 🎯 **Automatic Fixi Detection** - Middleware detects `FX-Request` headers
- 🔄 **Smart Template Selection** - Serve fragments for Fixi requests, full pages otherwise
- 🏗️ **View Mixins** - Drop-in enhancements for class-based views (`FxResponseMixin`, `ContextPersistenceMixin`, `OptimizedQueryMixin`)
- 🎨 **Template Tags** - Helpers for Fixi attributes, CSRF, and loading the (vendored) Fixi.js
- 📝 **Form Helpers** - `FxForm`/`FxModelForm` render Django forms with Fixi attributes
- 🧪 **Testing Utilities** - A test client that lints every response for what fixi.js would silently ignore, and refuses to guess about redirects
- 🔎 **Lint** - `dj_fixi.lint` knows the six attributes fixi reads and the htmx ones it does not (see [Lint](#lint))
- 🚨 **System Checks** - `manage.py check` catches the misconfigurations that would otherwise fail silently (see [System checks](#system-checks))

## Installation

```bash
pip install dj-fixi
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

### 2. Use FxView or mixins

```python
# views.py
from django.views.generic import ListView

from dj_fixi.views import FxView

class ProductListView(FxView, ListView):
    model = Product
    context_object_name = 'products'
    template_name = 'products/list.html'
    partial_template = 'products/list_partial.html'
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
    {% fixi_js %}      {# serves the fixi.js vendored with dj-fixi (needs staticfiles) #}
    {% fixi_events %}  {# optional: enables FX-Trigger events (see below) #}
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

## Architecture

Adapted from:
- [django-mod](https://github.com/...) - HypermediaView and middleware patterns
- [python-modules/crud](https://github.com/...) - CRUD mixins and renderers

### Key Differences: HTMX vs Fixi

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

- **Shipped shim (zero-config):** add `{% fixi_events %}` after `{% fixi_js %}`. It turns
  the header into a bubbling `CustomEvent` **after the swap**, dispatched on the element
  that made the request if it is still in the document and on `<body>` otherwise (a
  delete's `outerHTML` swap removes the element that asked). A string `target` key in
  the detail names a selector to dispatch on instead. Listen with
  `document.addEventListener("formSuccess", (e) => …)`. The same file logs to the console
  the three mistakes fixi swallows: an `fx-target` that matches nothing (fixi swaps into
  the element itself), a swap spelled so fixi cannot perform it, and a failed request.
- **moxi.js:** if you already use [moxi](https://fixiproject.org), write the equivalent
  `on-fx:swapped` handler that reads `evt.detail.cfg.response.headers.get('FX-Trigger')`.

Unsafe Fixi requests (POST/DELETE/…) still need a CSRF token; attach it per request via an
`fx:config` listener setting the `X-CSRFToken` header (see the demo's `base.html`).

## Lint

fixi.js reads six attributes and ignores everything else, so `hx-get` written from habit,
`fx-swap="outerhtml"`, `fx-trigger="keyup delay:200ms"` and an `fx-target` that matches
nothing all render a 200 and do nothing in the browser. `dj_fixi.lint` makes them loud on
the surface a test sees:

```python
from dj_fixi.testing import FxTestClient

client = FxTestClient()          # every text/html response is linted; errors raise
client.fx_get("/products/")     # a redirect here raises too: pass follow=True or False
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
|---|---|---|
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
in a separate companion package, **[dj-fixi-tables](https://github.com/codetalcott/dj-fixi-tables)**,
which builds on `dj-fixi`.

> Earlier releases shipped two half-finished table systems (a server-rendered
> `ModelTable` and a JSON `FxCRUDView` for a client plugin). Both were removed in favor
> of the focused `dj-fixi-tables` package.

## Documentation

- [llms.txt](llms.txt) - Complete API reference in one file, written for coding
  agents. Point your agent at it and it should not need to read the source.
- [CLAUDE.md](CLAUDE.md) - Development guide

## License

MIT
