/*
 * i1-summary.js: the result page's lead for the ChipIn i1 dashboard. Defines window.ChipInSummary.
 *
 * 1. A plain summary card above the tiles, tinted green or red by its verdict: first why this size, in one
 *    sentence with the numbers that decided it (one step smaller misses what, bigger gains what at what unit
 *    cost) and a jump to the Why this size panel; then the chip, pass or fail naming the miss, the estimated
 *    unit cost, the estimated battery life and the main risk.
 * 2. The chart's default view: the frontier, the bar and the chosen chip only, a Show all designs toggle for
 *    the full cloud, and short labels on the smaller and bigger frontier points.
 *
 * Every cost and battery figure comes from window.ChipInModels (costModel, costDelta, deviceBudget,
 * batteryClass); this file only picks designs and words. Page helpers arrive in P (the page is a module):
 *   { metricOf, targetState, frontier, MET, fmt, fmtVal, fmtTarget, esc, caseOf, budgetLabel, isSim, isMea,
 *     mFile, panelKind, AF_DESIGN, MEASURED, afFinal, afScopeWord, about }
 * Shown only once a run's result is final; nothing here invents a figure: a line without data is left out.
 */
(function () {
  "use strict";
  var M = function () { return window.ChipInModels; };
  var CSS = [
    // the card is tinted by its verdict: green when the design clears every target, red when it misses one
    ".sm{position:relative;background:#fff;border:1px solid rgb(0 0 0/.07);border-left:4px solid var(--i300);border-radius:14px;box-shadow:var(--sh-hair);padding:12px 0 12px}",
    ".sm.ok{background:#f3faf6;border-color:#cfe9db;border-left-color:#0f7a55}",
    ".sm.no{background:#fdf6f4;border-color:#f2d6d0;border-left-color:#c2362b}",
    ".sm-r{margin:0 16px 11px;padding-bottom:10px;border-bottom:1px solid rgb(0 0 0/.08);font-size:14px;color:var(--i800);line-height:1.5}",
    ".sm-r>b{color:var(--i900);font-weight:700}",
    ".sm.ok .sm-r>b{color:#0b5a3f}.sm.no .sm-r>b{color:#9f2a20}",
    ".sm-jump{display:inline-flex;align-items:center;gap:4px;margin-left:4px;font-size:13px;font-weight:600;color:var(--blue7);text-decoration:underline;text-underline-offset:3px;white-space:nowrap}",
    ".sm-jump::after{content:'\\2193'}",
    ".sm-mt{border:0;background:none;padding:0;margin-left:6px;font:inherit;font-size:13px;font-weight:600;color:var(--i700);cursor:pointer;text-decoration:underline dotted;text-underline-offset:3px;white-space:nowrap}",
    ".sm-g{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.6fr) minmax(0,.8fr) minmax(0,1fr) minmax(0,1.4fr);row-gap:10px}",
    "@media (min-width:641px){.sm-c.tg .sm-v{flex-wrap:nowrap;white-space:nowrap}}",
    ".sm-c{padding:0 16px;border-left:1px solid rgb(0 0 0/.08);min-width:0}",
    ".sm-c:first-child{border-left:0}",
    "@media (max-width:1100px){.sm-g{grid-template-columns:repeat(3,minmax(0,1fr))}.sm-c:nth-child(4){border-left:0}.sm-c.risk{grid-column:span 2}}",
    ".sm-l{display:block;font-size:12px;font-weight:600;color:var(--i700);line-height:1.35;margin-bottom:3px}",
    ".sm-v{font-size:20px;font-weight:650;color:var(--i900);line-height:1.25;display:flex;gap:6px;align-items:baseline;flex-wrap:wrap;font-variant-numeric:tabular-nums}",
    ".sm-c.chip .sm-v{color:var(--blue7)}",
    ".sm-v .pf{font-size:12.5px;padding:2px 10px;align-self:center}",
    ".sm-v small{font-size:12.5px;font-weight:500;color:var(--i700)}",
    ".sm-c.risk .sm-v,.sm-c.tg .sm-v{font-weight:500;font-size:14px;line-height:1.4}",
    ".sm-tog{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;color:var(--i700);cursor:pointer;white-space:nowrap}",
    ".sm-tog input{margin:0;accent-color:var(--blue7)}",
    "@media (max-width:640px){.sm-g{grid-template-columns:repeat(2,minmax(0,1fr))}.sm-c:nth-child(4){border-left:1px solid var(--hair)}.sm-c:nth-child(odd){border-left:0}.sm-c.risk{grid-column:1/-1}}",
  ].join("\n");
  function css() {
    if (document.getElementById("sm-styles")) return;
    var s = document.createElement("style"); s.id = "sm-styles"; s.textContent = CSS; document.head.appendChild(s);
  }
  function money(x) { return "$" + Math.abs(x).toFixed(2); }
  function life(days) { return days >= 2 ? Math.round(days).toLocaleString("en-GB") + " days" : (days * 24).toFixed(1) + " hours"; }

  // the run's result is on screen for good: the replay has finished, or the run is a measured file
  function final(run, v, P) {
    if (run.case === "af" && P.MEASURED.af) return P.afFinal(v);
    return !!(v.done || P.isMea(run));
  }
  // the design the card is about: the chosen chip, the AF circuit really built, else the best or nearest design
  function focusOf(run, v, P) {
    if (run.case === "af") return P.AF_DESIGN;
    return v.ev.chosen || v.ev.nearest[0] || null;
  }

  /* -------------------------------------------------------- battery and cost, all from ChipInModels */
  function designFor(kind, d) { return { gates: d.gates, channels: d.channels, sensors: d.sensors || d.channels, kind: kind, decisionsPerSecond: 1 }; }
  function batteryOf(kind, d) {
    var b = M().deviceBudget({ kind: kind, channels: d.channels, sensors: d.sensors || d.channels, gates: d.gates, decisionsPerSecond: 1 });
    return { budget: b, cls: M().batteryClass(b.total_uw) };
  }
  function unitCost(kind, d, inputs) {
    var o = {}, k;
    for (k in inputs || {}) o[k] = inputs[k];
    o.gates = d.gates;
    if (!o.battery_class) o.battery_class = batteryOf(kind, d).cls.class;
    return M().costModel(o).unit_cost;
  }
  function est(txt, field) { return '<span class="est" title="' + String(M().describeEstimate(field)).replace(/"/g, "&quot;") + '">' + txt + "</span>"; }
  function batteryText(bt) {
    var c = bt.cls;
    if (c.class === "primary coin cell") return { v: life(c.life_days), s: "on a coin cell" };
    if (c.class === "rechargeable lithium") return { v: life(c.life_days), s: "per charge, rechargeable" };
    return { v: "Larger pack", s: "or mains" };
  }

  /* ------------------------------------------------------------------- smaller and bigger designs */
  // on the chosen chip's own frontier (its channel budget, the run's judging rule): the next smaller frontier
  // point, which misses a target because the chosen chip is the smallest that clears them all, and the frontier
  // point nearest twice the chosen size above it
  function sides(run, v, P) {
    var ch = v.ev.chosen; if (!ch || run.case === "af") return null;
    var f = (v.ev.fronts || []).find(function (x) { return x.b.ch === ch.channels; });
    var pts = f ? f.pts : [];
    var smaller = null, bigger = null;
    pts.forEach(function (d) { if (d.gates < ch.gates && (!smaller || d.gates > smaller.gates)) smaller = d; });
    var up = pts.filter(function (d) { return d.gates > ch.gates; });
    if (up.length) bigger = up.reduce(function (a, d) { return Math.abs(Math.log(d.gates / (2 * ch.gates))) < Math.abs(Math.log(a.gates / (2 * ch.gates))) ? d : a; });
    var key = run.primary, mk = P.MET[key];
    var gain = bigger ? P.metricOf(run, bigger, key).v - P.metricOf(run, ch, key).v : null;
    var misses = smaller ? P.targetState(run, smaller).filter(function (s) { return s.ok !== true; }) : [];
    return { ch: ch, smaller: smaller, bigger: bigger, gain: gain, misses: misses, key: key, frac: mk.kind === "frac" };
  }
  function gainWords(run, S, P) {
    var g = S.gain, name = P.MET[S.key].name.toLowerCase();
    if (S.frac) return Math.abs(g) < 0.0005 ? "adds nothing to " + name : (g > 0 ? "adds " : "loses ") + (Math.abs(g) * 100).toFixed(1) + " points of " + name;
    return "moves " + name + " from " + P.fmtVal(S.key, P.metricOf(run, S.ch, S.key).v) + " to " + P.fmtVal(S.key, P.metricOf(run, S.bigger, S.key).v);
  }
  // the chart's short labels for the smaller and bigger points
  function marks(run, v, P) {
    var S = sides(run, v, P); if (!S) return [];
    var out = [];
    if (S.smaller && S.misses.length) out.push({ d: S.smaller, txt: "Smaller, fails your target", short: "Smaller: fails", col: "#9f2a20" });
    if (S.bigger && S.gain != null) {
      var little = S.frac ? S.gain < 0.02 : false;
      var txt = little ? "Bigger, little gain" : S.frac ? "Bigger: +" + (S.gain * 100).toFixed(1) + " points" : "Bigger";
      out.push({ d: S.bigger, txt: txt, short: little ? "Bigger: little gain" : txt, col: "#3a4052" });
    }
    return out;
  }

  /* ------------------------------------------------------------------------------- the card */
  function cardHTML(run, v, P) {
    if (!run.targets.length || !final(run, v, P)) return "";
    var d = focusOf(run, v, P); if (!d || !(d.gates > 0)) return "";
    var c = P.caseOf(run), kind = P.panelKind(run), af = run.case === "af", e = P.esc;
    var st = P.targetState(run, d), miss = st.filter(function (s) { return s.ok === false; }), pass = af ? st.every(function (s) { return s.ok === true; }) : !!v.ev.chosen; // AF: the built circuit's own test figures, never the replay's choice
    var cells = [];
    // 1. the chip
    var lab = af ? "Chip built and tested" : pass ? "Recommended chip" : "Best design";
    cells.push(cell(lab, P.fmt(d.gates) + " <small>gates</small>", "chip"));
    // 2. pass or fail, naming the miss
    var verdict;
    if (pass) verdict = '<span class="pf ok">Passes all your targets</span>';
    else if (miss.length === 1) verdict = '<span class="pf no">Fails ' + e(shortName(P, miss[0].t.metric)) + "</span> " + e(P.fmtVal(miss[0].t.metric, miss[0].v)) + " <small>target " + e(P.fmtTarget(miss[0].t).replace(/^at (least|most) /, "")) + "</small>";
    else if (miss.length) verdict = '<span class="pf no">Fails</span> ' + e(andList(miss.map(function (s) { return shortName(P, s.t.metric); })));
    else verdict = '<span class="pf na">Not measured</span>';
    cells.push(cell("Your targets", verdict, "tg"));
    // 3 and 4. estimated cost and battery, from ChipInModels; absent for a device the power model does not cover
    if (kind) {
      var bt = batteryOf(kind, d);
      cells.push(cell("Estimated cost", est(money(unitCost(kind, d, run.costInputs)), "cost") + " <small>per unit</small>"));
      var bx = batteryText(bt);
      cells.push(cell("Estimated battery", est(e(bx.v), "battery_life") + " <small>" + e(bx.s) + "</small>"));
    }
    // 5. the main risk, stated where it stands
    var risk = riskText(run, v, P, d, pass);
    if (risk) cells.push(cell("Main risk", e(risk.charAt(0).toUpperCase() + risk.slice(1)), "risk"));
    var mark = af || P.isMea(run) ? '<span class="mk mea" style="position:absolute;right:12px;top:-9px">measured</span>' : '<span class="mk sim" style="position:absolute;right:12px;top:-9px">simulated</span>';
    // why this size, first: one sentence with the numbers that decided it, and a jump to the panel
    var t = tradeText(run, v, P, d, kind);
    var why = '<p class="sm-r"><b>Why ' + P.fmt(d.gates) + " gates:</b> " + reasonLead(run, v, P, d, pass) + (t ? ' <span class="sm-more" hidden>' + t + '</span><button type="button" class="sm-mt" data-sm-more aria-expanded="false">' + (run.case === "af" ? "Why not bigger" : "Smaller and bigger") + "</button>" : "") +
      (kind ? ' <button type="button" class="sm-jump" data-ws-jump>Cost by size</button>' : "") + "</p>";
    return '<section class="sm ' + (pass ? "ok" : "no") + '" aria-label="Summary">' + mark + why + '<div class="sm-g">' + cells.join("") + "</div></section>";
  }
  // the first clause of the reason: what kind of choice this design is
  function reasonLead(run, v, P, d, pass) {
    if (run.case === "af") return "the one circuit built and checked bit for bit.";
    if (pass) return "the smallest design that clears all your targets.";
    return "no size clears your bar on this data, so this is the best that could be built.";
  }
  function cell(label, val, cls) { return '<div class="sm-c' + (cls ? " " + cls : "") + '"><span class="sm-l">' + label + '</span><span class="sm-v">' + val + "</span></div>"; }
  function shortName(P, k) { return (P.MET[k].short || P.MET[k].name).toLowerCase(); }
  function andList(a) { return a.length < 2 ? (a[0] || "") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]; }

  // passing chip: the target it clears by the least, on its worst patient when the rule says so;
  // failing measured file: its worst held-out patient; AF: the test recordings with AF it misses
  function riskText(run, v, P, d, pass) {
    var c = P.caseOf(run);
    if (run.case === "af") {
      var n = d.counts && d.counts.events_total, s = d.metrics.sensitivity_pooled;
      if (!(n > 0) || s == null) return "";
      var k = n * (1 - s);
      if (Math.abs(k - Math.round(k)) > 0.02) return "";
      return "misses " + Math.round(k) + " of " + n + " test recordings with AF.";
    }
    if (pass) {
      var st = P.targetState(run, d).filter(function (x) { return x.ok === true; });
      if (!st.length) return "";
      var norm = function (x) { return P.MET[x.t.metric].kind === "frac" ? Math.abs(x.v - x.t.value) / 0.05 : Math.abs(x.v - x.t.value) / Math.max(0.5, x.t.value); };
      var thin = st.reduce(function (a, x) { return norm(x) < norm(a) ? x : a; });
      var f = P.metricOf(run, d, thin.t.metric).f, who = "";
      if (f && /_worst$/.test(f) && (d.per_patient || []).length) {
        var p = (d.per_patient || []).find(function (q) {
          var val = /^sensitivity/.test(f) ? (q.total > 0 ? q.caught / q.total : null) : /^false_alarms/.test(f) ? (q.hours > 0 ? q.false_alarms / q.hours : null) : /^specificity/.test(f) ? (q.neg_total > 0 ? q.neg_correct / q.neg_total : null) : null;
          return val != null && Math.abs(val - thin.v) < 1e-9;
        });
        who = p ? (c.Who || "Patient") + " " + p.id + " is the weakest: " : "the worst " + c.who + ": ";
      }
      return (who || "thinnest margin: ") + shortName(P, thin.t.metric) + " " + P.fmtVal(thin.t.metric, thin.v) + ", target " + P.fmtTarget(thin.t).replace(/^at (least|most) /, "") + ".";
    }
    if (d.metrics.sensitivity_worst != null) return "on the worst held-out " + c.who + ", " + P.fmtVal("sensitivity", d.metrics.sensitivity_worst) + " of " + c.events + " caught.";
    var m = P.targetState(run, d).find(function (x) { return x.ok === false; });
    return m ? P.MET[m.t.metric].name.toLowerCase() + " " + P.fmtVal(m.t.metric, m.v) + ", target " + P.fmtTarget(m.t) + "." : "";
  }

  // one sentence on the trade-off, from the run's own designs
  function tradeText(run, v, P, d, kind) {
    var e = P.esc, c = P.caseOf(run);
    if (run.case === "af") {
      var F = P.MEASURED.af, B = F && F.bestD, C = F && F.chosenD;
      if (!B || !C || B.metrics.sensitivity_pooled == null || C.metrics.sensitivity_pooled == null) return "";
      var w = P.afScopeWord(F.scope);
      var lower = B.metrics.sensitivity_pooled < C.metrics.sensitivity_pooled;
      var big = '<span class="est" title="' + e(P.sizeTip()) + '">about ' + P.about(B.est) + " gates</span>";
      return "Going bigger is " + (lower ? "not the fix" : "untested") + ": the best candidate by validation F1, " + big + ", was too large to build" +
        (lower ? " and caught fewer AF windows (" + P.fmtVal("sensitivity", B.metrics.sensitivity_pooled) + " against " + P.fmtVal("sensitivity", C.metrics.sensitivity_pooled) + ", validation, " + e(w) + ")." : ".");
    }
    var costWords = function (a, b) {
      if (!kind) return "";
      var inputs = {}, k; for (k in run.costInputs || {}) inputs[k] = run.costInputs[k]; inputs.kind = kind;
      var dc = M().costDelta(designFor(kind, a), designFor(kind, b), inputs).unit_cost_delta;
      return Math.abs(dc) < 0.005 ? " at " + est("the same unit cost", "cost") : " for " + est("about " + money(dc) + (dc > 0 ? " more" : " less") + " per unit", "cost");
    };
    if (!v.ev.chosen) {
      var parts0 = [];
      if (d.counts && d.counts.events_total) parts0.push("It catches " + P.fmt(d.counts.events_caught) + " of " + P.fmt(d.counts.events_total) + " " + e(c.events) + ", all " + e(c.whoP) + " pooled.");
      // why bigger did not help: the bigger designs at the same channel count scored lower
      var key = run.primary, rr = P.mFile(run) ? Object.assign({}, run, { judge: "pooled" }) : run;
      var up = (v.vis || []).filter(function (x) { return x.gates > d.gates && x.channels === d.channels && x.role !== "baseline" && P.metricOf(rr, x, key).v != null; });
      if (up.length && P.metricOf(rr, d, key).v != null) {
        var top = up.reduce(function (a, x) { return P.metricOf(rr, x, key).v > P.metricOf(rr, a, key).v ? x : a; });
        var big = up.reduce(function (a, x) { return x.gates > a.gates ? x : a; });
        var tv = P.metricOf(rr, top, key).v, dv = P.metricOf(rr, d, key).v;
        if (tv <= dv) parts0.push("Bigger designs, up to " + P.fmt(big.gates) + " gates, scored lower (" + e(P.fmtVal(key, tv)) + " at best)" + costWords(d, big) + ".");
      }
      return parts0.join(" ");
    }
    var S = sides(run, v, P); if (!S) return "";
    var parts = [];
    if (S.smaller && S.misses.length) parts.push("One step smaller, " + P.fmt(S.smaller.gates) + " gates, misses " + e(andList(S.misses.map(function (s) { return shortName(P, s.t.metric) + (s.v != null ? " (" + P.fmtVal(s.t.metric, s.v) + ", target " + P.fmtTarget(s.t).replace(/^at (least|most) /, "") + ")" : ""); }))) + ".");
    if (S.bigger && S.gain != null) parts.push("Bigger, " + P.fmt(S.bigger.gates) + " gates, " + e(gainWords(run, S, P)) + costWords(S.ch, S.bigger) + ".");
    return parts.join(" ");
  }

  /* ------------------------------------------------------------------------- the chart's default */
  // the default view applies once the result is final; the toggle shows the full cloud
  function canSimplify(run, v, P) {
    if (run.case === "af") return !!P.MEASURED.af && final(run, v, P) && v.vis.length > 0; // without its file the AF run is one design
    return final(run, v, P) && v.vis.length > 0 && !!focusOf(run, v, P);
  }
  function simple(run, v, P) { return !run.ui.all && canSimplify(run, v, P); }
  // the designs drawn in the default view; key is the chart's metric, rr the run as the chart scores it
  function keep(run, v, P, rr, key) {
    var ids = new Set(), add = function (d) { if (d) ids.add(d.id); };
    if (run.case === "af") {
      P.frontier(rr, v.vis, key).forEach(add);
      add(P.MEASURED.af.chosenD); add(P.MEASURED.af.bestD);
    } else {
      var f = focusOf(run, v, P);
      P.frontier(rr, v.vis.filter(function (d) { return d.gates > 0 && d.role !== "baseline" && d.channels === f.channels; }), key).forEach(add);
      add(v.ev.chosen); (v.ev.chosen ? [] : v.ev.nearest).forEach(add);
      marks(run, v, P).forEach(function (m) { add(m.d); });
    }
    if (run.ui.sel) ids.add(run.ui.sel);
    return ids;
  }
  function toggleHTML(run, v, P) {
    if (!canSimplify(run, v, P)) return "";
    return '<label class="sm-tog"><input type="checkbox" id="allTog"' + (run.ui.all ? " checked" : "") + "> Show all designs</label>";
  }
  function legendHTML(run, v, P) {
    if (!simple(run, v, P)) return null;
    var line = function (col, dash) { return '<svg viewBox="0 0 14 14"><path d="' + (dash ? "M0 7h14" : "M1 12 5 7l4-2 4-4") + '" stroke="' + col + '" stroke-width="1.6" fill="none"' + (dash ? ' stroke-dasharray="3 2.5"' : "") + "/></svg>"; };
    var ring = '<svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.6" fill="none" stroke="#141a2e" stroke-width="1.8"/></svg>';
    if (run.case === "af") {
      var dot = function (c, fill) { return '<svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.2" fill="' + fill + '" stroke="' + c + '" stroke-width="1.5"/></svg>'; };
      return "<span>" + line("#4a5062") + "Frontier: best validation score at each size</span><span>" + dot("#2b55d0", "rgb(43 85 208 / .12)") + "Hollow: estimated size</span><span>" + dot("#141a2e", "#141a2e") + "Solid: measured size</span>";
    }
    var f = focusOf(run, v, P);
    return "<span>" + line("#4a5062") + "Frontier, " + P.esc(P.budgetLabel(run, f.channels).toLowerCase()) + ": smallest chip at each level</span><span>" + line("#141a2e", true) + "Your bar</span><span>" + ring + (v.ev.chosen ? "Chosen" : "Best so far") + "</span>";
  }
  // places each label beside its point where it covers no placed box and stays in the plot
  function drawMarks(g, items, o) {
    var placed = o.boxes.slice();
    g.save(); g.font = "700 12px Inter, system-ui, -apple-system, sans-serif"; g.textAlign = "left";
    items.forEach(function (m) {
      var p = m.p; if (!p) return;
      var txt = o.narrow ? m.short : m.txt, tw = g.measureText(txt).width;
      var cands = [[p.x + 12, p.y + 22], [p.x - 12 - tw, p.y + 22], [p.x + 12, p.y - 14], [p.x - 12 - tw, p.y - 14], [p.x - tw / 2, p.y + 34], [p.x - tw / 2, p.y - 26], [p.x + 12, p.y + 40], [p.x - 12 - tw, p.y + 40]];
      var score = function (c) {
        var b = { l: c[0] - 4, r: c[0] + tw + 4, t: c[1] - 13, b: c[1] + 5 };
        var s = placed.some(function (q) { return b.l < q.r && q.l < b.r && b.t < q.b && q.t < b.b; }) ? 1000 : 0;
        if (b.l < o.x0 - 30 || b.r > o.W - 2 || b.t < o.y0 + 2 || b.b > o.y1 - 2) s += 500;
        return { s: s, b: b, c: c };
      };
      var best = cands.map(score).reduce(function (a, x) { return x.s < a.s ? x : a; });
      placed.push(best.b);
      var cx = Math.max(best.b.l, Math.min(p.x, best.b.r)), cy = Math.max(best.b.t, Math.min(p.y, best.b.b));
      g.strokeStyle = m.col; g.lineWidth = 1; g.beginPath(); g.moveTo(p.x + Math.sign(cx - p.x) * 5, p.y + Math.sign(cy - p.y) * 5); g.lineTo(cx, cy); g.stroke();
      g.fillStyle = "rgb(255 255 255 / .92)"; g.fillRect(best.b.l, best.b.t, best.b.r - best.b.l, best.b.b - best.b.t);
      g.fillStyle = m.col; g.fillText(txt, best.c[0], best.c[1]);
    });
    g.restore();
  }
  // the card host: re-rendered when the result, the selection or the cost inputs change
  function tick(el, run, v, P, sig) {
    if (!el) return;
    css();
    var s = sig + "|" + JSON.stringify(run.costInputs || null) + "|" + final(run, v, P);
    if (el._sig === s) return;
    el._sig = s;
    var h = cardHTML(run, v, P);
    el.innerHTML = h; el.style.display = h ? "" : "none";
    if (!el._jump) {
      el._jump = true;
      el.addEventListener("click", function (e) {
        var mt = e.target.closest("[data-sm-more]");
        if (mt) { var sp = el.querySelector(".sm-more"), on = sp.hidden; sp.hidden = !on; mt.setAttribute("aria-expanded", String(on)); if (!mt.dataset.l) mt.dataset.l = mt.textContent; mt.textContent = on ? "Less" : mt.dataset.l; return; }
        if (!e.target.closest("[data-ws-jump]")) return;
        var ws = document.getElementById("whySize");
        if (ws && ws.style.display !== "none") ws.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }
  window.ChipInSummary = { tick: tick, cardHTML: cardHTML, marks: marks, simple: simple, keep: keep, toggleHTML: toggleHTML, legendHTML: legendHTML, drawMarks: drawMarks, css: css };
})();
