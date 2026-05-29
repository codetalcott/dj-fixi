# dj-fixi

Django integration for [Fixi.js](https://github.com/bigskysoftware/fixi) - a lightweight HTMX alternative for server-side rendering with hypermedia.

## Features

- 🎯 **Automatic Fixi Detection** - Middleware detects `FX-Request` headers
- 🔄 **Smart Template Selection** - Serve fragments for Fixi requests, full pages otherwise
- 🏗️ **View Mixins** - Drop-in enhancements for class-based views (`FxResponseMixin`, `ContextPersistenceMixin`, `OptimizedQueryMixin`)
- 🎨 **Template Tags** - Helpers for Fixi attributes, CSRF, and loading the (vendored) Fixi.js
- 📝 **Form Helpers** - `FxForm`/`FxModelForm` render Django forms with Fixi attributes
- 🧪 **Testing Utilities** - Test client with Fixi request helpers

## Installation

```bash
pip install dj-fixi
```

## Quick Start

### 1. Add middleware

```python
# settings.py
MIDDLEWARE = [
    ...
    'dj_fixi.middleware.FxMiddleware',
]
```

### 2. Use FxView or mixins

```python
# views.py
from dj_fixi.views import FxView

class ProductListView(FxView):
    template_name = 'products/list.html'
    partial_template = 'products/list_partial.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.all()
        return context
```

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
  client-side concerns — so `request.is_fx` is the one signal `FxMiddleware` sets.
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

- **Shipped shim (zero-config):** add `{% fixi_events %}` after `{% fixi_js %}`. It adds a
  small `fx:after` listener that turns the header into a bubbling `CustomEvent`, which you
  listen for with `document.addEventListener("formSuccess", (e) => …)`.
- **moxi.js:** if you already use [moxi](https://fixiproject.org), write the equivalent
  `on-fx:after` handler that reads `evt.detail.cfg.response.headers.get('FX-Trigger')`.

Unsafe Fixi requests (POST/DELETE/…) still need a CSRF token; attach it per request via an
`fx:config` listener setting the `X-CSRFToken` header (see the demo's `base.html`).

## Tables

`dj-fixi` deliberately stays small — it's the request/response/template adapter for
Fixi. Declarative, inline-editable tables (server-rendered, with Fixi row swaps) live
in a separate companion package, **[dj-fixi-tables](https://github.com/codetalcott/dj-fixi-tables)**,
which builds on `dj-fixi`.

> Earlier releases shipped two half-finished table systems (a server-rendered
> `ModelTable` and a JSON `FxCRUDView` for a client plugin). Both were removed in favor
> of the focused `dj-fixi-tables` package.

## Documentation

- [CLAUDE.md](CLAUDE.md) - Development guide

## License

MIT
