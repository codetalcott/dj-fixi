# Changelog

## 0.4.0 — what hx-flask taught

The handler-first htmx 4 work in hx-flask found failure shapes dj-fixi shares.
This release ports the ones that transfer to Fixi, in the usual order: delete
the dependency, else fail at the first deterministic moment, else check at
boot, else document. Every rule in the new lint was written against correct
Fixi code first (`tests/test_lint_no_false_positives.py`), and each names the
line of `fixi.js` it comes from.

### Breaking changes

- **`{% fixi_events %}` fires `FX-Trigger` events after the swap**, not before.
  The shim now listens on `fx:swapped` (fixi re-sends it on `document` when the
  requesting element is gone), so a handler can see the swapped-in DOM; the
  documented gotcha that it could not is gone. Events are dispatched on the
  element that made the request if it is still in the document, otherwise on
  `<body>` (never on `document`), and a string `target` key in the detail names
  a selector to dispatch on instead, so that key is reserved. A listener
  attached to the requesting element itself will miss events after an
  `outerHTML` swap; listen on `document`. Events are not fired when the swap
  throws (unknown `fx-swap`), which the shim now reports in the console.
- **`FxTestClient` lints every `text/html` response** and raises `FxLintError`
  on an error-level finding; warnings are `FxLintWarning`. Pass `lint=False`
  or `lint_ignore=(...)` to a client, or list ids in `SILENCED_SYSTEM_CHECKS`.
- **`FxTestClient.fx_*` raise `FxRedirectError` on a 3xx** unless the call
  says `follow=True` (what the browser would swap in) or `follow=False` (the
  redirect itself). fixi's fetch follows redirects; the test has to choose.
- **`{% fx_attrs %}` raises** on a `trigger` containing spaces or commas, a
  `method` fetch() refuses (CONNECT, TRACE, TRACK), and an empty `action`.
  `FxForm.render_attrs()` raises `ValueError` for the same, and now normalizes
  `swap` the way the tag does.
- **An explicit `partial_template` never falls through to the page.** For a
  Fixi request it is the only candidate; a missing file raises
  `TemplateDoesNotExist` at the first request instead of swapping the page into
  a div. W201 still reports it at boot.

### Fixed

- **`fx-method="DELETE"` works.** Django's `DeletionMixin.delete()` deletes and
  redirects without calling `form_valid`, so an HTTP DELETE from a Fixi
  control got a 302 that fetch followed *as a DELETE* and the list view's 405
  was swapped into the row. `FxResponseMixin.delete()` now answers a Fixi
  DELETE with the same 204 and `FX-Trigger` as the POST path. `delete` joined
  the hooks E101 checks. The demo's Delete button is an HTTP DELETE again.
- The derived `_partial` name replaced the first `.html` anywhere in the path
  (`v1.0/list.html` broke). `derived_partial_name()` uses the extension, and
  derives nothing from a Django 6 `file.html#partial` reference.
- The 0.3.0 entry said `fx-action=""` resolves to the current URL. fixi reads
  attributes with `||`, so it is `fetch(undefined)`: a request to `./undefined`.

### Added

- **`dj_fixi.lint`**: `lint_html`, `lint_response`, `Finding`, `FINDING_IDS`
  (`dj_fixi.L101` to `L111`). htmx attributes with the Fixi translation, typos
  of the four control attributes, swap spelled in the wrong case, swap with
  modifiers or an htmx style, trigger with modifiers, a method fetch refuses,
  an empty action, a target that matches nothing on the page, a targeted id
  that appears twice, control attributes without `fx-action`, a full document
  answering a Fixi request. Custom `fx-*` attributes are never flagged
  (`fx:config` listeners read them; dj-fixi-tables emits thirteen).
- **`dj_fixi.attrs`**: the vocabulary and the validators the tag, `FxForm` and
  the lint share, pinned against the vendored `fixi.js` by
  `tests/test_lint_vocabulary.py`.
- **Console guards in `fixi-events.js`**: an `fx-target` that matches nothing
  (fixi swaps into the element itself), a swap fixi cannot perform (instead of
  `Uncaught (in promise) outerhtml`), and the error fixi swallows on a failed
  request. Each is fixi's own predicate evaluated on the real DOM.
- **`FxMiddleware` under `DEBUG`** logs lint findings for every Fixi response,
  a redirect fetch would follow into a fragment (a DELETE/PUT/PATCH answered
  with a 3xx, or `APPEND_SLASH`'s fix-up), and the template each Fixi response
  came from, also sent as `X-FX-Template`. It never raises. `render_fx` sets
  the header too.
- **`FxTestClient.fx_put`**, and `response.fx_findings` on every response.
- **`dj_fixi.W203`**: a project template (never site-packages) uses htmx
  attributes; silent when django-htmx is installed. **`dj_fixi.W204`**: a
  routed view serves its fragment only through a derived name; the hint is the
  line to write. W201's hint explains Django 6 partial syntax.
- `partial_template = "products/list.html#rows"` documented (Django 6 native;
  older Django needs django-template-partials, and W201 says so).
- `tests/test_browser.py`: the shim under Playwright, opt-in (`pip install
  playwright`, `playwright install chromium`).

### Deprecated

- Derived partial names (`_partial` suffix, `fragments/` directory,
  `fx_template_suffix`). They still work; W204 names the one to write down.
  0.5.0 removes them.


## 0.3.0 — silent failures

An audit catalogued 47 configurations that produced wrong behavior with no
exception, no log line, and a 200 response. This release removes the root cause
of as many as possible, and makes most of the rest fail at startup.

The order of preference applied throughout: **delete the dependency** so the
wrong state cannot happen, else **fail loudly at the earliest deterministic
moment**, else **check at boot**, else document. A system check is only correct
when the defect lives in the *project's* settings, URLconf, or filesystem —
never in dj-fixi's own code.

### Fixed — these failure modes no longer exist

- **`FxMiddleware` is now optional.** Every call site read
  `getattr(request, "is_fx", False)`, so a forgotten middleware entry meant
  `is_fx` was False forever: full HTML pages served into swap targets, 302s that
  fixi followed, and 200s where a 422 was expected. Detection now reads the
  `FX-Request` header directly via the new `dj_fixi.is_fx()`. An explicitly set
  `request.is_fx` still wins, so the middleware and `FxTestClient` are unchanged.
- **`Vary: FX-Request` is now set** by the middleware, `FxView.render_to_response`,
  and `render_fx`. Without it, any URL that returns a fragment or a full page for
  the same path is a cache-poisoning bug that appears only behind a proxy.
- **`ContextPersistenceMixin.filterset_fields` actually filters.** It was
  documented and gated a branch, then discarded by `get_filterset`. A name that
  is not a field on the model now raises `ImproperlyConfigured` instead of
  quietly filtering nothing. New `filter_queryset()` hook; no new dependency.
- **Related-field sorts work.** `?sort=category__name` was validated with
  `_meta.get_field()`, which rejects `__` paths, so a valid sort was logged and
  dropped. Segments are now walked.
- **`FxForm`'s `cancel_action` is honored.** It was accepted, stored, documented,
  and then ignored in favor of a hardcoded `fx-action=""` — which fixi resolves
  to the *current URL*, so cancelling swapped the whole document into the target.
  `FxForm` also accepts an optional `request` and emits the CSRF input for unsafe
  methods.
- **`{% fx_csrf_token %}` works with no context-processor configuration.** It read
  `context["request"]` and returned `""` when absent, so the form rendered looking
  correct and every POST came back 403. It now reads `csrf_token` from the context
  the way Django's own tag does, and raises rather than returning empty.
- **`{% fx_attrs %}` normalizes swap case.** fixi dispatches swaps
  case-sensitively, so `swap="outerhtml"` reached fixi's `throw` and nothing
  swapped while the server returned 200. Unknown values now raise
  `TemplateSyntaxError`. `swap="morph"` is accepted for paxi.js.
- **`FxView.render_to_response` honors `response_class`, `content_type`, and
  `template_engine`.** They were previously ignored, with a docstring saying so.
- **`FxResponseMixin.get_success_message` no longer requires `self.model`.** On a
  `FormView` it raised `AttributeError` on the *success* path only.

### Added

- **Django system checks** (`dj_fixi.E101`, `W102`, `E103`, `E104`, `W001`,
  `W002`, `W201`, `W202`, `E301`, `W302`). The one that justifies the rest is
  **E101**: `class V(ListView, FxView)` silently disables partial-template
  selection and drops `is_fx` from the context while still returning 200. Checks
  never fire on a project that is not using the feature, and only routed views are
  inspected. Silence any with `SILENCED_SYSTEM_CHECKS`.
- **`dj_fixi.apps.DjFixiConfig`**, auto-discovered by `INSTALLED_APPS = ["dj_fixi"]`.
  Nothing about how you list the app changes.
- **`dj_fixi.urlconf`** — a defensive URLconf walk (`iter_routed_views`,
  `routed_view_classes`, `RoutedView`), public API. It never raises: a broken
  URLconf yields fewer results, leaving Django's own `urls.E00x` to report it.
- **`dj_fixi.request`** — `is_fx()`, `vary_on_fx()`, `FX_REQUEST_HEADER`.
- **`assert_no_fixi_check_issues()` / `fixi_check_messages()`** in
  `dj_fixi.testing`. Django runs system checks on `runserver`, `migrate`, and in
  its own test runner, but **not** under pytest — so for most Django projects the
  checks were invisible in the workflow where a wrong answer is cheapest to
  catch. One line in your suite closes that gap. Both honor
  `SILENCED_SYSTEM_CHECKS`.
- **`llms.txt`** — the complete API in one file, written for coding agents:
  the base-ordering rule, what Fixi deliberately does not do, every check ID, and
  how to verify. Pinned against drift by `tests/test_llms_txt.py`, because stale
  docs are a silent failure aimed at exactly the reader this project cares about.
- **`FxTemplateView` is now exported** from `dj_fixi` directly.

### Behavior changes to be aware of

- `{% fx_attrs %}` raises on a swap value fixi does not recognize, where it
  previously emitted it and let the swap silently fail in the browser.
- `FxView.render_to_response` now respects `content_type`/`response_class`, so a
  view that set them and relied on them being ignored will change behavior.
- `{% fx_csrf_token %}` raises outside a request context instead of returning "".

Tests: 45 → 173. Verified on Python 3.10–3.13 and Django 4.2–6.0.

## 0.2.0 — protocol correctness

This release realigns dj-fixi with what **Fixi.js actually does on the wire** (verified
against the upstream 90-line `fixi.js`). Several previously-shipped features assumed
HTMX's protocol, which Fixi does not implement, and were inert or incorrect.

### Breaking changes

- **Removed `request.fx_target` / `request.fx_swap` / `request.fx_trigger`** (and the
  matching `fx_target`/`fx_swap` template-context variables). Fixi never sends these
  request headers — target and swap are client-side concerns — so they were always
  empty. `request.is_fx` remains the one real signal `FxMiddleware` sets.
- **`{% fx_attrs %}` swap default is now `outerHTML`** (Fixi's real default; was
  `innerHTML`). Consequence: `{% fx_attrs swap="innerHTML" %}` now correctly *emits*
  `fx-swap="innerHTML"` — previously it was silently dropped, leaving Fixi to use
  `outerHTML`.
- **`FxForm` default `swap` is now `outerHTML`.**
- **`FxTestClient` now sends form-encoded bodies by default** (matching Fixi's
  `FormData`), instead of JSON-encoding. Pass `json=...` to send a JSON body; `fx_get`
  no longer forces an `Accept: application/json` header.
- **`{% fixi_cdn %}` is deprecated.** The old `unpkg.com/fixi@1.0.0/fixi.js` URL was
  wrong (that npm name is an unrelated, abandoned package). It now points at the real
  `the-fixi-project` bundle, but prefer `{% fixi_js %}`.

### Added

- **Vendored `fixi.js`** shipped as a static asset, served by the new `{% fixi_js %}`
  tag (offline, version-pinned — matches Fixi's "copy the file in" model).
- **`{% fixi_events %}` + `fixi-events.js`** — an optional, ~tiny `fx:after` listener that
  turns the `FX-Trigger` response header into client-side `CustomEvent`s (Fixi core does
  not read response headers). Or use a moxi.js `on-fx:after` handler instead.

### Fixed

- The example project now actually runs end-to-end: added the 3 missing templates
  (`confirm_delete.html`, `list_simple*.html`), a missing `wsgi.py`, a `get_absolute_url`
  on the model, CSRF-via-`fx:config`, and a working `formSuccess`/`formError` toast.

## 0.1.0

Initial release.
