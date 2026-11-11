/*
 * dj-fixi: the extension attributes. Load it after fixi.js, most simply with
 *
 *     {% fixi_scripts %}
 *
 * which also hands this file Django's CSRF token. The names follow fixi's own
 * convention for extensions (an ext-fx- prefix, in a file called ext-fixi.js),
 * and there are deliberately only two:
 *
 *   ext-fx-confirm="Delete this?"   ask first; Cancel sends nothing
 *   ext-fx-debounce="250"           wait for a pause in the triggering event,
 *                                   and let the newest request replace an
 *                                   unanswered older one
 *
 * and one behaviour with no attribute: every unsafe, same-origin request
 * carries Django's CSRF token in a header.
 *
 * This is not the start of an htmx. See "Extension attributes" in CLAUDE.md
 * for what may be added here and what may not; tests/test_ext_fixi_js.py caps
 * the vocabulary and the size of this file.
 */
(() => {
  const { csrfToken, csrfHeader = "X-CSRFToken" } = document.currentScript?.dataset ?? {};
  const SAFE = /^(GET|HEAD|OPTIONS|TRACE)$/;
  const sameOrigin = (action) => {
    try { return new URL(action, document.baseURI).origin === location.origin; } catch { return false; }
  };

  document.addEventListener("fx:config", (evt) => {
    const elt = evt.target;
    const cfg = evt.detail?.cfg;
    if (!cfg || !(elt instanceof Element)) return;

    if (csrfToken && !SAFE.test(cfg.method) && sameOrigin(cfg.action)) cfg.headers[csrfHeader] = csrfToken;

    const question = elt.getAttribute("ext-fx-confirm");
    if (question) cfg.confirm = () => confirm(question); // fixi awaits this (fixi.js:43-45)

    if (elt.hasAttribute("ext-fx-debounce")) {
      // fixi drops a request made while another from this element is in flight
      // (fixi.js:24, :35). For a debounced control the newest one is the one wanted.
      evt.detail.requests.forEach((request) => request.abort());
      cfg.drop = false;
    }
  });

  // fx:inited does not bubble, hence capture. By now elt.__fixi is fixi's
  // listener; swap it for one that waits for a pause before calling it.
  document.addEventListener("fx:inited", (evt) => {
    const elt = evt.target;
    const wait = elt instanceof Element ? parseInt(elt.getAttribute("ext-fx-debounce")) : NaN;
    if (!(wait > 0)) return;
    const send = elt.__fixi;
    let timer;
    elt.removeEventListener(send.evt, send);
    elt.addEventListener(send.evt, (trigger) => {
      clearTimeout(timer);
      timer = setTimeout(() => send(trigger), wait);
    });
  }, true);
})();
