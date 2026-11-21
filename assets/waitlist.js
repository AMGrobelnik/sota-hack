// Shows the real waitlist count from the store set in waitlist-config.js.
// Elements marked data-waitlist-count get the wording; their wrapper marked
// data-waitlist-wrap (which starts hidden) is shown only once a real number arrives.
(function () {
  "use strict";

  function endpoint() {
    var cfg = window.WAITLIST || {};
    return typeof cfg.endpoint === "string" ? cfg.endpoint.trim() : "";
  }

  function wording(n) {
    return n === 1 ? "1 person on the waitlist" : n.toLocaleString("en-GB") + " people on the waitlist";
  }

  function validCount(n) {
    return typeof n === "number" && isFinite(n) && n >= 0 && Math.floor(n) === n;
  }

  function show(n) {
    if (!validCount(n)) return;
    var els = document.querySelectorAll("[data-waitlist-count]");
    for (var i = 0; i < els.length; i++) {
      var wrap = els[i].closest("[data-waitlist-wrap]");
      // Nobody yet: keep the count hidden until the first real sign-up.
      if (n === 0) {
        if (wrap) wrap.hidden = true;
        continue;
      }
      els[i].textContent = wording(n);
      if (wrap) wrap.hidden = false;
    }
  }

  function load() {
    var url = endpoint();
    if (!url || !window.fetch) return;
    fetch(url, { method: "GET", headers: { Accept: "application/json" }, cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { if (data) show(data.count); })
      .catch(function () { /* store unreachable: the count stays hidden */ });
  }

  window.Waitlist = { endpoint: endpoint, show: show, wording: wording, validCount: validCount };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load);
  else load();
})();
