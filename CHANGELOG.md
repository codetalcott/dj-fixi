# Changelog

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
