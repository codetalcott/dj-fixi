# CLAUDE.md

This file provides guidance to Claude Code when working with the dj-fixi repository.

## Project Overview

**dj-fixi** is a Django integration library for Fixi.js - a lightweight HTMX alternative for server-side rendering with hypermedia.

This project was created by adapting code from:
- [django-mod](../django-mod/) - HypermediaView and middleware patterns
- [python-modules/crud](../python-modules/crud/) - CRUD mixins and table renderers

## Architecture

### Key Components

1. **Request detection** ([dj_fixi/request.py](dj_fixi/request.py))
   - `is_fx(request)` reads `FX-Request: true`, honoring `request.is_fx` when set
   - `vary_on_fx(response)` adds the `Vary` header every fragment/page URL needs
   - Detection deliberately does **not** default to False when the middleware is
     absent: that default was the root cause of seven silent failure modes

2. **Middleware** ([dj_fixi/middleware.py](dj_fixi/middleware.py))
   - Optional since 0.3.0. Sets `request.is_fx` and the `Vary` header
   - Fixi sends no target/swap/trigger headers, so `is_fx` is the only signal

3. **Views** ([dj_fixi/views.py](dj_fixi/views.py))
   - `FxView`: Base view with automatic template selection
   - `FxTemplateView`: Simple template view variant

4. **Mixins** ([dj_fixi/mixins.py](dj_fixi/mixins.py))
   - `FxResponseMixin`: Fragment template handling, form validation
   - `ContextPersistenceMixin`: URL state preservation
   - `OptimizedQueryMixin`: Query optimization

5. **Template Tags** ([dj_fixi/templatetags/fixi_tags.py](dj_fixi/templatetags/fixi_tags.py))
   - `{% fx_attrs %}`: Generate Fixi attributes
   - `{% fx_csrf_token %}`: CSRF tokens
   - `{% fixi_cdn %}`: Include Fixi.js

6. **Shortcuts** ([dj_fixi/shortcuts.py](dj_fixi/shortcuts.py))
   - `render_fx()`: Automatic template selection for FBVs

7. **System checks** ([dj_fixi/checks/](dj_fixi/checks/))
   - Registered by [dj_fixi/apps.py](dj_fixi/apps.py); IDs `dj_fixi.E101`…`W302`
   - Built on [dj_fixi/urlconf.py](dj_fixi/urlconf.py), a defensive URLconf walk
     that is public API (dj-fixi-tables reuses it) and never raises

## Fixi.js vs HTMX

### Fixi.js
- Request header: `FX-Request: true`
- Attributes: `fx-action`, `fx-method`, `fx-target`, `fx-swap`, `fx-trigger`
- Events: `fx:init`, `fx:before`, `fx:after`, `fx:swapped`
- Simpler, smaller (minimal feature set)

### HTMX
- Request header: `HX-Request: true`
- Attributes: `hx-get`, `hx-post`, `hx-target`, `hx-swap`
- More features (history, indicators, OOB swaps, etc.)

## Development

### Running Tests
```bash
pytest
```

Note that pytest does **not** run Django system checks (pytest-django has no
support for them). `tests/test_check_helper.py` covers dj-fixi's own, and
`dj_fixi.testing.assert_no_fixi_check_issues()` is what downstream projects use.
Run `manage.py check` in `examples/demo_project` to exercise them for real.

### Gotcha: stale bytecode when A/B testing a line

Toggling a line to compare before/after can silently keep running the old code.
CPython invalidates a `.pyc` on mtime **and size**, both at one-second
granularity — so an edit that swaps two names of equal length, applied within the
same second, looks unchanged. Reordering base classes is exactly this shape. Four
separate investigations of the same bug hit it. Clear caches before measuring:

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
```

### Running Demo
```bash
cd examples/demo_project
python manage.py migrate
python manage.py runserver
```

### Code Style
- Uses Ruff for linting and formatting
- Type hints required for public APIs
- Docstrings for all public functions/classes

## Migration from HTMX

If adapting HTMX code to Fixi:

1. Change request detection:
   ```python
   # Before (HTMX)
   if request.htmx:

   # After (Fixi)
   from dj_fixi import is_fx
   if is_fx(request):
   ```

2. Drop the request-header reads entirely:
   ```python
   # Before (HTMX)
   target = request.htmx.target
   swap = request.htmx.swap

   # After (Fixi): there is no equivalent.
   ```
   Fixi sends only `FX-Request: true`. Target and swap are client-side concerns
   it never puts on the wire, so there is nothing to read. (`request.fx_target`,
   `fx_swap` and `fx_trigger` existed briefly before 0.2.0 and were always empty.)

3. Change attributes in templates:
   ```django
   {# Before (HTMX) #}
   <button hx-get="/api/data" hx-target="#result">Load</button>

   {# After (Fixi) #}
   <button {% fx_attrs action="/api/data" target="#result" %}>Load</button>
   ```

4. Change headers in responses — and load the shim:
   ```python
   # Before (HTMX)
   response['HX-Trigger'] = 'myEvent'

   # After (Fixi)
   response['FX-Trigger'] = 'myEvent'
   ```
   Fixi core reads **no** response headers, so `FX-Trigger` is inert on its own.
   Add `{% fixi_events %}` after `{% fixi_js %}`, or write the equivalent moxi.js
   `on-fx:after` handler. Without one of those, this header does nothing.

## Design principle

When you find a failure mode, work down this list and stop at the first that
applies. Reaching for a system check when tier 1 is available is the
characteristic mistake in this codebase:

1. **Delete the dependency** so the wrong state cannot be represented
2. **Fail loudly** at the earliest deterministic moment (render, first request)
3. **Check at boot** with `django.core.checks`
4. **Document**

A check is only correct when the defect lives in the *project's* settings,
URLconf, or filesystem. A check that says "dj-fixi ignores this attribute" ships
a bug plus a note about the bug — fix the attribute instead.

## Important Notes

- `dj_fixi` must be in `INSTALLED_APPS`; `FxMiddleware` is optional since 0.3.0
- Read detection with `dj_fixi.is_fx(request)`, never `getattr(request, "is_fx", False)`
- dj-fixi classes go **first** in a base-class list (`FxView, ListView`)
- Template tags require `{% load fixi_tags %}`
- Fixi.js must be included in base templates
- Use `render_fx()` for simple cases, `FxView` for complex ones
- New checks need a case in `tests/test_checks_no_false_positives.py` first
