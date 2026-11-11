# dj-fixi Demo Project

Example Django project demonstrating dj-fixi usage.

## Setup

```bash
cd examples/demo_project
pip install -e ../../        # dj-fixi itself, from this checkout
python manage.py migrate
python manage.py seed        # 25 sample products; --reset starts over
python manage.py runserver
```

Then open <http://localhost:8000/> for the products app, and
<http://localhost:8000/pitfalls/> for the pitfalls page.

## The pitfalls page

Seven mistakes that are easy to make with Fixi and Django, each shown live,
twice: the naive version, which really is broken, next to what dj-fixi has you
write instead.

| # | Pitfall | What dj-fixi gives you |
| --- | --- | --- |
| 1 | A whole page lands inside a div | `render_fx` / `FxView`: fragment or page from one URL |
| 2 | htmx attributes, written from habit | `{% fx_attrs %}`, and lint `L101` |
| 3 | `fx-swap` in the wrong case | `{% fx_attrs %}` normalises it; lint `L103` |
| 4 | A form that redirects on success | `FxResponseMixin` |
| 5 | `FX-Trigger` with nobody listening | `{% fixi_events %}` |
| 6 | Cancel that does not cancel | `cfg.confirm`; lint `L112` |
| 7 | An unsafe request with no CSRF token | `{% fx_csrf_token %}` / `FxForm` |

The pairs are data in [pitfalls/catalog.py](pitfalls/catalog.py), and every
claim on the page is a test:

```bash
pip install pytest pytest-django
pytest                       # what the lint and the test client say about each pair

pip install playwright && playwright install chromium
pytest -m browser            # each pair in a real browser: the naive one fails, the other works
```

`PLAYWRIGHT_CHANNEL=chrome pytest -m browser` uses an installed Chrome instead
of downloading Chromium.

Some dj-fixi protections cannot be shown live because they stop the server from
starting: a wrong base-class order (`dj_fixi.E101`) and the other system checks.
Those are covered by the package's own tests.

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

### 4. Template Tags
- `{% fx_attrs %}`: Generate Fixi attributes
- `{% fx_csrf_token %}`: CSRF token for forms
- `{% fixi_js %}`: Include the vendored Fixi.js
- `{% fixi_events %}`: The `FX-Trigger` event shim

## Try It Out

Visit http://localhost:8000 and:

1. **Search and page through products** - The list swaps in place; the page doesn't reload
2. **Add a product** - Form validation with Fixi
3. **Edit a product** - Inline updates
4. **Delete a product** - Confirmation with Fixi

Open browser DevTools Network tab to see:
- Regular requests load full HTML
- Fixi requests only load fragments
- `FX-Request: true` header on Fixi requests
