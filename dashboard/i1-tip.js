/* i1-tip.js: detail on demand for the dashboard's short notes (window.ChipInTip).
 *
 * Any element with data-tip="<the full sentence>" (and the older estimate marks, .est[title]) shows that
 * sentence in one small popover: on hover with a mouse, on keyboard focus, and on tap on a touch screen
 * (a tap elsewhere, Escape or a scroll closes it). A dotted underline marks text that has detail.
 *
 *   ChipInTip.attr(detail)          ' data-tip="…"' for a tag the caller writes ("" when detail is empty)
 *   ChipInTip.wrap(shortHTML, detail[, tag])   shortHTML in a <span> (or tag) carrying the detail
 *
 * The popover is plain text, sits below the anchor (above it when there is no room), stays 8 px inside
 * the viewport at any width, and never takes pointer events, so it cannot hide what it explains.
 */
(function () {
  "use strict";
  var SEL = "[data-tip], .est[title]";
  var FOCUSABLE = "a[href], button, input, select, textarea, summary, [tabindex]";
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function attr(detail) {
    return detail ? ' data-tip="' + esc(detail) + '"' : "";
  }
  function wrap(shortHTML, detail, tag) {
    tag = tag || "span";
    return detail ? "<" + tag + attr(detail) + ">" + shortHTML + "</" + tag + ">" : shortHTML;
  }

  var css =
    "[data-tip]{text-decoration:underline dotted;text-decoration-color:color-mix(in srgb,currentColor 45%,transparent);text-decoration-thickness:1px;text-underline-offset:3px;cursor:help}" +
    "[data-tip]:focus-visible{outline:2px solid #2b55d0;outline-offset:2px;border-radius:3px}" +
    "button[data-tip],a[data-tip],.tip-nu[data-tip]{text-decoration:none}" +
    ".i1tip{position:fixed;z-index:2147483000;left:0;top:0;max-width:min(340px,calc(100vw - 16px));box-sizing:border-box;padding:8px 11px;border-radius:8px;" +
    "background:#141a2e;color:#f4f5f8;font:400 12.5px/1.5 Inter,system-ui,-apple-system,sans-serif;letter-spacing:0;text-align:left;white-space:normal;" +
    "box-shadow:0 6px 24px rgb(20 26 46/.22);pointer-events:none;opacity:0;transform:translateY(2px);transition:opacity .12s,transform .12s}" +
    ".i1tip.on{opacity:1;transform:none}" +
    "@media (prefers-reduced-motion:reduce){.i1tip{transition:none}}";

  var pop = null, cur = null, showT = 0, hideT = 0, touchAt = 0;
  function ensure() {
    if (pop) return pop;
    var st = document.createElement("style");
    st.textContent = css;
    document.head.appendChild(st);
    pop = document.createElement("div");
    pop.className = "i1tip";
    pop.id = "i1tip";
    pop.setAttribute("role", "tooltip");
    pop.hidden = true;
    document.body.appendChild(pop);
    return pop;
  }
  // the estimate marks carry their assumption in title; moved to data-tip so the browser's own tooltip does not double it
  function detailOf(a) {
    if (!a.hasAttribute("data-tip") && a.hasAttribute("title")) {
      a.setAttribute("data-tip", a.getAttribute("title"));
      a.removeAttribute("title");
    }
    return a.getAttribute("data-tip") || "";
  }
  function place(a) {
    var r = a.getBoundingClientRect(), W = document.documentElement.clientWidth, H = window.innerHeight, m = 8, gap = 6;
    // a short line in a wide block: centred on the text itself, not the empty end of its box; above or below the whole box
    var rg = document.createRange();
    rg.selectNodeContents(a);
    var rt = rg.getBoundingClientRect();
    if (rt.width > 0 && rt.height > 0) r = { left: rt.left, right: rt.right, width: rt.width, top: r.top, bottom: r.bottom };
    pop.style.left = "0px"; pop.style.top = "0px";
    var w = pop.offsetWidth, h = pop.offsetHeight;
    // a wide block (a whole line of text) anchors at the pointer's side of it, not its middle
    var cx = r.width > 360 && place.x != null && place.x >= r.left && place.x <= r.right ? place.x : r.left + r.width / 2;
    var left = Math.max(m, Math.min(W - w - m, cx - w / 2));
    var below = r.bottom + gap, above = r.top - gap - h;
    var top = below + h <= H - m || above < m ? below : above;
    top = Math.max(m, Math.min(H - h - m, top));
    pop.style.left = Math.round(left) + "px";
    pop.style.top = Math.round(top) + "px";
  }
  function show(a) {
    var t = detailOf(a);
    if (!t) return;
    ensure();
    clearTimeout(hideT);
    if (cur && cur !== a) cur.removeAttribute("aria-describedby");
    cur = a;
    pop.textContent = t;
    pop.hidden = false;
    a.setAttribute("aria-describedby", "i1tip");
    place(a);
    requestAnimationFrame(function () { if (cur === a) pop.classList.add("on"); });
  }
  function hide() {
    clearTimeout(showT);
    if (!pop || pop.hidden) { cur = null; return; }
    pop.classList.remove("on");
    pop.hidden = true;
    if (cur) cur.removeAttribute("aria-describedby");
    cur = null;
  }
  // a short note with detail that is not already a control takes keyboard focus, unless it sits inside one;
  // the many inline estimate marks (.est) stay hover and tap only, so they do not flood the tab order
  var pending = false;
  function makeFocusable() {
    pending = false;
    var list = document.querySelectorAll("[data-tip]:not([tabindex]):not(.est)");
    for (var i = 0; i < list.length; i++) {
      var a = list[i];
      if (a.matches(FOCUSABLE) || (a.parentElement && a.parentElement.closest("a[href], button, summary, label"))) continue;
      a.setAttribute("tabindex", "0");
    }
  }
  function schedule() {
    if (cur && !cur.isConnected) hide(); // a redraw replaced the text it explained
    if (pending) return;
    pending = true;
    requestAnimationFrame(makeFocusable);
  }

  function anchorOf(t) {
    return t && t.closest ? t.closest(SEL) : null;
  }
  document.addEventListener("pointerover", function (e) {
    if (e.pointerType === "touch" || Date.now() - touchAt < 600) return;
    var a = anchorOf(e.target);
    if (!a) return;
    place.x = e.clientX;
    clearTimeout(hideT); clearTimeout(showT);
    if (a === cur) return;
    showT = setTimeout(function () { show(a); }, cur ? 0 : 140);
  });
  document.addEventListener("pointerout", function (e) {
    if (e.pointerType === "touch") return;
    var a = anchorOf(e.target);
    if (!a || (e.relatedTarget && a.contains(e.relatedTarget))) return;
    clearTimeout(showT);
    hideT = setTimeout(hide, 90);
  });
  document.addEventListener("pointerdown", function (e) {
    if (e.pointerType !== "mouse") touchAt = Date.now();
    var a = anchorOf(e.target);
    if (e.pointerType === "mouse") { if (!a) hide(); return; }
    // a tap: toggles the tapped detail; a tap anywhere else closes it
    if (!a) { hide(); return; }
    place.x = e.clientX;
    if (a === cur) hide(); else show(a);
  }, true);
  document.addEventListener("focusin", function (e) {
    var a = anchorOf(e.target);
    if (a && a === e.target) { place.x = null; show(a); }
  });
  document.addEventListener("focusout", function (e) {
    if (cur && e.target === cur && Date.now() - touchAt > 600) hide();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && cur) hide();
  });
  window.addEventListener("scroll", function () { if (cur) hide(); }, true);
  window.addEventListener("resize", function () { if (cur) hide(); });
  window.addEventListener("hashchange", hide);

  function start() {
    ensure();
    makeFocusable();
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
  }
  if (document.body) start();
  else document.addEventListener("DOMContentLoaded", start);

  window.ChipInTip = { version: 1, attr: attr, wrap: wrap, show: show, hide: hide };
})();
