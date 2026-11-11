# Changelog

## 0.6.1 — 2026-11-11

### Fixed

- **A Fixi request could answer 500 under `runserver`, depending on which
  template loaded first.** Under `DEBUG`, `FxMiddleware` and `render_fx` put the
  template's name in an `X-FX-Template` header. When an `{% include %}` had
  loaded that template first, the cached loader's copy carried the name as a
  `SafeString`, and wsgiref refuses any header value that is not exactly `str`.
  Production servers and the test client were unaffected, which is why no test
  saw it. The header value is a plain string now.

### Demo

- The "form that redirects" pitfall shows a list of recent notes under each
  form, so adding a note visibly does something: with `FxResponseMixin` the
  form clears and the note appears (`fx_collection` supplies the list); without
  it, the page the redirect leads to lands where the form was.

## 0.6.0 — extension attributes

The demo's delete confirmation, active search and CSRF header each took a
hand-written `fx:config` listener, and each was a place to get it wrong: an
inline `confirm()` that fixi ignores, a debounce that dropped the last
keystroke, a POST that came back 403. This release ships those three as
declarative attributes, in fixi's own `ext-fx-` convention, and stops there.

### Added

- **`{% fixi_scripts %}`**: fixi.js, the events shim and the extensions, in
  order, in one tag. Use it in place of `{% fixi_js %}`.
- **`ext-fx-confirm="..."`** (`confirm=` on `{% fx_attrs %}` and `FxForm`):
  ask first; Cancel sends nothing.
- **`ext-fx-debounce="250"`** (`debounce=` on `{% fx_attrs %}`): wait for a
  pause in the triggering event. Unlike the sketch in fixi's README, the newest
  request also aborts an unanswered older one. Without that, fixi drops a
  request made while another is in flight, and a search box shows results for
  what was typed a moment ago with no error anywhere.
- **Automatic CSRF.** With `{% fixi_scripts %}` (or `{% fixi_ext %}`) on the
  page, every unsafe, same-origin Fixi request carries Django's token in the
  `CSRF_HEADER_NAME` header. The token is written onto the script element, so
  `CSRF_COOKIE_HTTPONLY` and `CSRF_USE_SESSIONS` work. It is never sent to
  another origin.
- **Lint `L113`–`L115`**: a typo of one of the two names; a value the script
  cannot use (no message, not whole milliseconds, or a debounced click or
  submit); and a page that uses an attribute without loading the script, which
  for a confirmation means the request goes out unasked.
- **Check `dj_fixi.W303`**: templates use an extension attribute and no
  template loads `ext-fixi.js`.
- `L112`, `L105` and the `hx-confirm` / `hx-trigger` translations now name the
  attribute to write.

### Fixed

- `manage.py fixi_lint` reported an id written once in each branch of an
  `{% if %}` as a duplicate (`L109`). Template source cannot know which branch
  renders; the rule stays on for rendered pages.

### Not added, on purpose

Disable-during-request, indicators, polling, history, boosting, out-of-band
swaps and inheritance. dj-fixi is not becoming htmx: the admission rule is in
CLAUDE.md, and `tests/test_ext_fixi_js.py` caps the vocabulary at two names and
the script at 40 lines of code.

### Demo

- The product list's delete, active search and CSRF use the new attributes and
  tag; about thirty lines of script are gone from `base.html`.
- The pitfalls page has an eighth row, "Trigger modifiers, written from habit",
  and the two rows that one script tag fixes (FX-Trigger, CSRF) show it as a
  pair of frames that differ only in that tag.

## 0.5.3 — 2026-11-11

### Fixed

- **`fixi-events.js` reported a deliberate abort as a failed request.** Calling
  `cfg.abort()` on an in-flight request (the way to let the newest keystroke win
  in an active search) rejects its fetch with `AbortError`, which the `fx:error`
  guard logged as "request failed". Aborts are no longer reported.

### Demo

- **Active search on the product list.** The list filters as you type: the
  demo debounces keystrokes and dispatches the event the input's `fx-trigger`
  names (fixi has no `delay` modifier), and aborts the older request so a slow
  answer cannot overwrite a newer one. Enter and no-JavaScript still work
  through the form. Five browser tests cover it.

- **The demo starts.** It had no migrations, so following its README ended in
  `no such table: products_product`. Migrations are committed, and
  `manage.py seed` creates 25 products.
- **A pitfalls page** (`/pitfalls/`): seven mistakes that are easy to make with
  Fixi and Django, each live next to what dj-fixi has you write instead. Every
  claim on it is a test: `examples/demo_project/tests/` checks what the lint and
  `FxTestClient` say about each pair, and drives each pair in a browser.
- **Two template comments were showing on the page.** Django's `{# #}` is
  single-line; the two that spanned lines rendered as text in the product list
  and above the product form. They are `{% comment %}` blocks now, and a demo
  test fails on any `{# #}` that crosses a line.
- CI runs the demo's tests on every Django version, and a browser job runs the
  shim's tests and the pitfalls in Chromium. Before this the browser tests only
  ran when someone ran them by hand.

## 0.5.2 — 2026-11-11

### Fixed

- **`fixi-events.js` reported a correct `fx-target` as matching nothing** when
  an element named itself (`<td id="c" fx-target="#c">`). The guard compared
  the resolved target with the element, which is also what a selector that
  matches nothing resolves to. It now checks whether the element matches its
  own selector. Found by driving dj-fixi-tables in Chrome.

## 0.5.1 — 2026-11-11

### Fixed

- **The demo's Delete button deleted when the user clicked Cancel.** It used
  `onclick="return confirm(...)"`. Returning false from an inline handler only
  calls `preventDefault()`, and fixi never reads `defaultPrevented`, so its own
  listener sent the DELETE anyway (confirmed in Chrome). The same attribute put
  the product name inside a JavaScript string, where HTML escaping does not
  protect it. The button now carries `data-confirm`, and the demo's `fx:config`
  listener turns that into `cfg.confirm`, which fixi awaits.

### Added

- **`dj_fixi.L112`** (error): an inline `confirm()` in the handler for the event
  fixi listens for on that element (`onclick` by default, `onsubmit` on a form,
  `onchange` on an input, or `on<fx-trigger>`). `FxTestClient` raises on it and
  `manage.py fixi_lint` reports it.
- CI runs `manage.py fixi_lint` on the demo.

## 0.5.0 — 2026-11-11

### Removed

- **`ContextPersistenceMixin`.** Filtering, sorting and query-string
  bookkeeping are not Fixi concerns, and its versions of them were wrong in
  ways that did not show: `query_string` included the current `page`, so a
  `?page=3&{{ query_string }}` link from page 2 led back to page 2; repeated
  parameters (`?tag=a&tag=b`) kept only the last value; and `?sort=` accepted
  any field path on the model, relations included, with no allow-list. Use
  django-filter for filtering, `{% querystring %}` (Django 5.1+) or three
  lines in `get_context_data` for links (see the demo's `ProductListView`),
  and an explicit allow-list for sorting. With it gone, `get_queryset` is no
  longer a hook E101/W102 watch.
- **`OptimizedQueryMixin`.** It wrapped `select_related`/`prefetch_related`
  and had nothing to do with Fixi. Call them in `get_queryset`.
- **`{% fixi_cdn %}`**, deprecated since 0.2.0. Use `{% fixi_js %}`, which
  serves the vendored, version-pinned `fixi.js`.
- **`X-Execution-Time` and `X-FX-Response` response headers** from
  `FxMiddleware`. Neither was read by anything; `X-FX-Template` (DEBUG) stays.
- **Derived partial names.** `template_name` no longer implies
  `<name>_partial.<ext>` or `<dir>/fragments/<leaf>`, and `fx_template_suffix`
  is gone. A view has a fragment when it names one in `partial_template`
  (`"products/list_partial.html"`, or `"products/list.html#rows"` on Django 6);
  otherwise Fixi requests get `template_name`, and W202 says so. W204, which
  existed to announce this removal, is gone with it. Announced in 0.4.0 as a
  0.5 change; nothing outside this repository depended on the derivation.

### Fixed

- The demo's pagination links carried no page number in `fx-action`, so under
  Fixi "Next" always fetched page one.

### Added

- **`manage.py fixi_lint [paths...] [--warnings-as-errors]`**: the lint over
  template source, without rendering; every project template directory by
  default, never site-packages. `dj_fixi.lint.lint_template_source` and
  `strip_template_syntax` are the functions behind it.

### Changed

- **W202 is exact now.** It fires when a routed dj-fixi view declares no
  `partial_template` and has a page to serve, whether or not a conventionally
  named file happens to exist, and its hint is the line to write. Delete views
  and views that override `get_template_names` stay exempt.


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
