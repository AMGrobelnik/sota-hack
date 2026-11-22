/*
 * i1-sizecost.js: unit cost against chip size, the first block of the "Why this size" panel.
 * Defines window.ChipInSizeCost.
 *
 * A stepped bar chart: the chosen chip, then the next larger designs from the same run, each bar the
 * estimated unit cost with the extra against the chosen chip written under it (plus so much per unit, plus so
 * many percent), and rows for the run's metric, battery life and silicon area. A phone keeps the chosen, the
 * largest run size and the sizes past the run. Two hatched bars past the run
 * (twice and five times the size where the die outgrows its pads) show where the cost starts to climb.
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
    ".scx-plot{height:116px;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;border-bottom:1px solid var(--i300);position:relative}",
    ".scx-plot>b{font-size:14px;font-weight:700;color:var(--i800);text-align:center;margin-bottom:3px}",
    ".scx-plot>i{display:block;width:min(64px,80%);border-radius:6px 6px 0 0;background:#8b93a7;min-height:3px;position:relative}",
    ".scx-plot>i>s{position:absolute;left:0;right:0;top:0;background:rgb(0 0 0/.28);border-radius:6px 6px 0 0;text-decoration:none}",
    ".scx-c.me .scx-plot>i{background:var(--blue7)}",
    ".scx-c.me .scx-plot>b{color:var(--blue7)}",
    ".scx-c.far .scx-plot>i{background:repeating-linear-gradient(135deg,#c9ced9 0 5px,#e4e7ee 5px 10px);box-shadow:inset 0 0 0 1px #b2b6c2}",
    ".scx-c.far .scx-plot>b{color:var(--i700)}",
    ".scx-sz{font-size:13.5px;font-weight:650;color:var(--i900);text-align:center;padding-top:5px;line-height:1.3}",
    ".scx-sz small{display:block;font-size:11.5px;font-weight:600;color:var(--i700)}",
    ".scx-c.me .scx-sz,.scx-c.me .scx-sz small{color:var(--blue7)}",
    ".scx-cell{font-size:12.5px;color:var(--i800);text-align:center;padding:5px 0;border-top:1px solid rgb(0 0 0/.07);line-height:1.35}",
    ".scx-st{font-weight:500}.scx-st.up{font-weight:700}",
    ".scx-cell small{font-size:11.5px;color:var(--i700)}",
    ".scx-far{font-size:11.5px;font-weight:600;color:var(--i700);text-align:center;border-top:1px dashed var(--i300);padding-top:3px;margin-top:2px}",
    ".scx-lev{display:flex;flex-wrap:wrap;gap:6px 18px;margin:10px 0 2px;font-size:13px;color:var(--i800);line-height:1.45}",
    ".scx-lev b{font-weight:650;color:var(--i900)}",
    ".scx-ft{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-top:6px}",
    ".scx-ft p{margin:0;font-size:12.5px;color:var(--i700);line-height:1.45}",
    "@media (max-width:767px){.scx-g{grid-template-columns:64px repeat(var(--np),minmax(58px,1fr));column-gap:4px}.scx-g .mid{display:none}.scx-rl{font-size:11.5px}.scx-v{font-size:14px}.scx-cell{font-size:12px}}",
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
    var top = all.reduce(function (a, p) { return Math.max(a, p.model.unit_cost); }, 0) || 1;

    // the metric column, read as the run's chart reads it (a measured file pooled)
    var showM = !af && P.MET[key];
    var rr = P.mFile(run) ? Object.assign({}, run, { judge: "pooled" }) : run;
    var mv = function (p) { if (p.far) return "&ndash;"; var x = P.metricOf(rr, p.d, key).v; return x == null ? "&ndash;" : esc(P.fmtVal(key, x)); };

    // a column's classes: the chosen one, the sizes past the run, and the middle run sizes a phone leaves out
    var cc = function (i) { return (i === 0 ? " me" : "") + (all[i].far ? " far" : "") + (i > 0 && i < pts.length - 1 ? " mid" : ""); };
    var np = n - Math.max(0, pts.length - 2), who = af ? "built" : v.ev.chosen ? "chosen" : "best";
    var g = '<div class="scx-rl">Unit cost ' + '<span class="mk est">estimated</span></div>';
    all.forEach(function (p, i) {
      var h = Math.max(2, p.model.unit_cost / top * 100), die = Math.min(100, p.model.die_cost / p.model.unit_cost * 100);
      var tip = "Die " + money(p.model.die_cost) + " of " + money(p.model.unit_cost) + " per unit (estimated)";
      g += '<div class="scx-c' + cc(i) + '"><div class="scx-plot" title="' + esc(tip) + '"><b>' + est(money(p.model.unit_cost), "cost") + '</b><i style="height:' + h.toFixed(1) + '%"><s style="height:' + die.toFixed(1) + '%"></s></i></div></div>';
    });
    g += '<div class="scx-rl">Chip size</div>';
    all.forEach(function (p, i) {
      var sz = p.estSize ? "about " + P.about(p.gates) : P.fmt(p.gates);
      var tag = i === 0 ? who : p.far ? "for scale" : p.note ? p.note.replace(/,.*$/, "") : "in this run";
      g += '<div class="scx-c' + cc(i) + '"><div class="scx-sz">' + sz + "<small>" + esc(tag) + "</small></div></div>";
    });
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
    else if (Math.abs(dc) < 0.005) verdict = "<b>Unit cost stays at " + est(money(pts[0].model.unit_cost), "cost") + " from " + sz(pts[0]) + " to " + sz(last) + " gates.</b> The pads, not the logic, set the die size, and the silicon is only " + est(money(pts[0].model.die_cost), "cost") + " of it.";
    else verdict = "<b>Unit cost rises from " + est(money(pts[0].model.unit_cost), "cost") + " at " + sz(pts[0]) + " gates to " + est(money(last.model.unit_cost), "cost") + " at " + sz(last) + "</b> (" + stepTxt(pts[0].model.unit_cost, last.model.unit_cost, "cost", "$") + " per unit).";
    var climb = far.length ? " Cost climbs only once the logic outgrows the pads, above about " + est(fmtInt(padGates) + " gates", "area") + ": at " + fmtInt(far[far.length - 1].gates) + " gates, " + stepTxt(pts[0].model.unit_cost, far[far.length - 1].model.unit_cost, "cost", "$") + " per unit." : "";

    // the lever that does move the cost: the battery class
    var bc = i0.battery_cost, mine = pts[0].model.inputs.battery_class;
    var lev = '<div class="scx-lev"><span><b>What does move the cost:</b> the battery, ' + ["primary coin cell", "rechargeable lithium"].map(function (k) { return esc(SHORT[k]) + " " + est(money(bc[k]), "cost") + (k === mine ? " (this design)" : ""); }).join(", ") + ".</span></div>";

    return '<div class="scx"><div class="scx-h"><h3>Unit cost as the chip grows</h3><span class="mk est">estimated</span></div>' +
      '<p class="scx-v">' + verdict + climb + "</p>" +
      '<div class="scx-w"><div class="scx-g" style="--n:' + n + ";--np:" + np + '">' + g + "</div></div>" + lev +
      '<div class="scx-ft"><button type="button" class="ws-b" data-ws-cost>Edit cost assumptions</button><p>Dark cap: the die&rsquo;s share. Hatched: sizes past this run.</p></div></div>';
  }
  window.ChipInSizeCost = { html: html };
})();
