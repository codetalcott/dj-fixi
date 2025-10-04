# FxCRUDView - Unified CRUD for FixiPlug Tables

`FxCRUDView` is a single Django view that handles **all** CRUD operations for FixiPlug table plugin integration.

## Why Use FxCRUDView?

Instead of creating separate views for list, detail, create, update, delete - use **one view** that handles everything:

✅ **GET** `/products/` → List with sorting, filtering, pagination
✅ **GET** `/products/123/` → Single record
✅ **POST** `/products/` → Create new record
✅ **PATCH** `/products/` → Inline edit single field
✅ **PATCH** `/products/123/` → Update full record
✅ **DELETE** `/products/123/` → Delete single record
✅ **DELETE** `/products/` → Bulk delete (with `{ids: [...]}`)

## Basic Example

```python
# views.py
from dj_fixi.views import FxCRUDView
from .models import Product

class ProductCRUDView(FxCRUDView):
    model = Product
    fields = ['name', 'price', 'stock', 'is_active']
    editable_fields = ['name', 'stock']
    searchable_fields = ['name', 'description']
    template_name = 'products/list.html'
    paginate_by = 20
    ordering = '-created_at'
```

```python
# urls.py
from .views import ProductCRUDView

urlpatterns = [
    path('products/', ProductCRUDView.as_view(), name='product_list'),
    path('products/<int:pk>/', ProductCRUDView.as_view(), name='product_detail'),
]
```

**That's it!** You now have a fully functional CRUD API that works with FixiPlug.

## Configuration

### Required Attributes

- **`model`** - Django model class
- **`fields`** - List of fields to expose (e.g., `['name', 'price']`)

### Optional Attributes

- **`editable_fields`** - Fields that can be edited inline (default: `[]`)
- **`searchable_fields`** - Fields that can be searched (default: `[]`)
- **`template_name`** - Template for HTML responses (default: `None`)
- **`paginate_by`** - Records per page (default: `10`)
- **`ordering`** - Default ordering (default: `None`)

## Supported Operations

### 1. List Records (GET)

**Request:**
```
GET /products/?page=1&limit=20&sort=name&dir=asc&q=widget
```

**Response (JSON for FixiPlug):**
```json
{
  "data": [
    {"id": 1, "name": "Widget", "price": 19.99, "stock": 100},
    {"id": 2, "name": "Gadget", "price": 29.99, "stock": 50}
  ],
  "columns": [
    {"key": "name", "label": "Name", "sortable": true, "editable": true},
    {"key": "price", "label": "Price", "sortable": true, "editable": false}
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 2,
    "totalPages": 1
  },
  "meta": {
    "editable": true,
    "searchable": true
  }
}
```

**Response (HTML for browser):**
- Renders `template_name` with `table` and `pagination` in context
- Or returns just table HTML if no template specified

### 2. Get Single Record (GET)

**Request:**
```
GET /products/123/
```

**Response (JSON):**
```json
{"id": 123, "name": "Widget", "price": 19.99, "stock": 100}
```

**Response (HTML):**
Returns a single table row HTML (for row replacement in tables)

### 3. Create Record (POST)

**Request:**
```
POST /products/
Content-Type: application/json

{"name": "New Product", "price": 39.99, "stock": 10}
```

**Response:**
```json
{
  "success": true,
  "id": 124,
  "data": {"id": 124, "name": "New Product", "price": 39.99, "stock": 10}
}
```

### 4. Inline Edit (PATCH)

**Request (from FixiPlug table plugin):**
```
PATCH /products/
Content-Type: application/json

{"id": 123, "column": "name", "value": "Updated Widget"}
```

**Response:**
```json
{
  "success": true,
  "id": 123,
  "column": "name",
  "value": "Updated Widget"
}
```

### 5. Full Update (PATCH)

**Request:**
```
PATCH /products/123/
Content-Type: application/json

{"name": "Updated Widget", "price": 24.99}
```

**Response:**
```json
{
  "success": true,
  "id": 123,
  "data": {"id": 123, "name": "Updated Widget", "price": 24.99, "stock": 100}
}
```

### 6. Delete Single Record (DELETE)

**Request:**
```
DELETE /products/123/
```

**Response:**
Empty response (status 200) - FixiPlug will swap outerHTML with nothing

### 7. Bulk Delete (DELETE)

**Request:**
```
DELETE /products/
Content-Type: application/json

{"ids": [123, 124, 125]}
```

**Response:**
```json
{"success": true, "deleted": 3}
```

## FixiPlug Integration

### HTML Template

```html
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
      fixiplug.use(createTablePlugin({
        enableSorting: true,
        enableFiltering: true,
        enablePagination: true,
        enableEditing: true,
      }));
    </script>
</head>
<body>
    <!-- FixiPlug renders table from JSON -->
    <div
        fx-action="/products/"
        fx-trigger="load"
        fx-data-type="json"
        fx-table
        fx-table-sortable
        fx-table-search
        fx-table-editable
        fx-table-save-url="/products/">
    </div>
</body>
</html>
```

### Features Enabled

- ✅ **Server-side sorting** - Click headers → Django sorts and returns JSON
- ✅ **Server-side search** - Type in search → Django filters
- ✅ **Server-side pagination** - Click page → Django paginates
- ✅ **Inline editing** - Double-click cell → Edit → PATCH to Django
- ✅ **Row deletion** - Click delete → DELETE to Django
- ✅ **Bulk operations** - Select rows → Bulk delete

## Advanced Customization

### Override Methods

```python
class ProductCRUDView(FxCRUDView):
    model = Product
    fields = ['name', 'price', 'stock']

    def get_queryset(self):
        """Filter queryset by current user."""
        return super().get_queryset().filter(owner=self.request.user)

    def serialize_object(self, obj):
        """Custom serialization."""
        data = super().serialize_object(obj)
        data['display_name'] = f"{obj.name} (${obj.price})"
        return data

    def get_column_config(self):
        """Custom column config."""
        columns = super().get_column_config()
        # Add custom formatter for price
        for col in columns:
            if col['key'] == 'price':
                col['formatter'] = 'currency'
        return columns
```

### Permission Checks

```python
class ProductCRUDView(FxCRUDView):
    model = Product
    fields = ['name', 'price']

    def dispatch(self, request, *args, **kwargs):
        # Check permissions
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Unauthorized'}, status=401)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Only staff can create
        if not request.user.is_staff:
            return JsonResponse({'error': 'Forbidden'}, status=403)
        return super().post(request, *args, **kwargs)

    def delete(self, request, pk=None, *args, **kwargs):
        # Only owners can delete
        obj = get_object_or_404(self.model, pk=pk)
        if obj.owner != request.user:
            return JsonResponse({'error': 'Forbidden'}, status=403)
        return super().delete(request, pk, *args, **kwargs)
```

### Custom Validation

```python
class ProductCRUDView(FxCRUDView):
    model = Product
    fields = ['name', 'price', 'stock']

    def patch(self, request, pk=None, *args, **kwargs):
        try:
            data = json.loads(request.body)

            # Custom validation for price
            if 'value' in data and data.get('column') == 'price':
                price = float(data['value'])
                if price < 0:
                    return JsonResponse(
                        {'error': 'Price cannot be negative'},
                        status=422
                    )

            return super().patch(request, pk, *args, **kwargs)

        except ValueError:
            return JsonResponse({'error': 'Invalid price'}, status=422)
```

## Comparison: Traditional vs FxCRUDView

### Traditional Approach (5+ views)

```python
class ProductListView(ListView):
    model = Product
    # ...

class ProductDetailView(DetailView):
    model = Product
    # ...

class ProductCreateView(CreateView):
    model = Product
    # ...

class ProductUpdateView(UpdateView):
    model = Product
    # ...

class ProductDeleteView(DeleteView):
    model = Product
    # ...

class ProductUpdateFieldView(View):
    def patch(self, request):
        # inline edit handler
        # ...
```

**URLs:**
```python
urlpatterns = [
    path('products/', ProductListView.as_view()),
    path('products/<int:pk>/', ProductDetailView.as_view()),
    path('products/create/', ProductCreateView.as_view()),
    path('products/<int:pk>/update/', ProductUpdateView.as_view()),
    path('products/<int:pk>/delete/', ProductDeleteView.as_view()),
    path('products/update-field/', ProductUpdateFieldView.as_view()),
]
```

### FxCRUDView Approach (1 view)

```python
class ProductCRUDView(FxCRUDView):
    model = Product
    fields = ['name', 'price', 'stock']
    editable_fields = ['name', 'stock']
```

**URLs:**
```python
urlpatterns = [
    path('products/', ProductCRUDView.as_view()),
    path('products/<int:pk>/', ProductCRUDView.as_view()),
]
```

**90% less code! 🎉**

## When to Use FxCRUDView

✅ **Use when:**
- Building a FixiPlug table with full CRUD operations
- You want RESTful JSON API + HTML in one view
- You need server-side sorting/filtering/pagination
- You want inline editing out of the box

❌ **Don't use when:**
- You need complex form handling (use Django forms + `FxResponseMixin`)
- You need custom URL patterns for different operations
- You're not using FixiPlug table plugin

## See Also

- [FxTableMixin](../dj_fixi/mixins.py) - For separate ListView + CRUD views
- [render_table()](../dj_fixi/shortcuts.py) - For function-based views
- [FixiPlug Integration Guide](../DJANGO_FIXIPLUG_INTEGRATION.md)
