/*
 * i1-whychip.js: the "Why this chip" card on the Chip tab of a finished backend or recorded run.
 * Defines window.ChipInWhyChip.
 *
 * html(m): m = the arguments ChipInFold.chipHTML gets ({ f, spec, T, id, chosenId, running }). Returns "" unless
 * the run has ended and the chip shown is its chosen chip. Short because-lines, each from the run's own data:
 *   targets       the chosen chip's figures against each target, per data basis, misses first
 *   verified      compiled to gates and matched its model (the same checks the Chip tab lists)
 *   price         gate count, unit cost from ChipInModels.costModel, the pad-limited threshold (estimated)
 *   alternatives  which rule the data shows, and the closest designs not chosen, each with its reason
 *   battery       the user's battery and cost answers, and battery life from deviceBudget and batteryClass
 *   regulation    entries of ChipInRegulation.sources() that apply to this device, with their source links
 * A line the run's data cannot support is left out.
 */
(function () {
  "use strict";
  var F = function () { return window.ChipInFold; };
  var M = function () { return window.ChipInModels; };
  var CSS = [
    ".wc{background:#f7f9ff;border:1px solid #dbe3f8;border-left:4px solid var(--blue7);border-radius:14px;box-shadow:var(--sh-hair);padding:12px 18px 10px;margin:10px 0 4px;max-width:880px}",
    ".wc-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 0 6px}",
    ".wc-h h2{font-size:16px;font-weight:700;margin:0;color:var(--blue7)}",
    ".wc-r{font-size:13.5px;color:var(--i800);line-height:1.5;margin:0;padding:6px 0;border-top:1px solid var(--hair)}",
    ".wc-r:first-of-type{border-top:0}",
    ".wc-r>b{color:var(--i900);font-weight:650}",
    ".wc-r.miss>b{color:#b91c1c}",
    ".wc-r ul{margin:3px 0 0;padding:0 0 0 16px}.wc-r li{margin:1px 0}",
    ".wc-r a{color:var(--blue7);font-weight:600}",
    ".wc-r .cf-id{margin-left:2px}",
    ".wc-d{border-top:1px solid var(--hair);margin-top:4px;padding-top:6px;font-size:12.5px;color:var(--i700)}",
    ".wc-d>summary{cursor:pointer;color:var(--blue7);font-weight:600;width:fit-content;max-width:100%}",
    ".wc-d>div{margin-top:6px;line-height:1.5}.wc-d p{margin:0 0 4px}.wc-d ul{margin:2px 0 6px;padding-left:16px}",
    ".wc-f{font-size:11.5px;color:var(--i600);margin:6px 0 0}",
    "@media (max-width:767px){.wc{padding:10px 12px 8px}.wc-r{font-size:13px}}"
  ].join("\n");
  function css() {
    if (document.getElementById("wc-styles")) return;
    var s = document.createElement("style"); s.id = "wc-styles"; s.textContent = CSS; document.head.appendChild(s);
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  var num = function (v) { return typeof v === "number" && isFinite(v) ? v : null; };
  var fmt = function (n) { return Math.round(n).toLocaleString("en-GB"); };
  var money = function (x) { return "$" + Math.abs(x).toFixed(2); };
  var pl = function (n, w) { return fmt(n) + " " + w + (n === 1 ? "" : "s"); };
  var lc = function (s) { return /^[A-Z][a-z]/.test(s) ? s.charAt(0).toLowerCase() + s.slice(1) : s; };
  function est(txt, field) { return '<span class="est" title="' + esc(M().describeEstimate(field)) + '">' + txt + "</span>"; }
  var SHORT = { "primary coin cell": "a coin cell", "rechargeable lithium": "a rechargeable cell", "larger pack or mains": "a larger pack or mains" };

  // the kinds of check the Chip tab lists, [label, vectors key, mismatches key] (copied from ../i1-fold.js, which does not export it)
  var CHECKS = [
    ["lab verification against the model", "verify_vectors", "verify_mismatches"],
    ["simulation against the model", "vectors_checked", "mismatches"],
    ["bit-exact simulation", "bitexact_vectors", "bitexact_mismatches"],
    ["simulation on the run's data", "sim_vectors", "sim_mismatches"],
    ["RTL simulation", "rtl_sim_vectors", "rtl_sim_mismatches"],
    ["RTL simulation, random vectors", "rtl_sim_random_vectors", "rtl_sim_random_mismatches"]
  ];
  var RUN_LAB = /^(gates|depth|verification_level|formal_proved)$/;

  // the lab's figures for the chip, as the Chip tab reads them: its own, else (an older backend) the run's for the chosen chip
  function labOf(f, id) {
    var mm = f.chips[id] || {};
    if (!Object.keys(mm).length && id === f.chosen) {
      var out = {};
      Object.keys(f.run).forEach(function (k) { if (RUN_LAB.test(k) || CHECKS.some(function (c) { return c[1] === k || c[2] === k; })) out[k] = f.run[k]; });
      return out;
    }
    return mm;
  }
  function gatesOf(f, d) {
    if (d && num(d.gates) != null) return d.gates;
    var mm = d ? labOf(f, d.id) : {};
    return num(mm.gates);
  }
  var verOK = function (d) { return !!(d && d.verified && typeof d.verified === "object" && d.verified.mismatches === 0); };
  var verBad = function (d) { return !!(d && d.verified && typeof d.verified === "object" && num(d.verified.mismatches) > 0); };
  var BASIS = function (b) { return b === "held-out" ? "test (held-out)" : b || "(basis not stated)"; };
  var mis = function (n) { return n === 1 ? "1 mismatch" : fmt(n) + " mismatches"; };

  // the chosen chip's accuracy figures: one per metric and data basis, the Chip tab's choice of key
  function figures(f, id, rec) {
    var Fd = F(), mm = labOf(f, id), out = {};
    var put = function (base, b, v, prio) { var k = base + "|" + b; if (!out[k] || out[k].prio < prio) out[k] = { base: base, b: b, v: v, prio: prio }; };
    Object.keys(mm).forEach(function (k) {
      var ki = Fd.keyInfo(k), v = num(mm[k]);
      if (v == null || !Fd.MET[ki.base] || ki.scope) return;
      put(ki.base, ki.basis || "", Fd.ratio(ki.base, v) / ki.per, /^chip_/.test(k) ? 3 : ki.basis ? 2 : 1);
    });
    if (rec) Object.keys(rec.metrics || {}).forEach(function (k) {
      var v = num(rec.metrics[k]); if (v == null || !Fd.MET[k]) return;
      var b = rec.basis === "test" ? "held-out" : rec.basis === "validation" ? "validation" : rec.basis === "train" || rec.basis === "training" ? "training" : "";
      put(k, b, v, 0);
    });
    var rank = function (b) { return b === "validation" ? 0 : b === "held-out" ? 1 : b === "" ? 2 : 3; };
    return Object.keys(out).map(function (k) { return out[k]; }).sort(function (a, b) { return rank(a.b) - rank(b.b); });
  }

  /* ---------- 1. targets ---------- */
  function targetsLine(m, rec, T, mark) {
    var Fd = F(), noFA = Fd.screenOnly(m.spec, T), figs = figures(m.f, m.id, rec), miss = [], pass = [];
    T.forEach(function (t) {
      if (noFA && t.metric === "fa_per_hour") return;
      var list = figs.filter(function (x) { return x.base === t.metric; });
      if (!list.length) return;
      var name = Fd.metaOf(t.metric).n, txt = function (x) { return Fd.fmtV(t.metric, x.v, m.spec) + " " + BASIS(x.b); };
      var bad = list.filter(function (x) { return Fd.meets(t, x.v) === false; }), good = list.filter(function (x) { return Fd.meets(t, x.v) === true; });
      if (bad.length) miss.push(name + " " + bad.map(txt).join(" and ") + ", against " + Fd.fmtT(t, m.spec));
      if (good.length) pass.push(name + " " + good.map(txt).join(" and ") + ", target " + Fd.fmtT(t, m.spec));
    });
    var unjudged = T.filter(function (t) { return !(noFA && t.metric === "fa_per_hour") && !figs.some(function (x) { return x.base === t.metric; }); }).map(function (t) { return lc(Fd.metaOf(t.metric).n); });
    if (!miss.length && !pass.length) return "";
    var tag = mark ? " " + mark : "";
    if (miss.length) return '<p class="wc-r miss"><b>It misses ' + (miss.length === 1 ? "a target" : miss.length + " target figures") + ":</b> " + esc(miss.join("; ")) + "." +
      (pass.length ? " It does clear: " + esc(pass.join("; ")) + "." : "") + (unjudged.length ? " No figure for " + esc(unjudged.join(", ")) + "." : "") + tag + "</p>";
    return '<p class="wc-r"><b>Because it clears your targets:</b> ' + esc(pass.join("; ")) + "." + (unjudged.length ? " No figure for " + esc(unjudged.join(", ")) + "." : "") + tag + "</p>";
  }

  /* ---------- 2. verified ---------- */
  function checksOf(m, rec) {
    var mm = labOf(m.f, m.id), vf = rec && rec.verified && typeof rec.verified === "object" ? rec.verified : {}, out = [];
    CHECKS.forEach(function (c, i) {
      var n = num(mm[c[1]]), x = num(mm[c[2]]);
      if (i === 0) { if (n == null) n = num(vf.vectors); if (x == null) x = num(vf.mismatches); }
      if (n == null && x == null) return;
      out.push({ label: c[0], n: n, x: x });
    });
    var proved = num(mm.formal_proved) != null ? !!mm.formal_proved : typeof vf.proved === "boolean" ? vf.proved : null;
    var lvl = mm.verification_level != null ? mm.verification_level : vf.level;
    return { list: out, proved: proved, level: lvl };
  }
  function verifiedLine(m, rec, g, ck) {
    var full = ck.list.filter(function (c) { return c.n > 0 && c.x != null; }), bad = full.filter(function (c) { return c.x > 0; });
    if (g == null) {
      var ge = rec && num(rec.gates_est);
      return '<p class="wc-r miss"><b>Not compiled:</b> the lab never compiled this design to gates' + (ge != null ? "; its size, about " + fmt(ge) + " gates, is the agent's estimate" : "") + ", so it was not checked on gates.</p>";
    }
    var head = "Compiled to " + pl(g, "gate");
    if (bad.length) return '<p class="wc-r miss"><b>' + esc(head) + ", but it did not match its model:</b> " + esc(bad.map(function (c) { return mis(c.x) + " in " + pl(c.n, "vector") + " (" + c.label + ")"; }).join("; ")) + ".</p>";
    var pr = ck.proved === true ? "; netlist proved equal to its RTL" : "";
    if (full.length) {
      var c0 = full[0];
      return '<p class="wc-r"><b>Because it is verified:</b> ' + esc(head) + " and matched its model on " + esc(pl(c0.n, "vector")) + " with " + esc(mis(c0.x)) + " (" + esc(c0.label) + ")" + esc(pr) + "." +
        (full.length > 1 ? " " + (full.length - 1) + " more check" + (full.length > 2 ? "s" : "") + " in the details." : "") + "</p>";
    }
    if (ck.proved === true) return '<p class="wc-r"><b>Partly verified:</b> ' + esc(head) + "; netlist proved equal to its RTL. No simulation against the model with a vector count was recorded.</p>";
    return '<p class="wc-r miss"><b>Not verified:</b> ' + esc(head) + ", but the run recorded no check of the circuit against its model.</p>";
  }

  /* ---------- device kind, battery and cost from ChipInModels ---------- */
  // the battery model's device kind, read from the spec as the page's panelKind reads a run (copied from variants/i1.html)
  function kindOf(spec) {
    if (!spec) return null;
    var s = [spec.signal, spec.device, spec.brief].filter(Boolean).join(" ").toLowerCase();
    return /\beeg\b|electroenceph/.test(s) ? "eeg-monitor" : /\becg\b|\bekg\b|electrocardio/.test(s) ? "ecg-patch" : /\bradar\b|thermal/.test(s) ? "incubator-radar-thermal" : null;
  }
  function chansOf(spec, rec) {
    var c = rec && rec.budget && num(rec.budget.ch);
    if (c == null && spec && spec.constraints) c = num(spec.constraints.channels);
    return c != null && c > 0 ? c : null;
  }
  function power(kind, ch, g) {
    var b = M().deviceBudget({ kind: kind, channels: ch, sensors: ch, gates: g, decisionsPerSecond: 1 });
    return { b: b, cls: M().batteryClass(b.total_uw) };
  }
  function cost(g, cls) { var i = { gates: g }; if (cls) i.battery_class = cls; return M().costModel(i); }

  /* ---------- 3. price ---------- */
  function priceLine(g, P) {
    if (g == null || !M()) return "";
    var c = cost(g, P ? P.cls.class : null), i = c.inputs, padG = i.pad_limited_floor_mm2 * 1e6 / i.area_per_gate_um2;
    var unit = P ? "estimated unit cost " + est(money(c.unit_cost), "cost") + " per device from the cost model, not a quote" : "estimated die cost " + est(money(c.die_cost), "cost") + " from the cost model, not a quote (the battery model does not cover this device, so the full unit cost is left out)";
    var pad = c.pad_limited
      ? " Below about " + est(fmt(padG) + " gates", "area") + " the pads, not the logic, set the die size, so a bigger chip would cost the same per unit."
      : " Above about " + est(fmt(padG) + " gates", "area") + " the logic sets the die size, so a bigger chip would cost more.";
    return '<p class="wc-r"><b>Because of the price:</b> ' + esc(pl(g, "gate")) + "; " + unit + "." + pad + "</p>";
  }

  /* ---------- 4. alternatives ---------- */
  function primaryOf(m, T) { var p = m.spec && m.spec.primary; return p && F().MET[p] ? p : T[0] ? T[0].metric : null; }
  function better(key, a, b) { var up = F().metaOf(key).up !== false; return up ? a > b + 1e-9 : a < b - 1e-9; }
  function altsLine(m, rec, T, g, P) {
    var Fd = F(), f = m.f, all = Fd.designs(f), others = all.filter(function (d) { return d.id !== m.id; });
    if (!rec || !others.length) return { html: "", more: "" };
    var key = primaryOf(m, T), mine = key ? num(rec.metrics[key]) : null, bw = rec.basis === "test" ? "test (held-out)" : rec.basis || "";
    var clears = function (d) { return T.length > 0 && Fd.passAll(T, d); };
    var noFA = Fd.screenOnly(m.spec, T), TT = T.filter(function (t) { return !(noFA && t.metric === "fa_per_hour"); });
    // which rule the data shows
    var rule = "";
    if (g != null && verOK(rec) && clears(rec) && !others.some(function (d) { var dg = gatesOf(f, d); return verOK(d) && clears(d) && dg != null && dg < g; }))
      rule = "it is the smallest verified design that clears your targets" + (bw ? " on " + bw : "");
    else if (verOK(rec) && key && mine != null && !others.some(function (d) { var v = num(d.metrics[key]); return verOK(d) && v != null && better(key, v, mine); }))
      rule = "it is the most accurate verified design on " + lc(Fd.metaOf(key).n) + (bw ? ", " + bw : "");
    // each design not chosen, with its reason from the data
    var rows = others.map(function (d) {
      var dg = gatesOf(f, d), r = { d: d, g: dg, cat: 9, why: "" }, fails = TT.filter(function (t) { return Fd.meets(t, num(d.metrics[t.metric])) === false; });
      if (verBad(d)) { r.cat = 1; r.kind = "failed verification"; r.why = "failed verification: " + mis(d.verified.mismatches) + " against its model"; }
      else if (fails.length) { r.cat = 4; r.kind = "missed a target"; r.why = "missed " + fails.map(function (t) { return lc(Fd.metaOf(t.metric).n) + " (" + Fd.fmtV(t.metric, d.metrics[t.metric], m.spec) + " against " + Fd.fmtT(t, m.spec) + ")"; }).join(" and "); }
      else if (dg == null) { r.cat = 3; r.kind = "were not compiled"; r.why = "was not compiled" + (num(d.gates_est) != null ? " (about " + fmt(d.gates_est) + " gates, estimated)" : "") + ", so it was never checked on gates"; }
      else if (!verOK(d)) { r.cat = 2; r.kind = "were compiled but not verified"; r.why = "compiled to " + pl(dg, "gate") + " but not verified against its model"; }
      else {
        r.cat = 0; r.kind = "verified";
        var v = key ? num(d.metrics[key]) : null, name = key ? lc(Fd.metaOf(key).n) : "";
        if (g != null && dg > g) {
          if (v != null && mine != null && better(key, v, mine)) {
            r.margin = true;
            var dc = P ? cost(dg, power(kindOf(m.spec), chansOf(m.spec, d) || chansOf(m.spec, rec), dg).cls.class).unit_cost - cost(g, P.cls.class).unit_cost : cost(dg).die_cost - cost(g).die_cost;
            r.why = "larger (" + pl(dg, "gate") + "), verified, and scores higher on " + name + ": " + Fd.fmtV(key, v, m.spec) + " against " + Fd.fmtV(key, mine, m.spec) + (Math.abs(dc) < 0.005 ? ", at the same estimated unit cost: a maker who wants more margin can choose it" : ", for about " + money(dc) + (dc > 0 ? " more" : " less") + " per unit (estimated): a maker who wants more margin can choose it");
          } else r.why = "larger (" + pl(dg, "gate") + ") with no gain" + (name && v != null ? " on " + name + " (" + Fd.fmtV(key, v, m.spec) + ")" : "");
        } else if (g != null && dg < g) r.why = "smaller (" + pl(dg, "gate") + ")" + (v != null && mine != null && better(key, mine, v) ? " but scores lower on " + name + " (" + Fd.fmtV(key, v, m.spec) + ")" : "");
        else r.why = "the same size, " + pl(dg, "gate");
      }
      r.dist = g != null && dg != null && dg > 0 ? Math.abs(Math.log(dg / g)) : num(d.gates_est) > 0 && g ? Math.abs(Math.log(d.gates_est / g)) + 1 : 9;
      return r;
    }).filter(function (r) { return r.why; });
    rows.sort(function (a, b) { return a.cat - b.cat || a.dist - b.dist; });
    var top = rows.slice(0, 3), rest = rows.slice(3);
    var nm = function (r) { return Fd.chipNameHTML(f, r.d.id, { files: m.files }); };
    var counts = {}; rest.forEach(function (r) { counts[r.kind] = (counts[r.kind] || 0) + 1; });
    var restTxt = rest.length ? "<li>" + esc(rest.length + " more: " + Object.keys(counts).map(function (k) { return counts[k] + " " + (counts[k] === 1 ? k.replace(/^were/, "was") : k); }).join(", ")) + ".</li>" : "";
    var html = '<div class="wc-r"><b>Because of the alternatives:</b> ' + (rule ? esc(rule) + "." : "the run's data does not show a single rule for this pick (neither the smallest verified design that clears your targets nor the most accurate verified design).") +
      (top.length ? "<ul>" + top.map(function (r) { return "<li>" + nm(r) + ": " + esc(r.why) + ".</li>"; }).join("") + restTxt + "</ul>" : "") + "</div>";
    var more = rest.length ? "<p><b>Every other design not chosen</b></p><ul>" + rest.map(function (r) { return "<li>" + nm(r) + ": " + esc(r.why) + ".</li>"; }).join("") + "</ul>" : "";
    return { html: html, more: more };
  }

  /* ---------- 5. battery and the limits you set ---------- */
  function said(spec, word) {
    var re = new RegExp("\\b" + word + ":\\s*([^\\n.]+)", "i"), x = spec && spec.brief ? re.exec(spec.brief) : null;
    return x ? x[1].trim() : "";
  }
  function batteryLine(m, P) {
    var spec = m.spec, bat = said(spec, "Battery"), cst = said(spec, "Cost"), hrs = spec && spec.constraints ? num(spec.constraints.battery_hours) : null;
    var asked = [];
    if (bat) asked.push("battery “" + esc(bat) + "”" + (hrs != null ? " (read as at least " + fmt(hrs) + " hours)" : ""));
    else if (hrs != null) asked.push("battery at least " + fmt(hrs) + " hours");
    if (cst) asked.push("cost “" + esc(cst) + "”");
    var life = "";
    if (P && P.cls.class !== "larger pack or mains") {
      var days = P.cls.life_days, lt = days >= 2 ? fmt(days) + " days" : (days * 24).toFixed(1) + " hours";
      life = "Estimated battery life for this chip: " + est("about " + lt, "battery_life") + " on " + est(SHORT[P.cls.class], "battery_class") +
        (hrs != null ? (days * 24 >= hrs ? ", more than the " + fmt(hrs) + " hours you set" : ", short of the " + fmt(hrs) + " hours you set") : "") + ".";
    } else if (P) life = "The battery model puts this device on " + est(SHORT[P.cls.class], "battery_class") + ".";
    if (!asked.length && !life) return "";
    return '<p class="wc-r"><b>Because of the battery and the limits you set:</b> ' + (asked.length ? "you asked for " + asked.join(" and ") + ". " : "") + life + "</p>";
  }

  /* ---------- 6. regulation ---------- */
  // which checked entries of ../i1-regulation.js apply: the cell standard and EU removability for a battery-powered device,
  // the software life cycle and the cyber device definition for any hard-wired chip
  function regLine(P) {
    var R = window.ChipInRegulation, all = R && R.sources ? R.sources() : [];
    if (!all.length) return "";
    var by = {}; all.forEach(function (e) { by[e.id] = e; });
    var ids = ["iec62304", "cyber"];
    if (P && P.cls.class !== "larger pack or mains") ids.unshift("iec62133", "eu");
    var list = ids.map(function (k) { return by[k]; }).filter(Boolean);
    if (!list.length) return "";
    var link = function (x, t) { return '<a href="' + esc(x[1]) + '" target="_blank" rel="noopener">' + esc(t) + "</a>"; };
    return '<div class="wc-r"><b>Regulation, what this design changes</b>' + (P ? " (" + est(SHORT[P.cls.class].replace(/^a /, ""), "battery_class") + ", hard-wired logic):" : " (hard-wired logic):") +
      "<ul>" + list.map(function (e) { return '<li title="' + esc(e.title + " (" + e.st + ")") + '">' + esc(e.say) + (e.st !== "checked" && !/^contested/i.test(e.say) ? " (" + esc(e.st) + ")" : "") + " " + link(e.src[0], e.cite) + "</li>"; }).join("") + "</ul></div>";
  }

  /* ---------- details ---------- */
  function detailsHTML(m, rec, g, ck, P, altMore) {
    var out = "";
    if (ck.list.length || ck.proved != null || ck.level != null) {
      out += "<p><b>Checks the run recorded</b></p><ul>" + ck.list.map(function (c) { return "<li>" + esc(c.label.charAt(0).toUpperCase() + c.label.slice(1)) + ": " + (c.n != null ? esc(pl(c.n, "vector")) : "vectors not reported") + ", " + (c.x != null ? esc(mis(c.x)) : "mismatches not reported") + "</li>"; }).join("") +
        (ck.level != null ? "<li>Verification level: " + esc(F().levelText(ck.level)) + "</li>" : "") + (ck.proved != null ? "<li>Formal proof: " + (ck.proved ? "netlist proved equal to the RTL" : "not proved") + "</li>" : "") + "</ul>";
    }
    if (g != null && M()) {
      var c = cost(g, P ? P.cls.class : null);
      out += "<p><b>Cost model for " + esc(pl(g, "gate")) + "</b> " + '<span class="mk est">estimated</span></p><ul>' + (P ? c.lines : c.lines.slice(0, 1)).map(function (l) { return "<li>" + esc(l.name) + ": " + est(money(l.cost), "cost") + "</li>"; }).join("") +
        "<li>Logic area " + est((c.logic_area_mm2 < 0.1 ? c.logic_area_mm2.toFixed(3) : c.logic_area_mm2.toFixed(2)) + " mm&sup2;", "area") + ", die " + est(c.die_area_mm2.toFixed(1) + " mm&sup2;", "area") + (c.pad_limited ? " (set by the pads)" : "") + "</li></ul>";
    }
    if (P) out += "<p><b>Device power</b> " + est((P.b.total_uw / 1000).toPrecision(3) + " mW", "device_power") + "; the chip is " + est((P.b.chip_share * 100 < 0.01 ? (P.b.chip_share * 100).toPrecision(2) : P.b.chip_share * 100 < 1 ? (P.b.chip_share * 100).toFixed(3) : (P.b.chip_share * 100).toFixed(1)) + "%", "chip_power") + " of it.</p>";
    out += altMore;
    return out;
  }

  var OPEN = {};
  document.addEventListener("toggle", function (e) { var d = e.target; if (d && d.classList && d.classList.contains("wc-d")) OPEN[d.dataset.chip] = d.open; }, true);

  function html(m) {
    if (!m || m.running || !m.id || m.id !== m.chosenId || !F() || !m.f) return "";
    try {
      css();
      var Fd = F(), f = m.f, rec = f.designs[m.id] || null, T = m.T || Fd.targetsOf(m.spec), g = gatesOf(f, rec || { id: m.id });
      var mark = Fd.dataMark(m.spec, rec ? [rec] : []);
      var kind = kindOf(m.spec), ch = chansOf(m.spec, rec), P = M() && kind && ch && g != null ? power(kind, ch, g) : null;
      var ck = checksOf(m, rec), alt = altsLine(m, rec, T, g, P);
      var rows = [targetsLine(m, rec, T, mark), verifiedLine(m, rec, g, ck), priceLine(g, P), alt.html, batteryLine(m, P), regLine(P)].filter(Boolean);
      if (!rows.length) return "";
      var det = detailsHTML(m, rec, g, ck, P, alt.more);
      return '<section class="wc" aria-label="Why this chip"><div class="wc-h"><h2>Why this chip</h2></div>' + rows.join("") +
        (det ? '<details class="wc-d" data-chip="' + esc(m.id) + '"' + (OPEN[m.id] ? " open" : "") + "><summary>Details: checks, cost model and every alternative</summary><div>" + det + "</div></details>" : "") +
        '<p class="wc-f">Estimates come from the page\'s cost and battery models, not quotes. General information, not regulatory advice: check every point with a regulatory specialist.</p></section>';
    } catch (err) {
      return "";
    }
  }
  window.ChipInWhyChip = { html: html };
})();
