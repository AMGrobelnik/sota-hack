// Fills every [data-waitlist-map] element with an inline SVG world map of the countries people
// signed up from. Needs waitlist.js (numbers) and waitlist-world.js (shapes: Natural Earth, public
// domain). No network request. Colours come from CSS on the element:
//   --wl-accent  sign-up countries and dots (default #2f6bff)
//   --wl-land    quiet fill of all other countries (default: the text colour at 14%)
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var world = window.WAITLIST_WORLD;
  if (!world) return;

  // The accent is read with a fallback (not declared), so --wl-accent set on the element or any
  // ancestor wins.
  var ACC = "var(--wl-accent,#2f6bff)";
  var CSS =
    "[data-waitlist-map]{display:block}" +
    "[data-waitlist-map] .wlm-svg{display:block;width:100%;height:auto;overflow:visible}" +
    ".wlm-land{fill:var(--wl-land,color-mix(in srgb,currentColor 14%,transparent));" +
    "stroke:color-mix(in srgb,currentColor 22%,transparent);stroke-width:.5px;stroke-linejoin:round;" +
    "vector-effect:non-scaling-stroke}" +
    ".wlm-land.wlm-on{fill:color-mix(in srgb," + ACC + " 50%,transparent);" +
    "stroke:" + ACC + ";stroke-opacity:.8;stroke-width:.8px}" +
    ".wlm-dot{fill:" + ACC + ";fill-opacity:.95;stroke:#fff;stroke-opacity:.55;stroke-width:.75px;" +
    "vector-effect:non-scaling-stroke}" +
    ".wlm-ring{fill:" + ACC + ";fill-opacity:.4;transform-box:fill-box;transform-origin:center;" +
    "animation:wlm-pulse 3.2s ease-out infinite}" +
    "@keyframes wlm-pulse{0%{transform:scale(.7);opacity:.7}100%{transform:scale(2.6);opacity:0}}" +
    "@media (prefers-reduced-motion:reduce){.wlm-ring{animation:none;opacity:.25}}" +
    ".wlm-legend{margin:.6em 0 0;font-size:.875rem;opacity:.75;text-align:center}" +
    ".wlm-legend strong{font-weight:600}";

  function el(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }

  function addStyle() {
    if (document.getElementById("wlm-style")) return;
    var s = document.createElement("style");
    s.id = "wlm-style";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function render(host, countries) {
    var list = countries.filter(function (c) { return world.c[c.code]; })
      .sort(function (a, b) { return b.count - a.count; });
    var max = list.length ? list[0].count : 1;
    var byCode = {};
    list.forEach(function (c) { byCode[c.code] = c.count; });

    var scale = host.clientWidth / world.w;
    if (!scale) return; // hidden: drawn when it gets a width (see watch)
    host.textContent = "";
    var svg = el("svg", {
      "class": "wlm-svg", viewBox: "0 0 " + world.w + " " + world.h, role: "img",
      "aria-label": "World map of the " + list.length + " countries people signed up from"
    }, host);

    var land = el("g", {}, svg);
    Object.keys(world.c).forEach(function (code) {
      var d = world.c[code][3];
      if (!d) return;
      var p = el("path", { d: d, "class": byCode[code] ? "wlm-land wlm-on" : "wlm-land" }, land);
      if (byCode[code]) el("title", {}, p).textContent = world.c[code][0] + ": " + byCode[code];
    });

    var dots = el("g", {}, svg);
    // Biggest first, so small neighbouring dots (Europe) are drawn on top of it.
    list.forEach(function (c, i) {
      var w = world.c[c.code];
      // Dot radius in screen pixels (3 to 10 px by count), converted to map units.
      var r = (3 + 7 * Math.sqrt(c.count / max)) / scale;
      var g = el("g", {}, dots);
      el("title", {}, g).textContent = w[0] + ": " + c.count;
      var ring = el("circle", { cx: w[1], cy: w[2], r: r, "class": "wlm-ring" }, g);
      ring.style.animationDelay = ((i * 0.37) % 3.2).toFixed(2) + "s";
      el("circle", { cx: w[1], cy: w[2], r: r * 0.55, "class": "wlm-dot" }, g);
    });

    var n = list.length;
    var legend = document.createElement("p");
    legend.className = "wlm-legend";
    legend.append("People from ");
    var strong = document.createElement("strong");
    strong.textContent = String(n);
    legend.append(strong, n === 1 ? " country" : " countries");
    host.appendChild(legend);
  }

  var current = null, drawnWidth = new WeakMap(), watcher = null;

  // Redraw when a map's width changes (dot sizes are in screen pixels); also covers hidden hosts.
  function draw(data) {
    if (!data) return;
    current = data;
    var hosts = document.querySelectorAll("[data-waitlist-map]");
    for (var i = 0; i < hosts.length; i++) {
      render(hosts[i], data.countries || []);
      drawnWidth.set(hosts[i], hosts[i].clientWidth);
      if (watcher) watcher.observe(hosts[i]);
    }
  }

  function watch() {
    if (!window.ResizeObserver) return;
    watcher = new ResizeObserver(function (entries) {
      entries.forEach(function (e) {
        var w = e.target.clientWidth;
        if (current && w && w !== drawnWidth.get(e.target)) {
          render(e.target, current.countries || []);
          drawnWidth.set(e.target, w);
        }
      });
    });
  }

  function init() {
    addStyle();
    watch();
    draw(window.Waitlist && window.Waitlist.data);
    document.addEventListener("waitlist:data", function (e) { draw(e.detail); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
