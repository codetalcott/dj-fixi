/*
 * dj-fixi: optional FX-Trigger event bridge.
 *
 * Fixi.js core does NOT read response headers, so the `FX-Trigger` header that
 * dj-fixi's FxResponseMixin (and dj-fixi-tables) set is inert on its own. Include
 * this ~tiny script *after* fixi.js to turn that header into client-side events:
 *
 *     <script src="{% static 'dj_fixi/fixi.js' %}"></script>
 *     <script src="{% static 'dj_fixi/fixi-events.js' %}"></script>
 *
 * A response header of `FX-Trigger: {"formSuccess": {"object_id": "7"}}` dispatches
 * a bubbling CustomEvent named "formSuccess" (detail = {"object_id": "7"}) on the
 * element that made the request. A bare `FX-Trigger: someEvent` dispatches
 * "someEvent" with no detail. Listen with addEventListener("formSuccess", ...).
 *
 * Already using moxi.js? You don't need this file — use an on-fx:after handler
 * instead (see the dj-fixi README).
 */
(() => {
  document.addEventListener("fx:after", (evt) => {
    const header = evt.detail?.cfg?.response?.headers?.get("FX-Trigger");
    if (!header) return;

    let triggers;
    try {
      triggers = JSON.parse(header);
    } catch {
      triggers = header; // bare event name, not JSON
    }

    const elt = evt.target;
    const dispatchOn = document.contains(elt) ? elt : document;
    const fire = (name, detail) =>
      dispatchOn.dispatchEvent(
        new CustomEvent(name, { detail, bubbles: true, composed: true })
      );

    if (typeof triggers === "string") {
      fire(triggers, null);
    } else if (triggers && typeof triggers === "object") {
      for (const [name, detail] of Object.entries(triggers)) fire(name, detail);
    }
  });
})();
