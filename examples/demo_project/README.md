# dj-fixi Demo Project

Example Django project demonstrating dj-fixi usage.

## Setup

```bash
# From the demo_project directory
cd examples/demo_project

# Install dependencies (assuming dj-fixi is in development mode)
pip install -e ../../

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Create sample data
python manage.py shell
>>> from products.models import Product
>>> Product.objects.create(name="Widget", price=19.99, stock=100)
>>> Product.objects.create(name="Gadget", price=29.99, stock=50)
>>> exit()

# Run server
python manage.py runserver
```

## Features Demonstrated

### 1. FxView (CBV)
- [products/views.py](products/views.py#ProductListView)
- Automatic template selection (full page vs fragment)
- Works with Django's generic views

### 2. render_fx() Shortcut (FBV)
- [products/views.py](products/views.py#product_list_simple)
- Simple function-based view pattern
- Clean separation of fragment and page templates

### 3. Mixins
- **FxResponseMixin**: Form handling with Fixi
- **ContextPersistenceMixin**: URL state preservation
- **OptimizedQueryMixin**: Automatic query optimization

### 4. Template Tags
- `{% fx_attrs %}`: Generate Fixi attributes
- `{% fx_csrf_token %}`: CSRF token for forms
- `{% fixi_cdn %}`: Include Fixi.js library

## Try It Out

Visit http://localhost:8000 and:

1. **Search products** - Notice the URL updates, page doesn't reload
2. **Add a product** - Form validation with Fixi
3. **Edit a product** - Inline updates
4. **Delete a product** - Confirmation with Fixi

Open browser DevTools Network tab to see:
- Regular requests load full HTML
- Fixi requests only load fragments
- `FX-Request: true` header on Fixi requests
