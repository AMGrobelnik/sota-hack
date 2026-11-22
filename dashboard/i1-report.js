/*
 * i1-report.js: the extras of the ChipIn i1 dashboard. Defines window.ChipInReport.
 *
 *   Assumptions and limits  a link always in the run's top bar: data source, simulated or measured, how the
 *                           data is split, what a design is judged on, and the run's own limits (from its file);
 *   design report           a one-page, print-styled view of the result (spec, chip, results, estimated cost
 *                           and battery, verification, assumptions) the browser can print or save as PDF;
 *   compare                 two designs side by side, from the inspector: the selected design and the chosen one.
 * Every power, battery and cost figure comes from window.ChipInModels; every other figure is the run's own.
 * The page hands one getter to bind(): () => { run, v, P, ctx, openModal, closeModal, toast, openCost }, with
 * P the page helpers (the summary module's, plus scopeText, noFileRefs, selDesign, afSize, badgeText, afFile).
 */
(function () {
  "use strict";
  var M = function () { return window.ChipInModels; };
  var get = null;
  var CSS = [
    ".rp-lim{gap:5px}.rp-lim .s{display:none}",
    "@media (max-width:767px){.rp-lim .l{display:none}.rp-lim .s{display:inline}}",
    ".rp-m{width:min(560px,100%)!important}.rp-m.w{width:min(680px,100%)!important}",
    ".rp-m h3{margin-right:34px}",
    ".rp-f{margin:10px 0 0}.rp-f>div{display:grid;grid-template-columns:118px minmax(0,1fr);gap:12px;padding:8px 0;border-top:1px solid var(--hair);font-size:13px;line-height:1.5;color:var(--i800)}",
    ".rp-f>div>span:first-child{color:var(--i600);font-size:12.5px}",
    ".rp-f .mk{white-space:normal;max-width:100%}.rp-f a{color:var(--blue7)}.rp-f ul{margin:0;padding-left:16px}.rp-f li+li{margin-top:2px}",
    ".rp-f details summary{cursor:pointer;color:var(--blue7);font-size:12.5px;font-weight:600;width:fit-content}",
    ".rp-f details p{margin:4px 0 0;font-size:12.5px}",
    ".rp-acts{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;margin-top:14px}",
    "@media (max-width:480px){.rp-f>div{grid-template-columns:1fr;gap:2px}}",
    ".rp-c{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums;margin-top:8px}",
    ".rp-c th,.rp-c td{padding:6px 0 6px 10px;border-top:1px solid var(--hair);text-align:right;vertical-align:baseline}",
    ".rp-c th:first-child,.rp-c td:first-child{text-align:left;padding-left:0;color:var(--i600);font-weight:400}",
    ".rp-c thead th{border-top:0;color:var(--i900);font-weight:650;font-size:13px}",
    ".rp-c td b{font-weight:600;color:var(--i900)}.rp-c .pf{margin-left:6px}.rp-c .mk{margin-left:4px}",
    ".rp-c td.dim{color:var(--i600)}",
    ".rp-n{font-size:12.5px!important;margin:10px 0 0}",
    ".ilinks .rp-cmp{cursor:pointer}",
    /* the report view: on screen a sheet over the app, in print the sheet alone */
    "#rpView{position:fixed;inset:0;z-index:95;background:var(--i150);overflow:auto;padding:0 12px 40px}",
    ".rp-bar{position:sticky;top:0;z-index:1;display:flex;gap:8px;align-items:center;justify-content:flex-end;max-width:794px;margin:0 auto;padding:12px 0}",
    ".rp-bar span{margin-right:auto;font-size:12.5px;color:var(--i700)}",
    ".rp-sh{max-width:794px;margin:0 auto;background:#fff;border-radius:6px;box-shadow:0 4px 24px rgb(0 0 0/.08);padding:34px 40px 28px;color:var(--i900);font-size:12.5px;line-height:1.45}",
    ".rp-sh h1{font-size:20px;margin:0;font-weight:650}",
    ".rp-sh .sub{margin:3px 0 0;color:var(--i600);display:flex;gap:8px;flex-wrap:wrap;align-items:center}",
    ".rp-sh h2{font-size:12px;font-weight:650;text-transform:uppercase;letter-spacing:.04em;color:var(--i600);margin:16px 0 4px;display:flex;gap:8px;align-items:center}",
    ".rp-sh h2 .mk{text-transform:none;letter-spacing:0}",
    ".rp-v{font-size:15px;font-weight:600;margin:12px 0 0;padding:10px 12px;border-radius:8px;background:var(--i100)}",
    ".rp-v .pf{margin-left:8px;vertical-align:1px;white-space:normal}",
    ".rp-sh .rp-f{margin:0}.rp-sh .rp-f>div{font-size:inherit;padding:5px 0;grid-template-columns:150px minmax(0,1fr)}.rp-sh .rp-f>div>span:first-child{font-size:inherit}",
    ".rp-two{display:grid;grid-template-columns:1fr 1fr;gap:0 28px}",
    ".rp-kv{display:flex;justify-content:space-between;gap:12px;padding:4px 0;border-top:1px solid var(--hair)}",
    ".rp-kv>span:first-child{color:var(--i600)}.rp-kv>span:last-child{text-align:right;font-variant-numeric:tabular-nums}",
    ".rp-kv .pf{margin-left:6px}",
    ".rp-ul{margin:0;padding-left:16px}.rp-ul li{margin:2px 0}",
    ".rp-sh a{color:var(--blue7)}",
    ".rp-foot{margin-top:16px;padding-top:8px;border-top:1px solid var(--hair);color:var(--i600);font-size:11px}",
    "@media (max-width:640px){.rp-sh{padding:20px 16px}.rp-two{grid-template-columns:1fr}.rp-bar span{display:none}}",
    "@media print{@page{size:A4;margin:12mm}html,body{background:#fff!important;height:auto!important;min-height:0!important;overflow:visible!important}body>*:not(#rpView){display:none!important}#rpView{position:static;inset:auto;overflow:visible;background:#fff;padding:0}.rp-bar{display:none}.rp-sh{box-shadow:none;max-width:none;padding:0;border-radius:0;font-size:10.5px}.rp-sh h1{font-size:17px}.rp-v{font-size:13px}.rp-sh *{-webkit-print-color-adjust:exact;print-color-adjust:exact}}",
  ].join("\n");
  function css() {
    if (document.getElementById("rp-styles")) return;
    var s = document.createElement("style"); s.id = "rp-styles"; s.textContent = CSS; document.head.appendChild(s);
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function money(x) { return "$" + Math.abs(x).toFixed(2); }
  function life(days) { return days >= 2 ? Math.round(days).toLocaleString("en-GB") + " days" : (days * 24).toFixed(1) + " hours"; }
  function share(x) { var v = x * 100; return (v < 0.01 ? v.toPrecision(2) : v < 1 ? v.toFixed(3) : v.toFixed(1)) + "%"; }
  function est(txt, field) { return '<span class="est" title="' + esc(M().describeEstimate(field)) + '">' + txt + "</span>"; }
  var MK = function (cls, t) { return '<span class="mk ' + cls + '">' + t + "</span>"; };
  function srcMk(d) { return d && d.source === "measured" ? MK("mea", "measured") : MK("sim", "simulated"); }
  function runMk(run, P) { return P.isSim(run) ? MK("sim", "simulated") : MK("mea", "measured"); }
  function andList(a) { return a.length < 2 ? (a[0] || "") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]; }
  function firstSentence(t) { var m = String(t || "").match(/^.*?\.(?=\s|$)/); return m ? m[0] : String(t || ""); }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

  function final(run, v, P) {
    if (run.case === "af" && P.MEASURED.af) return P.afFinal(v);
    return !!(v.done || P.isMea(run));
  }

  /* ------------------------------------------------------------ cost and battery, from ChipInModels */
  function count(d) { return d.sensors || d.channels || 1; }
  function budgetOf(kind, d, gates) { return M().deviceBudget({ kind: kind, channels: d.channels || 1, sensors: count(d), gates: gates, decisionsPerSecond: 1 }); }
  function costOf(ctx, d, gates) {
    var b = budgetOf(ctx.caseKind, d, gates), m = {}, k;
    for (k in ctx.costInputs || {}) m[k] = ctx.costInputs[k];
    m.gates = gates; if (!m.battery_class) m.battery_class = M().batteryClass(b.total_uw).class;
    return M().costModel(m).unit_cost;
  }
  function batteryWords(kind, d, gates) {
    var b = budgetOf(kind, d, gates), c = M().batteryClass(b.total_uw);
    var txt = c.class === "primary coin cell" ? est(life(c.life_days), "battery_life") + " on a coin cell" : c.class === "rechargeable lithium" ? est(life(c.life_days), "battery_life") + " per charge, rechargeable" : est("larger pack or mains", "battery_class");
    return { txt: txt, b: b, c: c };
  }

  /* ------------------------------------------------------------------- assumptions and limits */
  function facts(run, v, P) {
    var c = P.caseOf(run), F = P.afFile(run) && P.MEASURED.af, file = P.mFile(run) && P.MEASURED.eeg && run.case === "neonatal-eeg" ? P.MEASURED.eeg : null;
    var nf = P.noFileRefs, out = {};
    // data source: only the datasets the run's own file names
    if (F && F.dataset) {
      var ds = F.dataset;
      out.data = link(ds.url, ds.name) + (ds.recordings ? ", " + P.fmt(ds.recordings) + " recordings" : "") + ". " + MK("no", link(ds.licence_url, ds.licence));
    } else if (file && (file.datasets || []).length) {
      out.data = file.datasets.map(function (x) { return link(x.url, x.name) + (typeof x.subjects === "number" ? ", " + P.fmt(x.subjects) + " " + esc(c.whoP) : x.subjects ? ", " + esc(x.subjects) : "") + ". " + MK("no", link(x.licence_url, x.licence)); }).join("<br>");
    } else if (run.case === "af") {
      out.data = "PhysioNet/Computing in Cardiology Challenge 2017.";
    } else {
      out.data = "None: simulated " + esc(c.whoP) + ", demo data. No recording was used.";
    }
    // simulated or measured, and what is estimated
    var what;
    if (run.case === "af") what = F ? "Measured: the compiled design's gate count, test scores and bit-exact check. Candidate scores are measured on validation recordings; their sizes are " + est("estimated", "area") + "." : "Measured: one compiled circuit, its gate count, test scores and bit-exact check.";
    else if (file) what = "Measured: every design's gate count and scores on held-out " + esc(c.whoP) + ".";
    else what = "Simulated: every design and every score.";
    out.what = what + " Cost and battery are " + est("estimated", "cost") + " from editable assumptions.";
    // the split
    var split = nf(F && F.split ? F.split : file && file.split ? file.split : c.split || "");
    if (run.case === "af" && F && F.dataset && F.dataset.test_recordings) out.split = "By recording: " + P.fmt(F.dataset.test_recordings) + " test recordings, " + P.fmt(F.dataset.test_positive) + " with AF, never used for training or selection.";
    else if (run.case === "af") out.split = "By recording: " + P.fmt(P.AF_DESIGN.counts.patients) + " test recordings, never used for training.";
    else if (file) { var h = split.match(/(\d+) held out/); out.split = h ? "By " + esc(c.who) + ": " + h[1] + " held-out " + esc(c.whoP) + ", never used for training, thresholds or selection." : esc(firstSentence(split)); }
    else out.split = "By " + esc(c.who) + ": " + (c.N || 12) + " simulated " + esc(c.whoP) + " held out; no design trains on them.";
    out.splitFull = (file || F) && split ? esc(split) : "";
    // what a design is judged on
    if (run.case === "af") out.judge = "Per recording, all test recordings pooled. No per-patient results in this run.";
    else if (run.judge === "pooled") out.judge = "All held-out " + esc(c.whoP) + " pooled.";
    else {
      out.judge = "The worst held-out " + esc(c.who) + ": a chip passes only if it clears every target on that " + esc(c.who) + ".";
      var q = file && (file.notes || []).map(function (n) { return n.match(/(\d+) of (\d+) held-out (\w+) qualify/); }).filter(Boolean)[0];
      if (q) out.judge += " " + q[1] + " of " + q[2] + " held-out " + esc(q[3]) + " have enough events to count.";
    }
    // the run's own limits, from its file
    var notes = (F && F.notes) || (file && file.notes) || [];
    var pick = function (re) { var n = notes.find(function (x) { return re.test(x); }); return n ? esc(firstSentence(nf(n))) : null; };
    var lim = [];
    if (run.case === "af") lim = [pick(/one feasibility spike/i), pick(/not a real cell library/i), pick(/example targets/i)];
    else if (file) lim = [pick(/not clinical evidence/i), pick(/classifier only/i)];
    else lim = ["Demo data: no real " + esc(c.who) + " was recorded."];
    lim.push("Regulatory points on the page are general information from the cited sources, not regulatory advice: check every point with a regulatory specialist.");
    out.limits = lim.filter(Boolean);
    return out;
  }
  function link(url, text) { return url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(text) + "</a>" : esc(text); }
  function factsHTML(f) {
    return '<div class="rp-f">' +
      row("Data", f.data) + row("Measured or simulated", f.what) +
      row("Split", f.split + (f.splitFull ? '<details><summary>Full split</summary><p>' + f.splitFull + "</p></details>" : "")) +
      row("Judged on", f.judge) + row("Limits", "<ul>" + f.limits.map(function (x) { return "<li>" + x + "</li>"; }).join("") + "</ul>") + "</div>";
  }
  function row(k, v) { return "<div><span>" + k + "</span><span>" + v + "</span></div>"; }
  function limits() {
    if (!get) return;
    var g = get(); css();
    var bg = g.openModal('<h3>Assumptions and limits</h3>' + factsHTML(facts(g.run, g.v, g.P)) + (g.P.srcMoved ? g.P.srcMoved(g.run) : "") /* SOURCES HOOK: the notes moved from the Sources tab */ +
      '<div class="rp-acts"><button class="btn s" data-rp-report>Design report</button><button class="btn p" data-close>Close</button></div>',
      function (e) { if (e.target.closest("[data-rp-report]")) { g.closeModal(); report(); } });
    bg.querySelector(".modal").classList.add("rp-m");
  }
  function linkHTML() {
    css();
    return '<button class="cpill rp-lim" data-rp-lim title="Data source, simulated or measured, split, how designs are judged"><span class="l">Assumptions and limits</span><span class="s">Limits</span></button>';
  }

  /* ------------------------------------------------------------------------------- the report */
  function verdictOf(run, v, P, d) {
    var af = run.case === "af", st = P.targetState(run, d), miss = st.filter(function (s) { return s.ok === false; });
    var pass = af ? st.length > 0 && st.every(function (s) { return s.ok === true; }) : !!v.ev.chosen;
    var lab = af ? "Chip compiled and tested" : pass ? "Recommended chip" : "Best design, no size clears your targets";
    var pill = pass ? '<span class="pf ok">Passes all your targets</span>' : miss.length ? '<span class="pf no">Fails ' + esc(andList(miss.map(function (s) { return (P.MET[s.t.metric].short || P.MET[s.t.metric].name).toLowerCase() + " (" + P.fmtVal(s.t.metric, s.v) + ", target " + P.fmtTarget(s.t).replace(/^at (least|most) /, "") + ")"; }))) + "</span>" : '<span class="pf na">Not measured</span>';
    return { lab: lab, pill: pill, pass: pass };
  }
  function kv(k, v) { return '<div class="rp-kv"><span>' + k + "</span><span>" + v + "</span></div>"; }
  function sheetHTML(g) {
    var run = g.run, v = g.v, P = g.P, ctx = g.ctx, d = ctx.chosen, c = P.caseOf(run), af = run.case === "af", e = esc;
    var V = verdictOf(run, v, P, d), f = facts(run, v, P), when = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
    var h = '<h1>Design report: ' + e(af ? "AF patch" : run.title || c.title) + "</h1>" +
      '<p class="sub">' + runMk(run, P) + "<span>" + e(P.badgeText(run)) + "</span><span>Generated " + e(when) + "</span></p>" +
      '<p class="rp-v">' + e(V.lab) + ": " + P.fmt(d.gates) + " gates" + V.pill + "</p>";
    // spec
    var spec = kv("Device", e(run.device || "not given")) + kv("Signal", e(run.signal || "not given")) + kv("Detects", e(run.detect || "not given")) +
      run.targets.map(function (t) { return kv("Target", e(P.MET[t.metric].name) + " " + e(P.fmtTarget(t))); }).join("") + kv("Judged on", af ? "per recording, test set" : run.judge === "pooled" ? "all held-out " + e(c.whoP) + " pooled" : "the worst held-out " + e(c.who));
    // chip
    var chip = kv("Gates", P.fmt(d.gates)) + kv("Logic depth", d.depth != null ? String(d.depth) : "not recorded") + kv("Inputs", e(P.budgetLabel(run, d.channels || 1)));
    if (!af && d.id) chip += kv("Design", e(d.id));
    // results
    var res = run.targets.map(function (t) {
      var m = P.metricOf(run, d, t.metric), ok = m.v == null ? null : t.op === "<=" ? m.v <= t.value + 1e-12 : m.v >= t.value - 1e-12;
      return kv(e(P.MET[t.metric].name) + ", " + e(P.scopeText(run, t.metric, m.f)), e(P.fmtVal(t.metric, m.v)) + (ok === true ? '<span class="pf ok">Pass</span>' : ok === false ? '<span class="pf no">Fail</span>' : '<span class="pf na">Not measured</span>'));
    }).join("");
    if (af && d.metrics.sensitivity_window != null) res += kv("Sensitivity, per window, test", e(P.fmtVal("sensitivity", d.metrics.sensitivity_window))) + kv("Specificity, per window, test", e(P.fmtVal("specificity", d.metrics.specificity_window)));
    if (!af && d.counts && d.counts.events_total) res += kv(e(cap(c.events)) + " caught", P.fmt(d.counts.events_caught) + " of " + P.fmt(d.counts.events_total) + ", " + d.counts.patients + " " + e(c.whoP) + " pooled");
    if (!af && d.metrics.lead_time_s != null) res += kv("Lead time", d.metrics.lead_time_s.toFixed(1) + " s");
    // cost and battery
    var cb = "";
    if (ctx.caseKind) {
      var bw = batteryWords(ctx.caseKind, d, d.gates);
      cb = kv("Unit cost", est(money(costOf(ctx, d, d.gates)), "cost")) + kv("Battery", bw.txt) + kv("Device power", est((bw.b.total_uw / 1000).toPrecision(3) + " mW", "device_power")) + kv("Chip's share", est(share(bw.b.chip_share), "chip_power"));
    }
    // verification
    var vf = d.verified, ver;
    if (vf && vf.vectors > 0) { var same = vf.identical != null ? vf.identical : vf.vectors - (vf.mismatches || 0); ver = P.fmt(same) + " of " + P.fmt(vf.vectors) + " " + (af ? "test windows" : "test vectors") + " identical, circuit against its model " + srcMk(d); }
    else ver = "Not checked bit for bit for this design.";
    h += '<div class="rp-two"><div><h2>Spec</h2>' + spec + "</div><div><h2>Chip " + srcMk(d) + "</h2>" + chip + "</div></div>";
    h += '<div class="rp-two"><div><h2>Results ' + srcMk(d) + "</h2>" + res + "</div><div>" + (cb ? "<h2>Cost and battery " + MK("no", "estimated") + "</h2>" + cb : "") + "<h2>Verification</h2><p style=\"margin:0\">" + ver + "</p></div></div>";
    h += "<h2>Assumptions and limits</h2>" + factsHTML(Object.assign({}, f, { splitFull: "" }));
    h += "<h2>To check " + MK("no", "to check") + "</h2>" + '<ul class="rp-ul"><li>Hard-wired model: a locked algorithm that cannot drift; changing it means a new chip.</li><li>Bit-exact verification report: usable as design verification evidence.</li><li>Decisions on the device: no raw signal has to leave it.</li></ul>';
    h += '<p class="rp-foot">From the ChipIn dashboard, ' + e(location.origin + location.pathname) + ". Estimated figures are italic with a dotted underline; they come from editable assumptions, not quotes.</p>";
    return h;
  }
  function report() {
    if (!get) return;
    var g = get(); css();
    if (!g.ctx || !g.ctx.chosen || !(g.ctx.chosen.gates > 0) || !final(g.run, g.v, g.P)) { g.toast("The design report is ready when the run has finished."); return; }
    closeReport();
    var el = document.createElement("div"); el.id = "rpView"; el.setAttribute("role", "dialog"); el.setAttribute("aria-label", "Design report");
    el.innerHTML = '<div class="rp-bar"><span>One page. Print it, or choose Save as PDF.</span><button class="btn s" data-rp-x>Close</button><button class="btn p" data-rp-print>Print or save as PDF</button></div><article class="rp-sh">' + sheetHTML(g) + "</article>";
    el.addEventListener("click", function (e) {
      if (e.target.closest("[data-rp-x]")) closeReport();
      else if (e.target.closest("[data-rp-print]")) window.print();
    });
    document.body.appendChild(el);
    el.querySelector("[data-rp-print]").focus();
  }
  function closeReport() { var x = document.getElementById("rpView"); if (x) x.remove(); }

  /* ------------------------------------------------------------------------------ compare */
  // the inspector's button: shown when the selected design is not the chosen (or built, or best) one
  function focusOf(run, v, P) {
    if (run.case === "af") return P.MEASURED.af ? P.MEASURED.af.chosenD : null;
    return v.ev.chosen || v.ev.nearest[0] || null;
  }
  function cmpBtn(run, v, d, P) {
    css();
    var f = focusOf(run, v, P);
    if (!d || !f || d === f || d.id === f.id || !final(run, v, P)) return "";
    return '<button type="button" class="qbtn rp-cmp" data-rp-cmp>Compare with ' + (run.case === "af" ? "the compiled design" : v.ev.chosen ? "chosen" : "best") + "</button>";
  }
  function compare() {
    if (!get) return;
    var g = get(), run = g.run, v = g.v, P = g.P, ctx = g.ctx, c = P.caseOf(run), af = run.case === "af";
    var a = P.selDesign(run, v), b = focusOf(run, v, P);
    if (!a || !b || a === b) return;
    css();
    var cols = [a, b];
    var size = function (d) { if (!af) return { g: d.gates, m: true }; /* the design's own gate count */ var s = P.afSize(v, d); return { g: s.g, m: s.m }; };
    var sz = cols.map(size);
    var head = "<thead><tr><th></th>" + cols.map(function (d, i) { return "<th>" + esc(d.id) + (i === 1 ? ' <span class="pf ok">' + (af ? "Compiled" : v.ev.chosen ? "Chosen" : "Best") + "</span>" : "") + "</th>"; }).join("") + "</tr></thead>";
    var rows = [];
    var add = function (k, f) { rows.push("<tr><td>" + k + "</td>" + cols.map(function (d, i) { return "<td>" + f(d, i) + "</td>"; }).join("") + "</tr>"); };
    add("Chip size", function (d, i) { return sz[i].m ? "<b>" + P.fmt(sz[i].g) + "</b> gates" : '<span class="est" title="' + esc(af ? P.sizeTip() : M().describeEstimate("area")) + '">about ' + P.about(sz[i].g) + "</span> gates"; });
    if (!af) add("Inputs", function (d) { return esc(P.budgetLabel(run, d.channels)); });
    add("Logic depth", function (d) {
      var dep = af ? (d === b ? P.AF_DESIGN.depth : d.gm != null ? d.depth : null) : d.depth; // AF: only synthesised designs have a depth
      return dep != null ? String(dep) : '<span class="dim">not recorded</span>';
    });
    var rr = run, keys = af ? ["sensitivity", "specificity"] : run.targets.map(function (t) { return t.metric; });
    keys.forEach(function (k) {
      var t = run.targets.find(function (x) { return x.metric === k; });
      var f0 = P.metricOf(rr, b, k).f, scope = af ? P.afScopeWord(P.MEASURED.af.scope) + ", validation" : f0 ? P.scopeText(run, k, f0) : "";
      add(esc(P.MET[k].name) + (scope ? ", " + esc(scope) : ""), function (d) {
        var m = P.metricOf(rr, d, k), ok = t && m.v != null ? (t.op === "<=" ? m.v <= t.value + 1e-12 : m.v >= t.value - 1e-12) : null;
        return esc(P.fmtVal(k, m.v)) + (ok === true ? '<span class="pf ok">Pass</span>' : ok === false ? '<span class="pf no">Fail</span>' : "");
      });
    });
    if (!af && cols.some(function (d) { return d.counts && d.counts.events_total; })) add(esc(cap(c.events)) + " caught, pooled", function (d) { return d.counts && d.counts.events_total ? P.fmt(d.counts.events_caught) + " of " + P.fmt(d.counts.events_total) : '<span class="dim">not recorded</span>'; });
    if (!af && cols.some(function (d) { return d.metrics.lead_time_s != null; })) add("Lead time", function (d) { return d.metrics.lead_time_s != null ? d.metrics.lead_time_s.toFixed(1) + " s" : '<span class="dim">not recorded</span>'; });
    if (!af) add("Bit-exact check", function (d) { var vf = d.verified; return vf && vf.vectors > 0 ? P.fmt(vf.identical != null ? vf.identical : vf.vectors - (vf.mismatches || 0)) + " of " + P.fmt(vf.vectors) : '<span class="dim">not checked</span>'; });
    if (ctx.caseKind) {
      add("Unit cost " + MK("no", "estimated"), function (d, i) { return est(money(costOf(ctx, d, sz[i].g)), "cost"); });
      add("Battery " + MK("no", "estimated"), function (d, i) { return batteryWords(ctx.caseKind, d, sz[i].g).txt; });
    }
    var note = af ? "Both columns are validation scores from the search, so they compare; the compiled design's test scores are in the summary card." : "";
    var mk = af ? MK("mea", "measured") : srcMk(b);
    var bg = g.openModal("<h3>Compare two designs " + mk + "</h3><p style=\"margin:0\">The design you selected, beside the " + (af ? "one that was compiled" : v.ev.chosen ? "chosen chip" : "best design") + ".</p>" +
      '<table class="rp-c">' + head + "<tbody>" + rows.join("") + "</tbody></table>" + (note ? '<p class="rp-n">' + note + "</p>" : ""));
    bg.querySelector(".modal").classList.add("rp-m", "w");
  }

  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-rp-lim]")) limits();
    else if (e.target.closest("[data-rp-cmp]")) compare();
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeReport(); });
  window.addEventListener("hashchange", closeReport);
  window.ChipInReport = { bind: function (fn) { get = fn; }, linkHTML: linkHTML, limits: limits, report: report, compare: compare, cmpBtn: cmpBtn, facts: facts };
})();
