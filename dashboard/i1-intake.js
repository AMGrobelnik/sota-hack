/* ChipIn i1 intake: the path from a typed brief to the guided steps (window.ChipInIntake).
 *
 * 1. Every forward move in the guided flow passes through the loading stage (../i1-stage.js): the brief
 *    submitted, the questions answered, each Next, and Review your spec. The lines say what is being
 *    worked out for the screen that follows and what was found, from the spec itself. On the public
 *    site the lines are a paced replay, marked as one; with a backend connected they tick as the work
 *    is done and the backend's own follow-up questions step (../i1-questions.js) is used as before.
 * 2. With no backend, a short brief gets up to five scripted questions in the chat style (#/new/ask),
 *    one at a time, each with quick picks, free text and a skip. Simple keyword rules pick them; a
 *    topic the brief already answers is never asked. The answers are written into the spec's own
 *    fields (what it detects, who and where, channels, the false-alarm or specificity target, the
 *    battery), so the steps that follow show them; what cannot be read goes on the spec card as notes.
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
  var MAX_Q = 5;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var cap = function (t) { t = String(t || "").trim(); return t ? t.charAt(0).toUpperCase() + t.slice(1) : t; };
  var link = function (url, text) { return url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(text) + "</a>" : esc(text); };
  var conn = function () { var l = window.ChipInLive && window.ChipInLive.i1, c = l && l.connection ? l.connection() : null; return c ? c.state : "off"; };
  var NUMW = { single: 1, one: 1, two: 2, three: 3, four: 4, six: 6, eight: 8 };

  /* ---------- the scripted questions ---------- */
  function setTarget(s, ctx, metric, value) {
    var t = s.targets.filter(function (x) { return x.metric === metric; })[0];
    if (!t) { t = { metric: metric, op: ctx.met[metric].op }; s.targets.push(t); }
    t.value = value; t.op = ctx.met[metric].op; t.src = "answer";
    s.touched.targets = true;
    if (!s.primary) s.primary = s.targets[0].metric;
  }
  var screening = function (s) { return s.task === "screening"; };
  var Q = [
    {
      id: "detect", open: function (s) { return !s.parsed.detect && !s.touched.detect; },
      q: function () { return "What must it detect?"; }, why: "The chip is trained and judged on exactly this.",
      opts: function (s, ctx) { var g = ctx.sigOf(s); return (g === "ecg" ? ["Atrial fibrillation", "Arrhythmia", "Bradycardia"] : g === "eeg" ? ["Seizures", "Brain-injury grade"] : ["Falls", "Apnoea", "Seizures"]).map(function (x) { return [x, x]; }); },
      apply: function (s, ctx, v, text) {
        var t = (v || text || "").trim(); if (!t) return false;
        s.detect = cap(t); s.touched.detect = true;
        if (!s.parsed.task && !s.touched.task) { s.task = ctx.parseBrief(t).task || "continuous"; s.touched.task = true; }
        ctx.parse(s); return true;
      }
    },
    {
      id: "sensor", open: function (s) { return !(s.parsed.sigs || []).length && !s.touched.signal; },
      q: function () { return "Which sensor does it use?"; }, why: "It decides which recordings can train the chip.",
      opts: function () { return [["ECG (heart)", "ECG"], ["EEG (brain)", "EEG"], ["PPG (optical pulse)", "PPG"], ["Accelerometer", "Accelerometer"]]; },
      apply: function (s, ctx, v, text) { var t = (v || text || "").trim(); if (!t) return false; s.signal = t; s.touched.signal = true; ctx.parse(s); return true; }
    },
    {
      id: "wear", open: function (s, ctx) { return !ctx.parseGroup(s.brief); },
      q: function () { return "Who wears it, and where?"; }, why: "It sets which recordings fit and how false alarms are counted.",
      opts: function () { return [["Adults, worn day and night", "adults|self"], ["Adults on a hospital ward", "adults|ward"], ["Children, at home overnight", "children|home"], ["Newborns in hospital", "newborns|ward"]]; },
      apply: function (s, ctx, v, text) {
        var g = v ? v.split("|")[0] : ctx.parseGroup(text || ""), p = v ? v.split("|")[1] : ctx.parsePlace(text || "");
        if (!g && !p) return false;
        if (g) { s.group = g; s.touched.group = true; }
        if (p) { s.place = p; s.touched.place = true; s.targets.forEach(function (t) { if (t.metric === "false_alarms_per_hour" && t.src === "default") t.value = ctx.places[p].fa; }); }
        return true;
      }
    },
    {
      id: "chans", open: function (s, ctx) { var g = ctx.sigOf(s); return !ctx.cases[s.case] && !s.parsed.chans && (g === "ecg" || g === "eeg"); },
      q: function (s, ctx) { return ctx.sigOf(s) === "ecg" ? "How many ECG leads can it have?" : "How many electrodes can it have?"; }, why: "Fewer means a smaller, cheaper device; the chart compares them.",
      opts: function (s, ctx) { return ctx.budgets(s).map(function (b) { return [b.label, String(b.ch)]; }).concat([["Find the best for me", "best"]]); },
      apply: function (s, ctx, v, text) {
        var t = String(v || text || "").toLowerCase(), b = ctx.budgets(s), m = t.match(/\b(\d+|single|one|two|three|four|six|eight)\b/);
        if (/best|any|not sure|don.?t know|you (?:pick|choose)/.test(t)) { s.cons.findBest = true; s.touched.cons = true; return true; }
        var n = m ? NUMW[m[1]] || parseInt(m[1], 10) : null, hit = b.filter(function (x) { return x.ch === n; })[0];
        if (!hit) return false;
        s.cons.findBest = false; s.cons.channels = hit.ch; s.touched.cons = true; return true;
      }
    },
    {
      id: "fa", open: function (s) { return s.task !== "grading" && !s.parsed.targets.some(function (t) { return t.metric === "false_alarms_per_hour" || t.metric === "specificity"; }); },
      q: function (s) { return screening(s) ? "How often may it flag a healthy recording?" : "How often may it raise a false alarm?"; },
      why: "Each false alarm costs trust; fewer needs a bigger chip.",
      opts: function (s) { return screening(s) ? [["1 in 10 recordings", "0.9"], ["1 in 20", "0.95"], ["1 in 50", "0.98"]] : [["At most 1 an hour", "1"], ["At most 1 a day", String(1 / 24)], ["At most 1 a week", String(1 / 168)]]; },
      apply: function (s, ctx, v, text) {
        var t = String(text || "").toLowerCase(), m;
        if (screening(s)) {
          var spec = v ? +v : (m = t.match(/1\s*in\s*(\d+)/)) ? 1 - 1 / +m[1] : (m = t.match(/(\d+(?:\.\d+)?)\s*%/)) ? +m[1] / 100 : null;
          if (!(spec > 0 && spec < 1)) return false;
          setTarget(s, ctx, "specificity", Math.round(spec * 1e4) / 1e4); return true;
        }
        var per = v ? +v : null;
        if (per == null && (m = t.match(/(\d+(?:\.\d+)?|one|an?)\s*(?:false\s*alarms?\s*)?(?:an?|per|each|every)?\s*(hour|day|night|week)/))) {
          var n = /^\d/.test(m[1]) ? +m[1] : 1; per = n / ({ hour: 1, day: 24, night: 12, week: 168 })[m[2]];
        }
        if (!(per > 0)) return false;
        if (!s.task) { s.task = "continuous"; s.touched.task = true; ctx.parse(s); }
        setTarget(s, ctx, "false_alarms_per_hour", Math.round(per * 1e6) / 1e6); return true;
      }
    },
    {
      id: "battery", open: function (s) { return !s.parsed.bat; },
      q: function () { return "How long must one battery last?"; }, why: "A longer life needs a bigger battery or a leaner chip.",
      opts: function () { return [["24 hours", "24|hours"], ["3 days", "3|days"], ["7 days", "7|days"], ["14 days", "14|days"]]; },
      apply: function (s, ctx, v, text) {
        var n, u, m;
        if (v) { n = +v.split("|")[0]; u = v.split("|")[1]; }
        else if ((m = String(text || "").toLowerCase().match(/(\d+(?:\.\d+)?)\s*-?\s*(hours?|hrs?|days?|weeks?)/))) { n = +m[1]; u = /^w/.test(m[2]) ? "days" : /^d/.test(m[2]) ? "days" : "hours"; if (/^w/.test(m[2])) n *= 7; }
        if (!(n > 0)) return false;
        s.cons.batN = n; s.cons.batU = u; s.touched.cons = true; return true;
      }
    }
  ];
  var byId = function (id) { return Q.filter(function (q) { return q.id === id; })[0]; };
  // the questions still to ask: open topics not yet answered, at most five in all
  function pending(s, ctx) {
    var a = (s.sq && s.sq.ans) || {}, done = Object.keys(a).length;
    return Q.filter(function (q) { return !a[q.id] && q.open(s, ctx); }).slice(0, Math.max(0, MAX_Q - done));
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
        { p: "Checking disposable or reusable", w: "It sets which batteries fit", t: s.cons.reusable ? "Reusable" : "Disposable", d: s.cons.reusable ? "Charged and cleaned between patients" : "One patient, then replaced" }
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
      var c = conn();
      if (c === "on") { stage("brief", s, ctx, function () { ctx.go(1); }); return; }
      var n = pending(s, ctx).length;
      if (n) s.sq = { ans: {}, order: [], done: false };
      stage("brief", s, ctx, function () { ctx.go(n ? "ask" : 1); }, n);
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
    ".iq-err{font-size:12.5px;color:var(--falsea-t);margin:8px 0 0}";
  function css() { if (!document.getElementById("iq-css")) { var st = document.createElement("style"); st.id = "iq-css"; st.textContent = CSS; document.head.appendChild(st); } }
  var botHTML = function (inner) { return '<div class="msg"><span class="mav">' + BOT + '</span><div><div class="who">ChipIn</div>' + inner + "</div></div>"; };
  var youHTML = function (a, skip) { return '<div class="you"><p' + (skip ? ' class="sk"' : "") + ">" + esc(a) + "</p></div>"; };
  function introHTML(s) {
    var have = [s.device && "<b>" + esc(s.device) + "</b>", s.signal && "<b>" + esc(s.signal) + "</b>"].filter(Boolean).join(", ");
    return botHTML('<div class="mt">' + (have ? "From your brief I have " + have + "." : "I could not read a device from your brief.") + " A few quick questions to pin it down.</div>");
  }
  function askHTML(s, ctx, q, err) {
    return botHTML('<div class="mt">' + esc(q.q(s, ctx)) + '</div><p class="iq-why">' + esc(q.why) + "</p>" +
      '<div class="gch iq-opts" role="group" aria-label="' + esc(q.q(s, ctx)) + '">' + q.opts(s, ctx).map(function (o) { return '<button type="button" data-iq-v="' + esc(o[1]) + '"><span>' + esc(o[0]) + "</span></button>"; }).join("") + "</div>" +
      '<form class="iq-in" data-iq-form><input type="text" data-voice aria-label="Your answer" placeholder="Or type your own answer" autocomplete="off"><button type="submit" class="send" aria-label="Send">' + SEND + "</button></form>" +
      (err ? '<p class="iq-err" role="alert">' + esc(err) + "</p>" : "") +
      '<button type="button" class="iq-skip" data-iq-skip>Skip this question</button>');
  }
  function render(s, ctx) {
    if (!s) return false;
    if (conn() === "on" && !(s.sq && s.sq.order.length)) { location.replace(location.pathname + location.search + "#/new/1"); return true; }
    css();
    s.sq = s.sq || { ans: {}, order: [], done: false };
    var main = $("#main"), busy = false;
    function cur() { return s.sq.done ? null : pending(s, ctx)[0] || null; }
    function kicker() {
      var q = cur(), k = s.sq.order.length + (q ? 1 : 0), n = s.sq.order.length + pending(s, ctx).length;
      return (q ? "Question " + k + " of " + n : "All answered") + " · scripted, no backend connected";
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
      var e = $("#iqEnd"); if (e) { e.className = s.sq.done || !cur() ? "btn p" : "btn s"; e.textContent = s.sq.done || !cur() ? "Continue" : "Skip the questions"; }
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
      typing(cur() ? 850 : 650, function () { showAsk(); });
    }
    function finish() {
      if (s.sq.done) { paintTop(); return; }
      s.sq.done = true; ctx.save(); paintTop();
      add(botHTML('<div class="mt">Thanks. Building your spec from the brief and your answers.</div>'));
      setTimeout(function () { if (root.isConnected && /#\/new\/ask/.test(location.hash)) stage("answers", s, ctx, function () { ctx.go(1); }); }, 900);
    }
    root.addEventListener("click", function (e) {
      var o = e.target.closest("[data-iq-v]");
      if (o) { answer(cur(), o.dataset.iqV, o.textContent.trim()); return; }
      if (e.target.closest("[data-iq-skip]")) { answer(cur(), "__skip", "Skipped"); return; }
      var g = e.target.closest("[data-iq-go]");
      if (!g) return;
      if (g.dataset.iqGo === "back") { ctx.back(); return; }
      if (s.sq.done || !cur()) { stage("answers", s, ctx, function () { ctx.go(1); }); return; }
      s.sq.done = true; ctx.save(); stage("answers", s, ctx, function () { ctx.go(1); });
    });
    root.addEventListener("submit", function (e) {
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

  function cardRows(s) {
    var a = s && s.sq && s.sq.ans; if (!a || !Object.keys(a).length) return "";
    var got = Object.keys(a).filter(function (k) { return !a[k].skip; }).map(function (k) { return a[k].a; }), notes = s.sq.notes || [];
    if (!got.length && !notes.length) return "";
    return '<div class="gsr"><span class="k">Your answers</span><div class="v">' + esc(got.join(" · ")) + (notes.length ? '<small>Not read into a field, kept as notes: ' + esc(notes.join("; ")) + "</small>" : "") + '</div><button type="button" class="gchg" data-go="1" aria-label="Change your answers">Change</button></div>';
  }

  window.ChipInIntake = { begin: begin, next: next, render: render, cardRows: cardRows, pending: pending };
})();
