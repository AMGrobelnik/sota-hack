/* ChipIn i1 connect link: lets the public page use a backend on the reader's own computer.
 *
 * Classic script, no dependencies. Load it after ../live.js and BEFORE ../i1-live.js.
 * A link of the form  i1.html#backend=http://127.0.0.1:8805&token=...  stores the address and
 * token in this browser (the same localStorage entry Configure writes, "chipin-i1-backend"),
 * takes both out of the address bar at once, and lets i1-live.js connect from storage, now and on
 * later visits. Only loopback (127.0.0.1, localhost) and https addresses are accepted; anything
 * else is dropped from the address and ignored. This file makes no request: a visitor who never
 * opened such a link has nothing stored, so the page never contacts a local address.
 *
 * It also draws the one slim banner for a stored backend that cannot be used: window.ChipInConn
 * .set("expired" | "unreachable" | "") is called by i1-live.js; the banner never shows the token
 * or the address, and stays dismissible for the rest of the browser session. */
(function () {
  "use strict";
  var h = location.hash.replace(/^#/, "");
  if (/(^|&)backend=/.test(h)) takeLink(h);

  function takeLink(h) {
    var p = new URLSearchParams(h), raw = p.get("backend") || "", tok = p.get("token") || "";
    p.delete("backend"); p.delete("token");
    var rest = p.toString();
    try { history.replaceState(history.state, "", location.pathname + location.search + (rest ? "#" + rest : "")); } catch (e) { /* file:// */ }
    var u;
    try { u = new URL(raw); } catch (e) { return; }
    var ok = u.protocol === "https:" || (u.protocol === "http:" && /^(127\.0\.0\.1|localhost)$/.test(u.hostname));
    if (!ok || !tok || u.username || u.password || (u.pathname !== "/" && u.pathname !== "")) return;
    try { localStorage.setItem("chipin-i1-backend", JSON.stringify({ base: u.origin, token: tok })); } catch (e) { /* storage off: nothing is kept */ }
  }

  var TEXT = {
    expired: "This browser's backend link has expired. Open a fresh link to run for real; until then the page shows examples only.",
    unreachable: "The backend is not answering. Check it is running, then reload; until then the page shows examples only."
  };
  var kind = "", bar = null, ob = null;
  function dismissed(k) { try { return sessionStorage.getItem("chipin-i1-conn-dismissed") === k; } catch (e) { return false; } }
  function build() {
    var d = document.createElement("div");
    d.id = "lvConnBanner"; d.setAttribute("role", "status");
    d.innerHTML = '<span></span><button type="button" aria-label="Dismiss">&times;</button>';
    d.lastChild.onclick = function () { try { sessionStorage.setItem("chipin-i1-conn-dismissed", kind); } catch (e) { /* kept for this view only */ } d.hidden = true; };
    return d;
  }
  function paint() {
    var main = document.getElementById("main");
    if (!main) return;
    if (!kind || dismissed(kind)) { if (bar && bar.parentNode) bar.parentNode.removeChild(bar); return; }
    if (!bar) bar = build();
    var t = TEXT[kind];
    if (bar.firstChild.textContent !== t) bar.firstChild.textContent = t;
    bar.hidden = false;
    if (bar.parentNode !== main || main.firstChild !== bar) main.insertBefore(bar, main.firstChild);
  }
  var css = document.createElement("style");
  css.textContent = "#lvConnBanner{flex:none;display:flex;align-items:center;gap:10px;padding:6px 14px;background:#fdf3e3;color:#7a4208;border-bottom:1px solid #f0d9b3;font-size:12.5px;line-height:1.4}#lvConnBanner[hidden]{display:none}#lvConnBanner span{flex:1;min-width:0}#lvConnBanner button{flex:none;border:0;background:none;color:inherit;font-size:18px;line-height:1;padding:0 4px;cursor:pointer;opacity:.7}#lvConnBanner button:hover{opacity:1}";
  document.head.appendChild(css);
  window.ChipInConn = {
    set: function (k) {
      k = k === "expired" || k === "unreachable" ? k : "";
      if (k !== kind) { kind = k; }
      paint();
      if (!ob && document.getElementById("main")) { ob = new MutationObserver(function () { if (kind && !dismissed(kind) && (!bar || document.getElementById("main").firstChild !== bar)) paint(); }); ob.observe(document.getElementById("main"), { childList: true }); }
    }
  };
})();
