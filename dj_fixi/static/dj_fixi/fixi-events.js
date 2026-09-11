/*
 * dj-fixi: the FX-Trigger event bridge, and the console guards for what fixi
 * swallows. Load it after fixi.js:
 *
 *     {% fixi_js %}
 *     {% fixi_events %}
 *
 * Events. Fixi core does not read response headers, so the `FX-Trigger` header
 * dj-fixi's FxResponseMixin (and dj-fixi-tables) set is inert on its own. This
 * file turns it into DOM events after the swap, so a handler can see the new
 * DOM. A header of `FX-Trigger: {"formSuccess": {"object_id": "7"}}` dispatches
 * a bubbling CustomEvent "formSuccess" with that detail; a bare
 * `FX-Trigger: someEvent` dispatches "someEvent" with a null detail. The event
 * is dispatched on the element that made the request when it is still in the
 * document, otherwise on <body> (a delete's outerHTML swap removes the element
 * that asked). A string `target` key in the detail names a CSS selector to
 * dispatch on instead; it is reserved for that. Listen on document or body:
 *
 *     document.addEventListener("formSuccess", (e) => ...)
 *
 * Already using moxi.js? Write the equivalent on-fx:swapped handler instead.
 *
 * Guards. fixi.js is silent about three mistakes: an fx-target selector that
 * matches nothing (fixi swaps into the element itself, fixi.js:21), a swap
 * spelling it cannot perform (it throws after the request, fixi.js:61-65), and
 * a request that failed (fixi.js:51-53 swallows the error). Each is reported
 * with console.error, using fixi's own predicates on the real DOM.
 */
(() => {
  const fired = new WeakSet();

  const parseHeader = (header) => {
    try {
      return JSON.parse(header);
    } catch {
      return header; // bare event name, not JSON
    }
  };

  document.addEventListener("fx:swapped", (evt) => {
    const cfg = evt.detail?.cfg;
    const header = cfg?.response?.headers?.get("FX-Trigger");
    if (!cfg || !header || fired.has(cfg)) return; // fixi re-sends on document when the element is gone
    fired.add(cfg);

    const requester = evt.target;
    const fallback = requester instanceof Element && document.contains(requester) ? requester : document.body;
    const fire = (name, detail) => {
      let node = fallback;
      if (detail && typeof detail === "object" && typeof detail.target === "string") {
        const chosen = document.querySelector(detail.target);
        if (chosen) node = chosen;
        else console.error(`dj-fixi: FX-Trigger "${name}" names target "${detail.target}", which matches nothing; dispatching on <body>.`);
      }
      node.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
    };

    const triggers = parseHeader(header);
    if (typeof triggers === "string") {
      fire(triggers, null);
    } else if (triggers && typeof triggers === "object") {
      for (const [name, detail] of Object.entries(triggers)) fire(name, detail);
    }
  });

  document.addEventListener("fx:config", (evt) => {
    const elt = evt.target;
    const cfg = evt.detail?.cfg;
    if (!cfg || !(elt instanceof Element)) return;
    if (elt.hasAttribute("fx-target") && cfg.target === elt) {
      console.error(`dj-fixi: fx-target="${elt.getAttribute("fx-target")}" matches nothing on this page; fixi will swap the response into the element itself.`, elt);
    }
    const swap = cfg.swap;
    const canSwap =
      swap instanceof Function ||
      swap === "none" ||
      swap === "morph" || // paxi.js installs its own swap later
      /(before|after)(begin|end)/.test(swap) ||
      (cfg.target != null && swap in cfg.target);
    if (!canSwap) {
      console.error(`dj-fixi: fx-swap="${swap}" is nothing fixi can do (case matters: innerHTML, outerHTML, textContent, beforebegin, ...); fixi will throw after the request and nothing will swap.`, elt);
    }
  });

  document.addEventListener("fx:error", (evt) => {
    const { cfg, error } = evt.detail ?? {};
    console.error(`dj-fixi: request ${cfg?.method ?? ""} ${cfg?.action ?? ""} failed; fixi swallows this and swaps nothing.`, error, evt.target);
  });
})();
