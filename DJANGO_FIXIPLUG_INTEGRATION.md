# Django + FixiPlug Integration Guide

This guide shows how **dj-fixi** (Django backend) and **FixiPlug** (JavaScript client) work together for advanced table features.

## Overview

**dj-fixi** generates tables on the server with automatic Fixi.js attributes, while **FixiPlug** enhances them with client-side features like sorting, filtering, pagination, and inline editing.

### Two Integration Modes

#### Mode 1: Server-Side Rendering + Client Enhancement

Django renders the initial HTML table → FixiPlug enhances it with client-side features

#### Mode 2: Client-Side Rendering from JSON

Django provides JSON data → FixiPlug renders the entire table client-side

---

## Setup

### 1. Install dj-fixi (Django)

```python
# settings.py
INSTALLED_APPS = [
    'dj_fixi',
]

MIDDLEWARE = [
    'dj_fixi.middleware.FxMiddleware',
]
```

### 2. Install FixiPlug (JavaScript)

```html
<!-- Include Fixi.js and FixiPlug -->
<script src="https://unpkg.com/fixi.js@latest/fixi.min.js"></script>
<script type="module">
  import fixiplug from './fixiplug.js';
  import createDataPipeline from './plugins/data-pipeline.js';
  import createTablePlugin from './plugins/table.js';
  import createDjangoIntegration from './plugins/django-integration.js';

  // Register plugins
  fixiplug.use(createDjangoIntegration());
  fixiplug.use(createDataPipeline());
  fixiplug.use(createTablePlugin({
    enableSorting: true,
    enableFiltering: true,
    enablePagination: true,
  }));
</script>
```

---

## Mode 1: Server-Side Rendering + Client Enhancement

### Django View (Class-Based)

```python
from django.views.generic import ListView
from dj_fixi.mixins import FxTableMixin
from .models import Product

class ProductListView(FxTableMixin, ListView):
    model = Product
    template_name = "products/list.html"

    # Configure table
    table_fields = ['name', 'price', 'stock', 'is_active']
    editable_fields = ['name', 'stock']
    table_actions = ['edit', 'delete']
    table_formatters = {
        'price': lambda p: f'${p:.2f}',
        'is_active': lambda v: '✓' if v else '✗',
    }
```

### Django View (Function-Based)

**Option 1: Using `render_table()` shortcut**

```python
from dj_fixi.shortcuts import render_table
from .models import Product

def product_list(request):
    products = Product.objects.all()

    return render_table(
        request,
        queryset=products,
        fields=['name', 'price', 'stock', 'is_active'],
        editable_fields=['name', 'stock'],
        actions=['edit', 'delete'],
        template='products/list.html',
        formatters={
            'price': lambda p: f'${p:.2f}',
            'is_active': lambda v: '✓' if v else '✗',
        }
    )
```

**Option 2: Using `create_table()` for more control**

```python
from dj_fixi.shortcuts import create_table
from django.shortcuts import render
from .models import Product

def product_list(request):
    products = Product.objects.all()

    table = create_table(
        queryset=products,
        fields=['name', 'price', 'stock'],
        editable_fields=['name', 'stock'],
        formatters={'price': lambda p: f'${p:.2f}'}
    )

    # Add custom context alongside table
    return render(request, 'products/list.html', {
        'table': table,
        'featured_products': products.filter(featured=True),
        'categories': Category.objects.all()
    })
```

### Django Template

```django
{% load fixi_tags %}
<!DOCTYPE html>
<html>
<head>
    {% fixi_cdn %}
    <script type="module">
      import fixiplug from '/static/fixiplug.js';
      import createDjangoIntegration from '/static/plugins/django-integration.js';
      import createTablePlugin from '/static/plugins/table.js';

      fixiplug.use(createDjangoIntegration());
      fixiplug.use(createTablePlugin());
    </script>
</head>
<body>
    <div id="product-table" fx-table fx-table-sortable fx-table-search>
        {# Django renders initial HTML table #}
        {{ table }}
    </div>
</body>
</html>
```

### Result

- Django generates the initial HTML table with all data
- FixiPlug enhances it with:
  - Client-side sorting (click headers)
  - Client-side search/filtering
  - Client-side pagination
  - Inline editing (double-click cells)

---

## Mode 2: Client-Side Rendering from JSON

### Django View

```python
from django.http import JsonResponse
from django.views.generic import ListView
from dj_fixi.tables import ModelTable
from .models import Product

class ProductDataView(ListView):
    model = Product

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Handle server-side sorting
        sort = request.GET.get('sort')
        direction = request.GET.get('dir', 'asc')
        if sort:
            order = sort if direction == 'asc' else f'-{sort}'
            queryset = queryset.order_by(order)

        # Build table
        table = ModelTable(
            queryset=queryset,
            fields=['name', 'price', 'stock', 'is_active'],
            editable_fields=['name', 'stock'],
            actions=['edit', 'delete'],
        )

        # Return JSON for FixiPlug
        return JsonResponse(table.to_json(), safe=False)
```

### HTML Template

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://unpkg.com/fixi.js@latest/fixi.min.js"></script>
    <script type="module">
      import fixiplug from '/static/fixiplug.js';
      import createDjangoIntegration from '/static/plugins/django-integration.js';
      import createDataPipeline from '/static/plugins/data-pipeline.js';
      import createTablePlugin from '/static/plugins/table.js';

      fixiplug.use(createDjangoIntegration());
      fixiplug.use(createDataPipeline());
      fixiplug.use(createTablePlugin({
        enableSorting: true,
        enableFiltering: true,
        enablePagination: true,
      }));
    </script>
</head>
<body>
    <!-- FixiPlug will render the table here from JSON -->
    <div
        fx-action="/api/products/"
        fx-trigger="load"
        fx-data-type="json"
        fx-table
        fx-table-sortable
        fx-table-search>
    </div>
</body>
</html>
```

### Result

- FixiPlug fetches JSON data from Django endpoint
- FixiPlug renders the entire table client-side
- All features (sort, filter, edit) work client-side
- Optional: Server-side sorting/filtering for large datasets

---

## Inline Editing

### Django Endpoint

```python
from django.http import JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404
from .models import Product

class ProductUpdateFieldView(View):
    def patch(self, request, *args, **kwargs):
        import json
        data = json.loads(request.body)

        product = get_object_or_404(Product, pk=data['id'])
        field = data['column']
        value = data['value']

        # Validate field
        if field not in ['name', 'stock']:
            return JsonResponse({'error': 'Field not editable'}, status=403)

        # Update
        setattr(product, field, value)
        product.save(update_fields=[field])

        return JsonResponse({
            'success': True,
            'id': product.pk,
            'column': field,
            'value': value
        })
```

### URL Configuration

```python
urlpatterns = [
    path('products/', ProductListView.as_view(), name='product_list'),
    path('products/update-field/', ProductUpdateFieldView.as_view(), name='product_update_field'),
]
```

### How It Works

1. User double-clicks a cell in the FixiPlug table
2. FixiPlug shows an inline editor
3. User edits and presses Enter
4. FixiPlug sends PATCH request to Django endpoint
5. Django integration plugin auto-adds CSRF token
6. Django validates and saves
7. FixiPlug updates the UI

---

## Django Integration Plugin Features

### Auto-Added Headers

```javascript
// Automatically adds to all requests:
headers: {
  'FX-Request': 'true',           // Django middleware detection
  'X-CSRFToken': 'token123...'    // CSRF protection (POST/PUT/PATCH/DELETE only)
}
```

### Django Form Error Handling

When Django returns `422 Unprocessable Entity` with form errors:

```python
# Django view
return JsonResponse({'errors': form.errors.get_json_data()}, status=422)
```

FixiPlug automatically displays errors:

```javascript
// Fires event: django:formErrors
// Automatically renders errors in UI
<div class="fx-django-errors">
  <div class="fx-error fx-error-name">
    <strong>name:</strong> This field is required
  </div>
</div>
```

### Query Parameter Preservation

Django's `ContextPersistenceMixin` preserves filter/sort/page params. FixiPlug supports this:

```html
<div
    fx-action="/products/"
    fx-preserve-params="sort,page,q">
    <!-- FixiPlug will preserve these params across requests -->
</div>
```

### Django Success Events

Django can trigger client-side events via `FX-Trigger` header:

```python
# Django view
response['FX-Trigger'] = json.dumps({
    'formSuccess': {
        'message': 'Product saved!',
        'object_id': product.pk
    }
})
```

FixiPlug listens:

```javascript
document.addEventListener('django:formSuccess', (event) => {
    console.log('Success:', event.detail.message);
    alert(`Product ${event.detail.object_id} saved!`);
});
```

---

## JSON Format

### Django Table JSON Output

```python
table = ModelTable(queryset=products, fields=['name', 'price'])
print(table.to_json())
```

```json
{
  "data": [
    {"id": 1, "name": "Widget", "price": 19.99},
    {"id": 2, "name": "Gadget", "price": 29.99}
  ],
  "columns": [
    {
      "key": "name",
      "label": "Name",
      "sortable": true,
      "editable": true,
      "inputType": "text"
    },
    {
      "key": "price",
      "label": "Price",
      "sortable": true,
      "editable": false
    }
  ],
  "meta": {
    "editable": true,
    "viewPrefix": "product"
  }
}
```

### FixiPlug Table Plugin Usage

The table plugin automatically detects this format and renders accordingly:

```javascript
// FixiPlug sees "columns" and "data" keys
// Automatically renders table with configured features
```

---

## Advanced Patterns

### Server-Side Pagination

```python
# Django view
class ProductDataView(ListView):
    def get(self, request):
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 10))

        queryset = Product.objects.all()
        total = queryset.count()

        start = (page - 1) * limit
        products = queryset[start:start + limit]

        table = ModelTable(queryset=products, fields=['name', 'price'])

        response = json.loads(table.to_json())
        response['pagination'] = {
            'page': page,
            'limit': limit,
            'total': total,
            'totalPages': (total + limit - 1) // limit
        }

        return JsonResponse(response)
```

```html
<div
    fx-action="/api/products/"
    fx-data-type="json"
    fx-table
    fx-table-server-page
    fx-page-size="10">
</div>
```

### Hybrid Mode: HTML + JSON

Initial page load uses server-rendered HTML for SEO/speed, subsequent updates use JSON:

```python
class ProductListView(ListView):
    def get(self, request):
        # Check if this is a Fixi request
        if request.headers.get('FX-Request'):
            # Return JSON for client-side updates
            table = ModelTable(...)
            return JsonResponse(table.to_json(), safe=False)

        # Return HTML for initial page load
        return super().get(request)
```

---

## Benefits

### Backend-Driven (dj-fixi)

✅ No manual `{% fx_attrs %}` needed
✅ Consistent table markup
✅ Server-side validation
✅ SEO-friendly initial render
✅ Type-safe Python code

### Client-Enhanced (FixiPlug)

✅ Fast client-side sorting/filtering
✅ Smooth inline editing UX
✅ No full page reloads
✅ Works offline (with cached data)
✅ Tiny bundle size (<8KB)

### Best of Both Worlds

🚀 Django generates data → FixiPlug enhances UX
🚀 Progressive enhancement
🚀 Works with/without JavaScript
🚀 Minimal template code
