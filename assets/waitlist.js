// Shows the waitlist count (and hands the per-country numbers to waitlist-map.js).
// Elements marked data-waitlist-count get the wording; their wrapper marked
// data-waitlist-wrap (which starts hidden) is shown only once a number is known.
// Numbers come from window.WAITLIST.mock when that block exists (preview), else from the store.
(function () {
  "use strict";

  function cfg() { return window.WAITLIST || {}; }

  function endpoint() {
    return typeof cfg().endpoint === "string" ? cfg().endpoint.trim() : "";
  }

  function wording(n) {
    return n === 1 ? "1 person on the waitlist" : n.toLocaleString("en-GB") + " people on the waitlist";
  }

  function validCount(n) {
    return typeof n === "number" && isFinite(n) && n >= 0 && Math.floor(n) === n;
  }

  function cleanCountries(list) {
    var out = [];
    if (!Array.isArray(list)) return out;
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      if (c && typeof c.code === "string" && validCount(c.count) && c.count > 0) {
        out.push({ code: c.code.trim().toUpperCase(), count: c.count });
      }
    }
    return out;
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

  // Publish {count, countries}; waitlist-map.js reads Waitlist.data and listens for "waitlist:data".
  function publish(count, countries) {
    if (!validCount(count)) return;
    api.data = { count: count, countries: cleanCountries(countries) };
    show(count);
    document.dispatchEvent(new CustomEvent("waitlist:data", { detail: api.data }));
  }

  function load() {
    var m = cfg().mock;
    if (m && validCount(m.count)) { publish(m.count, m.countries); return; }
    var url = endpoint();
    if (!url || !window.fetch) return;
    fetch(url, { method: "GET", headers: { Accept: "application/json" }, cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { if (data) publish(data.count, data.countries); })
      .catch(function () { /* store unreachable: the count stays hidden */ });
  }

  var api = { endpoint: endpoint, show: show, wording: wording, validCount: validCount, data: null };
  window.Waitlist = api;

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load);
  else load();
})();
