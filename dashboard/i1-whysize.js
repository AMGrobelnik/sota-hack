/*
 * i1-whysize.js: the "Why this size" panel of the ChipIn i1 dashboard. Defines window.ChipInWhySize.
 *
 * Shown on the overview once a run's result is final, under the chart:
 *   cost along the curve  the chip and bigger designs on its own frontier, unit cost from the editable cost
 *                         model (ChipInModels.costModel and costDelta) and the pad-limited note;
 *   battery               total device power with the chip's share (deviceBudget), the channel-count lever
 *                         and where it tips from a coin cell to a rechargeable (classBoundaries, channelStory);
 *   regulation            a one-line pointer to the Regulation panel (i1-regulation.js), the one place for it;
 * The page's battery band (#batBand, ChipInPanels.mountBattery) moves into the panel as its detail.
 * Every power, battery and cost figure comes from ChipInModels; this file only picks designs and words.
 * tick(el, run, v, P, ctx, openCost): P = the page helpers (the summary module's), ctx = panelCtx(run, v).
 */
(function () {
  "use strict";
  var M = function () { return window.ChipInModels; };
  var CSS = [
    // the panel carries the brand accent: a blue left rule and a faint blue tint set it apart from the chart
    ".ws{background:#f7f9ff;border:1px solid #dbe3f8;border-left:4px solid var(--blue7);border-radius:14px;box-shadow:var(--sh-hair);padding:14px 18px 12px;scroll-margin-top:12px}",
    ".ws-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 0 2px}",
    ".ws-h h2{font-size:17px;font-weight:700;margin:0;color:var(--blue7)}",
    ".ws-lede{font-size:14px;color:var(--i800);margin:0 0 10px;line-height:1.45}",
    ".ws-g{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr) minmax(0,1.2fr);border-top:1px solid var(--hair)}",
    ".ws-g.two{grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);border-top-color:rgb(0 0 0/.08)}",
    ".ws-g.two .ws-c:nth-child(2){padding-right:0}",
    ".ws-g.one{grid-template-columns:minmax(0,1fr)}",
    ".ws-lk{border:0;background:none;padding:0;font:inherit;color:var(--blue7);font-weight:600;cursor:pointer;text-decoration:underline;text-underline-offset:3px}",
    ".ws-c{padding:10px 16px 4px;border-left:1px solid var(--hair);min-width:0}",
    ".ws-c:first-child{border-left:0;padding-left:0}.ws-c:last-child{padding-right:0}",
    ".ws-c h3{font-size:12.5px;font-weight:650;color:var(--i900);margin:0 0 6px;display:flex;gap:6px;align-items:baseline;flex-wrap:wrap}",
    ".ws-t{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}",
    ".ws-t th{font-weight:500;color:var(--i600);font-size:11.5px;text-align:right;padding:0 0 3px 8px;vertical-align:bottom;line-height:1.5;white-space:nowrap}",
    ".ws-t th.m{white-space:normal}",
    ".ws-t th:first-child,.ws-t td:first-child{text-align:left;padding-left:0}",
    ".ws-t td small{white-space:normal}",
    ".ws-t td{padding:4px 0 4px 8px;border-top:1px solid var(--hair);text-align:right;white-space:nowrap;color:var(--i800)}",
    ".ws-t tr.me td{font-weight:600;color:var(--i900)}",
    ".ws-t td small{font-weight:500;color:var(--i600);font-size:11.5px}",
    ".ws-p{font-size:12.5px;color:var(--i700);margin:7px 0 0;line-height:1.45}",
    ".ws-p b{color:var(--i900);font-weight:600}",
    ".ws-b{display:inline-flex;align-items:center;height:26px;padding:0 10px;margin:8px 0 4px;border-radius:8px;border:1px solid rgb(0 0 0/.12);background:#fff;font:inherit;font-size:12px;font-weight:500;color:var(--i700);cursor:pointer}",
    ".ws-b:hover{background:var(--i100)}",
    ".ws-l{list-style:none;margin:6px 0 0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:2px 12px;font-size:12.5px}",
    ".ws-l li{display:flex;align-items:baseline;gap:6px;color:var(--i800);white-space:nowrap}",
    ".ws-l li.me{font-weight:600;color:var(--i900)}",
    ".ws-l i{width:7px;height:7px;border-radius:50%;flex:none;align-self:center}",
    ".ws-l li span{color:var(--i600);font-weight:400}",
    ".ws-d{border-top:1px solid var(--hair);margin-top:10px;padding-top:8px;font-size:12.5px}",
    ".ws-d>summary{cursor:pointer;color:var(--blue7);font-weight:600;width:fit-content;max-width:100%}",
    ".ws-d>div{margin-top:8px}",
    "@media (max-width:1100px){.ws-g{grid-template-columns:1fr 1fr}.ws-c:nth-child(3){grid-column:1/-1;border-left:0;padding-left:0;border-top:1px solid var(--hair)}.ws-c:nth-child(2){padding-right:0}}",
    "@media (max-width:767px){.ws-g.two{grid-template-columns:1fr}}",
    "@media (max-width:767px){.ov #whySize{order:8}.ws{padding:12px 14px 10px}.ws-g{grid-template-columns:1fr}.ws-c{border-left:0;padding:10px 0 4px;border-top:1px solid var(--hair)}.ws-c:first-child{border-top:0}}",
  ].join("\n");
  function css() {
    if (document.getElementById("ws-styles")) return;
    var s = document.createElement("style"); s.id = "ws-styles"; s.textContent = CSS; document.head.appendChild(s);
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function fmtInt(x) { return Math.round(x).toLocaleString("en-GB"); }
  function money(x) { return "$" + Math.abs(x).toFixed(2); }
  function share(x) { var v = x * 100; return (v < 0.01 ? v.toPrecision(2) : v < 1 ? v.toFixed(3) : v.toFixed(1)) + "%"; }
  function mW(uw) { return (uw / 1000).toPrecision(3) + " mW"; }
  function life(days) { return days >= 2 ? fmtInt(days) + " days" : (days * 24).toFixed(1) + " h"; }
  function est(txt, field) { return '<span class="est" title="' + esc(M().describeEstimate(field)) + '">' + txt + "</span>"; }
  var DOT = { "primary coin cell": "#047857", "rechargeable lithium": "#b45309", "larger pack or mains": "#b91c1c" };
  var SHORT = { "primary coin cell": "coin cell", "rechargeable lithium": "rechargeable", "larger pack or mains": "larger pack" };
  var EST_MK = '<span class="mk est">estimated</span>';
  var srcMark = function (d) { return d && d.source === "measured" ? '<span class="mk mea">measured</span>' : '<span class="mk sim">simulated</span>'; };

  function final(run, v, P) {
    if (run.case === "af" && P.MEASURED.af) return P.afFinal(v);
    return !!(v.done || P.isMea(run));
  }
  function count(d) { return d.sensors || d.channels || 1; }
  function unitOf(kind, n) { var u = M().DEVICE_KINDS[kind].unit; return n === 1 ? u.replace(/s$/, "") : u; }

  /* ---------------------------------------------------------------- cost along the curve */
  function costOf(ctx, d) {
    // the battery class follows the design unless the cost drawer fixes one, as in ChipInPanels.openCost
    var b = M().deviceBudget({ kind: ctx.caseKind, channels: d.channels, sensors: count(d), gates: d.gates, decisionsPerSecond: 1 });
    var m = {}, k; for (k in ctx.costInputs || {}) m[k] = ctx.costInputs[k];
    m.gates = d.gates; if (!m.battery_class) m.battery_class = M().batteryClass(b.total_uw).class;
    return { model: M().costModel(m) };
  }
  function design(ctx, d) { return { gates: d.gates, channels: d.channels, sensors: count(d), kind: ctx.caseKind, decisionsPerSecond: 1 }; }
  function delta(ctx, a, b) {
    var o = {}, k; for (k in ctx.costInputs || {}) o[k] = ctx.costInputs[k]; o.kind = ctx.caseKind;
    return M().costDelta(design(ctx, a), design(ctx, b), o);
  }
  // bigger designs on the chip's own frontier: the next one up, the one nearest twice the size, the largest
  function biggerOf(run, v, P, d) {
    if (run.case === "af") {
      var F = P.MEASURED.af, out = [];
      if (F && F.bestD && F.bestD.gates > d.gates) out.push({ d: F.bestD, note: "best on validation, too large to build", estSize: true });
      var big = (v.vis || []).filter(function (x) { return x.gates > d.gates; }).reduce(function (a, x) { return !a || x.gates > a.gates ? x : a; }, null);
      if (big && (!out.length || big.gates > out[0].d.gates * 1.05)) out.push({ d: big, note: "largest candidate", estSize: true });
      return out;
    }
    var f = (v.ev.fronts || []).find(function (x) { return x.b.ch === d.channels; });
    var up = (f ? f.pts : []).filter(function (x) { return x.gates > d.gates; }).sort(function (a, b) { return a.gates - b.gates; });
    // no bigger frontier point (a best design that clears nothing): the bigger designs at the same channel count
    if (!up.length) up = (v.vis || []).filter(function (x) { return x.gates > d.gates && x.channels === d.channels && x.role !== "baseline"; }).sort(function (a, b) { return a.gates - b.gates; });
    if (!up.length) return [];
    // the next two sizes up, the one nearest twice the size and the largest, smallest first
    var two = up.reduce(function (a, x) { return Math.abs(Math.log(x.gates / (2 * d.gates))) < Math.abs(Math.log(a.gates / (2 * d.gates))) ? x : a; });
    var pick = [up[0], up[1], two, up[up.length - 1]].filter(function (x, i, a) { return x && a.indexOf(x) === i; }).sort(function (a, b) { return a.gates - b.gates; });
    return pick.map(function (x) { return { d: x }; });
  }
  function costHTML(run, v, P, ctx, d, rows) {
    var af = run.case === "af", key = run.primary;
    var showM = !af && P.MET[key];
    var me = costOf(ctx, d);
    var sizeTxt = function (r) { return r.estSize ? '<span class="est" title="' + esc(P.sizeTip ? P.sizeTip() : M().describeEstimate("area")) + '">about ' + P.about(r.d.gates) + "</span>" : P.fmt(r.d.gates); };
    // a measured results file reads pooled, as its chart does (its worst-patient figures can all sit at zero)
    var rr = P.mFile(run) ? Object.assign({}, run, { judge: "pooled" }) : run;
    var mv = function (x) { var val = P.metricOf(rr, x, key).v; return val == null ? "" : P.fmtVal(key, val); };
    var fld = showM ? P.metricOf(rr, d, key).f : null;
    var mName = showM ? (P.MET[key].short || P.MET[key].name) + (fld && /_worst$/.test(fld) ? ", worst " + P.caseOf(run).who : fld ? ", " + P.caseOf(run).whoP + " pooled" : "") : "";
    var head = "<tr><th>Gates</th>" + (showM ? '<th class="m">' + esc(mName) + " " + srcMark(d) + "</th>" : "") + "<th>Unit cost</th><th>Change</th></tr>";
    var body = '<tr class="me"><td>' + P.fmt(d.gates) + " <small>" + (af ? "built" : v.ev.chosen ? "chosen" : "best") + "</small></td>" + (showM ? "<td>" + mv(d) + "</td>" : "") + "<td>" + est(money(me.model.unit_cost), "cost") + "</td><td></td></tr>";
    var maxD = 0, allPad = me.model.pad_limited;
    rows.forEach(function (r) {
      var c = costOf(ctx, r.d), dc = c.model.unit_cost - me.model.unit_cost;
      if (Math.abs(dc) > Math.abs(maxD)) maxD = dc;
      if (!c.model.pad_limited) allPad = false;
      body += "<tr><td>" + sizeTxt(r) + (r.note ? " <small>" + esc(r.note) + "</small>" : "") + "</td>" + (showM ? "<td>" + mv(r.d) + "</td>" : "") + "<td>" + est(money(c.model.unit_cost), "cost") + "</td><td>" + est((dc < 0 ? "-" : "+") + money(dc), "cost") + "</td></tr>";
    });
    var i = me.model.inputs, padGates = i.pad_limited_floor_mm2 * 1e6 / i.area_per_gate_um2;
    var pad = allPad
      ? "<b>Pad-limited:</b> below about " + est(fmtInt(padGates) + " gates", "area") + " the pads set the die size, so silicon cost barely rises with size."
      : "Above about " + est(fmtInt(padGates) + " gates", "area") + " the logic outgrows the pads and the die grows with gates.";
    var small = rows.length ? (Math.abs(maxD) < 0.005 ? " Going bigger here costs " + est("nothing more", "cost") + " per unit." : " The largest step here is " + est(money(maxD) + " per unit", "cost") + ".") : "";
    return '<div class="ws-c"><h3>Cost per unit ' + EST_MK + '</h3><table class="ws-t">' + head + body + "</table>" +
      '<p class="ws-p">' + pad + small + "</p>" +
      '<button type="button" class="ws-b" data-ws-cost>Edit cost assumptions</button></div>';
  }

  /* --------------------------------------------------------------------------- battery */
  function batteryHTML(run, P, ctx, d) {
    var kind = ctx.caseKind, budgets = (ctx.budgets || []).map(function (b) { return kind === "incubator-radar-thermal" ? (b.sensors != null ? b.sensors : b.channels) : (b.channels != null ? b.channels : b.sensors); });
    if (!budgets.length) budgets = M().DEVICE_KINDS[kind].budgets;
    var mine = M().deviceBudget({ kind: kind, channels: d.channels, sensors: count(d), gates: d.gates, decisionsPerSecond: 1 });
    var rows = M().classBoundaries(kind, { budgets: budgets, gates: d.gates, decisionsPerSecond: 1 });
    var story = M().channelStory(kind, { budgets: budgets, gates: d.gates, decisionsPerSecond: 1 });
    var maxShare = rows.reduce(function (a, r) { return Math.max(a, r.chip_share); }, mine.chip_share);
    var n = count(d), u = M().DEVICE_KINDS[kind].unit;
    var html = '<div class="ws-c"><h3>Battery ' + EST_MK + "</h3>" +
      '<p class="ws-p" style="margin-top:0">Device ' + est(mW(mine.total_uw), "device_power") + " at " + n + " " + esc(unitOf(kind, n)) + "; the chip is " + est(share(mine.chip_share), "chip_power") + " of it.</p>";
    if (maxShare < 0.01) html += '<p class="ws-p"><b>The chip is never your battery bottleneck.</b></p>';
    html += '<p class="ws-p">What moves it: the number of ' + esc(u) + ".</p>";
    html += '<ul class="ws-l">' + rows.map(function (r) {
      var lt = r.class === "primary coin cell" ? life(r.life_days) : r.class === "rechargeable lithium" ? life(r.life_days) + "/charge" : "";
      return '<li class="' + (r.budget === n ? "me" : "") + '"><i style="background:' + DOT[r.class] + '"></i>' + r.budget + " " + esc(unitOf(kind, r.budget)) + " <span>" + (lt ? est(lt, "battery_life") + ", " : "") + est(SHORT[r.class], "battery_class") + "</span></li>";
    }).join("") + "</ul>";
    var t = story.tips && story.tips[0];
    html += '<p class="ws-p">' + (t
      ? "<b>Tips from " + esc(SHORT[t.from]) + " to " + esc(SHORT[t.to]) + " at " + t.budget + " " + esc(unitOf(kind, t.budget)) + ".</b>"
      : esc((SHORT[rows[0].class] || "").replace(/^./, function (c) { return c.toUpperCase(); })) + " from " + rows[0].budget + " to " + rows[rows.length - 1].budget + " " + esc(u) + ".") + "</p></div>";
    return { html: html, cls: M().batteryClass(mine.total_uw).class };
  }

  /* ------------------------------------------------------------------------------ the panel */
  function ledeText(run, v, P, ctx, d, rows) {
    var big = rows.length ? rows[rows.length - 1].d : null, r = big ? delta(ctx, d, big) : null;
    var cost = r ? (Math.abs(r.unit_cost_delta) < 0.005 ? "costs the same" : "costs about " + money(r.unit_cost_delta) + (r.unit_cost_delta > 0 ? " more" : " less")) : "";
    var bat = r ? (r.battery_class[0] !== r.battery_class[1] ? "moves the battery to " + SHORT[r.battery_class[1]] : Math.abs(r.life_days[1] / r.life_days[0] - 1) < 0.01 ? "barely changes the battery" : "changes battery life from " + life(r.life_days[0]) + " to " + life(r.life_days[1])) : "";
    var bigger = r ? "A bigger chip " + est(cost, "cost") + " and " + est(bat, "battery_life") + "." : "";
    if (run.case === "af") return "The one chip built and tested. " + bigger;
    if (!v.ev.chosen) return "No size clears your targets on this data; this is for the best design, " + P.fmt(d.gates) + " gates. " + bigger;
    return "The smallest chip that clears all your targets. " + bigger;
  }
  function innerHTML(run, v, P, ctx, d) {
    var rows = biggerOf(run, v, P, d);
    var b = batteryHTML(run, P, ctx, d);
    // cost against size first, full width (../i1-sizecost.js); the table stays as the fallback without it
    var SC = window.ChipInSizeCost, cost = SC ? SC.html(run, v, P, ctx, d, rows) : "";
    return '<div class="ws-h"><h2>Why this size</h2></div>' +
      '<p class="ws-lede">' + ledeText(run, v, P, ctx, d, rows) + "</p>" + cost +
      '<div class="ws-g ' + (cost ? "one" : "two") + '">' + (cost ? "" : costHTML(run, v, P, ctx, d, rows)) + b.html + "</div>" +
      '<p class="ws-p">Regulatory points to check with a regulatory specialist are in one place: <button type="button" class="ws-lk" data-ws-reg>the Regulation panel</button>.</p>';
  }

  function tick(el, run, v, P, ctx, openCost) {
    if (!el || !M() || !ctx) return;
    css();
    var d = ctx.chosen, on = !!(ctx.caseKind && d && d.gates > 0 && final(run, v, P));
    var band = document.getElementById("batBand");
    if (!on) {
      if (el.style.display !== "none") el.style.display = "none";
      if (band && el.contains(band)) el.after(band); // the band goes back under the funnel while the run plays
      el._sig = "";
      return;
    }
    if (!el.querySelector(".ws")) {
      var u = M().DEVICE_KINDS[ctx.caseKind].unit;
      el.innerHTML = '<section class="ws" aria-label="Why this size"><div class="ws-in"></div><details class="ws-d"><summary>Battery by ' + esc(u) + ": parts, sources and your wear time</summary><div class=\"ws-slot\"></div></details></section>";
      el.querySelector(".ws").addEventListener("click", function (e) {
        if (e.target.closest("[data-ws-cost]") && openCost) openCost();
        var rg = e.target.closest("[data-ws-reg]") && document.getElementById("regPanel");
        if (rg) rg.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
    var slot = el.querySelector(".ws-slot");
    if (band && !slot.contains(band)) slot.appendChild(band);
    el.style.display = "";
    var s = [run.id, d.id, d.gates, run.primary, v.ev.key, JSON.stringify(ctx.costInputs || null), (ctx.budgets || []).map(function (b) { return b.key; }).join(",")].join("|");
    if (el._sig === s) return;
    el._sig = s;
    el.querySelector(".ws-in").innerHTML = innerHTML(run, v, P, ctx, d);
  }
  window.ChipInWhySize = { tick: tick, biggerOf: biggerOf };
})();
