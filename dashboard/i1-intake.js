/* ChipIn i1 intake: the path from a typed brief to the guided steps (window.ChipInIntake).
 *
 * 1. Every forward move in the guided flow passes through the loading stage (../i1-stage.js): the brief
 *    submitted, the questions answered, each Next, and Review your spec. The lines say what is being
 *    worked out for the screen that follows and what was found, from the spec itself. On the public
 *    site the lines are a paced replay, marked as one; with a backend connected they tick as the work
 *    is done and the backend's own follow-up questions step (../i1-questions.js) is used as before.
 * 2. The chat (#/new/ask) is the whole intake, at most five turns: who and where, sensitivity (always,
 *    prefilled from the brief), the second target (specificity or false alarms), battery and cost in one
 *    turn, then data with the dataset search inside the chat; each with quick picks, free text and a
 *    skip. Reuse, alert latency, noise and the worse error are assumed and shown on the spec card. With
 *    a backend connected at most two of its own questions (../i1-questions.js) come last, never one the
 *    turns or the assumed rows cover.
 *    Then the "Your spec" card; the five step screens are only its edit view. Answers go into the
 *    spec's own fields; battery in words, cost and unread answers ride in the brief (briefNotes).
 *
 * The page calls (dashboard/variants/i1.html, INTAKE HOOK):
 *   ChipInIntake.begin(spec, ctx)            after the brief is submitted
 *   ChipInIntake.next(spec, i, to, ctx)      Next on step i (0-4) towards step `to` (2..5, "spec", "more")
 *   ChipInIntake.render(spec, ctx)           draws #/new/ask; true when drawn
 *   ChipInIntake.cardRows(spec)              the answers as one row of the spec card
 * ctx is built by the page: { go, save, parse, parseBrief, parseGroup, parsePlace, budgets, places, groups,
 *   tasks, met, dsf, fit, measured, cases, sigOf } */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var cap = function (t) { t = String(t || "").trim(); return t ? t.charAt(0).toUpperCase() + t.slice(1) : t; };
  var link = function (url, text) { return url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(text) + "</a>" : esc(text); };
  var conn = function () { var l = window.ChipInLive && window.ChipInLive.i1, c = l && l.connection ? l.connection() : null; return c ? c.state : "off"; };

  /* ---------- the scripted questions: at most five turns ----------
   * a. who wears it and where; b. the sensitivity target (always, prefilled from the brief);
   * c. the second target, specificity or false alarms (prefilled from the brief); d. battery and cost in
   * one turn; e. the data. Single-use or reusable, alert latency, signal noise and which error matters
   * more are not asked: the spec card shows them under "Assumed (edit if wrong)". */
  var FA_DAY = 1 / 24, FA_WEEK = 1 / 168, FA_MONTH = 1 / 720;
  function setTarget(s, ctx, metric, value, src) {
    var t = s.targets.filter(function (x) { return x.metric === metric; })[0];
    if (!t) { t = { metric: metric, op: ctx.met[metric].op }; s.targets.push(t); }
    t.value = value; t.op = ctx.met[metric].op; t.src = src || "answer";
    s.touched.targets = true;
    if (!s.primary) s.primary = s.targets[0].metric;
  }
  var screening = function (s) { return s.task === "screening"; };
  var fromBrief = function (s, metric) { return (s.parsed.targets || []).filter(function (t) { return t.metric === metric && t.value != null; })[0] || null; };
  var pctS = function (v) { return +(v * 100).toFixed(2) + "%"; };
  // a typed share: "92%", "92 percent", "0.92"
  function readFrac(t) {
    var m = String(t || "").match(/(\d+(?:\.\d+)?)\s*(?:%|percent)/i), v = m ? +m[1] / 100 : null;
    if (v == null && (m = String(t || "").match(/\b(0?\.\d+)\b/))) v = +m[1];
    if (v == null && (m = String(t || "").match(/\b(\d{2}(?:\.\d+)?)\b/))) v = +m[1] / 100;
    return v > 0 && v <= 1 ? Math.round(v * 1e4) / 1e4 : null;
  }
  // a typed false-alarm rate, per hour: "1 a week", "2 per day", "one a month"
  function readFa(t) {
    var m = String(t || "").toLowerCase().match(/(\d+(?:\.\d+)?|one|an?)\s*(?:false\s*alarms?\s*)?(?:an?|per|each|every)?\s*(hour|day|night|week|month)/);
    if (!m) return null;
    var n = /^\d/.test(m[1]) ? +m[1] : 1;
    return n > 0 ? Math.round(n / ({ hour: 1, day: 24, night: 12, week: 168, month: 720 })[m[2]] * 1e6) / 1e6 : null;
  }
  // the form of the second target: what the user picked, else what the brief or the defaults hold
  function secondOf(s) {
    if (s.second) return s.second;
    var has = function (k) { return s.targets.some(function (t) { return t.metric === k && t.value != null; }); };
    if (fromBrief(s, "specificity")) return "specificity";
    if (fromBrief(s, "false_alarms_per_hour")) return "false_alarms_per_hour";
    return has("specificity") && (screening(s) || !has("false_alarms_per_hour")) ? "specificity" : has("false_alarms_per_hour") ? "false_alarms_per_hour" : null;
  }
  // the second target set in one form: a default target of the other form goes, one from the brief stays
  function setSecond(s, ctx, metric, value, src) {
    var other = metric === "specificity" ? "false_alarms_per_hour" : "specificity";
    s.targets = s.targets.filter(function (t) { return t.metric !== other || t.src === "brief"; });
    setTarget(s, ctx, metric, value, src);
    s.second = metric;
    if (!s.task || (metric === "false_alarms_per_hour" && s.task === "screening" && !fromBrief(s, "specificity"))) { s.task = "continuous"; s.touched.task = true; }
    if (s.primary !== "sensitivity" && s.targets.some(function (t) { return t.metric === "sensitivity"; })) s.primary = "sensitivity";
  }
  function faWords(s, ctx, v) { var p = ctx.places[s.place] || ctx.places.ward, x = +(v * p.h).toFixed(3); return x + " false alarm" + (x === 1 ? "" : "s") + (p.per === "hour" ? " an hour" : " a " + p.per); }
  var Q = [
    {
      id: "wear", open: function (s, ctx) { return !(ctx.parseGroup(s.brief) && ctx.parsePlace(s.brief)); },
      q: function () { return "Who wears it, and where?"; }, why: "It sets which recordings fit and how false alarms are counted.",
      opts: function () { return [["Adults, worn day and night", "adults|self"], ["Adults in hospital", "adults|ward"], ["Children at home", "children|home"], ["Newborns in hospital", "newborns|ward"]]; },
      apply: function (s, ctx, v, text) {
        var g = v ? v.split("|")[0] : ctx.parseGroup(text || ""), p = v ? v.split("|")[1] : ctx.parsePlace(text || "");
        if (!g && !p) return false;
        // the answer overrides the brief's guess: worn over time monitors, a single spot check screens
        var words = v ? (this.opts().filter(function (o) { return o[1] === v; })[0] || [""])[0] : String(text || "");
        var spot = /spot[- ]check|one-off|single (?:reading|recording|measurement|test|check)|one-time/i.test(words);
        var worn = /\bpatch\b|\bband\b|\bworn\b|day and night|continuous|monitor|overnight|24\/7|around the clock/i.test(words);
        if (spot && s.task !== "screening") { s.task = "screening"; s.touched.task = true; }
        else if (worn && !spot && (s.task === "screening" || !s.task)) { s.task = "continuous"; s.touched.task = true; }
        if (g) { s.group = g; s.touched.group = true; }
        if (p) { s.place = p; s.touched.place = true; s.targets.forEach(function (t) { if (t.metric === "false_alarms_per_hour" && t.src === "default") t.value = ctx.places[p].fa; }); }
        return true;
      }
    },
    {
      id: "sens", open: function () { return true; },
      q: function (s) { var b = fromBrief(s, "sensitivity"); return b ? "You said " + pctS(b.value) + " sensitivity: keep it?" : "What sensitivity must it reach?"; },
      why: "The share of real events it must catch. Higher needs a bigger chip.",
      ph: "Or type another, for example 92%",
      opts: function (s) {
        var b = fromBrief(s, "sensitivity"), L = [["80%", "0.8"], ["90%", "0.9"], ["95%", "0.95"]];
        return b ? [["Keep " + pctS(b.value), "keep"]].concat(L.filter(function (o) { return +o[1] !== b.value; })) : L;
      },
      apply: function (s, ctx, v, text) {
        var b = fromBrief(s, "sensitivity");
        if (v === "keep" && b) { setTarget(s, ctx, "sensitivity", b.value, "brief"); s.primary = "sensitivity"; return true; }
        var x = v ? +v : readFrac(text); if (!(x > 0 && x <= 1)) return false;
        setTarget(s, ctx, "sensitivity", x); s.primary = "sensitivity"; return true;
      },
      // a skip keeps what the brief said, else the default
      skip: function (s, ctx) { var b = fromBrief(s, "sensitivity"); if (b) setTarget(s, ctx, "sensitivity", b.value, "brief"); }
    },
    {
      id: "second", open: function () { return true; },
      q: function (s, ctx) {
        var sp = fromBrief(s, "specificity"), fa = fromBrief(s, "false_alarms_per_hour");
        if (sp) return "You said " + pctS(sp.value) + " specificity: keep it?";
        if (fa) return "You said at most " + faWords(s, ctx, fa.value) + ": keep it?";
        return screening(s) ? "What specificity must it reach, or how many false alarms may it raise?" : "How many false alarms may it raise, or what specificity must it reach?";
      },
      why: "The second bar: how often it may flag someone who is fine. Pick the form you think in.",
      ph: "Or type it: 85% specificity, 1 false alarm a week",
      opts: function (s) {
        var sp = fromBrief(s, "specificity"), fa = fromBrief(s, "false_alarms_per_hour");
        var F = [["About 1 false alarm a day", "fa|" + FA_DAY], ["About 1 a week", "fa|" + FA_WEEK], ["About 1 a month", "fa|" + FA_MONTH]];
        var P = [["Specificity 90%", "sp|0.9"], ["Specificity 95%", "sp|0.95"]];
        if (sp) return [["Keep " + pctS(sp.value) + " specificity", "keep"]].concat(F);
        if (fa) return [["Keep it", "keep"]].concat(P);
        return screening(s) ? P.concat(F) : F.concat(P);
      },
      apply: function (s, ctx, v, text) {
        var sp = fromBrief(s, "specificity"), fa = fromBrief(s, "false_alarms_per_hour");
        if (v === "keep") { if (sp) setSecond(s, ctx, "specificity", sp.value, "brief"); else if (fa) setSecond(s, ctx, "false_alarms_per_hour", fa.value, "brief"); return !!(sp || fa); }
        if (v) { var k = v.split("|"); setSecond(s, ctx, k[0] === "sp" ? "specificity" : "false_alarms_per_hour", +k[1]); return true; }
        var t = String(text || ""), r = readFa(t);
        if (r != null && !/specific|%|\b1\s*in\s*\d/i.test(t)) { setSecond(s, ctx, "false_alarms_per_hour", r); return true; }
        var m = t.match(/1\s*in\s*(\d+)/i), x = m ? 1 - 1 / +m[1] : readFrac(t);
        if (!(x > 0 && x < 1)) return false;
        setSecond(s, ctx, "specificity", Math.round(x * 1e4) / 1e4); return true;
      },
      skip: function (s, ctx) {
        var sp = fromBrief(s, "specificity"), fa = fromBrief(s, "false_alarms_per_hour");
        if (sp) setSecond(s, ctx, "specificity", sp.value, "brief"); else if (fa) setSecond(s, ctx, "false_alarms_per_hour", fa.value, "brief");
      }
    },
    {
      id: "limits", open: function (s) { return !s.parsed.bat || !s.cons.cost; },
      q: function (s) { return s.parsed.bat ? "How much may the chip cost?" : "How long must one battery last, and how much may the chip cost?"; },
      why: "A longer life needs a bigger battery or a leaner chip; cheaper means a smaller chip.",
      ph: "Or type it: as long as possible, max 7 days, 220 mAh, cheapest possible",
      groups: function (s) {
        var G = [];
        if (!s.parsed.bat) G.push({ key: "bat", label: "Battery", opts: [["24 hours", "24|hours"], ["3 days", "3|days"], ["7 days", "7|days"], ["As long as possible", "longest"]] });
        G.push({ key: "cost", label: "Cost", opts: [["Cheapest possible", "Cheapest possible"], ["Cost is not a concern", "Cost is not a concern"]] });
        return G;
      },
      // picks: { bat, cost }; typed words are split into a battery part and a cost part, each kept as typed
      apply: function (s, ctx, v, text) {
        var k = s.cons, got = false;
        var bat = function (n, u, words) { if (words != null) k.batText = words; if (n > 0) { k.batN = n; k.batU = u; } got = true; };
        if (v && typeof v === "object") {
          if (v.bat === "longest") bat(0, "", "As long as possible"); else if (v.bat) bat(+v.bat.split("|")[0], v.bat.split("|")[1], "");
          if (v.cost) { k.cost = v.cost; got = true; }
        } else {
          String(text || "").split(/[,;]|\band\b/i).map(function (x) { return x.trim(); }).filter(Boolean).forEach(function (part) {
            var low = part.toLowerCase(), m;
            if (/cheap|low cost|lowest cost|not a concern|no (?:limit|concern)|any cost|price|[$£€]\s*\d|cost/.test(low)) { k.cost = /cheap|low/.test(low) ? "Cheapest possible" : /not a concern|no (?:limit|concern)|any cost/.test(low) ? "Cost is not a concern" : cap(part); got = true; return; }
            if ((m = low.match(/(\d+(?:\.\d+)?)\s*-?\s*(hours?|hrs?|h\b|days?|weeks?)/))) { var n = +m[1], u = /^[dw]/.test(m[2]) ? "days" : "hours"; if (/^w/.test(m[2])) n *= 7; bat(n, u, part); return; }
            if (/long|mah|battery|charge/.test(low)) bat(0, "", cap(part));
          });
        }
        if (got) s.touched.cons = true;
        return got;
      }
    },
    {
      id: "data", open: function () { return true; },
      q: function () { return "What should it be designed on?"; }, why: "The chip is trained on part of it and judged on patients it never saw.",
      opts: function () { return [["My own recordings", "own"], ["Find a public dataset", "public"], ["Synthetic data", "sim"]]; },
      apply: function (s, ctx, v, text) {
        var t = String(v || text || "").toLowerCase(), d = /own|my|our/.test(t) ? "own" : /public|open|find|search|dataset/.test(t) ? "public" : /sim|synth/.test(t) ? "sim" : "";
        if (!d) return false;
        s.data = d; s.touched.data = true; return true;
      }
    }
  ];
  var byId = function (id) { return Q.filter(function (q) { return q.id === id; })[0]; };
  // the questions still to ask: open topics not yet answered
  function pending(s, ctx) {
    var a = (s.sq && s.sq.ans) || {};
    return Q.filter(function (q) { return !a[q.id] && q.open(s, ctx); });
  }

  /* ---------- assumed, not asked: shown on the spec card, each editable in place ---------- */
  var ASM = {
    latency: { k: "Alert latency", re: /latenc|how (?:fast|quickly|soon)|alert after|delay|time to (?:alert|detect)|within \d+\s*(?:s\b|sec)/i },
    noise: { k: "Signal noise", opts: ["Low", "Medium", "High"], re: /noise|movement|motion|artefact|artifact|activity level/i },
    worse: { k: "Worse error", opts: ["A missed event", "A false alarm", "Both equally"], re: /mistake|missed (?:event|detection)|matters? (?:more|most)|\bworse\b|cost of a miss/i }
  };
  var REUSE_RE = /reusab|disposab|single[- ]use/i;
  // the topics the five turns cover: a backend question about any of them is not asked
  var FIXED_RE = /sensitiv|specific|false alarm|battery|\bcost|price|cheap|data ?set|public data|own recordings|synthetic|simulat|who (?:wears|uses|is it for)|patient group|age group|\bage\b|newborn|children|hospital|at home|\bward\b/i;
  function asmDefault(s, key) {
    if (key === "latency") return "Within 30 s of onset";
    if (key === "noise") return s.place === "ward" ? "Low" : "Medium";
    // derived from the two targets: the one held higher names the error that matters more
    var sens = s.targets.filter(function (t) { return t.metric === "sensitivity"; })[0], sec = secondOf(s);
    var o = s.targets.filter(function (t) { return t.metric === sec; })[0];
    if (!sens || sens.value == null) return "Both equally";
    if (sec === "specificity" && o && o.value != null) return sens.value > o.value ? "A missed event" : sens.value < o.value ? "A false alarm" : "Both equally";
    return sens.value >= 0.9 ? "A missed event" : "Both equally";
  }
  function asmVal(s, key) { var a = s && s.asm; return a && a[key] ? a[key] : asmDefault(s, key); }
  function asmWhy(s, key) {
    if (s.asm && s.asm[key]) return "As you set it";
    if (key === "latency") return "Default for this kind of device";
    if (key === "noise") return s.place === "ward" ? "From where it is worn: a hospital bed" : "From where it is worn: daily activity";
    return "From your two targets";
  }

  /* ---------- the stage before each screen ---------- */
  var pct = function (v) { return +(v * 100).toFixed(1) + "%"; };
  function tgtShort(s, ctx, t) {
    var m = ctx.met[t.metric], p = ctx.places[s.place] || ctx.places.ward;
    if (t.value == null) return (m.short || m.name) + ": no value";
    return (m.short || m.name) + (t.op === "<=" ? " ≤ " : " ≥ ") + (m.kind === "frac" ? pct(t.value) : +(t.value * p.h).toFixed(2) + (p.per === "hour" ? " an hour" : " a " + p.per));
  }
  var join = function (a) { return a.filter(Boolean).map(esc).join(" · "); };
  function caseLine(s, ctx) {
    if (s.case === "af") return { t: "Matches the AF patch case", d: esc("Measured on " + ctx.dsf.cinc17.short) };
    if (s.case === "neonatal-eeg") return { t: "Matches the neonatal EEG case", d: esc(ctx.measured(s) ? "Measured on " + ctx.dsf.helsinki.short : "Simulated in this demo") };
    if (s.case === "incubator") return { t: "Matches the Incubator Watch case", d: "Simulated in this demo" };
    return { t: "No recorded case matches", d: "The run will be simulated and marked so", warn: true };
  }
  function detectLine(s, ctx, miss) {
    return s.detect ? { t: "Detects " + s.detect.charAt(0).toLowerCase() + s.detect.slice(1), d: esc(ctx.tasks[s.task] ? ctx.tasks[s.task].n : "Task type: pick one next") }
      : { t: "What to detect: not in the brief", d: miss || "Set it on the next screen", warn: true };
  }
  function lines(kind, s, ctx, extra) {
    var p = ctx.places[s.place] || ctx.places.ward, g = ctx.groups[s.group];
    if (kind === "brief") {
      var fromBrief = s.parsed.targets.length, nq = extra || 0;
      var L = [
        { p: "Reading your brief", w: "Device and signal", t: "Read: " + (s.device || "device not named"), d: esc(s.signal || "Signal not named") },
        Object.assign({ p: "Working out what to detect", w: "Looking for a condition" }, detectLine(s, ctx, nq ? "We ask next" : "")),
        ctx.parseGroup(s.brief) ? { p: "Checking who wears it", w: "Patients and setting", t: "For " + g.n.toLowerCase(), d: esc(p.n) }
          : { p: "Checking who wears it", w: "Patients and setting", t: "Who wears it: not in the brief", d: nq ? "We ask next" : "Set it on step 2", warn: true },
        { p: "Looking for targets and limits", w: "Numbers next to sensitivity, false alarms, battery", t: fromBrief ? fromBrief + " target" + (fromBrief === 1 ? "" : "s") + " in your brief" : "No targets in the brief", d: fromBrief ? join(s.targets.filter(function (t) { return t.src === "brief"; }).map(function (t) { return tgtShort(s, ctx, t); })) : "Defaults come from the task type" }
      ];
      L.push(nq ? { p: "Writing questions for what is missing", w: "Only what the brief leaves open", t: nq + " question" + (nq === 1 ? "" : "s") + " to pin it down", d: "Quick picks, or type your own" }
        : Object.assign({ p: "Matching a known case", w: "Checking the recorded runs" }, caseLine(s, ctx)));
      L[1].ms = 1500; L[4].ms = 1500;
      return L;
    }
    if (kind === "answers") {
      var a = s.sq ? s.sq.ans : {}, n = Object.keys(a).filter(function (k) { return !a[k].skip; }).length;
      return [
        { p: "Adding your answers", w: "Writing them into the spec", t: n ? n + " answer" + (n === 1 ? "" : "s") + " added" : "No answers: defaults kept", d: join(Object.keys(a).filter(function (k) { return !a[k].skip; }).map(function (k) { return a[k].a; })) },
        Object.assign({ p: "Working out what to detect", w: "Condition and task type", ms: 1500 }, detectLine(s, ctx)),
        Object.assign({ p: "Matching a known case", w: "Checking the recorded runs", ms: 1500 }, caseLine(s, ctx)),
        { p: "Setting targets", w: "Your numbers first, then the task type's defaults", t: s.targets.length + " target" + (s.targets.length === 1 ? "" : "s") + " set", d: join(s.targets.map(function (t) { return tgtShort(s, ctx, t); })) }
      ];
    }
    if (kind === "2") return [
      { p: "Reading the task type", w: "Monitoring, screening or grading", t: ctx.tasks[s.task] ? ctx.tasks[s.task].n : "Task type not set", d: s.task ? "It picks the default targets" : "Defaults wait for a task type", warn: !s.task },
      { p: "Checking who it is for", w: "Patient group", t: g ? "For " + g.n.toLowerCase() : "Patient group: pick one", d: g ? "Recordings must match this group" : "Not in the brief", warn: !g },
      { p: "Setting how false alarms are counted", w: "Who responds, and how often", t: s.task === "screening" ? "Judged by specificity" : "Counted per " + p.per, d: esc(cap(p.r)) }
    ];
    if (kind === "3") return [
      { p: "Picking the task type's targets", w: "Which bars the chip must clear", t: s.targets.length + " target" + (s.targets.length === 1 ? "" : "s"), d: join(s.targets.map(function (t) { return (ctx.met[t.metric].short || ctx.met[t.metric].name); })) },
      { p: "Keeping your numbers", w: "From the brief and your answers", t: (function () { var k = s.targets.filter(function (t) { return t.src !== "default"; }).length; return k ? k + " kept as you set" : "None given: defaults"; })(), d: join(s.targets.map(function (t) { return tgtShort(s, ctx, t); })) },
      { p: "Choosing the one to chart", w: "The bar drawn on the chart", t: "Charting " + (s.primary ? (ctx.met[s.primary].short || ctx.met[s.primary].name).toLowerCase() : "the first target"), d: "Change it on the next screen" }
    ];
    if (kind === "4") {
      var b = ctx.budgets(s);
      return [
        { p: "Listing channel budgets", w: "Electrodes or sensors to compare", t: b.length + " budget" + (b.length === 1 ? "" : "s"), d: join(b.map(function (x) { return x.label; })) },
        { p: "Reading battery life", w: "How long between changes", t: "At least " + s.cons.batN + " " + s.cons.batU, d: s.touched.cons ? "As you set it" : "Default for this kind of device" },
        { p: "Checking disposable or reusable", w: "It sets which batteries fit", t: s.cons.reusable === true ? "Reusable" : s.cons.reusable === false ? "Single-use" : "Reuse not set", d: s.cons.reusable === true ? "Charged and cleaned between patients" : s.cons.reusable === false ? "One patient, then replaced" : "Set it on the spec card if it matters", warn: s.cons.reusable == null }
      ];
    }
    if (kind === "5") {
      var d = s.ds && ctx.dsf[s.ds], f = d ? ctx.fit(s, s.ds) : null, sig = ctx.sigOf(s);
      return [
        d ? { p: "Looking for open data", w: "Searching PhysioNet and Zenodo for " + (sig ? sig.toUpperCase() : "matching") + " recordings", t: "Found: " + d.short, tHTML: "Found: " + link(d.url, d.short), d: esc(d.labels), ms: 2200 }
          : { p: "Looking for open data", w: "Searching PhysioNet and Zenodo", t: "No open set matches", d: "Synthetic data instead, from a small stated model", warn: true, ms: 2200 },
        f ? { p: "Checking the fit with your device", w: "Signal, patients and labels", t: f.warn.length ? "Fit: " + f.warn.length + " warning" + (f.warn.length === 1 ? "" : "s") : "Fits, approximately", d: f.warn.length ? esc(f.warn[0]) : "Other devices recorded it: treat results as approximate", warn: f.warn.length > 0, ms: 1500 }
          : { p: "Checking the fit with your device", w: "Signal, patients and labels", t: "Nothing to check against", d: "Every number in the run is simulated", warn: true },
        { p: "Choosing a split", w: "Keeping test data unseen", t: "Split chosen", d: s.case === "af" ? "By recording: none in both training and test" : "By patient: none in both training and test" }
      ];
    }
    // the spec card, or the backend's follow-up questions
    var miss = s.targets.filter(function (t) { return t.value == null; }).length;
    var L2 = [
      { p: "Collecting your answers", w: "Five steps into one spec", t: "Spec assembled", d: join([s.device, s.detect, g && g.n]) },
      { p: "Checking every target has a value", w: "Each bar needs a number", t: miss ? miss + " target" + (miss === 1 ? "" : "s") + " without a value" : "All " + s.targets.length + " targets set", d: miss ? "Set it on the card, or the run leaves it out" : join(s.targets.map(function (t) { return tgtShort(s, ctx, t); })), warn: !!miss }
    ];
    if (kind === "more") L2.push({ p: "Asking the backend for follow-up questions", w: "Sending your brief and answers", t: "Request sent", d: "The questions load on the next screen" });
    else L2.push({ p: "Getting the run ready", w: "Model and run size", t: "Ready to review", d: "Check it, then run" });
    return L2;
  }
  var TITLES = { brief: "Reading your brief", answers: "Building your spec", "2": "Who it is for", "3": "Setting the targets", "4": "Working out the limits", "5": "Looking for open data", spec: "Assembling your spec", more: "Assembling your spec" };

  // plays the stage, then goes on; live (a backend connected): each line ticks as its part is ready
  function stage(kind, s, ctx, to, extra) {
    if (!window.ChipInStage) { to(); return; }
    var L = lines(kind, s, ctx, extra), live = conn() === "on";
    s.stg = s.stg || {};
    var again = !!s.stg[kind]; s.stg[kind] = 1; ctx.save();
    var ctl = window.ChipInStage.play({
      title: TITLES[kind] || "Working", kicker: live ? "Live" : again ? "Replay, shortened" : "Replay of the design steps",
      mark: live ? "" : ctx.measured(s) ? "mea" : "sim", lines: L, live: live,
      stepMs: function (i) { return again ? 280 : L[i].ms || 1150; }, skip: "Skip",
      onEnd: function (open) { if (open) to(); }
    });
    if (live) { for (var k = 1; k <= L.length; k++) ctl.tick(k); ctl.finish(); }
  }

  function begin(s, ctx) {
    s.sq = null; s.stg = {};
    var go = function () {
      // the chat is the whole intake, with or without a backend (its own questions come at the end)
      var n = pending(s, ctx).length;
      s.sq = { ans: {}, order: [], done: false };
      stage("brief", s, ctx, function () { ctx.go("ask"); }, n);
    };
    // a reload: the connection may still be under test; wait for its answer (at most 5 s)
    if (conn() !== "checking") { go(); return; }
    var t0 = Date.now(), iv = setInterval(function () { if (conn() !== "checking" || Date.now() - t0 > 5000) { clearInterval(iv); go(); } }, 150);
  }
  function next(s, i, to, ctx) { stage(String(to), s, ctx, function () { ctx.go(to); }); }

  /* ---------- the chat ---------- */
  var BOT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2.5"/><path d="M9 2.5v3M15 2.5v3M9 18.5v3M15 18.5v3M2.5 9h3M2.5 15h3M18.5 9h3M18.5 15h3"/></svg>';
  var SEND = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  var CSS = ".iq .gfc{max-width:680px}.iq-feed{margin-top:24px}.iq-feed .old{animation:none}" +
    ".iq .msg{background:#fff;border-left-color:var(--blue7)}.iq .mav{background:#eef2ff;color:var(--blue7)}.iq .who{color:var(--blue7)}" +
    ".iq .mt b{font-weight:600}.iq-why{font-size:12.5px;color:var(--i600);margin:3px 0 0}" +
    ".iq-opts{margin-top:12px}.iq-opts button{min-height:36px;padding:6px 14px;border-color:rgb(43 85 208/.28);color:#1f3f9e;background:#f5f7ff}" +
    ".iq-opts button:hover{border-color:var(--blue7);background:#eef2ff}" +
    ".iq-in{display:flex;align-items:center;gap:8px;margin-top:10px;padding:6px 6px 6px 14px;border-radius:14px;border:1px solid rgb(0 0 0/.12);background:#fff}" +
    ".iq-in input{flex:1;min-width:0;border:0;outline:0;background:transparent;font-size:14px;height:30px;color:var(--i900)}" +
    ".iq-in:focus-within{border-color:var(--blue7);box-shadow:0 0 0 3px rgb(43 85 208/.12)}" +
    ".iq-in .send{width:32px;height:32px}.iq-in .send.ready{background:var(--blue7);color:#fff}" +
    ".iq-skip{margin-top:8px;font-size:12.5px;color:var(--i600);text-decoration:underline;text-underline-offset:2px}.iq-skip:hover{color:var(--i900)}" +
    ".iq .you p.sk{background:var(--i150);color:var(--i600);font-style:italic}" +
    ".iq-dots{display:inline-flex;gap:4px;padding:6px 0}.iq-dots i{width:6px;height:6px;border-radius:50%;background:var(--blue7);opacity:.3;animation:iqd 1.2s infinite}" +
    ".iq-dots i:nth-child(2){animation-delay:.2s}.iq-dots i:nth-child(3){animation-delay:.4s}@keyframes iqd{0%,100%{opacity:.25;transform:translateY(0)}40%{opacity:1;transform:translateY(-3px)}}" +
    ".iq-err{font-size:12.5px;color:var(--falsea-t);margin:8px 0 0}" +
    ".iq-gl{font-size:12px;font-weight:600;color:var(--i600);margin:12px 0 -6px}.iq-opts button[aria-pressed=true]{background:var(--blue7);border-color:var(--blue7);color:#fff}" +
    ".gsr.ia-h{padding-bottom:0;border-bottom:0}.gsr.ia-h .k{font-weight:600;color:var(--i900)}.ia-in{width:100%;max-width:280px}.ia-ch{margin-top:4px}.ia-ch button{min-height:30px;padding:3px 12px}";
  function css() { if (!document.getElementById("iq-css")) { var st = document.createElement("style"); st.id = "iq-css"; st.textContent = CSS; document.head.appendChild(st); } }
  var botHTML = function (inner) { return '<div class="msg"><span class="mav">' + BOT + '</span><div><div class="who">ChipIn</div>' + inner + "</div></div>"; };
  var youHTML = function (a, skip) { return '<div class="you"><p' + (skip ? ' class="sk"' : "") + ">" + esc(a) + "</p></div>"; };
  function introHTML(s) {
    var have = [s.device && "<b>" + esc(s.device) + "</b>", s.signal && "<b>" + esc(s.signal) + "</b>"].filter(Boolean).join(", ");
    return botHTML('<div class="mt">' + (have ? "From your brief I have " + have + "." : "I could not read a device from your brief.") + " A few quick questions to pin it down.</div>");
  }
  function askHTML(s, ctx, q, err) {
    return botHTML('<div class="mt">' + esc(q.q(s, ctx)) + '</div><p class="iq-why">' + esc(q.why) + "</p>" +
      (q.groups ? q.groups(s, ctx).map(function (g) { return '<p class="iq-gl">' + esc(g.label) + '</p><div class="gch iq-opts" role="group" data-iq-g="' + esc(g.key) + '" aria-label="' + esc(g.label) + '">' + g.opts.map(function (o) { return '<button type="button" aria-pressed="false" data-iq-gv="' + esc(o[1]) + '"><span>' + esc(o[0]) + "</span></button>"; }).join("") + "</div>"; }).join("")
        : '<div class="gch iq-opts" role="group" aria-label="' + esc(q.q(s, ctx)) + '">' + q.opts(s, ctx).map(function (o) { return '<button type="button" data-iq-v="' + esc(o[1]) + '"><span>' + esc(o[0]) + "</span></button>"; }).join("") + "</div>") +
      '<form class="iq-in" data-iq-form><input type="text" data-voice aria-label="Your answer" placeholder="' + esc(q.ph || "Or type your own answer") + '" autocomplete="off"><button type="submit" class="send" aria-label="Send">' + SEND + "</button></form>" +
      (err ? '<p class="iq-err" role="alert">' + esc(err) + "</p>" : "") +
      '<button type="button" class="iq-skip" data-iq-skip>Skip this question</button>');
  }
  function render(s, ctx) {
    if (!s) return false;
    css();
    s.sq = s.sq || { ans: {}, order: [], done: false };
    var main = $("#main"), busy = false;
    function cur() { return s.sq.done ? null : pending(s, ctx)[0] || null; }
    var live = conn() === "on", FQ = window.ChipInQuestions;
    var scripted = function () { return s.sq.order.filter(function (id) { return !/^fq:/.test(id); }).length; };
    function kicker() {
      var q = cur(), k = scripted() + (q ? 1 : 0), n = scripted() + pending(s, ctx).length;
      return (q ? "Question " + k + " of " + n : s.sq.done ? "All answered" : live ? "Your backend's questions" : "All answered") + (live ? " · then your backend's own questions" : " · scripted, no backend connected");
    }
    main.innerHTML = '<div class="gf iq" id="gf"><div class="gfc"><header class="gfh"><p class="gfn" id="iqK"></p><h1 tabindex="-1" id="gfH">A few questions first</h1></header>' +
      '<div class="iq-feed" id="iqFeed" aria-live="polite"></div>' +
      '<div class="gfa"><button type="button" class="btn s" data-iq-go="back"><svg class="i s16" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>Back</button><span class="grow"></span><button type="button" class="btn s" id="iqEnd" data-iq-go="end">Skip the questions</button></div></div></div>';
    var feed = $("#iqFeed"), root = $("#gf");
    var transcript = introHTML(s) + s.sq.order.map(function (id) { var q = byId(id), a = s.sq.ans[id]; return botHTML('<div class="mt">' + esc(a.q || (q ? q.q(s, ctx) : id)) + "</div>") + youHTML(a.a, a.skip); }).join("");
    feed.innerHTML = transcript;
    if (s.sq.order.length) [].forEach.call(feed.children, function (n) { n.classList.add("old"); }); // a revisit: the transcript is already read
    function paintTop() {
      $("#iqK").textContent = kicker();
      var over = s.sq.done || (!cur() && !(live && !s.sq.fqDone)); // the backend's questions still to come count as open
      var e = $("#iqEnd"); if (e) { e.className = over ? "btn p" : "btn s"; e.textContent = over ? "Continue" : "Skip the questions"; }
    }
    function add(html) { var d = document.createElement("div"); d.innerHTML = html; while (d.firstChild) feed.appendChild(d.firstChild); }
    function showAsk(err) {
      var q = cur(); paintTop();
      if (!q) { finish(); return; }
      add(askHTML(s, ctx, q, err));
      var box = feed.lastElementChild, inp = box.querySelector("input"), send = box.querySelector(".send");
      inp.addEventListener("input", function () { send.classList.toggle("ready", !!inp.value.trim()); });
      if (feed.childElementCount > 2) box.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
    function typing(ms, then) {
      busy = true; add('<div class="msg iq-typing"><span class="mav">' + BOT + '</span><div><div class="who">ChipIn</div><span class="iq-dots" aria-label="Writing"><i></i><i></i><i></i></span></div></div>');
      setTimeout(function () { if (!root.isConnected) return; var t = feed.querySelector(".iq-typing"); if (t) t.remove(); busy = false; then(); }, ms);
    }
    function answer(q, v, label, text) {
      if (busy || !q) return;
      var skip = v === "__skip", ok = skip || q.apply(s, ctx, v, text);
      if (skip && q.skip) q.skip(s, ctx);
      var box = feed.lastElementChild;
      if (!ok && text != null) {
        // not read: keep it as a note on the spec card, and move on
        s.sq.notes = (s.sq.notes || []).concat([q.q(s, ctx) + " " + text]);
      }
      var qText = q.q(s, ctx);
      box.outerHTML = botHTML('<div class="mt">' + esc(qText) + "</div>");
      s.sq.order.push(q.id); s.sq.ans[q.id] = { q: qText, a: label, skip: v === "__skip" };
      ctx.save();
      add(youHTML(label, v === "__skip"));
      paintTop();
      var then = function () { typing(cur() ? 850 : 650, function () { showAsk(); }); };
      if (q.id === "data" && !skip && s.data === "public") { busy = true; dataSearch(function () { busy = false; then(); }); return; }
      if (q.id === "data" && !skip && s.data === "own") add(botHTML('<div class="mt">Attach them under Data on your spec. Files stay in this browser.</div>'));
      then();
    }
    // the dataset search, inside the chat: the set on record for the device's signal, and how well it fits
    function dataSearch(then) {
      var sig = ctx.sigOf(s), d = s.ds && ctx.dsf[s.ds], f = d ? ctx.fit(s, s.ds) : null;
      if (!d) { s.data = "sim"; ctx.save(); }
      var L = [
        { p: "Searching PhysioNet and Zenodo", w: "For " + (sig ? sig.toUpperCase() + " recordings" : "recordings of your signal"), t: "Searched PhysioNet and Zenodo", d: esc(sig ? sig.toUpperCase() + " recordings" : (s.signal || "Your signal")) },
        d ? { p: "Picking a dataset", w: "Reading its labels and licence", t: "Found: " + d.short, tHTML: "Found: " + link(d.url, d.short), d: esc(d.labels + " · " + d.lic) }
          : { p: "Picking a dataset", w: "Looking for a set that fits", t: "No open set matches", d: "Simulated data instead, from a small stated model", warn: true }
      ];
      if (f) L.push({ p: "Checking the fit with your device", w: "Signal, patients and labels", t: f.warn.length ? "Fit: " + f.warn.length + " warning" + (f.warn.length === 1 ? "" : "s") : "Fits, approximately", d: esc(f.warn.length ? f.warn.join(" ") : "Recorded on other devices: treat results as approximate"), warn: f.warn.length > 0 });
      var SG = window.ChipInStage, draw = function (k) { return SG ? SG.inline(L, k) : ""; };
      add(botHTML('<div class="mt">Looking for open data</div><p class="iq-why">From the public sets on record in this demo.</p><div data-iq-ds>' + draw(0) + "</div>"));
      var box = feed.lastElementChild.querySelector("[data-iq-ds]"), k = 0;
      box.scrollIntoView({ block: "nearest", behavior: "smooth" });
      (function step() {
        setTimeout(function () {
          if (!root.isConnected) return;
          k++; box.innerHTML = draw(k);
          if (k < L.length) step(); else { box.removeAttribute("data-iq-ds"); then(); }
        }, 1100);
      })();
    }
    // with a backend connected: its own questions, once, after the scripted ones (../i1-questions.js)
    function backendQuestions() {
      typing(400, function () {
        busy = true;
        add(botHTML('<div class="mt">Asking your backend for any follow-up questions</div><span class="iq-dots" aria-label="Waiting"><i></i><i></i><i></i></span>'));
        var wait = feed.lastElementChild;
        FQ.ask(s, ctx.save, function (qs) {
          if (!root.isConnected) return;
          busy = false; wait.remove();
          var left = triage(s, qs || []).filter(function (q) { return !s.sq.ans["fq:" + q.id]; });
          (function next(i) {
            if (i >= left.length) { s.sq.fqDone = true; ctx.save(); finish(); return; }
            askFq(left[i], function () { typing(650, function () { next(i + 1); }); });
          })(0);
        });
      });
    }
    function askFq(q, then) {
      var ctl = q.kind === "choice"
        ? '<div class="gch iq-opts" role="group" aria-label="' + esc(q.question) + '">' + q.options.map(function (o) { return '<button type="button" data-fqc="' + esc(o) + '"><span>' + esc(FQ.label(o)) + "</span></button>"; }).join("") + "</div>"
        : '<form class="iq-in" data-fqf><input type="text" data-voice aria-label="' + esc(q.question) + '" value="' + esc(q["default"]) + '" autocomplete="off"><button type="submit" class="send ready" aria-label="Send">' + SEND + "</button></form>";
      add(botHTML('<div class="mt">' + esc(q.question) + '</div><p class="iq-why">' + esc(q.why) + "</p>" + ctl));
      var box = feed.lastElementChild;
      box.scrollIntoView({ block: "nearest", behavior: "smooth" });
      var done = function (v, shown) {
        FQ.answer(s, q.id, v);
        box.outerHTML = botHTML('<div class="mt">' + esc(q.question) + "</div>");
        s.sq.order.push("fq:" + q.id); s.sq.ans["fq:" + q.id] = { q: q.question, a: shown };
        ctx.save(); add(youHTML(shown)); then();
      };
      box.addEventListener("click", function (e) { var b = e.target.closest("[data-fqc]"); if (b) done(b.dataset.fqc, b.textContent.trim()); });
      box.addEventListener("submit", function (e) { e.preventDefault(); e.stopPropagation(); var t = box.querySelector("input").value.trim(); if (t) done(t, t); });
    }
    function toSpec() { stage("answers", s, ctx, function () { ctx.go("spec"); }); }
    function finish() {
      if (s.sq.done) { paintTop(); return; }
      if (live && FQ && FQ.ask && !s.sq.fqDone) { backendQuestions(); return; }
      s.sq.done = true; ctx.save(); paintTop();
      add(botHTML('<div class="mt">Thanks. Building your spec from the brief and your answers.</div>'));
      setTimeout(function () { if (root.isConnected && /#\/new\/ask/.test(location.hash)) toSpec(); }, 900);
    }
    root.addEventListener("click", function (e) {
      var gv = e.target.closest("[data-iq-gv]");
      if (gv && !busy) {
        var grp = gv.closest("[data-iq-g]"), box = gv.closest(".msg");
        grp.querySelectorAll("[data-iq-gv]").forEach(function (b) { b.setAttribute("aria-pressed", String(b === gv)); });
        var all = box.querySelectorAll("[data-iq-g]"), pick = {}, lab = [], full = true;
        [].forEach.call(all, function (g) { var on = g.querySelector('[aria-pressed="true"]'); if (on) { pick[g.dataset.iqG] = on.dataset.iqGv; lab.push(on.textContent.trim()); } else full = false; });
        if (full) answer(cur(), pick, lab.join(" · "));
        return;
      }
      var o = e.target.closest("[data-iq-v]");
      if (o) { answer(cur(), o.dataset.iqV, o.textContent.trim()); return; }
      if (e.target.closest("[data-iq-skip]")) { answer(cur(), "__skip", "Skipped"); return; }
      var g = e.target.closest("[data-iq-go]");
      if (!g) return;
      if (g.dataset.iqGo === "back") { ctx.back(); return; }
      if (s.sq.done || !cur()) { s.sq.done = true; ctx.save(); toSpec(); return; }
      s.sq.done = true; ctx.save(); toSpec();
    });
    root.addEventListener("submit", function (e) {
      if (!e.target.matches("[data-iq-form]")) return;
      e.preventDefault();
      var inp = e.target.querySelector("input"), t = inp ? inp.value.trim() : "";
      if (!t) { if (inp) inp.focus(); return; }
      answer(cur(), null, t, t);
    });
    paintTop();
    $("#gfH").focus({ preventScroll: true });
    if (s.sq.done) { paintTop(); return true; }
    if (!s.sq.order.length) typing(900, function () { showAsk(); }); else showAsk();
    return true;
  }

  /* ---------- the backend's own questions: never one the five turns or an assumed row cover, at most two ---------- */
  var MAX_FQ = 2;
  function topicOf(q) {
    var t = String(q.id || "").replace(/_/g, " ") + " " + String(q.question || "");
    for (var k in ASM) if (ASM[k].re.test(t)) return k;
    return REUSE_RE.test(t) ? "reuse" : FIXED_RE.test(t) ? "fixed" : "";
  }
  // marks each question on s.fq: drop (covered: answered from the spec), capped (past two: its default, listed
  // under Assumed); returns the ones to ask
  function triage(s, qs) {
    var drop = {}, capped = {}, keep = [];
    qs.forEach(function (q) { var k = topicOf(q); if (k) drop[q.id] = k; else if (keep.length < MAX_FQ) keep.push(q); else capped[q.id] = true; });
    if (s.fq) { s.fq.drop = drop; s.fq.capped = capped; }
    return keep;
  }
  // the answer a covered backend question gets: the assumed row's value, or null to leave it out
  function coveredAnswer(s, key) {
    if (ASM[key]) return asmVal(s, key);
    if (key === "reuse") return s.cons && s.cons.reusable === true ? "Reusable" : s.cons && s.cons.reusable === false ? "Single-use" : null;
    return null;
  }

  /* ---------- the spec card ---------- */
  var S = null, SV = null;
  var tagOf = function (t) { return t.src === "brief" ? "From your brief" : t.src === "answer" ? "From your answer" : t.src === "you" ? "As you set it" : "Default for the task type"; };
  // the first two rows: sensitivity, then the second target
  function topRows(s, ctx) {
    if (!s || !s.targets) return "";
    var p = ctx.places[s.place] || ctx.places.ward;
    return ["sensitivity", secondOf(s)].map(function (m) {
      var t = m && s.targets.filter(function (x) { return x.metric === m; })[0];
      if (!t) return "";
      var k = m === "sensitivity" ? "Sensitivity" : m === "specificity" ? "Specificity" : "False alarms";
      var v = t.value == null ? "No value set" : (t.op === "<=" ? "At most " : "At least ") + (ctx.met[m].kind === "frac" ? pctS(t.value) : +(t.value * p.h).toFixed(3) + (p.per === "hour" ? " an hour" : " a " + p.per));
      return '<div class="gsr ia-top"><span class="k">' + k + '</span><div class="v">' + esc(v) + "<small>" + esc(tagOf(t)) + '</small></div><button type="button" class="gchg" data-go="3" aria-label="Change ' + k.toLowerCase() + '">Change</button></div>';
    }).join("");
  }
  // the metrics topRows shows, so the card's Targets row lists only the others
  function topMetrics(s) { return s && s.targets ? ["sensitivity", secondOf(s)].filter(Boolean) : []; }
  function chipsIA(key, opts, cur, label) {
    return '<div class="gch ia-ch" role="radiogroup" aria-label="' + esc(label) + '">' + opts.map(function (o) { return '<button type="button" role="radio" aria-checked="' + (o[0] === cur) + '" ' + (key === "reuse" ? 'data-c="reuse" data-v="' + esc(o[0]) + '"' : 'data-ia-k="' + key + '" data-ia-v="' + esc(o[0]) + '"') + "><span>" + esc(o[1]) + "</span></button>"; }).join("") + "</div>";
  }
  function cardRows(s, ctx) {
    if (!s || !s.cons) return "";
    S = s; SV = ctx && ctx.save;
    var row = function (k, body, note) { return '<div class="gsr ia-row"><span class="k">' + esc(k) + '</span><div class="v">' + body + (note ? "<small" + ' data-ia-note="' + esc(k) + '">' + esc(note) + "</small>" : "") + "</div></div>"; };
    var r = s.cons.reusable, words = /patch|sticker|adhesive|disposable|single[- ]use/i.test(s.brief || "");
    var html = '<div class="gsr ia-h"><span class="k">Assumed (edit if wrong)</span><div class="v"><small>Not asked: set from your brief and the device type.</small></div></div>';
    html += row("Single-use or reusable", chipsIA("reuse", [["disposable", "Single-use"], ["reusable", "Reusable"]], r === true ? "reusable" : r === false ? "disposable" : "", "Single-use or reusable"),
      r == null ? "Not in your brief; pick one if it matters" : r === false && words && !(s.touched && s.touched.reuse) ? "From the device words in your brief" : "As set");
    html += row(ASM.latency.k, '<div class="gie sm"><input class="gfin ia-in" data-ia="latency" data-voice value="' + esc(asmVal(s, "latency")) + '" aria-label="Alert latency"></div>', asmWhy(s, "latency"));
    html += row(ASM.noise.k, chipsIA("noise", ASM.noise.opts.map(function (o) { return [o, o]; }), asmVal(s, "noise"), "Signal noise"), asmWhy(s, "noise"));
    html += row(ASM.worse.k, chipsIA("worse", ASM.worse.opts.map(function (o) { return [o, o]; }), asmVal(s, "worse"), "Which error matters more"), asmWhy(s, "worse"));
    var FQ = window.ChipInQuestions;
    if (FQ && FQ.cardRows) html += FQ.cardRows(s, SV, "capped");
    // the answers already sit in the rows above; only what could not be read into a field shows here
    var notes = (s.sq && s.sq.notes) || [];
    if (notes.length) html += '<div class="gsr"><span class="k">Notes</span><div class="v">' + esc(notes.join("; ")) + '<small>Not read into a field; sent with your brief.</small></div><button type="button" class="gchg" data-go="ask" aria-label="See your answers">See chat</button></div>';
    return html;
  }
  // editing an assumed row in place
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-ia-v]");
    if (!b || !S) return;
    S.asm = S.asm || {}; S.asm[b.dataset.iaK] = b.dataset.iaV;
    b.parentNode.querySelectorAll("[data-ia-v]").forEach(function (x) { x.setAttribute("aria-checked", String(x === b)); });
    var n = b.closest(".v").querySelector("small"); if (n) n.textContent = "As you set it";
    if (typeof SV === "function") SV();
  });
  document.addEventListener("input", function (e) {
    var el = e.target;
    if (!el || !el.dataset || !el.dataset.ia || !S) return;
    S.asm = S.asm || {}; S.asm[el.dataset.ia] = el.value.trim();
    if (typeof SV === "function") SV();
  });
  // what the card shows but no field of the run's spec holds: sent as plain lines after the brief
  function briefNotes(s) {
    var k = (s && s.cons) || {}, L = [];
    if (k.batText) L.push("Battery: " + k.batText + ".");
    if (k.cost) L.push("Cost: " + k.cost + ".");
    if (s && s.targets) {
      L.push("Alert latency: " + asmVal(s, "latency") + ".");
      L.push("Signal noise: " + asmVal(s, "noise") + ".");
      L.push("Worse error: " + asmVal(s, "worse") + ".");
    }
    ((s && s.sq && s.sq.notes) || []).forEach(function (n) { L.push(n); });
    return L.join("\n");
  }

  window.ChipInIntake = { begin: begin, next: next, render: render, cardRows: cardRows, topRows: topRows, topMetrics: topMetrics, pending: pending, briefNotes: briefNotes, triage: triage, coveredAnswer: coveredAnswer };
})();
