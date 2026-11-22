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
 *   ChipInFold.subsHTML(f, spec, open), chipHTML(m): the shared panels
 *   ChipInFold.variantHTML(d)      the "Variant of <id>" line for a record with variant_of, else ""
 *   ChipInFold.chipName(f, id, o)  { name, id, from }: a chip named in words (record label, else its
 *                                  ir.json in o.files, else its size), never by the bare id
 *   ChipInFold.chipNameHTML(f, id, o) that name with the id small after it
 *   ChipInFold.plainWords(f, s, o) an agent's sentence with chip and subagent ids and shorthand in words
 *   ChipInFold.targetsOf, fmtV, fmtT, meets, passAll, metaOf, dataMark, metricText, sizeOf
 *   ChipInFold.humanKeys(s)        a sentence with any raw metric key in it read as that key's label,
 *                                  a ratio named by its metric as a percentage and long floats rounded
 *   ChipInFold.screenOnly(spec, T) a one-off screening spec with no false-alarm target
 *   ChipInFold.levelText(l)        the lab's verification level as words ("level 2", "bit-exact simulation")
 *   ChipInFold.fileView(el, path, text, opts) shows an image as the image (bytes from file?...&raw=1
 *                                  when the backend serves them) and names a binary file; true when handled
 *
 * Designs: one record per id, as the backend keeps designs.json: a record whose previous_id
 * (prev_id is accepted) names an earlier record takes over that record's place.
 * Cost: every cost event from the current backend carries run_total_usd (the whole run so far,
 * summaries included) and agent_usd (the named agent's own spend, or the orchestrator's); the
 * newest run_total_usd is the run's cost. Older recordings without them: a cost event with an
 * agent is that subagent's running total; one without is the orchestrator's, until an event
 * carries subagents_usd: that one and every later one without an agent is the whole run's total
 * so far (a follow-up's included). Never a sum of events.
 * Metric labels: metricText(key, value, unit, spec) is the one map from a metric key to the label
 * and unit a person reads; the Chip tab, the inspector and the message view all use it.
 * Lab sources: a metric event with a source (score-events, the chip lab's event-level referee) is
 * kept in f.src[chip or ""][key], never in the agent's figures, so neither replaces the other; the
 * Chip tab shows it as its own row under Measured by the chip lab, labelled by metricText(..., source). */
(function () {
  "use strict";

  /* ---------- display scrub ---------- */
  var HOME = /\/(?:Users|home)\/[^\/\s"'<>`]+(\/|(?=[\s"'<>`),;:]|$))/g;
  function scrub(s) { return typeof s === "string" && s.indexOf("/") >= 0 ? s.replace(HOME, function (m, sl) { return sl ? "~/" : "~"; }) : s; }
  // a log row's path read from the repo root: a home or worktree prefix of the repo is left out
  var REPO = /(?:~|\/(?:Users|home)\/[^\/\s"'<>`]+)\/projects\/sota-hack(?:\/\.worktrees\/[^\/\s"'<>`]+)?(?:\/|(?=[\s"'<>`),;:…]|$))/g;
  function repoPath(s) { return typeof s === "string" && s.indexOf("/") >= 0 ? scrub(s.replace(REPO, function (m) { return m.slice(-1) === "/" ? "" : "."; })) : s; }
  function scrubEvent(v) {
    if (!v || typeof v !== "object") return v;
    var keys = Array.isArray(v) ? v.map(function (x, i) { return i; }) : Object.keys(v);
    keys.forEach(function (k) { var x = v[k]; if (typeof x === "string") v[k] = scrub(x); else if (x && typeof x === "object") scrubEvent(x); });
    return v;
  }

  /* ---------- helpers ---------- */
  var esc = function (s) { return scrub(String(s == null ? "" : s)).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  // a short note's full sentence, shown on hover, focus or tap by ../i1-tip.js
  var tipA = function (full) { return ' data-tip="' + esc(full) + '"'; };
  var num = function (v) { return typeof v === "number" && isFinite(v) ? v : null; };
  var fmt = function (n) { return Math.round(n).toLocaleString("en-GB"); };
  var cap = function (s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; };
  var clip = function (s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n - 1).replace(/\s+\S*$/, "") + "…" : s; };
  var pl = function (n, w) { return n + " " + w + (n === 1 ? "" : "s"); };
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
  var BASIS_PRE = [[/^(?:chip_)?(?:val|validation)_/, "validation"], [/^(?:chip_)?(?:heldout|held_out|test)_/, "held-out"], [/^(?:chip_)?train(?:ing)?_/, "training"], [/^synthetic_/, ""]];
  var BASE_ALIAS = { false_alarms_per_h: "fa_per_hour", false_alarms_per_hour: "fa_per_hour", fa_per_h: "fa_per_hour", gate_equivalents: "ge" };
  // the same written at the end ("window_sens_test"), a per-window scope, short names and a false-alarm rate per day or night
  var BASIS_SUF = [[/_(?:test|heldout|held_out)$/, "held-out"], [/_(?:val|validation)$/, "validation"], [/_train(?:ing)?$/, "training"]];
  var SHORT = { sens: "sensitivity", spec: "specificity", acc: "accuracy" };
  function keyInfo(k) {
    var s = String(k), basis = null, scope = null, per = 1, i;
    for (i = 0; i < BASIS_PRE.length; i++) if (BASIS_PRE[i][0].test(s)) { basis = BASIS_PRE[i][1]; s = s.replace(BASIS_PRE[i][0], ""); break; }
    if (basis == null) for (i = 0; i < BASIS_SUF.length; i++) if (BASIS_SUF[i][0].test(s)) { basis = BASIS_SUF[i][1]; s = s.replace(BASIS_SUF[i][0], ""); break; }
    if (/^window_/.test(s)) { scope = "per window"; s = s.slice(7); }
    if (SHORT[s]) s = SHORT[s];
    var pd = /^(?:fa|false_alarms)_per_(day|night)$/.exec(s);
    if (pd) { per = FAU[pd[1]]; s = "fa_per_hour"; }
    return { base: BASE_ALIAS[s] || s, basis: basis, scope: scope, per: per };
  }
  // a key's label: its metric's name, then its scope and its patients ("Sensitivity, per window, held-out")
  var keyLabel = function (ki) { return MET[ki.base].n + (ki.scope ? ", " + ki.scope : "") + (ki.basis ? ", " + ki.basis : ""); };
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
  var OTHER = { luts: ["Lookup tables (FPGA estimate)", "LUTs"], rtl_vectors: ["Test vectors run on the circuit", ""], rtl_mismatches: ["Mismatches against the model", ""],
    verification_level: ["Verification level", ""], formal_proved: ["Formal proof", ""], candidates: ["Candidates", ""], patients_pass: ["Patients clearing every target", ""], patients_total: ["Patients", ""] };
  function numText(v, unit) {
    var s = Math.abs(v) >= 1000 ? fmt(v) : String(+v.toFixed(Math.abs(v) >= 100 ? 1 : 3));
    if (v === 1 && /^(tiles|gates|levels|LUTs|vectors|transistors)$/.test(unit || "")) unit = unit.replace(/s$/, "");
    return s + (unit ? " " + unit : "");
  }
  // figures a lab tool measured itself (a metric event's source), labelled apart from the agent's own
  var SRC = {
    "score-events": {
      by: "event-scored by the lab",
      keys: { event_sensitivity: ["Event sensitivity", "frac"], fa_per_hour: ["False alarms, event-scored by the lab", "fa"],
        worst_patient_sensitivity: ["Worst-patient sensitivity, event-scored", "frac"], auc: ["Area under the ROC curve, event-scored", ""] }
    }
  };
  function srcText(k, v, unit, spec, source) {
    var s = SRC[source], def = s && s.keys[k], by = s ? s.by : "from the lab's " + source;
    if (num(v) == null) return { label: cap(String(k).replace(/_/g, " ")) + ", " + by, value: String(v) };
    if (def && def[1] === "frac") return { label: def[0], value: ((v > 1.5 ? v / 100 : v) * 100).toFixed(1) + "%" };
    if (def && def[1] === "fa") return { label: def[0], value: fmtV("fa_per_hour", v, spec) };
    var m = metricText(k, v, unit === "FA/h" ? "/h" : unit, spec);
    return { label: def ? def[0] : m.label + ", " + by, value: m.value };
  }
  // one metric as a person reads it: { label, value }; source: the lab tool that measured it, if any
  function metricText(k, v, unit, spec, source) {
    if (typeof source === "string" && source) return srcText(k, v, unit, spec, source);
    var ki = keyInfo(k), b = ki.base;
    if (num(v) == null) return { label: cap(String(k).replace(/_/g, " ")), value: String(v) };
    if (MET[b]) return { label: keyLabel(ki), value: fmtV(b, ratio(b, v) / ki.per, spec) };
    if (LAB[b]) return { label: LAB[b][0], value: numText(v, LAB[b][1]) };
    for (var i = 0; i < CHECKS.length; i++) {
      if (CHECKS[i][1] === b) return { label: CHECKS[i][0] + ", vectors", value: numText(v, "") };
      if (CHECKS[i][2] === b) return { label: CHECKS[i][0] + ", mismatches", value: numText(v, "") };
    }
    if (b === "formal_proved") return { label: "Formal proof", value: v ? "proved equal" : "not proved" };
    if (OTHER[b]) return { label: OTHER[b][0], value: numText(v, OTHER[b][1]) };
    // any other ratio by name (train_accuracy, int_test_accuracy) reads as a percentage, whatever unit word came with it
    if (RATIO.test(String(b)) && ratio(b, v) <= 1.0001) return { label: cap(String(k).replace(/_/g, " ")), value: (ratio(b, v) * 100).toFixed(1) + "%" };
    var u = unit === "/h" ? "per hour" : unit === "um2" ? "µm²" : unit || "";
    return { label: cap(String(k).replace(/_/g, " ")), value: numText(v, u) };
  }

  // a raw metric key written into a sentence (a summary's "heldout_fa_per_hour") read as its label
  // (false alarms read "false alarms per hour" here, as a sentence names the rate), the one-word
  // "heldout" as held-out and "fa per hour" written with spaces as false alarms per hour
  function humanKeys(s) {
    return String(s == null ? "" : s).replace(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g, function (k) {
      var ki = keyInfo(k), b = ki.base;
      if (!(MET[b] || LAB[b] || OTHER[b] || CHECK_KEYS[b])) return k;
      var l = metricText(k, 0, "", null).label;
      if (b === "fa_per_hour") l = l.replace(/^False alarms/, "False alarms per " + (ki.per === 24 ? "day" : ki.per === 12 ? "night" : "hour"));
      return /^[A-Z][a-z]/.test(l) ? l.charAt(0).toLowerCase() + l.slice(1) : l;
    }).replace(/\b(?:fa|false alarms?)[ _]per[ _]h(?:our|r)?\b/gi, function (m) { return /^F[a-z]/.test(m) ? "False alarms per hour" : "false alarms per hour"; })
      .replace(/\b(H|h)eld_?out\b/g, "$1eld-out").replace(/\bHELDOUT\b/g, "HELD-OUT")
      .replace(FRAC_AFTER, function (m, w, mid, v) { return /^(?:validation|test|held.?out)$/i.test(w) && v.indexOf(".") < 0 ? m : w + mid + v.split("/").map(pct).join("/"); })
      .replace(FRAC_BEFORE, function (m, v, sp, w) { return pct(v) + sp + w; })
      .replace(/(?<![\w.:])\d+\.\d{4,}(?!\w|\.\d|:\d)/g, function (m) { return tidyNum(Number(m)); });
  }
  // numbers in a sentence as a person writes them: a ratio named by its metric ("specificity 0.9888",
  // "0.9871 sens") as a percentage with one decimal, any other long float rounded to its size
  // "validation 0.912/0.897": a pair of ratios after the word, each as a percentage
  var FRAC_AFTER = /\b(sensitivity|specificity|accuracy|precision|recall|agreement|validation|test|held[-\u2010\u2011]?out|sens|spec)((?:,\s*(?:held-out|validation|training|per window))*\s*(?:(?:of|was|is|at|reached|hit|=|:|≈|~)\s*)?(?:about\s+)?)((?:0?\.\d+|1\.0+)(?:\/(?:0?\.\d+|1\.0+))+|0?\.\d+|1\.0+|1|0)(?!\d|\.\d|%|\s*(?:per\b|\/|gates?\b))/gi;
  var FRAC_BEFORE = /(?<![\w.])(0?\.\d{2,}|1(?:\.0+)?)(\s+)(sens(?:itivity)?|spec(?:ificity)?)\b(?!\s+(?:targets?|bars?|goals?)\b)/gi;
  var pct = function (v) { return +(Number(v) * 100).toFixed(1) + "%"; };
  function tidyNum(v) { var a = Math.abs(v); return String(a >= 100 ? Math.round(v) : a >= 10 ? +v.toFixed(1) : a >= 1 ? +v.toFixed(2) : +v.toPrecision(3)); }
  // a one-off screening spec with no false-alarm target: judged per recording, never by false alarms over time
  function screenOnly(spec, T) {
    var tt = spec && spec.task_types;
    return Array.isArray(tt) && tt.length === 1 && tt[0] === "screening" && !(T || targetsOf(spec)).some(function (t) { return t.metric === "fa_per_hour"; });
  }
  // the lab's verification level: a number reads "level 2", a name ("bit-exact simulation") as itself
  var levelText = function (l) { return typeof l === "number" || /^\d+$/.test(String(l)) ? "level " + l : String(l); };

  /* ---------- a run file in a viewer: an image as the image, a binary file named, never its bytes as text ---------- */
  var BIN_KIND = { gds: "a GDS layout file", gdsii: "a GDS layout file", gds2: "a GDS layout file", oas: "an OASIS layout file", oasis: "an OASIS layout file", vcd: "a waveform dump", fst: "a waveform dump",
    npz: "a NumPy archive", npy: "a NumPy array", pt: "a PyTorch file", pth: "a PyTorch file", pkl: "a Python pickle", onnx: "an ONNX model", h5: "an HDF5 file", zip: "a zip archive", gz: "a compressed file", tar: "a tar archive", pdf: "a PDF", bin: "a binary file" };
  function fileKind(path) {
    var x = (/\.([a-z0-9]+)$/i.exec(String(path || "")) || [, ""])[1].toLowerCase();
    return x === "svg" ? "svg" : /^(png|jpe?g|gif|webp|bmp)$/.test(x) ? "image" : BIN_KIND[x] ? "binary" : "text";
  }
  // text that came from bytes which are not UTF-8 (a NUL, or the replacement character the backend put in)
  var looksBinary = function (t) { t = String(t || "").slice(0, 4096); var n = (t.match(/[\u0000�]/g) || []).length; return n > 8 || (t.length > 0 && n / t.length > 0.02); };
  var fileNote = function (path, kind) {
    var name = String(path || "").split("/").pop(), x = (/\.([a-z0-9]+)$/i.exec(name) || [, ""])[1].toLowerCase();
    return kind === "image" ? name + " is an image. This backend sends run files as text only, so the image cannot be shown here."
      : name + " is " + (BIN_KIND[x] || "a binary file") + ", not text, so it is not shown here.";
  };
  // an image file's bytes, from a backend that serves them (file?path=...&raw=1 answered with an image type); null otherwise
  function rawImage(base, token, id, path) {
    if (!base || typeof fetch !== "function") return Promise.resolve(null);
    return fetch(base + "/api/runs/" + encodeURIComponent(id) + "/file?path=" + encodeURIComponent(path) + "&raw=1", { headers: { "X-ChipIn-Token": token || "" }, cache: "no-store" })
      .then(function (r) { return r.ok && /^image\//.test(r.headers.get("Content-Type") || "") ? r.blob() : null; })
      .catch(function () { return null; });
  }
  // fills el with the file: path, its text (or null when not read yet), and opts { base, token, id } to fetch an image's bytes;
  // returns true when it handled the file (an image, an SVG or a binary), false when the text is to be shown as it is
  function fileView(el, path, text, opts) {
    var kind = fileKind(path), name = String(path || "").split("/").pop();
    var note = function (k) { el.innerHTML = '<p class="cf-sub">' + esc(fileNote(path, k)) + "</p>"; };
    if (kind === "image") {
      el.innerHTML = '<p class="cf-sub">Opening the image…</p>';
      rawImage(opts && opts.base, opts && opts.token, opts && opts.id, path).then(function (b) {
        if (!b) { note("image"); return; }
        el.innerHTML = '<img alt="' + esc(name) + '" style="display:block;max-width:100%;height:auto;border:1px solid #e3e6ec;border-radius:8px;background:#fff">';
        el.querySelector("img").src = URL.createObjectURL(b);
      });
      return true;
    }
    if (kind === "binary") { note("binary"); return true; }
    if (text == null) return false;
    if (kind === "svg" && /<svg[\s>]/i.test(text)) { el.innerHTML = '<img alt="' + esc(name) + '" style="display:block;max-width:100%;height:auto;background:#fff">'; el.querySelector("img").src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(text); return true; }
    if (looksBinary(text)) { note("binary"); return true; }
    return false;
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
    return { designs: {}, order: [], chips: {}, units: {}, run: {}, runUnits: {}, src: {}, chosen: null, spec: null,
      cost: { orch: null, agents: {}, total: null, totalMode: false, runTotal: null }, subs: {}, subOrder: [], merged: {}, mergedOrder: [] };
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
        // every id a record has carried keeps its label (a renamed or recompiled record drops the old one from
        // f.designs), so a reason that names the agent's working id still reads as that chip's name
        var lb = f.labels || (f.labels = {});
        if (typeof d.label === "string" && d.label) { lb[d.id] = d.label; if (prev && prev !== d.id && !lb[prev]) lb[prev] = d.label; }
        return { id: d.id, isNew: same < 0 && took < 0, renamed: renamed, d: d };
      }
      case "metric": {
        if (typeof ev.key !== "string") break;
        var chip = typeof ev.chip === "string" && ev.chip ? ev.chip : null, v = ratio(ev.key, ev.value);
        if (typeof ev.source === "string" && ev.source) {
          // a lab tool's own figure (score-events): kept apart, so it never replaces the agent's figure of the same key
          var sm = f.src[chip || ""] || (f.src[chip || ""] = {});
          sm[ev.key] = { value: ev.value, unit: ev.unit || "", source: ev.source };
          if (ev.agent && f.subs[ev.agent]) f.subs[ev.agent].latest = { key: ev.key, value: ev.value, unit: ev.unit || "", source: ev.source };
          break;
        }
        var vals = chip ? f.chips[chip] || (f.chips[chip] = {}) : f.run, units = chip ? f.units[chip] || (f.units[chip] = {}) : f.runUnits;
        vals[ev.key] = v; if (ev.unit) units[ev.key] = ev.unit;
        if (ev.agent && f.subs[ev.agent]) f.subs[ev.agent].latest = { key: ev.key, value: v, unit: ev.unit || "" };
        break;
      }
      case "chosen": if (typeof ev.chip === "string" && ev.chip) f.chosen = ev.chip; break;
      case "cost": {
        var c = f.cost, part = costPart(ev), own = num(ev.agent_usd);
        if (num(ev.run_total_usd) != null) c.runTotal = ev.run_total_usd;
        if (typeof ev.agent === "string" && ev.agent) { if (own != null) part.usd = own; c.agents[ev.agent] = part; }
        else if (num(ev.subagents_usd) != null || c.totalMode) { c.totalMode = true; c.total = part; }
        else { if (own != null) part.usd = own; c.orch = part; }
        break;
      }
      case "subagent.started": {
        var key = ev.agent || ev.id || ("sub" + ev.seq);
        if (!f.subs[key]) f.subOrder.push(key);
        f.subs[key] = { key: key, stage: ev.stage || "", strategy: ev.strategy || ev.name || "", name: typeof ev.name === "string" ? ev.name : "", model: ev.model || "", state: "running", latest: null, result: "" };
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
  // { usd, tokens_in, tokens_out, summaries_usd }; usd is run_total_usd when the events carry it
  // (it already counts the summaries, so summaries_usd is then null), else the older reckoning
  function cost(f) {
    var c = f.cost, add = function (a, b) { return a == null ? b : b == null ? a : a + b; }, out;
    if (c.total) out = { usd: c.total.usd, tokens_in: c.total.tokens_in, tokens_out: c.total.tokens_out, summaries_usd: c.total.summaries_usd };
    else {
      var ids = Object.keys(c.agents);
      if (!c.orch && !ids.length) return null;
      out = c.orch ? { usd: c.orch.usd, tokens_in: c.orch.tokens_in, tokens_out: c.orch.tokens_out, summaries_usd: c.orch.summaries_usd } : { usd: null, tokens_in: null, tokens_out: null, summaries_usd: null };
      ids.forEach(function (k) { var a = c.agents[k]; out.usd = add(out.usd, a.usd); out.tokens_in = add(out.tokens_in, a.tokens_in); out.tokens_out = add(out.tokens_out, a.tokens_out); });
    }
    if (num(c.runTotal) != null) { out.usd = c.runTotal; out.summaries_usd = null; }
    return out;
  }
  function funnel(f, T) {
    var ds = designs(f), cand = num(f.run.candidates);
    return {
      proposed: Math.max(ds.length, cand || 0),
      scored: ds.filter(function (d) { return Object.keys(d.metrics).some(function (k) { return num(d.metrics[k]) != null; }); }).length,
      compiled: ds.filter(function (d) { return num(d.gates) > 0; }).length,
      verified: ds.filter(function (d) { return d.verified && typeof d.verified === "object"; }).length,
      clear: ds.filter(function (d) { return d.verified && typeof d.verified === "object" && passAll(T || [], d); }).length, // only a verified design can clear them, so this count never passes Verified
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

  /* ---------- a chip named in words ---------- */
  // A chip id is a hash (e51a3da485f2) or the agent's working name (p2-lin-05): never the name a
  // person reads. chipName gives words: the design record's label read in plain language, else what
  // the chip's ir.json computes (when the run's files are at hand), else its measured size.
  var and = function (a) { return a.length < 2 ? a[0] || "" : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]; };
  var FEAT = [[/\bll\d*\b/i, "line length"], [/\b(?:bd\d*|band\d+)\b/i, "band energy"], [/\bzc\d*\b/i, "zero crossings"], [/\bsd\d*\b/i, "amplitude"]];
  function humanLabel(s) {
    s = String(s == null ? "" : s).replace(/^[A-Z]\d+\s+/, "").trim();
    if (!s) return "";
    var alt = /alkaid/i.test(s) ? ", alternative synthesis" : "";
    if (/[<>=]/.test(s) && s.length <= 40) { // a written-out rule (3*bd1+1*zc1 >= 208), its features in words
      var r = s.replace(/\s*\(?\balkaid\b\)?/gi, "").replace(/\s*>=\s*/g, " ≥ ").replace(/\s*<=\s*/g, " ≤ ").replace(/\s*([<>])\s*/g, " $1 ").replace(/\s*\+\s*/g, " + ").replace(/\s*\*\s*/g, "×");
      FEAT.forEach(function (p) { r = r.replace(new RegExp(p[0].source, "gi"), p[1]); });
      return "Rule " + r.trim() + alt;
    }
    if (/[*<>=]|\bt\d{2,}\b/.test(s)) { // a longer rule: which features it compares
      var fs = []; FEAT.forEach(function (p) { if (p[0].test(s) && fs.indexOf(p[1]) < 0) fs.push(p[1]); });
      return "Threshold rule" + (fs.length ? " on " + and(fs) : "") + alt;
    }
    s = s.replace(/\s*\(?\balkaid\b\)?/gi, "").replace(/\bint\s+MLP\b/gi, "small integer network").replace(/\bMLP\b/g, "small network").replace(/\bint\b/gi, "integer")
      .replace(/\b(\d+)h\b/g, "$1 hidden units").replace(/\b(\d+)f\b/g, function (m, n) { return n + (n === "1" ? " feature" : " features"); }).replace(/\b(\d+)ch\b/g, "$1 channels")
      .replace(/(\d+)-bit w\b/g, "$1-bit weights").replace(/\bhard-neg\b/gi, "hard-negative").replace(/\bLOPO\b/g, "leave-one-patient-out");
    FEAT.forEach(function (p) { s = s.replace(new RegExp(p[0].source, "gi"), p[1]); });
    return cap(s.replace(/\s+/g, " ").replace(/\s+,/g, ",").replace(/,\s*$/, "").trim()) + alt;
  }
  // what a chipir/1 file computes, in a few words
  function irName(text) {
    var j = null; try { j = JSON.parse(text); } catch (e) { return ""; }
    if (!j || !Array.isArray(j.nodes)) return "";
    var ops = j.nodes.map(function (n) { return n && String(n.op || ""); }), inp = Array.isArray(j.inputs) && j.inputs[0] || {};
    var layers = j.nodes.filter(function (n) { var W = n && n.op === "matvec" && Array.isArray(n.W) ? n.W : []; return [].concat.apply([], W).length > 1; }).length;
    var kind = ops.some(function (o) { return /tree|lut/i.test(o); }) ? "Decision trees" : layers === 1 ? "Linear classifier" : layers > 1 ? "Small network, " + layers + " layers" : ops.indexOf("cmp") >= 0 ? "Threshold rule" : "";
    if (!kind) return "";
    return kind + (num(inp.lanes) ? " on " + inp.lanes + " input" + (inp.lanes === 1 ? "" : "s") + (num(inp.bits) ? " of " + inp.bits + " bits" : "") : "");
  }
  // { name, id, from: "label" | "ir" | "size" | "" }; opts.files: the run's files [{ path, text }]
  function chipName(f, id, opts) {
    if (!id) return { name: "", id: "", from: "" };
    var rid = id, rec = f.designs[id], nm = humanLabel(rec && rec.label || (f.labels || {})[id]);
    if (nm) return { name: nm, id: rid, from: "label" };
    var files = opts && Array.isArray(opts.files) ? opts.files : [], ir = files.filter(function (x) { return x && typeof x.path === "string" && x.path.slice(-("/chips/" + rid + "/ir.json").length) === "/chips/" + rid + "/ir.json" && x.text; })[0];
    nm = ir ? irName(ir.text) : "";
    if (nm) return { name: nm, id: rid, from: "ir" };
    var g = rec && num(rec.gates) > 0 ? rec.gates : num((f.chips[rid] || {}).gates) > 0 ? f.chips[rid].gates : null;
    return { name: g != null ? "Chip of " + fmt(g) + " gates" : "Unnamed chip", id: rid, from: g != null ? "size" : "" };
  }
  // the name, with the technical id small after it (and on hover)
  function chipNameHTML(f, id, opts) {
    var c = chipName(f, id, opts);
    return c.id ? '<span class="cf-nm">' + esc(c.name) + '</span> <span class="cf-id" title="Technical id of this chip">' + esc(c.id) + "</span>" : "";
  }
  // a sentence the agent wrote, with chip ids, subagent ids and its shorthand read in words
  function shortStrategy(a) {
    var s = String(a && a.strategy || "").replace(/^Strategy\s*[A-Z]?\d*\s*[:-]?\s*/i, "").replace(/…$/, "");
    var cut = s.search(/\s*[(:;]|\s+-\s/); if (cut > 3) s = s.slice(0, cut);
    return s.trim() || String(a && (a.name || a.key) || "");
  }
  // a subagent named by what it tried, in words, short
  function stratName(f, a, opts) { return cap(clip(plainWords(f, shortStrategy(a), opts), 56)); }
  // chip ids in a sentence read as the chips' names
  function idWords(f, s, opts) {
    s = String(s == null ? "" : s);
    var ids = {}; Object.keys(f.designs).concat(Object.keys(f.labels || {}), Object.keys(f.chips)).forEach(function (k) { if (k && k.length >= 4) ids[k] = 1; });
    var list = Object.keys(ids).sort(function (a, b) { return b.length - a.length; }).map(function (k) { return k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); });
    if (list.length) s = s.replace(new RegExp("(^|[^\\w-])(" + list.join("|") + ")(?![\\w-])", "g"), function (m, pre, k) { return pre + chipName(f, k, opts).name.replace(/^./, function (c) { return c.toLowerCase(); }); });
    return s;
  }
  function plainWords(f, s, opts) {
    s = idWords(f, String(s == null ? "" : s).replace(/\*\*([^*]+)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1"), opts);
    s = s.replace(/\ba(\d{1,2})\b(?:-alk)?(?:'s)?/g, function (m, n) { var a = f.subs["a" + n]; var w = clip(idWords(f, shortStrategy(a), opts), 40); return a ? "“" + (/^[A-Z][a-z]/.test(w) ? w.charAt(0).toLowerCase() + w.slice(1) : w) + "”" : m; });
    return humanKeys(s.replace(/\bval\s+sens\b/gi, "validation sensitivity").replace(/\bval\b/gi, "validation").replace(/\bsens\b/gi, "sensitivity").replace(/\bspec\b(?!\.md)/gi, "specificity")
      .replace(/\bFA\/h\b/gi, "false alarms per hour").replace(/\bum2\b/g, "µm²").replace(/\bGBT\b/g, "gradient boosting").replace(/\blogreg\b/gi, "logistic regression").replace(/\bintnn neuron\b/gi, "integer neuron").replace(/\bintnn\b/gi, "integer network"));
  }
  // a merge reason as short reasons: one per clause the agent wrote
  function reasons(f, why, opts) {
    // split at a semicolon or a sentence end outside brackets
    var t = plainWords(f, why, opts), out = [], cur = "", depth = 0;
    for (var i = 0; i < t.length; i++) {
      var c = t[i];
      if (c === "(") depth++; else if (c === ")") depth = Math.max(0, depth - 1);
      if (!depth && (c === ";" || c === "." && /\s[A-Z“]/.test(t.substr(i + 1, 2))) && /\s/.test(t[i + 1] || "")) { out.push(cur); cur = ""; continue; }
      cur += c;
    }
    out.push(cur);
    return out.map(function (x) { return x.replace(/\.$/, "").trim(); }).filter(Boolean).map(cap);
  }

  /* ---------- shared panels ---------- */
  var BAR_CSS = "";
  // one quiet line for a design record that is another compile of an earlier design (variant_of)
  function variantHTML(d) {
    var v = d && typeof d.variant_of === "string" ? d.variant_of : "";
    return v ? '<p class="cf-var" data-variant-of="' + esc(v) + '">Variant of <span class="cf-vid">' + esc(v) + "</span></p>" : "";
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
    var noFA = screenOnly(m.spec, T); // a one-off screening test is judged per recording, so no false-alarm rate is shown for it
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
    if (lvl != null) lab.push(["Verification level", esc(levelText(lvl))]);
    // the lab's prove-equivalence proves the gate netlist against the RTL (abc cec); the match to the model
    // rests on the simulated vectors, so it is named as such only when vectors ran with no mismatch
    var simOK = CHECKS.some(function (c, i) { var n = num(mm[c[1]]), x = num(mm[c[2]]); if (i === 0) { if (n == null) n = num(vf.vectors); if (x == null) x = num(vf.mismatches); } return n > 0 && x === 0; });
    if (proved != null) lab.push(["Formal proof", proved ? "netlist proved equal to the RTL" + (simOK ? "; model match by simulation" : "") : "not proved"]);
    // a lab tool's own figures (a metric with a source, e.g. score-events), each its own labelled row;
    // for the chosen chip also the ones the lab sent without a chip
    var SORD = ["event_sensitivity", "worst_patient_sensitivity", "fa_per_hour", "auc"], sord = function (k) { var i = SORD.indexOf(k); return i < 0 ? 99 : i; };
    var srcRows = function (sm, tail) {
      Object.keys(sm || {}).sort(function (a, b) { return sord(a) - sord(b) || (a < b ? -1 : 1); }).forEach(function (k) {
        if (noFA && keyInfo(k).base === "fa_per_hour") return;
        var e = sm[k], t = metricText(k, e.value, e.unit, m.spec, e.source);
        lab.push([t.label + tail, esc(t.value)]);
      });
    };
    var own = f.src[id] || {};
    srcRows(own, "");
    if (id === f.chosen && f.src[""]) { var loose = {}; Object.keys(f.src[""]).forEach(function (k) { if (!own[k]) loose[k] = f.src[""][k]; }); srcRows(loose, ", no chip named"); }
    // what the agent reported for this chip: one row per measure and set of patients
    var BW = function (b) { return b === "held-out" ? "test (held-out)" : b; };
    var agent = {}, order = [], put = function (label, k, v, prio, b) { var key = label; if (!agent[key]) order.push(key); if (!agent[key] || agent[key].prio < prio) agent[key] = { label: label, k: k, v: v, prio: prio, b: b }; };
    Object.keys(mm).forEach(function (k) {
      if (seen[k]) return;
      var ki = keyInfo(k), v = num(mm[k]);
      if (v == null || (noFA && ki.base === "fa_per_hour")) return;
      if (MET[ki.base]) {
        // the basis the key itself names (validation_, test_, _train); none readable, no basis word
        var b = ki.basis || "";
        // a per-window figure is its own row and is not judged against a per-recording target
        put(MET[ki.base].n + (ki.scope ? ", " + ki.scope : "") + (b ? ", " + BW(b) : ""), ki.scope ? null : ki.base, ki.scope ? fmtV(ki.base, ratio(ki.base, v) / ki.per, m.spec) : ratio(ki.base, v) / ki.per, (/^chip_/.test(k) ? 3 : ki.basis ? 2 : 1), b);
      } else if (!LAB[ki.base] && !CHECK_KEYS[k]) { var mt = metricText(k, v, uu[k], m.spec); put(mt.label, null, mt.value, 1, ""); }
    });
    if (rec) Object.keys(rec.metrics).forEach(function (k) { var v = num(rec.metrics[k]); if (v == null || !MET[k] || (noFA && k === "fa_per_hour")) return; var b = rec.basis === "test" ? "held-out" : rec.basis === "validation" ? "validation" : rec.basis === "train" || rec.basis === "training" ? "training" : ""; put(MET[k].n + (b ? ", " + BW(b) : ""), k, v, 0, b); });
    var rank = function (r) { return (r.b === "validation" ? 0 : r.b === "held-out" ? 1 : 2) * 10 + (r.k === "sensitivity" ? 0 : r.k === "fa_per_hour" ? 1 : r.k === "specificity" ? 2 : 3); };
    var ag = order.map(function (k) { return agent[k]; }).sort(function (a, b) { return rank(a) - rank(b); });
    var row = function (r) { return '<div class="irow"><span>' + esc(r[0]) + "</span><b>" + r[1] + "</b></div>"; };
    var mark = dataMark(m.spec, rec ? [rec] : []);
    return '<div class="vh"><p class="cf-k">' + (id === m.chosenId ? "Chosen chip:" : "Chip:") + " " + chipNameHTML(f, id, { files: m.files }) + " " + mark + "</p>" + variantHTML(rec) + '<h2>The chip</h2><p class="vs"' + tipA("Two kinds of figure: what the chip lab measured on the circuit, and what the agent computed on the patients.") + '>Lab-measured circuit figures, then agent-computed accuracy.</p></div>' +
      '<section class="stage cf-sec" data-sec="lab"><h3 class="cf-h3">Measured by the chip lab</h3>' + (lab.length || checks.length ? '<div class="cf-kv">' + lab.map(function (r) { return row([r[0], r[1]]); }).join("") + "</div>" : '<p class="cf-sub">The lab has not reported figures for this chip yet.</p>') +
      (checks.length ? '<h4 class="cf-h4">Vectors checked against the model</h4><div class="cf-kv">' + checks.map(function (c) { return row([c[0], esc(c[1])]); }).join("") + "</div>" + (checks.length > 1 ? '<p class="cf-sub"' + tipA("Each kind of check runs its own set of input vectors, so the counts differ.") + ">Each check uses its own vectors.</p>" : "") : "") + "</section>" +
      '<section class="stage cf-sec" data-sec="agent"><h3 class="cf-h3">Reported by the agent</h3>' + (ag.length ? '<div class="cf-kv">' + ag.map(function (r) {
        var tg = r.k ? T.filter(function (x) { return x.metric === r.k; })[0] : null, txt = r.k ? fmtV(r.k, r.v, m.spec) : r.v;
        return row([r.label, esc(txt) + (tg ? '<span class="cf-tg">target ' + esc(fmtT(tg, m.spec)) + "</span>" + pf(meets(tg, r.v)) : "")]);
      }).join("") + '</div><p class="cf-sub"' + tipA("Computed by the agent on " + (/mk sim/.test(mark) ? "synthetic " : mark ? "public " : "") + "patient data, not measured by the lab.") + ">By the agent" + (/mk sim/.test(mark) ? " on synthetic data" : mark ? " on public data" : "") + ", not measured by the lab.</p>" : '<p class="cf-sub">The agent reported no accuracy figures for this chip.</p>') + "</section>";
  }

  // Subagent batches: one line per stage that opens to its entries. open: { stage: true }
  function subsHTML(f, spec, open, opts) {
    opts = opts || {};
    if (!f.subOrder.length) return opts.empty ? '<section class="pan cf-subs" aria-label="Subagent batches"><div class="cf-subh"><h2>Subagent batches</h2></div><p class="cf-sub">' + esc(opts.empty) + "</p></section>" : "";
    var no = { files: opts.files }, who = function (k) { return f.subs[k] ? stratName(f, f.subs[k], no) : k; };
    var kept = {}; f.mergedOrder.forEach(function (s) { (f.merged[s].kept || []).forEach(function (k) { kept[k] = 1; }); });
    var stages = []; f.subOrder.forEach(function (k) { var s = f.subs[k].stage || "other"; if (stages.indexOf(s) < 0) stages.push(s); });
    stages.sort(function (a, b) { var i = STAGES.indexOf(a), j = STAGES.indexOf(b); return (i < 0 ? 99 : i) - (j < 0 ? 99 : j); });
    var fin = f.subOrder.filter(function (k) { return f.subs[k].state !== "running"; }).length;
    var mark = dataMark(spec, designs(f));
    return '<section class="pan cf-subs" aria-label="Subagent batches"><div class="cf-subh"><h2>Subagent batches</h2><span class="cf-sub">' + fin + " of " + f.subOrder.length + " finished</span>" + mark + "</div>" + stages.map(function (s) {
      var list = f.subOrder.filter(function (k) { return (f.subs[k].stage || "other") === s; }).map(function (k) { return f.subs[k]; }), mg = f.merged[s];
      var dots = list.map(function (a) { return '<i class="' + (kept[a.key] ? "kept " : "") + (a.state === "running" ? "" : a.state) + '" title="' + esc(who(a.key) + ": " + (a.state === "running" ? "running" : a.state) + (kept[a.key] ? ", kept" : "")) + '"></i>'; }).join("");
      // the merge read as short reasons in words: what was kept, then why, each clause with its own numbers
      var why = mg && mg.why ? reasons(f, mg.why, no) : [], keptN = mg ? mg.kept.map(who) : [];
      var kept0 = mg ? (keptN.length ? "Kept " + keptN.join(" · ") : "Kept none") : "", line = mg ? kept0 + (why.length ? ": " + why[0].charAt(0).toLowerCase() + why[0].slice(1) : "") : list.some(function (a) { return a.state === "running"; }) ? "running" : "waiting for the merge";
      return '<details class="cf-sb" data-batch="' + esc(s) + '"' + (open && open[s] ? " open" : "") + "><summary><b>" + esc(STAGE_N[s] || cap(s)) + '</b><span class="cf-dots" aria-label="' + esc(pl(list.length, "subagent")) + '">' + dots + '</span><span class="cf-line"><span class="cf-short">' + esc(line) + '</span><span class="cf-kept">' + esc(mg ? kept0 : line) + "</span></span></summary>" +
        '<div class="cf-sbb">' + (why.length ? '<ul class="cf-why" aria-label="Why">' + why.map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("") + "</ul>" : "") + list.map(function (a) {
          var lt = a.latest ? metricText(a.latest.key, a.latest.value, a.latest.unit, spec, a.latest.source) : null, full = plainWords(f, String(a.strategy || "").replace(/^Strategy\s*[A-Z]?\d*\s*[:-]?\s*/i, ""), no);
          return '<div class="cf-se' + (kept[a.key] ? " kept" : "") + '"><span class="cf-st"' + tipA(full) + ' title="Subagent ' + esc(a.key) + '">' + esc(stratName(f, a, no)) + (kept[a.key] ? ' <span class="cf-kb">kept</span>' : a.state === "failed" ? ' <span class="cf-kb no">failed</span>' : "") + "</span>" + (lt ? '<span class="cf-sm">' + esc(lt.label) + ": " + esc(lt.value) + "</span>" : "") + "</div>";
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
    ".cf-var{font-size:12px;color:var(--i600);margin:0 0 4px}.cf-vid{font-family:var(--mono);font-size:11px;color:var(--i700)}",
    ".cf-sub{font-size:12.5px;color:var(--i600);margin:4px 0 8px;line-height:1.5}",
    ".cf-kv{max-width:620px}.cf-kv .irow b{display:inline-flex;flex-wrap:wrap;justify-content:flex-end;align-items:center;gap:4px 8px;text-align:right}",
    ".cf-tg{font-weight:400;color:var(--i600);font-size:12px}",
    ".cf-subs{padding:10px 16px 8px}.cf-subh{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 0 4px}.cf-subh h2{font-size:13px;font-weight:650;margin:0}.cf-subh .cf-sub{margin:0}",
    ".cf-sb{border-top:1px solid var(--hair)}.cf-sb summary{display:grid;grid-template-columns:90px auto minmax(0,1fr);gap:4px 12px;align-items:center;padding:6px 0;cursor:pointer;list-style:none;font-size:12.5px}.cf-sb summary::-webkit-details-marker{display:none}",
    ".cf-sb summary b{font-weight:600}.cf-sb summary b::before{content:'';display:inline-block;width:0;height:0;border:4px solid transparent;border-left:5px solid var(--i500);margin-right:6px;vertical-align:1px;transition:transform .15s}.cf-sb[open] summary b::before{transform:rotate(90deg);transform-origin:2px 4px}",
    ".cf-sb summary:hover .cf-line{color:var(--i900)}.cf-sb summary:focus-visible{outline:2px solid var(--blue7);outline-offset:2px;border-radius:6px}",
    ".cf-line{color:var(--i700);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}.cf-sb[open] .cf-short,.cf-sb:not([open]) .cf-kept{display:none}",
    ".cf-dots{display:flex;gap:4px;flex-wrap:wrap}.cf-dots i{width:10px;height:10px;border-radius:50%;border:1.5px solid var(--blue6,#3d6df0);box-sizing:border-box}",
    ".cf-dots i.done{background:var(--blue6,#3d6df0)}.cf-dots i.failed{background:#ef4444;border-color:#ef4444}.cf-dots i.kept{box-shadow:0 0 0 2px #fff,0 0 0 3.5px var(--i900)}",
    ".cf-sbb{padding:0 0 10px 14px;display:flex;flex-direction:column;gap:6px}",
    ".cf-why{margin:0 0 4px;padding:8px 10px 8px 24px;font-size:12.5px;color:var(--i800);line-height:1.5;overflow-wrap:anywhere;background:rgb(59 130 246/.06);border-left:3px solid var(--blue6,#3d6df0);border-radius:0 6px 6px 0}.cf-why li+li{margin-top:3px}",
    ".cf-se{display:flex;flex-direction:column;gap:1px;font-size:12px;line-height:1.45;color:var(--i800);padding-left:10px;border-left:2px solid var(--hair)}.cf-se.kept{border-left-color:var(--i900)}",
    ".cf-st{overflow-wrap:anywhere;font-weight:550}.cf-sm{color:var(--i600);font-variant-numeric:tabular-nums;overflow-wrap:anywhere}",
    ".cf-kb{display:inline-block;font-size:10.5px;font-weight:600;padding:0 6px;border-radius:9px;background:var(--i900);color:#fff;vertical-align:1px}.cf-kb.no{background:#fee2e2;color:#b91c1c}",
    ".cf-nm{font-weight:600;color:var(--i900)}.cf-id{font-family:var(--mono);font-size:10.5px;color:var(--i550,#7a8194);font-weight:400}",
    "@media (max-width:767px){.cf-sb summary{grid-template-columns:auto minmax(0,1fr)}.cf-line{grid-column:1/-1;white-space:normal}.cf-sbb{padding-left:0}.cf-kv .irow{flex-wrap:wrap}}"
  ].join("\n");
  document.head.appendChild(css);

  window.ChipInFold = {
    version: 1, scrub: scrub, repoPath: repoPath, scrubEvent: scrubEvent, create: create, fold: fold, designs: designs, cost: cost, funnel: funnel, heldOut: heldOut,
    subsHTML: subsHTML, wireSubs: wireSubs, chipHTML: chipHTML, variantHTML: variantHTML,
    chipName: chipName, chipNameHTML: chipNameHTML, humanLabel: humanLabel, plainWords: plainWords,
    targetsOf: targetsOf, fmtV: fmtV, fmtT: fmtT, meets: meets, passAll: passAll, metaOf: metaOf, MET: MET, FAU: FAU, faUnit: faUnit,
    dataMark: dataMark, metricText: metricText, humanKeys: humanKeys, screenOnly: screenOnly, levelText: levelText, fileKind: fileKind, fileView: fileView, keyInfo: keyInfo, sizeOf: sizeOf, ratio: ratio, normDesign: normDesign
  };
})();
