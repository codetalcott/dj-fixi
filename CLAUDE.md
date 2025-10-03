# CLAUDE.md

This file provides guidance to Claude Code when working with the dj-fixi repository.

## Project Overview

**dj-fixi** is a Django integration library for Fixi.js - a lightweight HTMX alternative for server-side rendering with hypermedia.

This project was created by adapting code from:
- [django-mod](../django-mod/) - HypermediaView and middleware patterns
- [python-modules/crud](../python-modules/crud/) - CRUD mixins and table renderers

## Architecture

### Key Components

1. **Middleware** ([dj_fixi/middleware.py](dj_fixi/middleware.py))
   - Detects `FX-Request: true` header
   - Sets `request.is_fx`, `request.fx_target`, `request.fx_swap`, `request.fx_trigger` attributes

2. **Views** ([dj_fixi/views.py](dj_fixi/views.py))
   - `FxView`: Base view with automatic template selection
   - `FxTemplateView`: Simple template view variant

3. **Mixins** ([dj_fixi/mixins.py](dj_fixi/mixins.py))
   - `FxResponseMixin`: Fragment template handling, form validation
   - `ContextPersistenceMixin`: URL state preservation
   - `OptimizedQueryMixin`: Query optimization

4. **Template Tags** ([dj_fixi/templatetags/fixi_tags.py](dj_fixi/templatetags/fixi_tags.py))
   - `{% fx_attrs %}`: Generate Fixi attributes
   - `{% fx_csrf_token %}`: CSRF tokens
   - `{% fixi_cdn %}`: Include Fixi.js

5. **Shortcuts** ([dj_fixi/shortcuts.py](dj_fixi/shortcuts.py))
   - `render_fx()`: Automatic template selection for FBVs

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
   if request.is_fx:
   ```

2. Change headers:
   ```python
   # Before (HTMX)
   target = request.htmx.target

   # After (Fixi)
   target = request.fx_target
   swap = request.fx_swap
   trigger = request.fx_trigger
   ```

3. Change attributes in templates:
   ```django
   {# Before (HTMX) #}
   <button hx-get="/api/data" hx-target="#result">Load</button>

   {# After (Fixi) #}
   <button {% fx_attrs action="/api/data" target="#result" %}>Load</button>
   ```

4. Change headers in responses:
   ```python
   # Before (HTMX)
   response['HX-Trigger'] = 'myEvent'

   # After (Fixi)
   response['FX-Trigger'] = 'myEvent'
   ```

## Important Notes

- Always use `FxMiddleware` in Django settings
- Template tags require `{% load fixi_tags %}`
- Fixi.js must be included in base templates
- Use `render_fx()` for simple cases, `FxView` for complex ones
