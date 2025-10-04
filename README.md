# dj-fixi

Django integration for [Fixi.js](https://github.com/bigskysoftware/fixi) - a lightweight HTMX alternative for server-side rendering with hypermedia.

## Features

- 🎯 **Automatic Fixi Detection** - Middleware detects `FX-Request` headers
- 🔄 **Smart Template Selection** - Serve fragments for Fixi requests, full pages otherwise
- 🏗️ **View Mixins** - Drop-in enhancements for class-based views
- 📊 **CRUD Renderers** - Field-type aware table rendering with inline editing
- 🎨 **Template Tags** - Helpers for Fixi attributes and patterns
- ✨ **Out-of-Band Updates** - Support for OOB swaps
- 🤖 **MCP Integration** - Standardized JSON responses for LLM agents
- ✅ **Field Validation** - Declarative validation rules with type checking
- 📝 **Audit Logging** - Optional change tracking for updates
- 🧪 **Testing Utilities** - Test client with Fixi and MCP helpers

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
<!DOCTYPE html>
<html>
<head>
    <script src="https://unpkg.com/fixi@1.0.0/fixi.js"></script>
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

**Fixi** uses:
- Request header: `FX-Request: true`
- Attributes: `fx-action`, `fx-method`, `fx-target`, `fx-swap`, `fx-trigger`
- Custom events: `fx:init`, `fx:before`, `fx:after`, `fx:swapped`

**HTMX** uses:
- Request header: `HX-Request: true`
- Attributes: `hx-get`, `hx-post`, `hx-target`, `hx-swap`
- More complex features (history, indicators, etc.)

## MCP Integration

dj-fixi provides standardized JSON responses compatible with Model Context Protocol (MCP) for LLM agent integration.

```python
from dj_fixi.views import FxCRUDView

class ProductCRUDView(FxCRUDView):
    model = Product
    fields = ['name', 'price', 'stock']
    editable_fields = ['price', 'stock']

    # Field validation
    validation_rules = {
        'price': {
            'required': True,
            'type': (int, float, Decimal),
            'validator': lambda v: v > 0 or ValueError("Must be positive")
        }
    }

    # Audit logging
    enable_audit_log = True

    def log_change(self, obj, old_values, new_values, user):
        AuditLog.objects.create(...)
```

All responses follow MCP format:
```json
{
  "success": true,
  "data": {"id": 1, "name": "Product"},
  "meta": {
    "timestamp": "2024-01-01T00:00:00",
    "view": "ProductCRUDView",
    "model": "Product"
  }
}
```

See [MCP_IMPLEMENTATION_SUMMARY.md](MCP_IMPLEMENTATION_SUMMARY.md) for details.

## Documentation

- [MCP_IMPLEMENTATION_SUMMARY.md](MCP_IMPLEMENTATION_SUMMARY.md) - MCP integration guide
- [MCP_INTEGRATION_PATTERNS.md](MCP_INTEGRATION_PATTERNS.md) - Patterns and best practices
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Core features overview
- [CLAUDE.md](CLAUDE.md) - Development guide

## License

MIT
