# CLAUDE.md

Guidance for Claude Code when working in the dj-fixi repository.

## What this is

**dj-fixi** is the Django adapter for [Fixi.js](https://github.com/bigskysoftware/fixi):
request detection, fragment-or-page template selection, form and delete views that
answer Fixi requests, template tags, and the checks and lint that make Fixi's silent
failures loud. It deliberately stops there. Tables live in `dj-fixi-tables`; filtering,
sorting and query optimization belong to Django and django-filter, and were removed
in 0.5.0.

The user-facing documentation is [README.md](README.md) and [llms.txt](llms.txt);
[CHANGELOG.md](CHANGELOG.md) records why each thing changed. Read the changelog
before reintroducing anything that looks missing.

## The one fact about Fixi

Fixi sends exactly one request header, `FX-Request: true`, and reads **no** response
headers. Everything else follows from that:

- There is no target, swap or trigger on the wire. Nothing like `request.htmx.target`
  exists or can exist.
- `FX-Trigger` on a response is inert unless the page loads `{% fixi_events %}`
  (or an equivalent moxi.js handler).
- The default swap is `outerHTML`, not `innerHTML`.
- `fetch()` follows redirects before fixi sees them, so a redirect answered to a
  Fixi request swaps the redirect target's body into the control's target.

`dj_fixi/static/dj_fixi/fixi.js` is the vendored source and the authority. When a
claim about Fixi matters, read it there (it is 90 lines).

## Layout

| Path | What it holds |
| --- | --- |
| [dj_fixi/request.py](dj_fixi/request.py) | `is_fx(request)`, `vary_on_fx(response)`, `redirect_note` |
| [dj_fixi/middleware.py](dj_fixi/middleware.py) | `FxMiddleware`: optional. Sets `request.is_fx` and `Vary`; under `DEBUG` logs lint findings, risky redirects, and the template used (`X-FX-Template`). Never raises |
| [dj_fixi/views.py](dj_fixi/views.py) | `FxView` (no HTTP handlers of its own), `FxTemplateView` |
| [dj_fixi/mixins.py](dj_fixi/mixins.py) | `FxResponseMixin` for Django's form and delete views |
| [dj_fixi/shortcuts.py](dj_fixi/shortcuts.py) | `render_fx()` for function-based views |
| [dj_fixi/forms.py](dj_fixi/forms.py) | `FxForm`, `InlineEditForm`, `FxModelForm` |
| [dj_fixi/templatetags/fixi_tags.py](dj_fixi/templatetags/fixi_tags.py) | `fx_attrs`, `fx_csrf_token`, `fixi_js`, `fixi_events` |
| [dj_fixi/attrs.py](dj_fixi/attrs.py) | The one source of truth for what fixi.js accepts. The tag, `FxForm` and the lint all import it; `tests/test_lint_vocabulary.py` pins it against the vendored `fixi.js` |
| [dj_fixi/lint.py](dj_fixi/lint.py) | HTML lint. Runs in `FxTestClient` (raises), in `FxMiddleware` under `DEBUG` (logs), and over template source via `manage.py fixi_lint` |
| [dj_fixi/checks/](dj_fixi/checks/) | System checks `dj_fixi.E101`…`W302`, registered by [dj_fixi/apps.py](dj_fixi/apps.py) |
| [dj_fixi/urlconf.py](dj_fixi/urlconf.py) | Defensive URLconf walk the checks are built on. Public API; never raises |
| [dj_fixi/testing.py](dj_fixi/testing.py) | `FxTestClient`, `assert_no_fixi_check_issues()`, `fixi_check_messages()` |
| [dj_fixi/static/dj_fixi/](dj_fixi/static/dj_fixi/) | Vendored `fixi.js` and the `fixi-events.js` shim |
| [examples/demo_project/](examples/demo_project/) | A working app that exercises all of it |

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

## Rules

- Read detection with `dj_fixi.is_fx(request)`, never `getattr(request, "is_fx", False)`.
  That default turned a missing middleware into a permanent, silent "not a Fixi
  request" and was the root cause of seven failure modes.
- dj-fixi classes go **first** in a base-class list (`FxView, ListView`). Django's
  generic mixins do not call `super()` in the hooks dj-fixi overrides.
- A fragment exists only when a view names it in `partial_template`. Nothing is
  derived from `template_name`.
- Any response that differs by `FX-Request` must go through `vary_on_fx`.
- A new check needs a case in `tests/test_checks_no_false_positives.py` first; a new
  lint rule needs one in `tests/test_lint_no_false_positives.py` first. An Error
  stops `runserver`, so a false positive blocks someone rather than annoying them.
- Custom `fx-*` attribute names are never flagged by the lint.
- Type hints and docstrings on public APIs.

## Keeping the docs honest

`tests/test_llms_txt.py` pins [llms.txt](llms.txt) to the code: check IDs, swap
values, exported names and template tags must all match. Adding, renaming or
removing public API means editing `llms.txt`, the README and the changelog in the
same change; the test will fail on the first of those if you forget.

## Development

```bash
uv venv && uv pip install -e ".[dev]" && source .venv/bin/activate
pytest
ruff check . && ruff format --check .     # the formatter also covers code blocks in the .md files
(cd examples/demo_project && python manage.py check --fail-level WARNING && python manage.py fixi_lint)
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs the same, with
ruff pinned to one version so a formatter release cannot turn main red, on
Python 3.10 / Django 4.2, 3.12 / 5.2 and 3.13 / 6.0. Supporting 4.2 means no
`{% querystring %}` and no template partials in anything the package itself renders.

pytest does **not** run Django system checks (pytest-django has no support for
them). `tests/test_check_helper.py` covers dj-fixi's own, and
`assert_no_fixi_check_issues()` is what downstream projects use; `manage.py check`
in the demo exercises them for real.

`tests/test_browser.py` drives the events shim in Chromium and is skipped unless
Playwright is installed (`pip install playwright && playwright install chromium`).

To run the demo: `python manage.py migrate && python manage.py runserver` in
`examples/demo_project`.

### Gotcha: stale bytecode when A/B testing a line

Toggling a line to compare before/after can silently keep running the old code.
CPython invalidates a `.pyc` on mtime **and size**, both at one-second
granularity — so an edit that swaps two names of equal length, applied within the
same second, looks unchanged. Reordering base classes is exactly this shape. Four
separate investigations of the same bug hit it. Clear caches before measuring:

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
```

## Downstream

Two sibling repositories depend on this one. Check them when changing public API:

- **dj-fixi-tables** (`../dj-fixi-tables`) imports `dj_fixi.request` and renders
  `{% fixi_js %}` and `{% fixi_events %}` in its default page template. Removing
  `{% fixi_cdn %}` in 0.5.0 broke it until it was updated.
- **dj-hx** (`../dj-hx`) vendors `dj_fixi/urlconf.py` verbatim under its own
  docstring. After changing that file, run `tools/sync_shared.py` there.

## Releasing

Bump the version in `pyproject.toml`, `dj_fixi/__init__.py` and the first lines of
`llms.txt`; move the changelog's Unreleased section under the new version with a
date; tag `vX.Y.Z` on main. The package is not on PyPI; the README installs it from
GitHub.
