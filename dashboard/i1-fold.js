/* ChipIn i1 fold: one reducer for the figures a run's pages show, shared by the live view
 * (../i1-live.js) and the recorded playback (../i1-playback.js), so both show the same numbers
 * for the same events. Classic script, no dependencies; load it before ../live.js.
 *
 *   ChipInFold.scrub(s)            a display string with any absolute home folder path (a Mac or
 *                                  Linux user's home) shown as ~/
 *   ChipInFold.scrubEvent(ev)      the same for every string in an event (in place); returns ev
 *   ChipInFold.create()            an empty fold (plain JSON, so it can be cloned)
 *   ChipInFold.fold(f, ev)         applies one event; for a design event returns
 *                                  { id, isNew, renamed } (renamed: the id it took over)
 *   ChipInFold.designs(f)          the design records, in the backend's designs.json order
 *   ChipInFold.cost(f)             { usd, tokens_in, tokens_out, summaries_usd } or null
 *   ChipInFold.funnel(f, T)        { proposed, scored, compiled, verified, clear, chosen }
 *   ChipInFold.heldOut(f, id, fin) the held-out figures for chip id, or null
 *   ChipInFold.subsHTML(f, spec, open), chipHTML(m), patientsHTML(m): the shared panels
 *   ChipInFold.targetsOf, fmtV, fmtT, meets, passAll, metaOf, dataMark, metricText, sizeOf
 *
 * Designs: one record per id, as the backend keeps designs.json: a record whose previous_id
 * (prev_id is accepted) names an earlier record takes over that record's place.
 * Cost: a cost event with an agent is that subagent's running total; one without is the
 * orchestrator's, until an event carries subagents_usd: that one and every later one without
 * an agent is the whole run's total so far (a follow-up's included). Never a sum of events. */
(function () {
  "use strict";

  /* ---------- display scrub ---------- */
  var HOME = /\/(?:Users|home)\/[^\/\s"'<>`]+(\/|(?=[\s"'<>`),;:]|$))/g;
  function scrub(s) { return typeof s === "string" && s.indexOf("/") >= 0 ? s.replace(HOME, function (m, sl) { return sl ? "~/" : "~"; }) : s; }
  function scrubEvent(v) {
    if (!v || typeof v !== "object") return v;
    var keys = Array.isArray(v) ? v.map(function (x, i) { return i; }) : Object.keys(v);
    keys.forEach(function (k) { var x = v[k]; if (typeof x === "string") v[k] = scrub(x); else if (x && typeof x === "object") scrubEvent(x); });
    return v;
  }

  /* ---------- helpers ---------- */
  var esc = function (s) { return scrub(String(s == null ? "" : s)).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var num = function (v) { return typeof v === "number" && isFinite(v) ? v : null; };
  var fmt = function (n) { return Math.round(n).toLocaleString("en-GB"); };
  var cap = function (s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; };
  var clip = function (s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n - 1).replace(/\s+\S*$/, "") + "…" : s; };
  var pl = function (n, w) { return n + " " + w + (n === 1 ? "" : "s"); };
  var dur = function (h) { return h >= 1 ? +h.toFixed(1) + " h" : +(h * 60).toFixed(1) + " min"; };
  var STAGES = ["spec", "reference", "propose", "finetune", "compile", "verify", "report"];
  var STAGE_N = { spec: "Spec", reference: "Reference", propose: "Propose", finetune: "Fine-tune", compile: "Compile", verify: "Verify", report: "Report" };

  /* ---------- metrics, targets, formats ---------- */
  var MET = {
    sensitivity: { n: "Sensitivity", frac: true, up: true },
    specificity: { n: "Specificity", frac: true, up: true },
    fa_per_hour: { n: "False alarms", frac: false, up: false },
    agreement: { n: "Agreement with experts", frac: true, up: true },
    accuracy: { n: "Accuracy", frac: true, up: true }
  };
  var metaOf = function (k) { return MET[k] || { n: cap(String(k).replace(/_/g, " ")), frac: false, up: true }; };
  var FAU = { hour: 1, night: 12, day: 24 };
  var faUnit = function (spec) { return spec && FAU[spec.fa_unit] ? spec.fa_unit : "hour"; };
  function targetsOf(spec) {
    if (!spec || !Array.isArray(spec.targets)) return [];
    return spec.targets.filter(function (t) { return t && t.metric && num(t.value) != null; }).map(function (t) {
      var m = metaOf(t.metric), v = t.value, u = String(t.unit || "").toLowerCase();
      if (m.frac && (u === "%" || u === "percent" || v > 1)) v = v / 100;
      if (t.metric === "fa_per_hour") v = v / (/night/.test(u) ? 12 : /day/.test(u) ? 24 : /hour/.test(u) ? 1 : FAU[faUnit(spec)]);
      return { metric: t.metric, up: t.op ? t.op !== "at_most" : m.up, value: v };
    });
  }
  function fmtV(k, v, spec) {
    if (v == null) return "not reported";
    if (metaOf(k).frac) return (v * 100).toFixed(1) + "%";
    if (k === "fa_per_hour") { var u = faUnit(spec), y = v * FAU[u]; return (y < 10 ? y.toFixed(2) : y.toFixed(1)) + " per " + u; }
    return String(+v.toFixed(4));
  }
  var fmtT = function (t, spec) { return (t.up ? "at least " : "at most ") + fmtV(t.metric, t.value, spec); };
  var meets = function (t, v) { return v == null ? null : t.up ? v >= t.value - 1e-12 : v <= t.value + 1e-12; };
  var val = function (d, k) { return d && d.metrics ? num(d.metrics[k]) : null; };
  var passAll = function (T, d) { return T.length > 0 && T.every(function (t) { return meets(t, val(d, t.metric)) === true; }); };
  var sizeOf = function (d) { return num(d.gates) > 0 ? { g: d.gates, m: true } : num(d.gates_est) > 0 ? { g: d.gates_est, m: false } : null; };
  var pf = function (ok) { return ok === true ? '<span class="pf ok">Pass</span>' : ok === false ? '<span class="pf no">Fail</span>' : ""; };
  // runs recorded before the backend sent ratios as fractions mix 0 to 1 and 0 to 100: a ratio metric (by name) above 1.5 is a percentage
  var RATIO = /^(?:[a-z0-9]+_)*(?:accuracy|sensitivity|specificity|precision|recall|f1)(?:_(?:test|train|val|heldout|held_out))?$/;
  var ratio = function (k, v) { return RATIO.test(String(k)) && typeof v === "number" && v > 1.5 ? v / 100 : v; };

  // what a metric key means: its base metric and the patients it was measured on
  var BASIS_PRE = [[/^(?:chip_)?(?:val|validation)_/, "validation"], [/^(?:chip_)?(?:heldout|held_out|test)_/, "held-out"], [/^synthetic_/, ""]];
  var BASE_ALIAS = { false_alarms_per_h: "fa_per_hour", false_alarms_per_hour: "fa_per_hour", fa_per_h: "fa_per_hour", gate_equivalents: "ge" };
  function keyInfo(k) {
    var s = String(k), basis = null;
    for (var i = 0; i < BASIS_PRE.length; i++) if (BASIS_PRE[i][0].test(s)) { basis = BASIS_PRE[i][1]; s = s.replace(BASIS_PRE[i][0], ""); break; }
    return { base: BASE_ALIAS[s] || s, basis: basis };
  }
  // the chip lab's figures: label and unit
  var LAB = {
    gates: ["Logic gates", "gates"], depth: ["Logic depth", "levels"], transistors: ["Transistors", ""], area_um2: ["Area before layout", "µm²"],
    ge: ["Gate equivalents", "GE"], luts_xc7: ["LUTs, Xilinx 7-series", "LUTs"], luts_ice40: ["LUTs, iCE40", "LUTs"], tt_tiles: ["Tiny Tapeout tiles", "tiles"],
    cost_eur: ["Tiny Tapeout price", "EUR"], timing_slack_ns: ["Timing slack", "ns"], power_uw_at_rate: ["Power at the decision rate", "µW"]
  };
  // kinds of check: [label, vectors key, mismatches key]
  var CHECKS = [
    ["Lab verification against the model", "verify_vectors", "verify_mismatches"],
    ["Simulation against the model", "vectors_checked", "mismatches"],
    ["Bit-exact simulation", "bitexact_vectors", "bitexact_mismatches"],
    ["Simulation on the run's data", "sim_vectors", "sim_mismatches"],
    ["RTL simulation", "rtl_sim_vectors", "rtl_sim_mismatches"],
    ["RTL simulation, random vectors", "rtl_sim_random_vectors", "rtl_sim_random_mismatches"]
  ];
  var CHECK_KEYS = {}; CHECKS.forEach(function (c) { CHECK_KEYS[c[1]] = 1; CHECK_KEYS[c[2]] = 1; });
  var OTHER = { verification_level: ["Verification level", ""], formal_proved: ["Formal proof", ""], candidates: ["Candidates", ""], patients_pass: ["Patients clearing every target", ""], patients_total: ["Patients", ""] };
  function numText(v, unit) {
    var s = Math.abs(v) >= 1000 ? fmt(v) : String(+v.toFixed(Math.abs(v) >= 100 ? 1 : 3));
    if (v === 1 && /^(tiles|gates|levels|LUTs|vectors|transistors)$/.test(unit || "")) unit = unit.replace(/s$/, "");
    return s + (unit ? " " + unit : "");
  }
  // one metric as a person reads it: { label, value }
  function metricText(k, v, unit, spec) {
    var ki = keyInfo(k), b = ki.base, bas = ki.basis ? ", " + ki.basis : "";
    if (num(v) == null) return { label: cap(String(k).replace(/_/g, " ")), value: String(v) };
    if (MET[b]) return { label: MET[b].n + bas, value: fmtV(b, ratio(b, v), spec) };
    if (LAB[b]) return { label: LAB[b][0], value: numText(v, LAB[b][1]) };
    for (var i = 0; i < CHECKS.length; i++) {
      if (CHECKS[i][1] === b) return { label: CHECKS[i][0] + ", vectors", value: numText(v, "") };
      if (CHECKS[i][2] === b) return { label: CHECKS[i][0] + ", mismatches", value: numText(v, "") };
    }
    if (b === "formal_proved") return { label: "Formal proof", value: v ? "proved equal" : "not proved" };
    if (OTHER[b]) return { label: OTHER[b][0], value: numText(v, OTHER[b][1]) };
    var u = unit === "/h" ? "per hour" : unit === "um2" ? "µm²" : unit || "";
    return { label: cap(String(k).replace(/_/g, " ")), value: numText(v, u) };
  }

  function dataMark(spec, designs) {
    var mode = spec && spec.data && spec.data.mode, pub = null, syn = mode === "simulate";
    (designs || []).forEach(function (d) { var s = String(d && d.data || ""); if (s === "synthetic") syn = true; else if (/^public:/.test(s)) pub = s.slice(7); });
    if (syn) return '<span class="mk sim">synthetic data</span>';
    if (pub) return '<span class="mk mea">public data: ' + esc(pub) + "</span>";
    return "";
  }

  /* ---------- the fold ---------- */
  function create() {
    return { designs: {}, order: [], chips: {}, units: {}, run: {}, runUnits: {}, chosen: null, spec: null,
      cost: { orch: null, agents: {}, total: null, totalMode: false }, subs: {}, subOrder: [], merged: {}, mergedOrder: [] };
  }
  function normDesign(d) {
    if (!d || typeof d !== "object" || typeof d.id !== "string" || !d.id) return null;
    var b = d.budget, budget = typeof b === "number" ? { ch: b, name: b + " channels" } : b && typeof b === "object" ? { ch: num(b.channels != null ? b.channels : b.sensors), name: b.name || (num(b.channels) != null ? b.channels + " channels" : "") } : { ch: null, name: "" };
    var out = {};
    for (var k in d) out[k] = d[k];
    out.budget = budget;
    var dm = {}, m = d.metrics && typeof d.metrics === "object" ? d.metrics : {};
    for (var mk in m) dm[mk] = ratio(mk, m[mk]);
    out.metrics = dm;
    out.counts = d.counts && typeof d.counts === "object" ? d.counts : {};
    out.per_patient = Array.isArray(d.per_patient) ? d.per_patient.filter(function (p) { return p && num(p.total) != null; }) : [];
    return out;
  }
  var costPart = function (ev) { return { usd: num(ev.usd), tokens_in: num(ev.tokens_in), tokens_out: num(ev.tokens_out), summaries_usd: num(ev.summaries_usd) }; };
  function fold(f, ev) {
    if (!ev || typeof ev !== "object") return null;
    switch (ev.type) {
      case "run.started": if (ev.spec && typeof ev.spec === "object") f.spec = ev.spec; break;
      case "design": {
        var d = normDesign(ev.design || ev.record);
        if (!d) break;
        if (num(ev.revision) != null) d.revision = ev.revision;
        var prev = d.previous_id || d.prev_id, same = f.order.indexOf(d.id), took = prev && prev !== d.id ? f.order.indexOf(prev) : -1, renamed = null;
        if (same < 0 && took < 0) f.order.push(d.id);
        else if (took >= 0) {
          renamed = prev; delete f.designs[prev];
          if (same < 0) f.order[took] = d.id; else f.order.splice(took, 1);
        }
        f.designs[d.id] = d;
        return { id: d.id, isNew: same < 0 && took < 0, renamed: renamed, d: d };
      }
      case "metric": {
        if (typeof ev.key !== "string") break;
        var chip = typeof ev.chip === "string" && ev.chip ? ev.chip : null, v = ratio(ev.key, ev.value);
        var vals = chip ? f.chips[chip] || (f.chips[chip] = {}) : f.run, units = chip ? f.units[chip] || (f.units[chip] = {}) : f.runUnits;
        vals[ev.key] = v; if (ev.unit) units[ev.key] = ev.unit;
        if (ev.agent && f.subs[ev.agent]) f.subs[ev.agent].latest = { key: ev.key, value: v, unit: ev.unit || "" };
        break;
      }
      case "chosen": if (typeof ev.chip === "string" && ev.chip) f.chosen = ev.chip; break;
      case "cost": {
        var c = f.cost, part = costPart(ev);
        if (typeof ev.agent === "string" && ev.agent) c.agents[ev.agent] = part;
        else if (num(ev.subagents_usd) != null || c.totalMode) { c.totalMode = true; c.total = part; }
        else c.orch = part;
        break;
      }
      case "subagent.started": {
        var key = ev.agent || ev.id || ("sub" + ev.seq);
        if (!f.subs[key]) f.subOrder.push(key);
        f.subs[key] = { key: key, stage: ev.stage || "", strategy: ev.strategy || ev.name || "", model: ev.model || "", state: "running", latest: null, result: "" };
        break;
      }
      case "subagent.finished": {
        var s = f.subs[ev.agent || ev.id];
        if (s) { var stt = String(ev.status || ev.state || "done"); s.state = /fail|error/.test(stt) ? "failed" : "done"; s.result = ev.summary || (typeof ev.result === "string" ? ev.result : "") || ""; }
        break;
      }
      case "stage.merged": {
        if (!f.merged[ev.stage]) f.mergedOrder.push(ev.stage);
        f.merged[ev.stage] = { kept: Array.isArray(ev.kept) ? ev.kept : [], why: ev.why || ev.reason || "" };
        break;
      }
      default: break;
    }
    return null;
  }
  var designs = function (f) { return f.order.map(function (i) { return f.designs[i]; }).filter(Boolean); };
  function cost(f) {
    var c = f.cost, add = function (a, b) { return a == null ? b : b == null ? a : a + b; };
    if (c.total) return c.total;
    var ids = Object.keys(c.agents);
    if (!c.orch && !ids.length) return null;
    var out = c.orch ? { usd: c.orch.usd, tokens_in: c.orch.tokens_in, tokens_out: c.orch.tokens_out, summaries_usd: c.orch.summaries_usd } : { usd: null, tokens_in: null, tokens_out: null, summaries_usd: null };
    ids.forEach(function (k) { var a = c.agents[k]; out.usd = add(out.usd, a.usd); out.tokens_in = add(out.tokens_in, a.tokens_in); out.tokens_out = add(out.tokens_out, a.tokens_out); });
    return out;
  }
  function funnel(f, T) {
    var ds = designs(f), cand = num(f.run.candidates);
    return {
      proposed: Math.max(ds.length, cand || 0),
      scored: ds.filter(function (d) { return Object.keys(d.metrics).some(function (k) { return num(d.metrics[k]) != null; }); }).length,
      compiled: ds.filter(function (d) { return num(d.gates) > 0; }).length,
      verified: ds.filter(function (d) { return d.verified && typeof d.verified === "object"; }).length,
      clear: ds.filter(function (d) { return passAll(T || [], d); }).length,
      chosen: f.chosen ? 1 : 0
    };
  }

  /* ---------- held-out figures for one chip ---------- */
  var HELD_PRE = ["chip_heldout_", "heldout_", "held_out_", "chip_test_", "test_"];
  var HELD_BASE = { sensitivity: ["sensitivity"], specificity: ["specificity"], fa_per_hour: ["fa_per_hour", "false_alarms_per_h", "false_alarms_per_hour"] };
  // a test-basis block: the record itself, or its test / held_out / heldout part
  function testBlock(r) {
    if (!r || typeof r !== "object") return null;
    if (r.basis === "test" && Array.isArray(r.per_patient)) return r;
    var t = r.test || r.held_out || r.heldout;
    return t && typeof t === "object" && (Array.isArray(t.per_patient) || t.metrics) ? t : null;
  }
  function heldOut(f, id, fin) {
    if (!id) return null;
    var m = f.chips[id] || {}, rec = f.designs[id], pooled = {}, src = "metrics", rows = [], counts = {}, from = null;
    Object.keys(HELD_BASE).forEach(function (b) {
      HELD_PRE.forEach(function (p) { HELD_BASE[b].forEach(function (n) { if (pooled[b] == null && num(m[p + n]) != null) pooled[b] = ratio(b, m[p + n]); }); });
      if (pooled[b] == null && id === f.chosen) HELD_PRE.forEach(function (p) { HELD_BASE[b].forEach(function (n) { if (pooled[b] == null && num(f.run[p + n]) != null) pooled[b] = ratio(b, f.run[p + n]); }); });
    });
    var blocks = [[testBlock(rec), "record"], [fin && (fin.id == null || fin.id === id) ? testBlock(fin) : null, "final"]];
    for (var i = 0; i < blocks.length; i++) {
      var tb = blocks[i][0]; if (!tb) continue;
      var pp = Array.isArray(tb.per_patient) ? tb.per_patient.filter(function (p) { return p && num(p.total) != null; }) : [];
      if (pp.length && !rows.length) { rows = pp; from = blocks[i][1]; counts = tb.counts || {}; }
      var tm = tb.metrics || {};
      Object.keys(HELD_BASE).forEach(function (b) { if (pooled[b] == null && num(tm[b]) != null) { pooled[b] = ratio(b, tm[b]); src = blocks[i][1]; } });
    }
    if (!rows.length && !Object.keys(pooled).length) return null;
    return { id: id, pooled: pooled, rows: rows, counts: counts, from: from || src, sameRecord: from === "record" };
  }

  /* ---------- shared panels ---------- */
  var BAR_CSS = "";
  function barsHTML(rows, t) {
    return rows.slice().sort(function (a, b) { return a.caught / (a.total || 1) - b.caught / (b.total || 1); }).map(function (p) {
      var r = p.total ? p.caught / p.total : 0, ok = t ? r >= t.value - 1e-12 : true, fa = num(p.false_alarms);
      return '<div class="cf-pr"><span class="cf-pid">' + esc(p.id) + '</span><span class="cf-pb"><i style="width:' + (r * 100).toFixed(1) + "%;background:" + (ok ? "var(--caught)" : "var(--missed)") + '"></i>' + (t ? '<s style="left:' + (t.value * 100).toFixed(1) + '%"></s>' : "") + '</span><span class="cf-pv">' + p.caught + " of " + p.total + " caught, " + (r * 100).toFixed(1) + "%</span>" +
        '<span class="cf-pf">' + (fa != null ? pl(fa, "false alarm") + (num(p.hours) ? " in " + dur(p.hours) : "") : "") + "</span></div>";
    }).join("");
  }
  var basisName = function (b) { return b === "validation" ? "validation" : b === "test" ? "held-out test" : b ? String(b) : ""; };
  // Where it fails. m: { f, spec, T, chosenId, selId, final, running }
  function patientsHTML(m) {
    var f = m.f, T = m.T || targetsOf(m.spec), ds = designs(f), withPP = ds.filter(function (d) { return d.per_patient.length; });
    var d = m.selId ? f.designs[m.selId] : null;
    if (!d || !d.per_patient.length) d = (m.chosenId && f.designs[m.chosenId] && f.designs[m.chosenId].per_patient.length ? f.designs[m.chosenId] : null) || withPP[withPP.length - 1] || null;
    var held = heldOut(f, m.chosenId, m.final), t = T.filter(function (x) { return x.metric === "sensitivity"; })[0];
    if (!d && !held) return '<div class="vh"><h2>Where it fails</h2><p class="vs">' + (m.running ? "No per-patient results yet. They appear when the agent reports a design with its per-patient results." : "This run reported no per-patient results.") + "</p></div>";
    var out = '<div class="vh"><h2>Where it fails</h2><p class="vs">' + (held ? "The held-out patients first: the chosen chip never saw them while it was designed and picked. Then the patients each design was scored on." : "One bar per patient, worst first.") + "</p></div>";
    if (held) {
      var hc = f.designs[held.id], mark = dataMark(m.spec, hc ? [hc] : []);
      out += '<section class="stage cf-sec" data-sec="heldout"><p class="cf-k">Chip ' + esc(held.id) + ", the chosen chip " + mark + '</p><h3 class="cf-h3">Held-out patients</h3>';
      if (held.rows.length) {
        var below = t ? held.rows.filter(function (p) { return p.total && p.caught / p.total < t.value; }).length : null;
        out += '<p class="cf-sub">One bar per held-out patient, worst first.' + (t ? " The line is your bar, " + esc(fmtT(t, m.spec)) + "; " + below + " of " + pl(held.rows.length, "patient") + (below === 1 ? " falls" : " fall") + " below it." : "") + "</p>" + barsHTML(held.rows, t);
      }
      var pk = ["sensitivity", "fa_per_hour", "specificity"].filter(function (k) { return held.pooled[k] != null; });
      if (pk.length) out += '<div class="cf-kv">' + pk.map(function (k) {
        var tg = T.filter(function (x) { return x.metric === k; })[0], v = held.pooled[k];
        return '<div class="irow"><span>' + esc(metaOf(k).n) + ", held-out, pooled</span><b>" + esc(fmtV(k, v, m.spec)) + (tg ? '<span class="cf-tg">target ' + esc(fmtT(tg, m.spec)) + "</span>" + pf(meets(tg, v)) : "") + "</b></div>";
      }).join("") + "</div>";
      if (!held.rows.length) out += '<p class="cf-sub">Per-patient held-out data was not reported for this chip; these are the pooled figures the agent reported.</p>';
      out += "</section>";
    }
    if (d && !(held && held.sameRecord && held.id === d.id)) {
      var rows = d.per_patient.slice().sort(function (a, b) { return a.caught / (a.total || 1) - b.caught / (b.total || 1); });
      var w = rows[0], wr = w.total ? w.caught / w.total : null, below2 = t ? rows.filter(function (p) { return p.total && p.caught / p.total < t.value; }).length : null;
      var bn = basisName(d.basis), title = d.basis === "validation" ? "Validation patients" : d.basis === "test" ? "Held-out test patients" : "Patients";
      var picks = withPP.length > 1 ? '<div class="ptiles2">' + withPP.map(function (x) { var s = sizeOf(x); return '<button class="ptb' + (x.id === d.id ? " on" : "") + '" data-pick="' + esc(x.id) + '"><i' + (passAll(T, x) ? "" : ' style="background:var(--missed)"') + "></i>" + esc(x.id) + (s ? ", " + fmt(s.g) + " gates" : "") + "</button>"; }).join("") + "</div>" : "";
      out += '<section class="stage cf-sec" data-sec="' + esc(d.basis || "patients") + '"><p class="cf-k">Design ' + esc(d.id) + (d.id === m.chosenId ? ", the chosen chip" : "") + " " + dataMark(m.spec, [d]) + '</p><h3 class="cf-h3">' + title + ": worst " + esc(w.id) + ", " + (wr == null ? "no events" : (wr * 100).toFixed(1) + "% caught") + "</h3>" +
        '<p class="cf-sub">One bar per patient, worst first' + (bn ? ", on the " + esc(bn) + " set" : "") + "." + (t ? " The line is your bar, " + esc(fmtT(t, m.spec)) + "; " + below2 + " of " + pl(rows.length, "patient") + (below2 === 1 ? " falls" : " fall") + " below it." : "") + "</p>" + picks + barsHTML(rows, t) + "</section>";
    }
    return out;
  }

  // Chip. m: { f, spec, T, id, chosenId, running }
  function chipHTML(m) {
    var f = m.f, id = m.id;
    if (!id) return '<div class="vh"><h2>The chip</h2><p class="vs">' + (m.running ? "No chip yet. The chosen chip's figures appear here once the chip lab reports them." : "This run chose no chip.") + "</p></div>";
    var rec = f.designs[id] || null, mm = f.chips[id] || {}, uu = f.units[id] || {};
    if (!Object.keys(mm).length && id === f.chosen) {
      // an older backend sent the lab's figures without a chip id: for the chosen chip, the run's own
      var r = f.run; mm = {}; Object.keys(r).forEach(function (k) { if (LAB[keyInfo(k).base] || CHECK_KEYS[k] || OTHER[k]) mm[k] = r[k]; }); uu = f.runUnits;
    }
    var vf = rec && rec.verified && typeof rec.verified === "object" ? rec.verified : {}, T = m.T || targetsOf(m.spec);
    var lab = [], seen = {};
    var labV = function (k) { if (k === "gates" && rec && num(rec.gates) != null) return rec.gates; if (k === "depth" && rec && num(rec.depth) != null) return rec.depth; var v = null; Object.keys(mm).forEach(function (x) { if (keyInfo(x).base === k && !keyInfo(x).basis && num(mm[x]) != null) { v = mm[x]; seen[x] = 1; } }); return v; };
    Object.keys(LAB).forEach(function (k) { var v = labV(k); seen[k] = 1; if (v != null) lab.push([LAB[k][0], numText(v, LAB[k][1])]); });
    if (rec && num(rec.gates) == null && num(rec.gates_est) != null && labV("gates") == null) lab.unshift(["Logic gates", '<span class="est" title="Estimated by the agent; the chip lab has not measured it">about ' + fmt(rec.gates_est) + " gates, estimated</span>"]);
    // vectors checked and mismatches, per kind of check
    var checks = [];
    CHECKS.forEach(function (c, i) {
      var n = num(mm[c[1]]), x = num(mm[c[2]]);
      if (i === 0) { if (n == null) n = num(vf.vectors); if (x == null) x = num(vf.mismatches); }
      seen[c[1]] = seen[c[2]] = 1;
      if (n == null && x == null) return;
      checks.push([c[0], (n != null ? fmt(n) + " vectors" : "vectors not reported") + ", " + (x != null ? fmt(x) + (x === 1 ? " mismatch" : " mismatches") : "mismatches not reported")]);
    });
    var lvl = mm.verification_level != null ? mm.verification_level : vf.level; seen.verification_level = 1;
    var proved = num(mm.formal_proved) != null ? !!mm.formal_proved : typeof vf.proved === "boolean" ? vf.proved : null; seen.formal_proved = 1;
    if (lvl != null) lab.push(["Verification level", "level " + esc(lvl)]);
    if (proved != null) lab.push(["Formal proof", proved ? "proved equal to the model" : "not proved"]);
    // what the agent reported for this chip: one row per measure and set of patients
    var agent = {}, order = [], put = function (label, k, v, prio, b) { var key = label; if (!agent[key]) order.push(key); if (!agent[key] || agent[key].prio < prio) agent[key] = { label: label, k: k, v: v, prio: prio, b: b }; };
    Object.keys(mm).forEach(function (k) {
      if (seen[k]) return;
      var ki = keyInfo(k), v = num(mm[k]);
      if (v == null) return;
      if (MET[ki.base]) {
        var b = ki.basis || (rec && rec.basis === "test" ? "held-out" : rec && rec.basis === "validation" ? "validation" : "");
        put(MET[ki.base].n + (b ? ", " + b : ""), ki.base, v, (/^chip_/.test(k) ? 3 : ki.basis ? 2 : 1), b);
      } else if (!LAB[ki.base] && !CHECK_KEYS[k]) { var mt = metricText(k, v, uu[k], m.spec); put(mt.label, null, mt.value, 1, ""); }
    });
    if (rec) Object.keys(rec.metrics).forEach(function (k) { var v = num(rec.metrics[k]); if (v == null || !MET[k]) return; var b = rec.basis === "test" ? "held-out" : rec.basis === "validation" ? "validation" : ""; put(MET[k].n + (b ? ", " + b : ""), k, v, 0, b); });
    var rank = function (r) { return (r.b === "validation" ? 0 : r.b === "held-out" ? 1 : 2) * 10 + (r.k === "sensitivity" ? 0 : r.k === "fa_per_hour" ? 1 : r.k === "specificity" ? 2 : 3); };
    var ag = order.map(function (k) { return agent[k]; }).sort(function (a, b) { return rank(a) - rank(b); });
    var row = function (r) { return '<div class="irow"><span>' + esc(r[0]) + "</span><b>" + r[1] + "</b></div>"; };
    var mark = dataMark(m.spec, rec ? [rec] : []);
    return '<div class="vh"><p class="cf-k">Chip ' + esc(id) + (id === m.chosenId ? ", chosen" : "") + " " + mark + '</p><h2>The chip</h2><p class="vs">Two kinds of figure: what the chip lab measured on the circuit, and what the agent computed on the patients.</p></div>' +
      '<section class="stage cf-sec" data-sec="lab"><h3 class="cf-h3">Measured by the chip lab</h3>' + (lab.length || checks.length ? '<div class="cf-kv">' + lab.map(function (r) { return row([r[0], r[1]]); }).join("") + "</div>" : '<p class="cf-sub">The lab has not reported figures for this chip yet.</p>') +
      (checks.length ? '<h4 class="cf-h4">Vectors checked against the model</h4><div class="cf-kv">' + checks.map(function (c) { return row([c[0], esc(c[1])]); }).join("") + "</div>" + (checks.length > 1 ? '<p class="cf-sub">Each kind of check runs its own set of input vectors, so the counts differ.</p>' : "") : "") + "</section>" +
      '<section class="stage cf-sec" data-sec="agent"><h3 class="cf-h3">Reported by the agent</h3>' + (ag.length ? '<div class="cf-kv">' + ag.map(function (r) {
        var tg = r.k ? T.filter(function (x) { return x.metric === r.k; })[0] : null, txt = r.k ? fmtV(r.k, r.v, m.spec) : r.v;
        return row([r.label, esc(txt) + (tg ? '<span class="cf-tg">target ' + esc(fmtT(tg, m.spec)) + "</span>" + pf(meets(tg, r.v)) : "")]);
      }).join("") + '</div><p class="cf-sub">Computed by the agent on ' + (mark ? "synthetic " : "") + "patient data, not measured by the lab.</p>" : '<p class="cf-sub">The agent reported no accuracy figures for this chip.</p>') + "</section>";
  }

  // Subagent batches: one line per stage that opens to its entries. open: { stage: true }
  function subsHTML(f, spec, open, opts) {
    opts = opts || {};
    if (!f.subOrder.length) return opts.empty ? '<section class="pan cf-subs" aria-label="Subagent batches"><h2>Subagent batches</h2><p class="cf-sub">' + esc(opts.empty) + "</p></section>" : "";
    var kept = {}; f.mergedOrder.forEach(function (s) { (f.merged[s].kept || []).forEach(function (k) { kept[k] = 1; }); });
    var stages = []; f.subOrder.forEach(function (k) { var s = f.subs[k].stage || "other"; if (stages.indexOf(s) < 0) stages.push(s); });
    stages.sort(function (a, b) { var i = STAGES.indexOf(a), j = STAGES.indexOf(b); return (i < 0 ? 99 : i) - (j < 0 ? 99 : j); });
    var fin = f.subOrder.filter(function (k) { return f.subs[k].state !== "running"; }).length;
    var mark = dataMark(spec, designs(f));
    return '<section class="pan cf-subs" aria-label="Subagent batches"><div class="cf-subh"><h2>Subagent batches</h2><span class="cf-sub">' + fin + " of " + f.subOrder.length + " finished</span>" + mark + "</div>" + stages.map(function (s) {
      var list = f.subOrder.filter(function (k) { return (f.subs[k].stage || "other") === s; }).map(function (k) { return f.subs[k]; }), mg = f.merged[s];
      var dots = list.map(function (a) { return '<i class="' + (kept[a.key] ? "kept " : "") + (a.state === "running" ? "" : a.state) + '" title="' + esc(a.key + ": " + (a.state === "running" ? "running" : a.state) + (kept[a.key] ? ", kept" : "")) + '"></i>'; }).join("");
      var kept0 = mg ? "Kept " + (mg.kept.length ? mg.kept.join(", ") : "none") : "", line = mg ? kept0 + (mg.why ? ": " + clip(mg.why, 90) : "") : list.some(function (a) { return a.state === "running"; }) ? "running" : "waiting for the merge";
      return '<details class="cf-sb" data-batch="' + esc(s) + '"' + (open && open[s] ? " open" : "") + "><summary><b>" + esc(STAGE_N[s] || cap(s)) + '</b><span class="cf-dots" aria-label="' + esc(pl(list.length, "subagent")) + '">' + dots + '</span><span class="cf-line"><span class="cf-short">' + esc(line) + '</span><span class="cf-kept">' + esc(mg ? kept0 : line) + "</span></span></summary>" +
        '<div class="cf-sbb">' + (mg && mg.why ? '<p class="cf-why">' + esc(mg.why) + "</p>" : "") + list.map(function (a) {
          var lt = a.latest ? metricText(a.latest.key, a.latest.value, a.latest.unit, spec) : null;
          return '<div class="cf-se"><span class="cf-sid">' + esc(a.key) + '</span><span class="cf-st">' + esc(a.strategy.replace(/^Strategy\s*[:-]?\s*/i, "") || a.key) + "</span>" + (lt ? '<span class="cf-sm">' + esc(lt.label) + ": " + esc(lt.value) + "</span>" : "") + "</div>";
        }).join("") + "</div></details>";
    }).join("") + "</section>";
  }
  // keeps which stages are open across redraws
  function wireSubs(host, open) {
    if (!host || host._cfWired) return; host._cfWired = true;
    host.addEventListener("toggle", function (e) { var d = e.target; if (d && d.classList && d.classList.contains("cf-sb")) { if (d.open) open[d.dataset.batch] = true; else delete open[d.dataset.batch]; } }, true);
  }

  /* ---------- styles ---------- */
  var css = document.createElement("style");
  css.textContent = [
    ".cf-sec{margin-top:14px}.cf-h3{font-size:14px;font-weight:650;margin:0 0 6px}.cf-h4{font-size:12.5px;font-weight:650;margin:12px 0 4px;color:var(--i700)}",
    ".cf-k{font-size:12.5px;color:var(--i600);margin:0 0 4px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}",
    ".cf-sub{font-size:12.5px;color:var(--i600);margin:4px 0 8px;line-height:1.5}",
    ".cf-kv{max-width:620px}.cf-kv .irow b{display:inline-flex;flex-wrap:wrap;justify-content:flex-end;align-items:center;gap:4px 8px;text-align:right}",
    ".cf-tg{font-weight:400;color:var(--i600);font-size:12px}",
    ".cf-pr{display:grid;grid-template-columns:64px minmax(0,1fr) 170px 150px;gap:12px;align-items:center;padding:5px 0;border-top:1px solid var(--hair);font-size:12.5px}.cf-pr:first-of-type{border-top:0}",
    ".cf-pid{font-weight:600}.cf-pb{position:relative;height:12px;border-radius:3px;background:var(--i100)}.cf-pb i{position:absolute;left:0;top:0;bottom:0;border-radius:3px}.cf-pb s{position:absolute;top:-4px;bottom:-4px;border-left:1.5px dashed var(--i900)}",
    ".cf-pv,.cf-pf{color:var(--i700);font-variant-numeric:tabular-nums}.cf-pf{color:var(--falsea-t)}",
    ".cf-subs{padding:10px 16px 8px}.cf-subh{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 0 4px}.cf-subh h2{font-size:13px;font-weight:650;margin:0}.cf-subh .cf-sub{margin:0}",
    ".cf-sb{border-top:1px solid var(--hair)}.cf-sb summary{display:grid;grid-template-columns:90px auto minmax(0,1fr);gap:4px 12px;align-items:center;padding:6px 0;cursor:pointer;list-style:none;font-size:12.5px}.cf-sb summary::-webkit-details-marker{display:none}",
    ".cf-sb summary b{font-weight:600}.cf-sb summary b::before{content:'';display:inline-block;width:0;height:0;border:4px solid transparent;border-left:5px solid var(--i500);margin-right:6px;vertical-align:1px;transition:transform .15s}.cf-sb[open] summary b::before{transform:rotate(90deg);transform-origin:2px 4px}",
    ".cf-sb summary:hover .cf-line{color:var(--i900)}.cf-sb summary:focus-visible{outline:2px solid var(--blue7);outline-offset:2px;border-radius:6px}",
    ".cf-line{color:var(--i700);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}.cf-sb[open] .cf-short,.cf-sb:not([open]) .cf-kept{display:none}",
    ".cf-dots{display:flex;gap:4px;flex-wrap:wrap}.cf-dots i{width:10px;height:10px;border-radius:50%;border:1.5px solid var(--blue6,#3d6df0);box-sizing:border-box}",
    ".cf-dots i.done{background:var(--blue6,#3d6df0)}.cf-dots i.failed{background:#ef4444;border-color:#ef4444}.cf-dots i.kept{box-shadow:0 0 0 2px #fff,0 0 0 3.5px var(--i900)}",
    ".cf-sbb{padding:0 0 8px 102px;display:flex;flex-direction:column;gap:4px}",
    ".cf-why{margin:0 0 4px;font-size:12px;color:var(--i700);line-height:1.5;overflow-wrap:anywhere}",
    ".cf-se{display:grid;grid-template-columns:34px minmax(0,1fr);gap:2px 10px;font-size:12px;line-height:1.45;color:var(--i800)}.cf-sid{font-family:var(--mono);font-size:11px;color:var(--i600)}",
    ".cf-st{overflow-wrap:anywhere}.cf-sm{grid-column:2;color:var(--i600);font-variant-numeric:tabular-nums;overflow-wrap:anywhere}",
    "@media (max-width:767px){.cf-pr{grid-template-columns:44px minmax(0,1fr);row-gap:2px}.cf-pv,.cf-pf{grid-column:2;font-size:11.5px}.cf-sb summary{grid-template-columns:auto minmax(0,1fr)}.cf-line{grid-column:1/-1;white-space:normal}.cf-sbb{padding-left:0}.cf-kv .irow{flex-wrap:wrap}}"
  ].join("\n");
  document.head.appendChild(css);

  window.ChipInFold = {
    version: 1, scrub: scrub, scrubEvent: scrubEvent, create: create, fold: fold, designs: designs, cost: cost, funnel: funnel, heldOut: heldOut,
    subsHTML: subsHTML, wireSubs: wireSubs, chipHTML: chipHTML, patientsHTML: patientsHTML,
    targetsOf: targetsOf, fmtV: fmtV, fmtT: fmtT, meets: meets, passAll: passAll, metaOf: metaOf, MET: MET, FAU: FAU, faUnit: faUnit,
    dataMark: dataMark, metricText: metricText, keyInfo: keyInfo, sizeOf: sizeOf, ratio: ratio, normDesign: normDesign
  };
})();
