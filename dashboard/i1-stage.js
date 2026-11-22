/* ChipIn i1 loading stage: the one screen every step of a new design passes through (window.ChipInStage).
 *
 * A staged list of what the system is doing right now. Each line shows what it is working on, then
 * ticks off with what it found, and the next line starts. On the public site (no backend) the lines
 * are a replay, paced so they can be followed, and the caller marks them so; with a connected
 * backend the caller drives the ticks from real events (ctl.tick, ctl.finish) and no timer runs.
 *
 *   ChipInStage.play(o) -> ctl
 *     o.title, o.kicker      heading and the small line above it
 *     o.mark                 "sim" | "mea" | "" : the page's simulated or measured marking
 *     o.lines                [{ p: working title, w: working line, t: done title, tHTML, d: done detail (HTML), warn }]
 *     o.stepMs               ms per line (number, or function of the line index); replay only
 *     o.live                 true: no timers, the caller ticks
 *     o.skip                 the skip button's text
 *     o.onEnd(open)          called once: true when the stage ends or is skipped, false when the user left
 *   ctl.tick(k, patch)       live: lines before k are done, line k is running; patch { d, warn, t } for line k-1
 *   ctl.finish()             live: every line done, then onEnd(true)
 *   ctl.close()              remove the stage without calling onEnd (a failed start)
 *   ChipInStage.inline(lines, now)  the same list as static HTML, for a wait inside another screen
 */
(function () {
  "use strict";
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var LIVE_MIN = 380, END_MS = 650;

  var CSS = ".stg{position:absolute;inset:0;z-index:20;background:var(--page);overflow:auto;display:flex;justify-content:center;padding:44px 24px 80px}" +
    ".stg .sgc{width:100%;max-width:640px}" +
    ".stg .sgh{display:flex;align-items:center;gap:18px}" +
    ".stg .sgk{font-size:12.5px;color:var(--i600);margin:0 0 4px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}" +
    ".stg h1{font-family:var(--serif);font-weight:400;font-size:30px;line-height:1.15;letter-spacing:-.012em;margin:0;color:var(--i900)}.stg h1:focus{outline:0}" +
    ".sgchip{flex:none;width:64px;height:64px;border-radius:18px;background:linear-gradient(140deg,#eef2ff,#e6f6f1);display:grid;place-items:center;box-shadow:inset 0 0 0 1px rgb(43 85 208/.12)}" +
    ".sgchip svg{width:46px;height:46px;overflow:visible}.sgchip .pin{stroke:#c3cbe0;stroke-width:2.2;stroke-linecap:round;transition:stroke .5s}" +
    ".sgchip .pin.on{stroke:var(--blue7)}.sgchip .die{fill:#fff;stroke:var(--blue7);stroke-width:1.6}" +
    ".sgchip .scan{fill:url(#sgGrad);animation:sgscan 2.6s ease-in-out infinite}" +
    "@keyframes sgscan{0%{transform:translateY(-14px);opacity:0}25%{opacity:1}75%{opacity:1}100%{transform:translateY(14px);opacity:0}}" +
    ".sgchip .core{fill:var(--blue7);animation:sgbeat 2.6s ease-in-out infinite;transform-origin:23px 23px}" +
    "@keyframes sgbeat{0%,100%{opacity:.35;transform:scale(.85)}50%{opacity:1;transform:scale(1)}}" +
    ".sgbar{height:5px;border-radius:99px;background:var(--i150);margin:26px 0 8px;overflow:hidden}" +
    ".sgbar i{display:block;height:100%;width:0;border-radius:99px;background:linear-gradient(90deg,#2b55d0,#6b46c1 55%,#0f7a55);transition:width .9s cubic-bezier(.3,.7,.2,1)}" +
    ".stg ol,.sgin{list-style:none;margin:18px 0 0;padding:0;display:flex;flex-direction:column;gap:6px}" +
    ".stg li,.sgin li{display:grid;grid-template-columns:24px minmax(0,1fr);gap:12px;padding:12px 14px;border-radius:14px;border:1px solid transparent;transition:background .35s,border-color .35s}" +
    ".stg li.now,.sgin li.now{background:#fff;border-color:rgb(43 85 208/.18);box-shadow:0 6px 22px -14px rgb(43 85 208/.45)}" +
    ".stg li.done,.sgin li.done{background:rgb(15 122 85/.045)}.stg li.warn,.sgin li.warn{background:var(--amb-bg)}" +
    ".sgic{width:24px;height:24px;display:grid;place-items:center;border-radius:50%;margin-top:-1px}" +
    ".sgic i{width:9px;height:9px;border-radius:50%;border:1.6px solid var(--i200)}" +
    "li.done .sgic{background:#d9f2e6}li.warn .sgic{background:#fde9c8}li.now .sgic .spin{width:15px;height:15px}" +
    ".sgic svg{width:14px;height:14px;fill:none;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round}" +
    ".sgt{font-size:14.5px;font-weight:600;color:var(--i900);line-height:1.35;overflow-wrap:anywhere}.sgt a{color:inherit}" +
    "li.pend .sgt{color:var(--i300);font-weight:500}li.now .sgt{color:var(--blue7)}" +
    ".sgd{font-size:12.5px;color:var(--i600);margin-top:2px;line-height:1.5;overflow-wrap:anywhere}.sgd a{color:var(--blue7)}li.warn .sgd{color:var(--falsea-t)}" +
    "li.now .sgd::after{content:'';display:inline-block;width:1.2em;text-align:left;animation:sgdots 1.4s steps(4,end) infinite;vertical-align:bottom;overflow:hidden;white-space:nowrap}" +
    "@keyframes sgdots{0%{content:''}25%{content:'.'}50%{content:'..'}75%{content:'...'}}" +
    ".sgf{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:22px}.sgf .n{font-size:12px;color:var(--i550);font-variant-numeric:tabular-nums}" +
    "@media (max-width:767px){.stg{padding:28px 16px 70px}.stg h1{font-size:25px}.sgchip{width:52px;height:52px;border-radius:15px}.sgchip svg{width:38px;height:38px}.stg li{padding:11px 12px}}";

  var ICON = {
    ok: '<svg viewBox="0 0 24 24" stroke="var(--okt)"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    warn: '<svg viewBox="0 0 24 24" stroke="#b45309"><path d="M12 7v6M12 17h.01"/></svg>'
  };
  function css() { if (!document.getElementById("stg-css")) { var st = document.createElement("style"); st.id = "stg-css"; st.textContent = CSS; document.head.appendChild(st); } }

  // the chip mark: twelve pins light up as the lines tick off; a slow scan crosses the die
  function chipSVG() {
    var pins = "", k = 0;
    for (var side = 0; side < 4; side++) for (var j = 0; j < 3; j++) {
      var o = 15 + j * 8, a = side === 0 ? [o, 2, o, 8] : side === 1 ? [38, o, 44, o] : side === 2 ? [o, 38, o, 44] : [2, o, 8, o];
      pins += '<line class="pin" data-k="' + (k++) + '" x1="' + a[0] + '" y1="' + a[1] + '" x2="' + a[2] + '" y2="' + a[3] + '"/>';
    }
    return '<svg viewBox="0 0 46 46" aria-hidden="true"><defs><linearGradient id="sgGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2b55d0" stop-opacity="0"/><stop offset=".5" stop-color="#2b55d0" stop-opacity=".22"/><stop offset="1" stop-color="#2b55d0" stop-opacity="0"/></linearGradient>' +
      '<clipPath id="sgClip"><rect x="9" y="9" width="28" height="28" rx="5"/></clipPath></defs>' + pins +
      '<rect class="die" x="9" y="9" width="28" height="28" rx="5"/><g clip-path="url(#sgClip)"><rect class="scan" x="9" y="15" width="28" height="16"/></g><rect class="core" x="19" y="19" width="8" height="8" rx="2"/></svg>';
  }

  function itemHTML(s, state) {
    var ic = state === "done" ? ICON.ok : state === "warn" ? ICON.warn : state === "now" ? '<span class="spin"></span>' : "<i></i>";
    var title = state === "done" || state === "warn" ? (s.tHTML || esc(s.t || s.p)) : esc(s.p || s.t);
    var line = state === "done" || state === "warn" ? (s.d || "") : state === "now" ? esc(s.w || "") : "";
    return '<li class="' + state + '"><span class="sgic" aria-hidden="true">' + ic + '</span><div><div class="sgt">' + title + "</div>" + (line ? '<div class="sgd">' + line + "</div>" : "") + "</div></li>";
  }
  var stateOf = function (s, i, now) { return i < now ? (s.warn ? "warn" : "done") : i === now ? "now" : "pend"; };
  function inline(lines, now) { css(); return '<ul class="sgin" aria-live="polite">' + lines.map(function (s, i) { return itemHTML(s, stateOf(s, i, now)); }).join("") + "</ul>"; }

  function play(o) {
    var main = document.getElementById("main"), lines = (o.lines || []).slice(), ended = false, closed = false, timers = [], now = 0, hash = location.hash;
    // on the way forward the next screen replaces the stage; it is removed after a moment in case none does
    var end = function (open) {
      if (ended) return; ended = true; timers.forEach(clearTimeout); unhide();
      if (!open) root.remove(); else setTimeout(function () { if (root.isConnected) root.remove(); }, 600);
      if (typeof o.onEnd === "function") o.onEnd(open);
    };
    if (!main) { setTimeout(function () { if (typeof o.onEnd === "function") o.onEnd(true); }, 0); return { tick: function () {}, finish: function () {}, close: function () {} }; }
    css();
    var old = document.getElementById("stg"); if (old) old.remove();
    var root = document.createElement("section");
    root.className = "stg"; root.id = "stg"; root.setAttribute("aria-label", o.title || "Working");
    var mark = o.mark === "sim" ? '<span class="mk sim">simulated</span>' : o.mark === "mea" ? '<span class="mk mea">measured</span>' : "";
    root.innerHTML = '<div class="sgc"><header class="sgh"><span class="sgchip">' + chipSVG() + '</span><div><p class="sgk"><span>' + esc(o.kicker || "") + "</span>" + mark + '</p><h1 tabindex="-1">' + esc(o.title || "") + "</h1></div></header>" +
      '<div class="sgbar" aria-hidden="true"><i></i></div><ol aria-live="polite"></ol><div class="sgf"><span class="n" aria-hidden="true"></span><button type="button" class="btn s">' + esc(o.skip || "Skip") + "</button></div></div>";
    // the page under the stage stays put but out of reach while the stage is up
    var hidden = [].filter.call(main.children, function (n) { return n !== root && !n.inert; });
    hidden.forEach(function (n) { n.inert = true; });
    function unhide() { hidden.forEach(function (n) { n.inert = false; }); }
    main.appendChild(root);
    var list = root.querySelector("ol"), bar = root.querySelector(".sgbar i"), count = root.querySelector(".sgf .n"), pins = root.querySelectorAll(".pin");
    function draw() {
      list.innerHTML = lines.map(function (s, i) { return itemHTML(s, stateOf(s, i, now)); }).join("");
      var f = lines.length ? Math.min(now, lines.length) / lines.length : 1;
      bar.style.width = Math.max(4, f * 100) + "%";
      count.textContent = Math.min(now, lines.length) + " of " + lines.length;
      var lit = Math.round(f * pins.length);
      [].forEach.call(pins, function (p, k) { p.classList.toggle("on", k < lit); });
    }
    // the user went elsewhere (a link, Back): stop, and do not open the next screen
    var alive = function () { if (ended) return false; if (!root.isConnected || location.hash !== hash) { end(false); return false; } return true; };
    root.querySelector(".sgf .btn").onclick = function () { now = lines.length; end(true); };
    draw();
    root.querySelector("h1").focus({ preventScroll: true });

    if (!o.live) {
      var at = 0, ms = function (i) { return typeof o.stepMs === "function" ? o.stepMs(i) : (o.stepMs || 1200); };
      lines.forEach(function (_, i) { at += ms(i); timers.push(setTimeout(function () { if (alive()) { now = i + 1; draw(); } }, at)); });
      timers.push(setTimeout(function () { if (alive()) end(true); }, at + END_MS));
      return { tick: function () {}, finish: function () {}, close: function () { closed = true; ended = true; timers.forEach(clearTimeout); unhide(); root.remove(); } };
    }
    // live: ticks come from real events; each one stays on screen a moment so it can be read
    var queue = [], busy = false;
    function pump() {
      if (busy || !queue.length || ended) return;
      var job = queue.shift(); busy = true;
      if (!alive()) return;
      job();
      draw();
      timers.push(setTimeout(function () { busy = false; pump(); }, LIVE_MIN));
    }
    return {
      tick: function (k, patch) { queue.push(function () { if (patch && lines[k - 1]) Object.assign(lines[k - 1], patch); now = Math.max(now, k); }); pump(); },
      finish: function () { queue.push(function () { now = lines.length; timers.push(setTimeout(function () { if (alive()) end(true); }, END_MS)); }); pump(); },
      close: function () { if (closed) return; closed = true; ended = true; timers.forEach(clearTimeout); unhide(); root.remove(); }
    };
  }

  window.ChipInStage = { play: play, inline: inline };
})();
