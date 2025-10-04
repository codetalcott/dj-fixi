# Using dj-fixi with Function-Based Views

While `FxTableMixin` only works with class-based views, dj-fixi provides two shortcuts for function-based views.

## Quick Reference

### 1. `render_table()` - All-in-one shortcut

```python
from dj_fixi.shortcuts import render_table
from .models import Product

def product_list(request):
    products = Product.objects.all()

    return render_table(
        request,
        queryset=products,
        fields=['name', 'price', 'stock'],
        editable_fields=['name', 'stock'],
        actions=['edit', 'delete'],
        template='products/list.html',
        formatters={'price': lambda p: f'${p:.2f}'}
    )
```

**Features:**
- Automatically returns JSON for FixiPlug requests (`FX-Data: json` header)
- Automatically returns HTML for browser requests
- No template needed (can return just table HTML)

### 2. `create_table()` - Manual control

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

    return render(request, 'products/list.html', {
        'table': table,
        'custom_data': 'example'
    })
```

**Features:**
- Returns a `ModelTable` object
- Add table to context alongside other data
- Full control over response

## Arguments

Both functions accept:

- `queryset` - Django queryset to display
- `fields` - List of field names to show (e.g., `['name', 'price']`)
- `editable_fields` - Fields that can be edited inline (optional)
- `actions` - List of actions: `['edit', 'delete']` (optional)
- `formatters` - Dict of field formatters (optional)

### `render_table()` specific:
- `request` - HttpRequest (required)
- `template` - Template path (optional)
- `json_mode` - Force JSON response (optional)
- `context` - Additional template context (optional)

## Examples

### Minimal Example (No Template)

```python
def product_list(request):
    return render_table(
        request,
        queryset=Product.objects.all(),
        fields=['name', 'price']
    )
```

Returns just the table HTML - useful for fragments.

### With Search/Filtering

```python
def product_list(request):
    products = Product.objects.all()

    search = request.GET.get('q')
    if search:
        products = products.filter(name__icontains=search)

    return render_table(
        request,
        queryset=products,
        fields=['name', 'price', 'stock'],
        template='products/list.html'
    )
```

### With Custom Formatters

```python
def product_list(request):
    return render_table(
        request,
        queryset=Product.objects.all(),
        fields=['name', 'price', 'created_at', 'is_active'],
        formatters={
            'price': lambda p: f'${p:.2f}',
            'created_at': lambda d: d.strftime('%Y-%m-%d'),
            'is_active': lambda v: '✅' if v else '❌'
        },
        template='products/list.html'
    )
```

### JSON API for FixiPlug

```python
def product_data(request):
    """JSON-only endpoint for FixiPlug client-side rendering."""
    return render_table(
        request,
        queryset=Product.objects.all(),
        fields=['name', 'price', 'stock'],
        json_mode=True  # Always return JSON
    )
```

### Hybrid: HTML + JSON

```python
def product_list(request):
    """Serves HTML initially, JSON for subsequent requests."""
    return render_table(
        request,
        queryset=Product.objects.all(),
        fields=['name', 'price', 'stock'],
        editable_fields=['name', 'stock'],
        template='products/list.html'
    )
    # Automatically returns:
    # - HTML when browser requests
    # - JSON when FixiPlug requests (FX-Data: json)
```

## Template Usage

### With `render_table()`

```django
{% load fixi_tags %}
<div fx-table fx-table-sortable>
    {{ table }}
</div>
```

### With `create_table()`

```django
{% load fixi_tags %}
<div>
    <h2>Products</h2>
    <p>Featured: {{ featured_products.count }}</p>

    <div fx-table>
        {{ table }}
    </div>
</div>
```

## Comparison: FBV vs CBV

### Class-Based View
```python
class ProductListView(FxTableMixin, ListView):
    model = Product
    table_fields = ['name', 'price']
    template_name = 'products/list.html'
```

### Function-Based View
```python
def product_list(request):
    return render_table(
        request,
        queryset=Product.objects.all(),
        fields=['name', 'price'],
        template='products/list.html'
    )
```

Both produce the same result! Use whichever style you prefer.
