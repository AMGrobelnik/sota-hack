/*
 * i1-sizecost.js: unit cost against chip size, the first block of the "Why this size" panel.
 * Defines window.ChipInSizeCost.
 *
 * A small line chart: estimated unit cost against gates on a log axis, flat while the pads set the die and
 * rising past the pad-limited threshold, with this run's designs as dots and the chosen one highlighted. Under it,
 * folded, the sizes side by side (unit cost, extra against the chosen chip, metric, battery life, logic area),
 * plus two sizes past the run where the die outgrows its pads.
 * When the cost is flat across the run, the block says so and names the lever that does move it: the battery.
 * Every figure comes from window.ChipInModels (costModel, deviceBudget, batteryClass); nothing here is a price.
 * html(run, v, P, ctx, d, rows): P = the page helpers, ctx = panelCtx(run, v), d = the chosen design,
 * rows = [{ d, note, estSize }] the larger designs, smallest first.
 */
(function () {
  "use strict";
  var M = function () { return window.ChipInModels; };
  var CSS = [
    ".scx{padding:12px 0 4px;border-top:1px solid rgb(0 0 0/.08)}",
    ".scx-h{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;margin:0 0 4px}",
    ".scx-h h3{font-size:14px;font-weight:650;color:var(--i900);margin:0}",
    ".scx-v{font-size:15px;color:var(--i900);line-height:1.45;margin:0 0 10px;max-width:880px}",
    ".scx-v b{font-weight:650}",
    ".scx-w{overflow-x:auto;padding-bottom:2px}",
    ".scx-g{display:grid;grid-template-columns:120px repeat(var(--n),minmax(78px,1fr));column-gap:8px;min-width:min-content;font-variant-numeric:tabular-nums}",
    ".scx-g>div{min-width:0}",
    ".scx-rl{font-size:12px;font-weight:600;color:var(--i700);align-self:center;line-height:1.3}",
    ".scx-ch{margin:2px 0 4px}.scx-cn{display:none}",
    ".scx-svg{display:block;max-width:100%;height:auto;overflow:visible;font-family:inherit}",
    ".scx-svg .ln{fill:none;stroke:#8b93a7;stroke-width:2}.scx-svg .ax{stroke:var(--i300);stroke-width:1}",
    ".scx-svg .th{stroke:var(--i400,#9aa1b1);stroke-width:1;stroke-dasharray:3 3}",
    ".scx-svg .z,.scx-svg .tk{font-size:10.5px;fill:var(--i600)}.scx-svg .v{font-size:11px;font-weight:600;fill:var(--i800)}",
    ".scx-svg .dt{fill:#fff;stroke:#5c6477;stroke-width:1.5}.scx-svg .me{fill:var(--blue7);stroke:#fff;stroke-width:1.5}",
    ".scx-svg .ml{font-size:11px;font-weight:650;fill:var(--blue7)}",
    ".scx-svg .nl{font-size:10.5px;fill:var(--i700)}",
    ".scx-cap{margin:2px 0 0;font-size:12px;color:var(--i600)}",
    ".scx-sz{font-size:13.5px;font-weight:650;color:var(--i900);text-align:center;padding-top:5px;line-height:1.3}",
    ".scx-sz small{display:block;font-size:11.5px;font-weight:600;color:var(--i700)}",
    ".scx-c.me .scx-sz,.scx-c.me .scx-sz small{color:var(--blue7)}",
    ".scx-cell{font-size:12.5px;color:var(--i800);text-align:center;padding:5px 0;border-top:1px solid rgb(0 0 0/.07);line-height:1.35}",
    ".scx-st{font-weight:500}.scx-st.up{font-weight:700}",
    ".scx-cell small{font-size:11.5px;color:var(--i700)}",
    ".scx-far{font-size:11.5px;font-weight:600;color:var(--i700);text-align:center;border-top:1px dashed var(--i300);padding-top:3px;margin-top:2px}",
    ".scx-lev{display:flex;flex-wrap:wrap;gap:6px 18px;margin:10px 0 2px;font-size:13px;color:var(--i800);line-height:1.45}",
    ".scx-lev b{font-weight:650;color:var(--i900)}",
    ".scx-d{margin:8px 0 0;font-size:13px;color:var(--i800)}.scx-d>summary{cursor:pointer;color:var(--blue7);font-weight:600;width:fit-content}.scx-m{margin:6px 0 0;line-height:1.45}",
    ".scx-ft{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-top:6px}",
    ".scx-ft p{margin:0;font-size:12.5px;color:var(--i700);line-height:1.45}",
    "@media (max-width:767px){.scx-cw{display:none}.scx-cn{display:block}.scx-g{grid-template-columns:64px repeat(var(--np),minmax(58px,1fr));column-gap:4px}.scx-g .mid{display:none}.scx-rl{font-size:11.5px}.scx-v{font-size:14px}.scx-cell{font-size:12px}}",
  ].join("\n");
  function css() {
    if (document.getElementById("scx-styles")) return;
    var s = document.createElement("style"); s.id = "scx-styles"; s.textContent = CSS; document.head.appendChild(s);
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function fmtInt(x) { return Math.round(x).toLocaleString("en-GB"); }
  function money(x) { return "$" + Math.abs(x).toFixed(2); }
  function life(days) { return days >= 2 ? fmtInt(days) + " days" : (days * 24).toFixed(1) + " h"; }
  function est(txt, field) { return '<span class="est" title="' + esc(M().describeEstimate(field)) + '">' + txt + "</span>"; }
  function pct(a, b) { var p = a > 0 ? (b / a - 1) * 100 : 0; return (p < 0 ? "-" : "+") + (Math.abs(p) < 0.05 ? "0" : Math.abs(p) < 10 ? Math.abs(p).toFixed(1) : Math.round(Math.abs(p))) + "%"; }
  function count(d) { return d.sensors || d.channels || 1; }
  var SHORT = { "primary coin cell": "coin cell", "rechargeable lithium": "rechargeable", "larger pack or mains": "larger pack" };

  // one size: unit cost, its die share, battery class and life, all from ChipInModels with the run's cost inputs
  function point(ctx, gates, d) {
    var b = M().deviceBudget({ kind: ctx.caseKind, channels: d.channels, sensors: count(d), gates: gates, decisionsPerSecond: 1 });
    var cls = M().batteryClass(b.total_uw);
    var m = {}, k; for (k in ctx.costInputs || {}) m[k] = ctx.costInputs[k];
    m.gates = gates; if (!m.battery_class) m.battery_class = cls.class;
    return { gates: gates, d: d, model: M().costModel(m), cls: cls };
  }
  function stepTxt(a, b, field, unit) {
    var dv = b - a, flat = Math.abs(dv) < (unit === "$" ? 0.005 : Math.abs(a) * 0.0005);
    var cls = flat ? "flat" : "up";
    var abs = unit === "$" ? (dv < 0 ? "-" : "+") + money(dv) : "";
    return '<span class="scx-st ' + cls + '">' + est((abs ? abs + " (" : "") + (flat ? "+0%" : pct(a, b)) + (abs ? ")" : ""), field) + "</span>";
  }

  // the cost line: unit cost from costModel at each gate count (battery class held at the chosen chip's), on a log
  // gate axis, flat while the pads set the die and rising past padGates; the run's designs sit on it as dots
  function chart(ctx, pts, padGates, who, W, P) {
    var H = 142, L = 46, R = W - 14, T = 14, B = H - 34;
    var m = {}, k; for (k in ctx.costInputs || {}) m[k] = ctx.costInputs[k];
    m.battery_class = pts[0].model.inputs.battery_class;
    var gMin = pts.reduce(function (a, p) { return Math.min(a, p.gates); }, Infinity), gMax = pts.reduce(function (a, p) { return Math.max(a, p.gates); }, 0);
    var lo = Math.pow(10, Math.floor(Math.log10(Math.min(gMin, padGates / 10)))), hi = Math.pow(10, Math.ceil(Math.log10(Math.max(gMax * 2, padGates * 5))));
    var x = function (g) { return L + (Math.log10(g) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo)) * (R - L); };
    var line = [], n = 80, j, c;
    for (j = 0; j <= n; j++) { var g = lo * Math.pow(hi / lo, j / n); m.gates = g; line.push([g, M().costModel(m).unit_cost]); }
    var yMax = Math.max(line[n][1], pts.reduce(function (a, p) { return Math.max(a, p.model.unit_cost); }, 0)) * 1.08;
    var y = function (u) { return B - u / yMax * (B - T); };
    var s = '<svg class="scx-svg" viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '" role="img" aria-label="Estimated unit cost against chip size: flat below ' + esc(fmtInt(padGates)) + ' gates, rising above">';
    // threshold and the two zones
    var xp = x(padGates);
    s += '<line x1="' + xp.toFixed(1) + '" y1="' + T + '" x2="' + xp.toFixed(1) + '" y2="' + B + '" class="th"/>';
    s += '<text x="' + (xp - 6).toFixed(1) + '" y="' + (B - 6) + '" text-anchor="end" class="z">pads set the size</text>';
    s += '<text x="' + (xp + 6).toFixed(1) + '" y="' + (B - 6) + '" class="z">logic sets it</text>';
    // axis and ticks at each decade
    s += '<line x1="' + L + '" y1="' + B + '" x2="' + R + '" y2="' + B + '" class="ax"/>';
    for (c = lo; c <= hi * 1.001; c *= 10) {
      var lab = c >= 1e6 ? c / 1e6 + "M" : c >= 1e3 ? c / 1e3 + "k" : String(c);
      s += '<line x1="' + x(c).toFixed(1) + '" y1="' + B + '" x2="' + x(c).toFixed(1) + '" y2="' + (B + 4) + '" class="ax"/><text x="' + x(c).toFixed(1) + '" y="' + (B + 15) + '" text-anchor="middle" class="tk">' + lab + "</text>";
    }
    s += '<text x="' + R + '" y="' + (B + 30) + '" text-anchor="end" class="tk">gates, log scale</text>';
    // the line, its start and end values
    s += '<polyline class="ln" points="' + line.map(function (p) { return x(p[0]).toFixed(1) + "," + y(p[1]).toFixed(1); }).join(" ") + '"/>';
    s += '<text x="' + (L - 6) + '" y="' + (y(line[0][1]) + 4).toFixed(1) + '" text-anchor="end" class="v">' + money(line[0][1]) + "</text>";
    s += '<text x="' + (R - 2) + '" y="' + (y(line[n][1]) - 8).toFixed(1) + '" text-anchor="end" class="v">' + money(line[n][1]) + "</text>";
    // the designs: the chosen one last so it draws on top, labelled
    pts.slice(1).forEach(function (p) {
      s += '<circle cx="' + x(p.gates).toFixed(1) + '" cy="' + y(p.model.unit_cost).toFixed(1) + '" r="3.5" class="dt"><title>' + esc((p.estSize ? "about " + P.about(p.gates) : P.fmt(p.gates)) + " gates" + (p.note ? ", " + p.note.replace(/,.*$/, "") : "") + ": " + money(p.model.unit_cost) + " per unit (estimated)") + "</title></circle>";
    });
    // the first noted design (the best on validation, sized by estimate) gets a short label above the line
    var nb = pts.slice(1).find(function (p) { return p.note && p.estSize && p.d && p.d.gm === null; });
    if (nb) s += '<text x="' + x(nb.gates).toFixed(1) + '" y="' + (y(nb.model.unit_cost) - 10).toFixed(1) + '" text-anchor="middle" class="nl">' + esc("about " + P.about(nb.gates) + ", not compiled") + "</text>";
    var p0 = pts[0], cx = x(p0.gates), cy = y(p0.model.unit_cost);
    s += '<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="5" class="me"><title>' + esc(P.fmt(p0.gates) + " gates, " + who + ": " + money(p0.model.unit_cost) + " per unit (estimated)") + "</title></circle>";
    s += '<text x="' + cx.toFixed(1) + '" y="' + (cy + 18).toFixed(1) + '" text-anchor="middle" class="ml">' + esc(P.fmt(p0.gates) + " " + who) + "</text>";
    return s + "</svg>";
  }

  function html(run, v, P, ctx, d, rows) {
    if (!M() || !ctx || !ctx.caseKind || !d) return "";
    css();
    var af = run.case === "af", key = run.primary;
    var pts = [point(ctx, d.gates, d)].concat(rows.map(function (r) { var p = point(ctx, r.d.gates, r.d); p.note = r.note; p.estSize = r.estSize; return p; }));
    var i0 = pts[0].model.inputs, padGates = i0.pad_limited_floor_mm2 * 1e6 / i0.area_per_gate_um2;
    // past the run: where the die outgrows its pads, so the climb the run's own sizes never reach is visible
    var far = [2, 5].map(function (x) { return Math.round(padGates * x / 1000) * 1000; }).filter(function (g) { return g > pts[pts.length - 1].gates * 1.5; })
      .map(function (g) { var p = point(ctx, g, d); p.far = true; return p; });
    var all = pts.concat(far), n = all.length;

    // the metric column, read as the run's chart reads it (a measured file pooled)
    var showM = !af && P.MET[key];
    var rr = P.mFile(run) ? Object.assign({}, run, { judge: "pooled" }) : run;
    var mv = function (p) { if (p.far) return "&ndash;"; var x = P.metricOf(rr, p.d, key).v; return x == null ? "&ndash;" : esc(P.fmtVal(key, x)); };

    // a column's classes: the chosen one, the sizes past the run, and the middle run sizes a phone leaves out
    var cc = function (i) { return (i === 0 ? " me" : "") + (all[i].far ? " far" : "") + (i > 0 && i < pts.length - 1 ? " mid" : ""); };
    var np = n - Math.max(0, pts.length - 2), who = af ? "compiled" : v.ev.chosen ? "chosen" : "best";
    var g = '<div class="scx-rl">Chip size</div>';
    all.forEach(function (p, i) {
      var sz = p.estSize ? "about " + P.about(p.gates) : P.fmt(p.gates);
      var tag = i === 0 ? who : p.far ? "for scale" : p.note ? p.note.replace(/,.*$/, "") : "in this run";
      g += '<div class="scx-c' + cc(i) + '"><div class="scx-sz">' + sz + "<small>" + esc(tag) + "</small></div></div>";
    });
    g += '<div class="scx-rl">Unit cost</div>';
    all.forEach(function (p, i) { g += '<div class="scx-cell' + cc(i) + '">' + est(money(p.model.unit_cost), "cost") + "</div>"; });
    // each step is written against the chosen chip: plus so much per unit, plus so many percent
    g += '<div class="scx-rl">Extra per unit</div>';
    all.forEach(function (p, i) { g += '<div class="scx-cell' + cc(i) + '">' + (i ? stepTxt(all[0].model.unit_cost, p.model.unit_cost, "cost", "$") : "<small>" + esc(who) + "</small>") + "</div>"; });
    if (showM) {
      g += '<div class="scx-rl">' + esc(P.MET[key].short || P.MET[key].name) + "</div>";
      all.forEach(function (p, i) { g += '<div class="scx-cell' + cc(i) + '">' + mv(p) + "</div>"; });
    }
    g += '<div class="scx-rl">Battery life</div>';
    all.forEach(function (p, i) {
      var c = p.cls, lt = c.class === "larger pack or mains" ? SHORT[c.class] : est(life(c.life_days), "battery_life");
      g += '<div class="scx-cell' + cc(i) + '">' + lt + (i ? "<br>" + stepTxt(all[0].cls.life_days, c.life_days, "battery_life", "d") : "<br><small>" + esc(SHORT[c.class]) + "</small>") + "</div>";
    });
    g += '<div class="scx-rl">Logic area</div>';
    all.forEach(function (p, i) {
      var mm = p.model.logic_area_mm2;
      g += '<div class="scx-cell' + cc(i) + '">' + est((mm < 0.1 ? mm.toFixed(3) : mm.toFixed(2)) + " mm&sup2;", "area") + "<br><small>" + (p.model.pad_limited ? "inside the pads" : "die " + p.model.die_area_mm2.toFixed(1) + " mm&sup2;") + "</small></div>";
    });
    if (far.length) g += "<div></div>" + all.map(function (p, i) { return p.far ? (i === pts.length ? '<div class="scx-far" style="grid-column:span ' + far.length + '">Beyond this run</div>' : "") : '<div class="' + cc(i) + '"></div>'; }).join("");

    // the verdict sentence: the climb across the run's own sizes, or that there is none and why
    var last = pts[pts.length - 1], dc = last.model.unit_cost - pts[0].model.unit_cost, sz = function (p) { return p.estSize ? "about " + P.about(p.gates) : P.fmt(p.gates); };
    var verdict;
    if (pts.length < 2) verdict = "No larger design in this run to compare.";
    else if (Math.abs(dc) < 0.005 && pts[0].model.pad_limited && last.model.pad_limited) verdict = "<b>Below about " + est(fmtInt(padGates) + " gates", "area") + " the pads, not the logic, set the die size, so a bigger chip costs the same per unit.</b> Here unit cost stays at " + est(money(pts[0].model.unit_cost), "cost") + " from " + sz(pts[0]) + " to " + sz(last) + " gates.";
    else if (Math.abs(dc) < 0.005) verdict = "<b>Unit cost stays at " + est(money(pts[0].model.unit_cost), "cost") + " from " + sz(pts[0]) + " to " + sz(last) + " gates:</b> the silicon is a small share of it.";
    else verdict = "<b>Unit cost rises from " + est(money(pts[0].model.unit_cost), "cost") + " at " + sz(pts[0]) + " gates to " + est(money(last.model.unit_cost), "cost") + " at " + sz(last) + "</b> (" + stepTxt(pts[0].model.unit_cost, last.model.unit_cost, "cost", "$") + " per unit).";
    var silicon = "The silicon is " + est(money(pts[0].model.die_cost), "cost") + " of the " + est(money(pts[0].model.unit_cost), "cost") + " per unit.";
    var climb = far.length ? "Cost climbs only once the logic outgrows the pads, above about " + est(fmtInt(padGates) + " gates", "area") + ": at " + fmtInt(far[far.length - 1].gates) + " gates, " + stepTxt(pts[0].model.unit_cost, far[far.length - 1].model.unit_cost, "cost", "$") + " per unit." : "";

    // the lever that does move the cost: the battery class
    var bc = i0.battery_cost, mine = pts[0].model.inputs.battery_class;
    var lev = '<div class="scx-lev"><span><b>What does move the cost:</b> the battery, ' + ["primary coin cell", "rechargeable lithium"].map(function (k) { return esc(SHORT[k]) + " " + est(money(bc[k]), "cost") + (k === mine ? " (this design)" : ""); }).join(", ") + ".</span></div>";

    return '<div class="scx"><div class="scx-h"><h3>Unit cost as the chip grows</h3><span class="mk est">estimated</span></div>' +
      '<p class="scx-v">' + verdict + "</p>" +
      '<div class="scx-ch"><div class="scx-cw">' + chart(ctx, pts, padGates, who, 560, P) + '</div><div class="scx-cn">' + chart(ctx, pts, padGates, who, 340, P) + "</div>" +
      '<p class="scx-cap">Estimated unit cost from the cost model, not a quote. Dots: designs in this run.</p></div>' +
      '<details class="scx-d"><summary>Sizes side by side</summary><div class="scx-w"><div class="scx-g" style="--n:' + n + ";--np:" + np + '">' + g + "</div></div></details>" +
      '<details class="scx-d"><summary>More on cost</summary><p class="scx-m">' + silicon + (climb ? " " + climb : "") + "</p>" + lev + "</details>" +
      '<div class="scx-ft"><button type="button" class="ws-b" data-ws-cost>Edit cost assumptions</button></div></div>';
  }
  window.ChipInSizeCost = { html: html };
})();
