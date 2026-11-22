/* ChipIn i1 connect link: lets the public page use a backend on the reader's own computer.
 *
 * Classic script, no dependencies. Load it after ../live.js and BEFORE ../i1-live.js.
 * A link of the form  i1.html#backend=http://127.0.0.1:8805&token=...  stores the address and
 * token in this browser (the same localStorage entry Configure writes, "chipin-i1-backend"),
 * takes both out of the address bar at once, and lets i1-live.js connect from storage, now and on
 * later visits. Only loopback (127.0.0.1, localhost) and https addresses are accepted; anything
 * else is dropped from the address and ignored. This file makes no request: a visitor who never
 * opened such a link has nothing stored, so the page never contacts a local address. */
(function () {
  "use strict";
  var h = location.hash.replace(/^#/, "");
  if (!/(^|&)backend=/.test(h)) return;
  var p = new URLSearchParams(h), raw = p.get("backend") || "", tok = p.get("token") || "";
  p.delete("backend"); p.delete("token");
  var rest = p.toString();
  try { history.replaceState(history.state, "", location.pathname + location.search + (rest ? "#" + rest : "")); } catch (e) { /* file:// */ }
  var u;
  try { u = new URL(raw); } catch (e) { return; }
  var ok = u.protocol === "https:" || (u.protocol === "http:" && /^(127\.0\.0\.1|localhost)$/.test(u.hostname));
  if (!ok || !tok || u.username || u.password || (u.pathname !== "/" && u.pathname !== "")) return;
  try { localStorage.setItem("chipin-i1-backend", JSON.stringify({ base: u.origin, token: tok })); } catch (e) { /* storage off: nothing is kept */ }
})();
