/* ChipIn i1 live mode: a real backend run drives the run view of dashboard/variants/i1.html.
 *
 * Classic script, no dependencies. Load ../live.js first (the stream reader, window.ChipInLive),
 * then this file; it adds window.ChipInLive.i1, which the page calls from a few marked hook lines.
 * Nothing here is simulated: every number on a live run's pages comes from the run's event stream
 * or its files. Without a connected backend the page's example runs behave exactly as before.
 *
 *   ChipInLive.i1.owns()            true when the address is a live run (#/live/<run id>/<view>)
 *   ChipInLive.i1.render()          draws that run's view into #main; returns true when it did
 *   ChipInLive.i1.start(spec, done) Run on the "Your spec" card: with a backend connected it sends
 *                                   POST /api/runs, calls done() once the run exists and returns true;
 *                                   without one it says this is an example run and returns false
 *   ChipInLive.i1.configure(panel)  adds the Backend section after Configure's panel
 *   ChipInLive.i1.recents()         sidebar HTML: the connection chip and the backend's runs
 *   ChipInLive.i1.sig()             changes whenever that HTML has to be redrawn
 *   ChipInLive.i1.state()           { connection, base, runs } (for tests)
 *   ChipInLive.i1.exampleBox()      the message box, disabled and explained, for an example run's Chat tab
 *
 * The message box (under the Overview's log and in the Chat tab) talks to the run's agent through
 * POST /api/runs/{id}/messages: your message shows at once, then its delivery from the stream
 * (sent, waiting, reached the agent). On a finished run it sends a follow-up and reopens the stream.
 *
 * The server address and token are kept in this browser's localStorage only (never in the URL or
 * the page). A page served by the backend itself finds it on its own origin and asks only for the
 * token, or takes it once from a #token=... fragment, which is removed from the address at once.
 * A browser with nothing stored (any visitor of the public page) uses the public backend (PUBLIC
 * below); a stored link wins, and one that is refused or silent falls back to the public backend.
 *
 * What a run sends: POST /api/runs { prompt, preset, agent, model, spec }: agent and model from the
 * chosen one of the four models (RUN_MODELS in chipin-models.js). spec follows the
 * dashboard contract (brief, device, signal, detect, task_types, patient_group, place, fa_unit,
 * targets, primary, constraints, data); the backend checks it, saves it as workspace/spec.json and
 * puts it on run.started.
 * What a run reads: the event stream (run.started, stage, status, message, tool, metric, artifact,
 * chosen, cost, error, evidence, run.finished, design, subagent.started, subagent.finished,
 * stage.merged), GET /api/runs, GET /api/runs/{id}/files and /file (spec.json, the report and other
 * artifacts) and POST /api/runs/{id}/stop and /messages. */
(function () {
  "use strict";
  var L = window.ChipInLive;
  if (!L || typeof L.watch !== "function") return; // live.js is missing: the page stays as it is
  var F = window.ChipInFold; // ../i1-fold.js: the figures, shared with the recorded playback
  if (!F) return;

  /* ---------- helpers ---------- */
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return F.scrub(String(s == null ? "" : s)).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var fmt = function (n) { return Math.round(n).toLocaleString("en-GB"); };
  var clamp = function (x, a, b) { return Math.max(a, Math.min(b, x)); };
  var cap = function (s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; };
  // a live run's size as the page names it: Pro · 15 agents (subagents per run, set by the preset)
  var SIZE_AGENTS = { lite: 5, pro: 15, max: 50 };
  var runSize = function (M) { var n = SIZE_AGENTS[String(M.r.preset).toLowerCase()]; return cap(M.r.preset) + (n ? " · " + n + " agents" : ""); };
  var clip = function (s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n - 1) + "…" : s; };
  var clock = function (s) { s = Math.max(0, Math.floor(s)); var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = String(s % 60).padStart(2, "0"); return h ? h + ":" + String(m).padStart(2, "0") + ":" + x : m + ":" + x; };
  var tsMs = function (ts) { var t = Date.parse(ts || ""); return isNaN(t) ? null : t; };
  var num = function (v) { return typeof v === "number" && isFinite(v) ? v : null; };
  var bytes = function (n) { return n == null ? "" : n < 1024 ? n + " B" : n < 1048576 ? (n / 1024).toFixed(n < 10240 ? 1 : 0) + " KB" : (n / 1048576).toFixed(1) + " MB"; };
  var pl = function (n, w) { return n + " " + w + (n === 1 ? "" : "s"); };
  var dur = function (h) { return h >= 1 ? +h.toFixed(1) + " h" : +(h * 60).toFixed(1) + " min"; };
  var andList = function (a) { return a.length < 2 ? (a[0] || "") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]; };
  var SVG = {
    check: '<path d="M20 6 9 17l-5-5"/>', x: '<path d="M18 6 6 18M6 6l12 12"/>', file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
    down: '<path d="m6 9 6 6 6-6"/>', right: '<path d="m9 6 6 6-6 6"/>', stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>', up: '<path d="M12 19V5M5 12l7-7 7 7"/>',
    chip: '<rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4"/>', minus: '<path d="M5 12h14"/>'
  };
  var I = function (n, c) { return '<svg class="i ' + (c || "s14") + '" viewBox="0 0 24 24" aria-hidden="true">' + SVG[n] + "</svg>"; };
  function lsGet(k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } }
  function lsSet(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage off: nothing is kept */ } }

  var K_CONN = "chipin-i1-backend", K_RUNS = "chipin-i1-live-runs", K_VIEW = "chipin-i1-live-view";
  var STAGES = ["spec", "reference", "propose", "finetune", "compile", "verify", "report"];
  var STAGE_N = { spec: "Spec", reference: "Reference", propose: "Propose", finetune: "Fine-tune", compile: "Compile", verify: "Verify", report: "Report" };
  var BCOL = ["#2b55d0", "#0f7a55", "#a04812", "#6b46c1"];
  var CREDIT = "Built at the SoTA Scientific Parallelism Hackathon, London, November 2026. Supported by Callosum, Inherent Labs, ARIA and Fractile.";
  var loopback = /^https?:$/.test(location.protocol) && /^(127\.0\.0\.1|localhost)$/.test(location.hostname);
  var apiParam = (function () { try { return new URLSearchParams(location.search).get("api"); } catch (e) { return null; } })();

  /* ---------- a one-time #token=... fragment: kept for this origin's backend, removed from the address ---------- */
  (function takeFragmentToken() {
    var h = location.hash.replace(/^#/, "");
    if (!/(^|&)token=/.test(h)) return;
    var p = new URLSearchParams(h), tok = p.get("token");
    p.delete("token");
    var rest = p.toString();
    try { history.replaceState(history.state, "", location.pathname + location.search + (rest ? "#" + rest : "")); } catch (e) { /* file:// */ }
    var base = apiParam ? apiParam.replace(/\/+$/, "") : loopback ? location.origin : null;
    if (tok && base) lsSet(K_CONN, { base: base, token: tok });
  })();

  /* ---------- connection ---------- */
  // state: off (nothing set up), found (a backend on this origin, no token yet), checking, on, bad
  var C = { state: "off", kind: "", base: null, token: null, msg: "", defaults: null, same: false, pub: false, v: 0 };
  // the default backend for a browser with no link stored; the token is deliberately public (anyone may run), fine to commit
  var PUBLIC = { base: "https://api.chipin.space", token: "chipin-public-demo" };
  var hostOf = function () { return C.pub ? "the live backend" : C.base ? C.base.replace(/^https?:\/\//, "") : ""; };
  var REASON = {
    unreachable: "No backend answers at this address. Start it, then test again.",
    "no-token": "The backend is running and needs its token.",
    "bad-token": "The backend did not accept this token. Paste the link it printed again.",
    "version-mismatch": "This backend speaks another version of the API.",
    unhealthy: "The backend answered but reported a problem."
  };
  function bump() { C.v++; try { if (window.ChipInConn) window.ChipInConn.set(C.state === "on" ? "" : C.kind); } catch (e) { /* banner only */ } if (V && V.cfgMounted) paintConfigure(); }
  // pub: the default public backend (never stored, no banner); hold: a failure is left for the caller to show
  function connect(base, token, pub, hold) {
    base = String(base || "").trim().replace(/\/+$/, "");
    if (!/^https?:\/\/[^\s/]+$/.test(base)) { C.state = "bad"; C.pub = false; C.msg = "Enter the address as http://127.0.0.1:<port>."; bump(); return Promise.resolve({ ok: false }); }
    var st = lsGet(K_CONN), stored = !pub && !!(st && st.base === base);
    C.state = "checking"; C.pub = !!pub; C.kind = ""; C.base = base; C.token = token || null; C.msg = ""; bump();
    return L.connect({ base: base, token: token || undefined }).then(function (r) {
      try { sessionStorage.removeItem("chipin.token:" + base); } catch (e) { /* the reader's tab copy; ours is in localStorage */ }
      if (r.ok) {
        C.state = "on"; C.kind = ""; C.defaults = r.defaults || null;
        if (!pub) lsSet(K_CONN, { base: base, token: token });
        syncList();
      } else if (pub) {
        // the public backend is off or refuses the token: a calm "offline" chip, examples only, no banner
        C.state = "off"; C.kind = ""; C.msg = "";
      } else {
        // a stored backend that cannot be used: its link expired (token rejected) or it does not answer
        C.kind = !stored ? "" : /^(bad-token|http-40[13])$/.test(r.reason) ? "expired" : r.reason === "unreachable" ? "unreachable" : "";
        C.state = r.reason === "no-token" && C.same ? "found" : "bad";
        C.msg = REASON[r.reason] || ("The backend could not be used (" + r.reason + ").");
        // an https page and an http loopback backend: the browser, not the backend, is the usual cause
        if (r.reason === "unreachable" && location.protocol === "https:" && /^http:/.test(base)) C.msg = "This https page may not reach a backend on your computer: Chrome asks first for local network access (allow it, then test again) and Safari blocks it. Or open the dashboard from the backend itself: " + base + "/dashboard/variants/i1.html with the token the backend printed.";
        if (r.reason === "unreachable" && !token) C.state = "off";
      }
      if (r.ok || !hold) bump();
      return r;
    });
  }
  function connectPublic() { return connect(PUBLIC.base, PUBLIC.token, true); }
  // a link-stored backend wins; one that refuses its token or does not answer falls back to the public
  // default, and its banner shows only when the default fails too
  function connectStored(saved) {
    return connect(saved.base, saved.token, false, true).then(function (r) {
      if (r.ok || !/^(bad-token|http-40[13]|unreachable)$/.test(r.reason || "")) { if (!r.ok) bump(); return r; }
      var kind = C.kind, msg = C.msg;
      return connectPublic().then(function (p) { if (!p.ok && kind) { C.kind = kind; C.msg = msg; bump(); } return p; });
    });
  }
  function boot() {
    var saved = lsGet(K_CONN);
    if (saved && saved.base && saved.base !== PUBLIC.base) { C.same = loopback && saved.base === location.origin; return connectStored(saved); }
    return connectPublic();
  }
  // voice.js asks the reader for the token; answer from here so no tab copy has to be kept
  try { Object.defineProperty(L, "token", { configurable: true, get: function () { return C.state === "on" ? C.token : null; } }); } catch (e) { /* older reader */ }
  L.onStatus(function (s) {
    if (s === "disconnected" && C.state === "on") {
      C.state = "bad"; C.msg = "The backend stopped answering. Runs resume when it is back."; bump();
      // the stream dropped: if the health route is silent too, the run view says the connection was lost
      fetch(C.base + "/api/health", { cache: "no-store" }).then(function (r) { if (!r.ok) throw 0; }).catch(function () { if (C.state === "bad" && !C.lost) { C.lost = true; C.lostAt = Date.now(); bump(); } });
    }
    else if (s === "connected") { if (C.lost) { C.lost = false; bump(); } if (C.state === "bad" && C.token) { C.state = "on"; C.msg = ""; bump(); } }
  });
  // the health probe: the connection chip and the lost note follow it on every view, a finished
  // run's page and a recorded run included (a finished run has no open stream to notice the loss)
  var probing = false;
  setInterval(function () {
    if (probing || !C.base || !C.token || (C.state !== "on" && C.state !== "bad")) return;
    probing = true;
    var ac = typeof AbortController === "function" ? new AbortController() : null, tm = setTimeout(function () { if (ac) ac.abort(); }, 2500);
    fetch(C.base + "/api/health", { cache: "no-store", signal: ac ? ac.signal : undefined }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); })
      .then(function () { if (C.lost || C.kind === "unreachable") { C.lost = false; if (C.state === "bad") connect(C.base, C.token, C.pub); else bump(); } })
      .catch(function () {
        var was = C.state + C.lost;
        if (!C.lost) { C.lost = true; C.lostAt = Date.now(); }
        if (C.state === "on") { C.state = "bad"; C.msg = "The backend stopped answering. Runs resume when it is back."; C.kind = C.pub ? "" : "unreachable"; }
        if (was !== C.state + C.lost) bump();
      })
      .then(function () { clearTimeout(tm); probing = false; });
  }, 3000);
  function init() {
    var saved = lsGet(K_CONN);
    // the backend is checked again whenever the tab comes back to the front
    document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible" && C.state !== "on" && C.state !== "checking" && C.state !== "found") boot(); });
    if ((saved && saved.base) || !loopback) { boot(); return; }
    // served by the backend itself? Its health route needs no token. A plain static server: the public default.
    fetch(location.origin + "/api/health", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (h) {
      if (h && h.ok === true && h.version === 1) { C.same = true; C.base = location.origin; C.state = "found"; C.msg = REASON["no-token"]; C.defaults = h.defaults || null; bump(); }
      else connectPublic();
    }).catch(function () { connectPublic(); });
  }

  /* ---------- the backend's runs ---------- */
  var RUNS = (lsGet(K_RUNS) || []).filter(function (r) { return r && typeof r.id === "string"; });
  function saveRuns() { lsSet(K_RUNS, RUNS.slice(0, 40)); }
  var findRun = function (id) { for (var i = 0; i < RUNS.length; i++) if (RUNS[i].id === id) return RUNS[i]; return null; };
  var shownRuns = function () { return C.base ? RUNS.filter(function (r) { return r.base === C.base; }) : []; };
  var listT = 0;
  function syncList() {
    if (C.state !== "on") return;
    L.listRuns().then(function (list) {
      var seen = 0;
      list.forEach(function (s) {
        var r = findRun(s.id);
        if (r) { if (s.status) r.status = s.status; return; }
        if (seen++ >= 5) return; // runs started elsewhere: the newest few
        RUNS.push({ id: s.id, base: C.base, title: clip(s.prompt || s.id, 60), brief: s.prompt || "", status: s.status || "running", created: s.started_at || null, server: true });
      });
      RUNS.sort(function (a, b) { return String(b.created || "").localeCompare(String(a.created || "")); });
      saveRuns(); bump();
    }).catch(function () { /* the status chip says so */ });
  }
  setInterval(function () {
    if (C.state === "on" && RUNS.some(function (r) { return r.base === C.base && r.status === "running" && !(W[r.id] && W[r.id].open); }) && Date.now() - listT > 5000) { listT = Date.now(); syncList(); }
  }, 1000);

  /* ---------- watching one run: the reader's state plus what the i1 view needs ---------- */
  var W = {}; // id -> { w (reader watcher), st, x (extra state), open }
  function watchRun(id) {
    if (W[id]) return W[id];
    var x = { f: F.create(), items: [], tools: {}, subOpen: {}, final: null, spec: null, named: {}, evidence: null, v: 0, files: null, filesAt: 0, filesN: -1, chips: {}, umsg: {}, lastUser: null, wantLive: false };
    var rec = { id: id, x: x, open: true, st: null, w: null, h: null };
    rec.h = {
      onEvent: function (ev, st) {
        F.scrubEvent(ev);
        rec.st = st; reduce(x, ev, st);
        if (window.ChipInMessages) window.ChipInMessages.feed(ev, id); /* MESSAGES HOOK: the message view (../i1-messages.js) reads the same stream */
        if (ev.type === "run.started") { var rr = findRun(id); if (rr && (rr.title === id || !rr.title) && ev.prompt) { rr.title = clip(ev.prompt, 60); rr.brief = ev.prompt; saveRuns(); bump(); } }
        if (ev.type === "run.finished") { rec.open = false; var r = findRun(id); if (r) { r.status = ev.status; saveRuns(); } bump(); }
        else if (!rec.open) { rec.open = true; var f = findRun(id); if (f) { f.status = "running"; saveRuns(); } bump(); } // a follow-up
      }
    };
    rec.w = L.watch(id, rec.h);
    rec.st = rec.w.state;
    W[id] = rec;
    return rec;
  }
  // After a follow-up is sent: the reader's stream closed at run.finished, so open it again from the next seq.
  function resume(rec) {
    var w = rec.w;
    if (typeof w.isClosed !== "function") return; // an older reader: the next page load catches up
    if (w.isClosed()) { rec.w = L.watch(rec.id, rec.h, { state: rec.st }); rec.x.wantLive = false; }
    else if (!rec.st.finished) rec.x.wantLive = false; // the open stream carried the follow-up
  }
  function push(x, it, ev) { it.seq = ev.seq; it.ts = ev.ts; if (ev.agent) it.agent = ev.agent; x.items.push(it); }
  function reduce(x, ev, st) {
    x.v++;
    var fd = F.fold(x.f, ev);
    switch (ev.type) {
      case "run.started": if (ev.spec && typeof ev.spec === "object") x.spec = ev.spec; break;
      case "stage": push(x, { k: "stage", n: ev.stage || ev.name, state: ev.state, reason: ev.reason || "" }, ev); break;
      case "status": {
        // the delivery of your message is shown on the message itself, not as a line of its own
        var um = ev.message_id ? x.umsg[ev.message_id] : null;
        if (um && /reached/i.test(ev.text || "")) { um.dlv = "reached"; um.chg = x.v; break; }
        if (/^Your message waits/i.test(ev.text || "") && x.lastUser && x.lastUser.dlv === "sent") { x.lastUser.dlv = "waiting"; x.lastUser.chg = x.v; break; }
        push(x, { k: "status", text: ev.text || "" }, ev);
        break;
      }
      case "message": {
        var mi = { k: "msg", role: ev.role, author: ev.author, text: ev.text || "" };
        if (ev.role === "user") { mi.mid = ev.message_id || null; mi.dlv = mi.mid ? "sent" : null; if (mi.mid) x.umsg[mi.mid] = mi; x.lastUser = mi; }
        push(x, mi, ev);
        break;
      }
      case "tool": {
        var t = x.tools[ev.call_id];
        if (!t) { t = { k: "tool", id: ev.call_id, name: ev.name, summary: ev.summary, state: ev.state, detail: ev.detail || null }; x.tools[ev.call_id] = t; push(x, t, ev); }
        else { if (ev.name) t.name = ev.name; if (ev.summary) t.summary = ev.summary; if (ev.detail) t.detail = ev.detail; t.state = ev.state; t.chg = x.v; }
        break;
      }
      case "error": push(x, { k: "err", text: ev.message || "" }, ev); break;
      case "design": {
        if (!fd) break;
        if (fd.renamed && V && V.sel === fd.renamed) V.sel = fd.id;
        push(x, { k: "design", id: fd.id, d: fd.d, isNew: fd.isNew }, ev);
        break;
      }
      case "chosen": push(x, { k: "chosen", chip: ev.chip }, ev); break;
      case "artifact": if (ev.kind === "report") push(x, { k: "art", name: ev.name, path: ev.path }, ev); break;
      case "subagent.started": push(x, { k: "sub", key: ev.agent || ev.id || ("sub" + ev.seq), stage: ev.stage, strategy: ev.strategy || "", state: "started" }, ev); break;
      case "subagent.finished": { var s = x.f.subs[ev.agent || ev.id]; push(x, { k: "sub", key: ev.agent || ev.id, stage: ev.stage || (s && s.stage), strategy: s ? s.strategy : "", state: ev.status || ev.state || "finished" }, ev); break; }
      case "stage.merged": push(x, { k: "merge", stage: ev.stage, kept: Array.isArray(ev.kept) ? ev.kept : [], reason: ev.why || ev.reason || "" }, ev); break;
      case "evidence": x.evidence = ev; break;
      case "run.finished": x.fin = { status: ev.status, summary: ev.summary || "" }; push(x, { k: "fin", status: ev.status, summary: ev.summary || "" }, ev); break;
      default: break;
    }
  }

  /* ---------- metrics, targets and the spec ---------- */
  var MET = F.MET, metaOf = F.metaOf, FAU = F.FAU, faUnit = F.faUnit, targetsOf = F.targetsOf, fmtV = F.fmtV, fmtT = F.fmtT, meets = F.meets, passAll = F.passAll, sizeOf = F.sizeOf, dataMark = F.dataMark;
  var val = function (d, k) { return d && d.metrics ? num(d.metrics[k]) : null; };
  var budgetKey = function (d) { return (d.budget.ch == null ? "" : d.budget.ch) + "|" + (d.budget.name || ""); };
  var budgetName = function (d) { return d.budget.name || (d.budget.ch != null ? d.budget.ch + " channels" : "budget not given"); };
  function worstOf(d) {
    var w = null;
    d.per_patient.forEach(function (p) { if (p.total > 0) { var r = p.caught / p.total; if (!w || r < w.r) w = { r: r, p: p }; } });
    return w;
  }
  // everything a live view shows, from the run's state
  function modelOf(id) {
    var rec = W[id], st = rec.st, x = rec.x, r = findRun(id) || {};
    var spec = x.spec || r.spec || null, T = targetsOf(spec);
    var designs = F.designs(x.f);
    var chosenId = st.chosenChip || null, chosen = null;
    designs.forEach(function (d) { if (d.id === chosenId) chosen = d; });
    var keys = {};
    designs.forEach(function (d) { if (!keys[budgetKey(d)]) keys[budgetKey(d)] = d; });
    var budgets = Object.keys(keys).map(function (k) { return keys[k]; }).sort(function (a, b) { return (a.budget.ch || 0) - (b.budget.ch || 0) || budgetName(a).localeCompare(budgetName(b)); }).map(budgetKey);
    var status = st.finished ? st.finished.status : st.status === "connecting" ? (r.status && r.status !== "running" ? r.status : "connecting") : "running";
    var t0 = tsMs(st.startedAt), t1 = st.finishedAt ? tsMs(st.finishedAt) : null;
    return { id: id, r: r, st: st, x: x, spec: spec, T: T, designs: designs, chosenId: chosenId, chosen: chosen, budgets: budgets, status: status, running: status === "running", t0: t0, lost: !!C.lost && status === "running", gone: !!C.lost, elapsed: t0 == null ? null : ((t1 || (C.lost ? C.lostAt : Date.now())) - t0) / 1000 };
  }
  var budgetIdx = function (M, d) { return Math.max(0, M.budgets.indexOf(budgetKey(d))); };

  /* ---------- the run, from the "Your spec" card ---------- */
  var TASK = { continuous: ["monitoring"], screening: ["screening"], grading: ["grading"], monitor_grade: ["monitoring", "grading"] };
  var PLACE = { ward: ["ward", "hour"], home: ["home", "night"], self: ["patient", "day"] };
  var MKEY = { sensitivity: "sensitivity", specificity: "specificity", false_alarms_per_hour: "fa_per_hour", accuracy: "accuracy", expert_agreement: "agreement" };
  var r6 = function (v) { return Math.round(v * 1e6) / 1e6; };
  // the flow's answers, named exactly as the contract names them
  function buildSpec(s) {
    var pl = PLACE[s.place] || [null, "hour"], per = FAU[pl[1]], k = s.cons || {};
    var targets = (s.targets || []).filter(function (t) { return t && num(t.value) != null && MKEY[t.metric]; }).map(function (t) {
      var m = MKEY[t.metric], fa = m === "fa_per_hour";
      // the flow keeps rates per hour; the spec states them in the user's unit, rounded as typed
      return { metric: m, op: t.op === "<=" ? "at_most" : "at_least", value: fa ? +(t.value * per).toFixed(4) : r6(t.value), unit: fa ? "per " + pl[1] : "fraction" };
    });
    var mode = { sim: "simulate", public: "public", own: "own" }[s.data] || "simulate";
    // "find the best" with a brief that names one channel has a single budget: the card says so, so does the spec
    var one = k.findBest && s.chans === 1, best = !!k.findBest && !one;
    return {
      brief: s.brief || "", device: s.device || null, signal: s.signal || null, detect: s.detect || null,
      task_types: TASK[s.task] || [], patient_group: s.group || null, place: pl[0], fa_unit: pl[1], targets: targets,
      primary: MKEY[s.primary] && targets.some(function (t) { return t.metric === MKEY[s.primary]; }) ? MKEY[s.primary] : targets[0] ? targets[0].metric : null,
      constraints: { channels: best ? null : one ? 1 : num(k.channels), find_best: best, battery_hours: num(k.batN) != null ? k.batN * (k.batU === "days" ? 24 : 1) : null, reusable: typeof k.reusable === "boolean" ? k.reusable : null },
      data: { mode: mode, dataset: mode === "public" ? (s.ds || null) : null }
    };
  }
  var AGN = { claude: "Claude", openrouter: "OpenRouter", stub: "the scripted stub" };
  // the model a live run really used: what it sent, else its agent's default (run.started names the agent)
  function usedModel(M) { var a = M.st && M.st.agent; return window.ChipInModels.usedModelName(a === "stub" ? a : M.r.agent || a, a === "stub" ? null : M.r.model); }
  function start(s, done) {
    if (!s || !s.brief) return false;
    if (C.state !== "on") {
      note(C.pub ? "Live runs are offline right now, so this is an example run on demo data." : C.state === "bad" ? "The backend is not answering, so this is an example run on demo data." : "No backend is connected, so this is an example run on demo data.");
      return false;
    }
    var spec = buildSpec(s), mod = window.ChipInModels.runModel(s.agent && s.agent.model), D = C.defaults || {}, srv = D.agent;
    var body = { prompt: s.brief, spec: spec };
    // a backend that lists run_agents takes a run's own agent and model; an older one only a model for its own agent
    if (!srv || srv === mod.agent || Array.isArray(D.run_agents)) { body.agent = mod.agent; body.model = mod.id; }
    if (s.preset) body.preset = String(s.preset).toLowerCase();
    // the preset alone sets the run's subagents (lite 5, pro 15, max 50 in total); a width would override it
    if (body.preset) body.fanout = true;
    var fu = window.ChipInQuestions && window.ChipInQuestions.payload(s); // QUESTIONS HOOK: the follow-up answers (../i1-questions.js)
    if (fu) body.follow_up = fu;
    var notes = [];
    if (srv === "stub") notes.push("This backend runs the scripted stub: no model was called" + (body.model ? "; " + mod.name + " is recorded as the choice." : "."));
    var btn = $('.gfa [data-a="run"]');
    // never send a model the backend cannot run: it runs only the agents its health answer lists
    var no = window.ChipInModels.unavailableReason(mod, C.defaults);
    if (no) {
      var g0 = $(".gfa");
      if (g0) { var p0 = $(".lv-runerr", g0) || g0.appendChild(document.createElement("p")); p0.className = "lv-runerr"; p0.textContent = "The run did not start: this backend cannot run " + mod.name + " (" + no.charAt(0).toLowerCase() + no.slice(1) + "). Pick another model."; }
      return true;
    }
    if (btn) { btn.disabled = true; btn.dataset.lvTxt = btn.innerHTML; btn.textContent = "Starting the run…"; }
    // STAGE HOOK (../i1-stage.js): the shared loading stage, ticked by the real request, not by timers
    var stg = window.ChipInStage ? window.ChipInStage.play({
      live: true, kicker: "Live", title: "Starting your run", skip: "Hide",
      lines: [{ p: "Sending your spec to the backend", w: "Brief, answers and model", t: "Spec sent" }, { p: "Waiting for the backend to accept the run", w: "It checks the spec and creates the run", t: "Run accepted" }, { p: "Opening the run view", w: "The search's own steps show there" }]
    }) : null;
    if (stg) stg.tick(1);
    fetch(C.base + "/api/runs", { method: "POST", cache: "no-store", headers: { "Content-Type": "application/json", "X-ChipIn-Token": C.token || "" }, body: JSON.stringify(body) })
      .then(function (res) { return res.json().catch(function () { return {}; }).then(function (j) { if (!res.ok) { var er = new Error(j.error || "the backend answered HTTP " + res.status); er.status = res.status; throw er; } return j; }); })
      .then(function (j) {
        RUNS.unshift({ id: j.id, base: C.base, title: s.device ? clip(cap(s.device), 60) : clip(s.brief, 60), brief: s.brief, spec: spec, preset: body.preset || null, agent: srv === "stub" ? "stub" : mod.agent, model: srv === "stub" ? null : mod.id, notes: notes, created: new Date().toISOString(), status: "running" });
        saveRuns(); bump();
        if (stg) stg.tick(2);
        if (typeof done === "function") done();
        location.hash = "#/live/" + encodeURIComponent(j.id) + "/overview";
      })
      .catch(function (e) {
        if (stg) stg.close();
        if (btn && btn.isConnected) { btn.disabled = false; btn.innerHTML = btn.dataset.lvTxt || "Run"; }
        var g = $(".gfa");
        if (g) { var p = $(".lv-runerr", g) || g.appendChild(document.createElement("p")); p.className = "lv-runerr"; p.textContent = e && e.status === 429 ? "Two runs are already in progress. Try again in a few minutes." : "The run did not start: " + (e && e.message ? e.message : "the backend did not answer") + "."; }
      });
    return true;
  }
  function note(msg) {
    var t = $(".toast"); if (t) t.remove();
    t = document.createElement("div"); t.className = "toast"; t.setAttribute("role", "status"); t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { if (t.isConnected) t.remove(); }, 5200);
  }

  /* ---------- light markdown (escaped first; no links, no HTML) ---------- */
  function inl(s) {
    return esc(s).split(/(`[^`]+`)/).map(function (p) {
      if (/^`[^`]+`$/.test(p)) return "<code>" + p.slice(1, -1) + "</code>";
      return p.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[\s(])\*([^*\s][^*]*)\*(?=[\s).,;:!?]|$)/g, "$1<i>$2</i>");
    }).join("");
  }
  function md(src) {
    var lines = String(src || "").replace(/\r/g, "").split("\n"), out = [], i = 0;
    var isBlock = function (l) { return /^```/.test(l) || /^#{1,6}\s/.test(l) || /^\s*([-*]|\d+\.)\s+/.test(l) || /^\s*\|.*\|\s*$/.test(l); };
    while (i < lines.length) {
      var l = lines[i];
      if (/^```/.test(l)) { var buf = []; i++; while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]); i++; out.push("<pre><code>" + esc(buf.join("\n")) + "</code></pre>"); continue; }
      if (/^\s*\|.*\|\s*$/.test(l) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
        var row = function (x) { return x.trim().replace(/^\||\|$/g, "").split("|").map(function (c) { return c.trim(); }); };
        var head = row(l), rows = []; i += 2;
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(row(lines[i++]));
        out.push('<div class="lv-tw"><table><thead><tr>' + head.map(function (c) { return "<th>" + inl(c) + "</th>"; }).join("") + "</tr></thead><tbody>" + rows.map(function (r) { return "<tr>" + r.map(function (c) { return "<td>" + inl(c) + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div>");
        continue;
      }
      var hm = l.match(/^(#{1,6})\s+(.*)$/);
      if (hm) { var n = Math.min(6, hm[1].length + 2); out.push("<h" + n + ">" + inl(hm[2]) + "</h" + n + ">"); i++; continue; }
      if (/^\s*([-*]|\d+\.)\s+/.test(l)) {
        var ord = /^\s*\d+\./.test(l), items = [];
        while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) { var it = lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ""); while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s+/.test(lines[i])) it += " " + lines[i++].trim(); items.push("<li>" + inl(it) + "</li>"); }
        out.push((ord ? "<ol>" : "<ul>") + items.join("") + (ord ? "</ol>" : "</ul>"));
        continue;
      }
      if (!l.trim()) { i++; continue; }
      var para = [];
      while (i < lines.length && lines[i].trim() && !isBlock(lines[i])) para.push(lines[i++]);
      if (!para.length) { para.push(lines[i++]); }
      out.push("<p>" + para.map(inl).join(" ") + "</p>");
    }
    return out.join("");
  }

  /* ---------- the view ---------- */
  var V = null; // { id, view, sel, y, follow, logN, chatN, cfgMounted }
  var VIEWS = [["overview", "Overview"], ["chip", "Chip"], ["chat", "Chat"], ["sources", "Sources"]];
  function parse() {
    var m = location.hash.match(/^#\/live\/([^/]+)(?:\/([a-z]+))?/);
    if (!m) return null;
    var view = m[2] && VIEWS.some(function (v) { return v[0] === m[2]; }) ? m[2] : "overview";
    return { id: decodeURIComponent(m[1]), view: view };
  }
  function owns() { return !!parse(); }
  var viewPrefs = lsGet(K_VIEW) || {};
  function render() {
    var r = parse();
    if (!r) { V = null; return false; }
    closeDrawer();
    document.body.classList.add("inrun");
    var main = $("#main"); if (!main) return false;
    var known = findRun(r.id);
    // a run the backend lists as ended opens straight in the replay, without replaying its stream here first
    if (known && ended(known.status) && !W[r.id] && window.ChipInPlayback) { location.replace(location.pathname + location.search + recHref(r.id, r.view)); return true; }
    if (C.state !== "on" && !W[r.id]) {
      main.innerHTML = '<div class="body"><div class="vis lv-empty"><div class="vh"><h2>This run lives on a backend that is not connected</h2><p class="vs">' +
        esc(C.state === "checking" ? "Connecting to the backend…" : C.msg || "Connect a backend under Configure, then open the run again.") + '</p></div><p><a class="qbtn" href="#/configure">Open Configure</a></p></div></div>';
      V = { id: r.id, view: r.view, waiting: true };
      setDemo("");
      return true;
    }
    var rec = watchRun(r.id);
    var pref = viewPrefs[r.id] || {};
    V = { id: r.id, view: r.view, sel: V && V.id === r.id ? V.sel : pref.sel || null, y: pref.y || null, follow: true, logN: 0, chatN: 0, sig: {}, chartSig: "", hover: null, pts: [] };
    main.innerHTML = topHTML(r) + '<div class="lv-lost" id="lvLost" role="alert" hidden>Connection to the backend was lost; the run may still be going on that computer. Retrying...</div><div class="body" id="body"></div>';
    wireTop(rec);
    var body = $("#body");
    if (r.view === "overview") { body.innerHTML = overviewHTML(); wireOverview(); F.wireSubs($("#lvSubs"), rec.x.subOpen); }
    else if (r.view === "chat") { body.innerHTML = chatHTML(); wireChat(); }
    else body.innerHTML = (r.view === "chip" ? '<div class="vis dz-vis" id="lvDz"></div>' /* DESIGNS HOOK */ : "") + '<div class="vis" id="lvTab"></div>';
    if (window.ChipInMessages && (r.view === "overview" || r.view === "chat")) { if (r.view === "overview") $("#lvLog .lv-lh").remove(); window.ChipInMessages.mount(r.view === "chat" ? $("#lvChatFeed") : $("#lvLog .lv-fw"), { runId: r.id, mode: r.view === "chat" ? "page" : "panel", title: r.view === "chat" ? "Messages" : "Agent log", more: r.view === "chat" ? null : "#/live/" + encodeURIComponent(r.id) + "/chat" }); } /* MESSAGES HOOK: messages with levels of summaries, above the message box */
    if (!known) { RUNS.push({ id: r.id, base: C.base, title: r.id, brief: "", status: "running", created: null, server: true }); saveRuns(); }
    update(true);
    return true;
  }
  function setDemo(t) { var b = $("#demo"); if (b) { b.textContent = t; b.className = t === "Finished run" ? "demo mea" : "demo"; } }
  function topHTML(r) {
    var tabs = VIEWS.map(function (v) { return '<a class="tab' + (v[0] === r.view ? " on" : "") + '" href="#/live/' + encodeURIComponent(r.id) + "/" + v[0] + '">' + v[1] + "</a>"; }).join("");
    return '<div class="top"><nav class="tabs" aria-label="Run views">' + tabs + '</nav><span id="lvSt"></span><span class="clk" id="lvClk" title="Elapsed time from the run\'s own clock"></span><span class="lv-cost" id="lvCost"></span><span class="grow" style="flex:1"></span>' +
      '<div class="tright"><span class="mk lv-live topbadge" id="lvBadge">Live run</span><button class="cpill rset" id="lvSet" title="Run settings"><span class="pv" id="lvSetT">Run settings</span></button><button class="qbtn lv-stop" id="lvStop" hidden>' + I("stop", "s13") + "Stop</button></div></div>";
  }
  function wireTop(rec) {
    $("#lvSet").onclick = function () { settingsModal(modelOf(V.id)); };
    $("#lvStop").onclick = function () { stopRun(); };
  }

  /* ----- overview ----- */
  function overviewHTML() {
    return '<div class="ov lv-ov" id="lvOv"><div id="lvBan"></div><header class="ovh" id="lvHead"></header><p class="lv-costm" id="lvCostM"></p><div class="status" id="lvStatus" role="status"></div>' +
      '<div class="lv-stages" id="lvStages"></div><div class="tiles" id="lvTiles" style="position:relative"></div>' +
      '<section class="cgrid2"><div class="pan chartp"><div class="chh"><h2>Chip size against</h2><select class="ys" id="lvY" aria-label="Metric on the chart"></select><span class="grow"></span><span id="lvChMark"></span></div>' +
      '<div class="cwrap" id="lvWrap"><canvas id="lvChart" tabindex="0" role="img" aria-label="Trade-off chart"></canvas><div class="ctip" id="lvTip"></div></div><div class="legend" id="lvLegend"></div><div id="lvUnsized"></div></div>' +
      '<div class="side"><div id="lvSubs"></div><section class="pan lv-log" id="lvLog" aria-label="Agent log"><div class="lv-lh"><h2>Agent log</h2><span class="lv-n" id="lvLogN"></span></div><div class="lv-fw"><div class="lv-feed" id="lvFeed" role="log" aria-live="polite"></div><button class="lv-jump" id="lvJump" hidden>' + I("down", "s12") + 'Latest</button></div>' + boxHTML() + '</section><aside class="pan insp" id="lvInsp" aria-label="Selected design"></aside></div></section>' +
      '<div class="fun" id="lvFun"></div><p class="funn" id="lvFunN"></p><section class="pan lv-files" id="lvFiles" aria-label="Files"></section>' +
      '<div class="ovf"><span id="lvFoot"></span><span>' + esc(CREDIT) + "</span></div></div>";
  }
  function wireOverview() {
    $("#lvY").onchange = function (e) { V.y = e.target.value; keepPrefs(); V.sig = {}; V.chartSig = ""; update(true); };
    var feed = $("#lvFeed");
    feed.addEventListener("scroll", function () { V.follow = feed.scrollTop + feed.clientHeight >= feed.scrollHeight - 24; $("#lvJump").hidden = V.follow; });
    feed.addEventListener("click", toggleTool);
    $("#lvJump").onclick = function () { V.follow = true; feed.scrollTop = feed.scrollHeight; $("#lvJump").hidden = true; };
    wireBox();
    $("#lvInsp").addEventListener("click", function (e) { var b = e.target.closest("[data-open]"); if (b) openFile(b.dataset.open); });
    $("#lvFiles").addEventListener("click", function (e) { var b = e.target.closest("[data-open]"); if (b) openFile(b.dataset.open); });
    $("#lvUnsized").addEventListener("click", function (e) { var b = e.target.closest("[data-sel]"); if (b) select(b.dataset.sel); });
    var cv = $("#lvChart"), tip = $("#lvTip");
    var hit = function (e) { var r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top, best = null, bd = 13; V.pts.forEach(function (p) { var d = Math.hypot(p.x - x, p.y - y); if (d < bd) { bd = d; best = p; } }); return best; };
    cv.addEventListener("pointermove", function (e) { var p = hit(e), id = p ? p.d.id : null; if (id !== V.hover) { V.hover = id; V.chartSig = ""; drawChart(); } showTip(p); cv.style.cursor = p ? "pointer" : "default"; });
    cv.addEventListener("pointerleave", function () { V.hover = null; tip.style.display = "none"; V.chartSig = ""; drawChart(); });
    cv.addEventListener("click", function (e) { var p = hit(e); if (p) select(p.d.id); });
    cv.addEventListener("keydown", function (e) {
      var M = modelOf(V.id), list = M.designs.filter(sizeOf).sort(function (a, b) { return sizeOf(a).g - sizeOf(b).g; });
      if (!list.length) return;
      var cur = selected(M), i = Math.max(0, list.findIndex(function (d) { return cur && d.id === cur.id; })), j = null;
      if (e.key === "ArrowRight" || e.key === "ArrowUp") j = Math.min(list.length - 1, i + 1);
      else if (e.key === "ArrowLeft" || e.key === "ArrowDown") j = Math.max(0, i - 1);
      else if (e.key === "Home") { V.sel = null; keepPrefs(); V.sig = {}; V.chartSig = ""; update(true); e.preventDefault(); return; }
      if (j == null) return;
      e.preventDefault(); select(list[j].id);
    });
    function showTip(p) {
      if (!p) { tip.style.display = "none"; return; }
      var M = modelOf(V.id), d = p.d, s = sizeOf(d);
      tip.innerHTML = "<b>" + esc(d.id) + (d.label ? ", " + esc(clip(d.label, 40)) : "") + "</b>" + (s.m ? fmt(s.g) + " gates, measured" : "about " + fmt(s.g) + " gates, estimated") + "<br>" +
        (M.T.length ? M.T.map(function (t) { return esc(metaOf(t.metric).n) + ": " + fmtV(t.metric, val(d, t.metric), M.spec); }).join("<br>") + "<br>" + (passAll(M.T, d) ? "Passes every target" : "Fails a target") : "");
      tip.style.display = "block";
      var Wd = cv.clientWidth, tw = tip.offsetWidth, th = tip.offsetHeight;
      tip.style.left = clamp(p.x + 12, 4, Wd - tw - 4) + "px"; tip.style.top = Math.max(4, p.y - th - 10) + "px";
    }
  }
  function select(id) { V.sel = id; keepPrefs(); V.sig = {}; V.chartSig = ""; update(true); var l = $("#lvInsp"); if (l && innerWidth < 1101) l.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
  function keepPrefs() { viewPrefs[V.id] = { sel: V.sel, y: V.y }; lsSet(K_VIEW, viewPrefs); }
  // The chip lab's figures for a chip. Today's backend sends its metric events without a chip
  // id, so for the chosen chip the run-level figures stand in, marked as untagged.
  // the chip lab's figures for a chip, from the fold (chip-tagged metric events)
  function chipMetrics(M, id) {
    var f = M.x.f, m = id ? f.chips[id] || {} : {};
    if (Object.keys(m).length || !id || id !== M.chosenId) return { m: m, u: f.units[id] || {}, untagged: false };
    var r = f.run, has = ["gates", "depth", "mismatches", "verification_level"].some(function (k) { return num(r[k]) != null; });
    return has ? { m: r, u: f.runUnits, untagged: true } : { m: {}, u: {}, untagged: false };
  }
  function selected(M) {
    var d = null;
    if (V.sel) M.designs.forEach(function (x) { if (x.id === V.sel) d = x; });
    return d || M.chosen || M.designs[M.designs.length - 1] || null;
  }
  // a status line's area unit as written for a person: um2 as µm² (square micrometres)
  var units = function (s) { return s ? String(s).replace(/(?<![A-Za-z])um(?:\^?2|²)(?![\w])/g, "µm²") : s; };
  var primaryOf = function (M) {
    if (V.y) return V.y;
    if (M.spec && M.spec.primary) return M.spec.primary;
    return M.T[0] ? M.T[0].metric : "sensitivity";
  };

  // the headline, in the page's voice
  function headHTML(M0) {
    // a follow-up after a finished run: the finished run's headline stays, with a quiet line under it
    var follow = M0.running && M0.x.fin ? M0.x.fin : null;
    var M = follow ? Object.assign({}, M0, { status: follow.status, running: false, lost: false }) : M0;
    var c = M.chosen, h1, st = M.status, held = "";
    var sizeTxt = function (d) { var s = sizeOf(d); return s ? (s.m ? fmt(s.g) + " gates" : "about " + fmt(s.g) + " gates (estimated)") : "size not reported"; };
    if (st === "failed") { var ls = lastStage(M), open = ls && M.st.stages[ls].state === "started"; h1 = "The run failed" + (ls ? (open ? " during " : " after ") + STAGE_N[ls].toLowerCase() : "") + "."; }
    else if (st === "stopped") h1 = "The run was stopped" + (M.designs.length ? " after " + M.designs.length + " design" + (M.designs.length === 1 ? "" : "s") + " were scored." : " before any design was scored.");
    else if (c) {
      var miss = M.T.filter(function (t) { return meets(t, val(c, t.metric)) === false; }).map(function (t) { return metaOf(t.metric).n.toLowerCase(); });
      var hit = M.T.filter(function (t) { return meets(t, val(c, t.metric)) === true; }).map(function (t) { return metaOf(t.metric).n.toLowerCase(); });
      var on = c.basis === "validation" ? " on validation" : c.basis === "test" ? " on the test set" : "";
      h1 = !M.T.length ? "The chosen chip: " + sizeTxt(c) + "." : !miss.length && hit.length === M.T.length ? "The chosen chip clears every target" + on + ": " + sizeTxt(c) + ", " + esc(budgetName(c)) + "." :
        "The chosen chip, " + sizeTxt(c) + ", misses your " + andList(miss) + " target" + (miss.length === 1 ? "" : "s") + (hit.length ? " and clears " + andList(hit) : "") + on + ".";
      var hm = c.basis === "test" ? [] : heldMiss(M, c);
      if (hm.length) held = '<p class="k1 lv-held">On the held-out patients it misses your ' + andList(hm.map(function (x) { return metaOf(x.t.metric).n.toLowerCase(); })) + " target" + (hm.length === 1 ? "" : "s") + ": " +
        andList(hm.map(function (x) { return fmtV(x.t.metric, x.v, M.spec) + " against " + fmtT(x.t, M.spec); })) + ".</p>";
    } else if (M.chosenId) h1 = "Chip " + esc(M.chosenId) + " is chosen; its design record has not arrived.";
    else if (M.designs.length) h1 = M.designs.length + " design" + (M.designs.length === 1 ? "" : "s") + " scored" + (M.running ? " so far; none chosen yet." : "; none chosen.");
    else h1 = M.running || st === "connecting" ? (M.lost ? "Disconnected. No design scored yet." : "Running. No design scored yet.") : "The run finished without a design record.";
    var mark = dataMark(M.spec, M.designs), sp = M.spec || {};
    var chips = M.T.map(function (t) { var s = c ? meets(t, val(c, t.metric)) : null; return '<span class="tgt' + (t.metric === primaryOf(M) ? " pri" : "") + '">' + esc(metaOf(t.metric).n) + " " + esc(fmtT(t, M.spec)) + " " + (c ? pf(s) : "") + "</span>"; }).join("");
    var fu = follow ? '<p class="k1 lv-mute lv-follow">' + (M0.lost ? "Disconnected while the agent answers your follow-up." : "The agent is answering your follow-up.") + "</p>" : "";
    return '<div class="tx"><p class="k0"><span>' + esc(M.r.title || "Live run") + "</span>" + mark + "</p><h1>" + h1 + "</h1>" + held + fu +
      '<p class="k1">Device: ' + ng(sp.device) + ". Signal: " + ng(sp.signal) + ". Detects: " + ng(sp.detect) + ".</p>" +
      (M.T.length ? '<div class="tgts">' + chips + "</div>" : M.spec ? "" : '<p class="k1 lv-mute">The spec for this run has not arrived from the backend.</p>') + "</div>";
  }
  // targets the chosen chip misses on the held-out patients, from the chip-tagged metrics the agent reported
  function heldMiss(M, c) {
    var h = F.heldOut(M.x.f, c.id, M.x.final), out = [];
    if (!h) return out;
    M.T.forEach(function (t) { var v = h.pooled[t.metric]; if (v != null && meets(t, v) === false) out.push({ t: t, v: v }); });
    return out;
  }
  var ng = function (s) { return s ? esc(s) : '<span style="color:#9a7a4e">not given</span>'; };
  var pf = function (ok) { return ok === true ? '<span class="pf ok">Pass</span>' : ok === false ? '<span class="pf no">Fail</span>' : '<span class="pf na">Not reported</span>'; };
  function lastStage(M) { var s = null; STAGES.forEach(function (n) { var x = M.st.stages[n]; if (x && x.state !== "pending") s = n; }); return s; }

  function tilesHTML(M) {
    var d = M.chosen, out = [], lab = d ? "chosen chip" : "", mark = dataMark(M.spec, M.designs);
    var scope = function (x) { var c = x.counts || {}; return (x.basis === "test" ? "test set" : x.basis === "validation" ? "validation set" : "") + (num(c.patients) ? ", " + pl(c.patients, "patient") + (c.patients === 1 ? "" : " pooled") : ""); };
    M.T.forEach(function (t) {
      var v = d ? val(d, t.metric) : null, w = d && t.metric === "sensitivity" ? worstOf(d) : null;
      var big = v == null ? "–" : metaOf(t.metric).frac ? (v * 100).toFixed(1) + "<small>%</small>" : t.metric === "fa_per_hour" ? fmtV(t.metric, v, M.spec).replace(/ per (\w+)$/, "<small>per $1</small>") : esc(String(+v.toFixed(4)));
      out.push('<div class="tile' + (v == null ? " empty" : "") + '"><div class="tl">' + esc(metaOf(t.metric).n) + (d ? ", " + esc(scope(d) || lab) : "") + '</div><div class="tv">' + big + '</div><div class="ts">Target ' + esc(fmtT(t, M.spec)) + " " + (d ? pf(meets(t, v)) : "") + "</div>" +
        (w ? '<div class="ts lv-mute">Worst patient ' + esc(w.p.id) + ": " + (w.r * 100).toFixed(1) + "%</div>" : "") + "</div>");
    });
    var CM = chipMetrics(M, M.chosenId), chipM = CM.m, s = d ? sizeOf(d) : num(chipM.gates) ? { g: chipM.gates, m: true } : null;
    var depth = d && num(d.depth) != null ? d.depth : num(chipM.depth);
    out.push('<div class="tile' + (s ? "" : " empty") + '"><div class="tl">Chip size' + (M.chosenId ? ", chosen chip" : "") + '</div><div class="tv">' + (s ? (s.m ? fmt(s.g) : '<span class="est" title="Estimated by the agent; the chip lab has not measured it">' + fmt(s.g) + "</span>") + "<small>gates</small>" : "–") +
      '</div><div class="ts">' + (s ? (s.m ? "measured by the chip lab" + (CM.untagged && !d ? " (reported for the run)" : "") : "estimated") + (depth != null ? ", logic depth " + depth : "") : M.running ? "after the chosen chip is compiled" : M.chosenId ? "chip " + esc(M.chosenId) + " has no size reported" : "no chosen chip") + "</div></div>");
    var vf = d && d.verified;
    if (!vf && (num(chipM.mismatches) != null || num(chipM.vectors_checked) != null)) vf = { mismatches: num(chipM.mismatches), vectors: num(chipM.vectors_checked), level: chipM.verification_level };
    if (vf || num(chipM.verification_level) != null) {
      var lvl = vf && vf.level != null ? vf.level : chipM.verification_level;
      out.push('<div class="tile"><div class="tl">Circuit against its model</div><div class="tv">' + (vf && num(vf.mismatches) != null ? fmt(vf.mismatches) + "<small>mismatches</small>" : esc(F.levelText(lvl))) + '</div><div class="ts">' +
        (vf && num(vf.vectors) != null ? fmt(vf.vectors) + " vectors" : "") + (lvl != null ? (vf && num(vf.vectors) != null ? ", " : "") + esc(F.levelText(lvl)) : "") + (vf && vf.proved ? ", proved equal" : "") + "</div></div>");
    }
    if (!M.T.length && !s) return '<div class="tile empty lv-wide"><div class="tl">Results</div><div class="tv">–</div><div class="ts">' + (M.running ? "Tiles fill in when the run chooses a chip." : "This run chose no chip.") + "</div></div>";
    return out.join("") + (mark ? '<span style="position:absolute;right:12px;top:-9px">' + mark + "</span>" : "");
  }

  function stagesHTML(M) {
    var t0 = M.t0;
    return "<ol>" + STAGES.map(function (n) {
      var s = M.st.stages[n] || { state: "pending" }, cls = s.state === "done" ? "done" : s.state === "started" ? "now" : s.state === "skipped" ? "skip" : "";
      if (cls === "now" && !M.running) cls = M.status === "failed" ? "fail" : "halt";
      var at = s.at && t0 != null ? clock((tsMs(s.at) - t0) / 1000) : "";
      var sub = s.state === "done" ? "done " + at : s.state === "started" ? (M.running ? "running" : M.status === "failed" ? "failed here" : "stopped here") : s.state === "skipped" ? "skipped" : "";
      return '<li class="' + cls + '"' + (s.reason ? ' title="Skipped: ' + esc(s.reason) + '"' : "") + "><i></i><span>" + STAGE_N[n] + "</span><small>" + esc(sub) + "</small></li>";
    }).join("") + "</ol>";
  }
  function subsHTML(M) { return F.subsHTML(M.x.f, M.spec, M.x.subOpen); }
  function funnel(M) { return F.funnel(M.x.f, M.T); }
  function funHTML(M) {
    var f = funnel(M), cur = null;
    STAGES.forEach(function (n) { var s = M.st.stages[n]; if (s && s.state === "started") cur = n; });
    var nowK = !M.running ? null : cur === "propose" ? "proposed" : cur === "reference" || cur === "finetune" ? "scored" : cur === "compile" ? "compiled" : cur === "verify" ? "verified" : null;
    var S = [["proposed", "Proposed"], ["scored", "Scored"], ["compiled", "Compiled to gates"], ["verified", "Verified against the model"], ["clear", "Clear your targets"], ["chosen", "Chosen"]];
    if (!M.T.length) S = S.filter(function (s) { return s[0] !== "clear"; });
    return S.map(function (s) { return '<div class="fs' + (s[0] === nowK ? " now" : "") + (s[0] === "chosen" ? " last" : "") + (!f[s[0]] ? " mute" : "") + '"><div class="fn">' + fmt(f[s[0]]) + '</div><div class="fl">' + s[1] + "</div></div>"; }).join("");
  }

  function inspHTML(M) {
    var d = selected(M);
    if (!d) {
      var rm = M.x.f.run, ru = M.x.f.runUnits, rk = Object.keys(rm).filter(function (k) { return num(rm[k]) != null; });
      var lead = M.running ? "Each design the agent scores appears on the chart. Click one to see it here." : "This run reported no design.";
      if (!rk.length) return '<h2>Inspector</h2><p class="is">' + lead + "</p>";
      return '<h2>Inspector</h2><p class="is">' + lead + " The run reported these numbers without a design record, so none is plotted.</p>" +
        rk.map(function (k) { var t = F.metricText(k, rm[k], ru[k], M.spec); return '<div class="irow"><span>' + esc(t.label) + "</span><b>" + esc(t.value) + "</b></div>"; }).join("");
    }
    var isCh = M.chosenId === d.id, s = sizeOf(d), rows = [], c = d.counts || {};
    if (d.label) rows.push(["Design", esc(d.label)]);
    rows.push(["Budget", esc(budgetName(d))]);
    rows.push(["Chip size", s ? (s.m ? fmt(s.g) + " gates, measured" : '<span class="est" title="Estimated by the agent; the chip lab has not measured it">about ' + fmt(s.g) + " gates, estimated</span>") : "not known yet"]);
    if (num(d.depth) != null) rows.push(["Logic depth", d.depth + " levels"]);
    var keys = M.T.map(function (t) { return t.metric; });
    Object.keys(d.metrics).forEach(function (k) { if (keys.indexOf(k) < 0 && num(d.metrics[k]) != null) keys.push(k); });
    keys.forEach(function (k) {
      var t = M.T.filter(function (x) { return x.metric === k; })[0], v = val(d, k);
      rows.push([esc(metaOf(k).n) + (d.basis ? ", " + esc(d.basis) : ""), fmtV(k, v, M.spec) + (t ? pf(meets(t, v)) : "")]);
    });
    if (num(c.events_total)) rows.push(["Events caught", fmt(c.events_caught || 0) + " of " + fmt(c.events_total)]);
    if (num(c.negatives_total)) rows.push(["Negatives correct", fmt(c.negatives_correct || 0) + " of " + fmt(c.negatives_total)]);
    if (num(c.patients) || num(c.hours)) rows.push([d.basis === "validation" ? "Validation set" : d.basis === "test" ? "Held-out test set" : "Scored on", (num(c.patients) ? pl(c.patients, "patient") : "") + (num(c.hours) ? (num(c.patients) ? ", " : "") + (+c.hours.toFixed(2)) + " hours" : "")]);
    var vf = d.verified;
    rows.push(["Circuit against its model", vf ? (num(vf.vectors) != null ? fmt(vf.vectors) + " vectors, " : "") + (num(vf.mismatches) != null ? fmt(vf.mismatches) + " mismatches" : "") + (vf.level != null ? ", " + esc(F.levelText(vf.level)) : "") + (vf.proved ? ", proved equal" : "") : "not checked yet"]);
    var files = chipFiles(M, d.id);
    return "<h2>Design " + esc(d.id) + " " + (s ? '<span class="mk ' + (s.m ? "mea" : "no") + '">' + (s.m ? "size measured" : "size estimated") + "</span>" : "") + (isCh ? '<span class="pf ok">Chosen</span>' : "") + "</h2>" +
      '<p class="is">' + esc(d.data === "synthetic" ? "Scored on synthetic data" : /^public:/.test(d.data || "") ? "Scored on public data: " + d.data.slice(7) : d.data ? String(d.data) : "") + "</p>" + F.variantHTML(d) +
      rows.map(function (r) { return '<div class="irow"><span>' + r[0] + "</span><b>" + r[1] + "</b></div>"; }).join("") +
      (d.note ? '<p class="inote">' + esc(d.note) + "</p>" : "") +
      '<div class="ilinks">' +
      files.slice(0, 3).map(function (f) { return '<button class="qbtn" data-open="' + esc(f.path) + '">' + I("file", "s13") + esc(f.name) + "</button>"; }).join("") + "</div>";
  }
  function chipFiles(M, id) {
    var out = [], seen = {};
    M.st.artifacts.forEach(function (a) { if (a.path && a.path.indexOf("/chips/" + id + "/") >= 0 && !seen[a.path]) { seen[a.path] = 1; out.push(a); } });
    return out.sort(function (a, b) { return (a.kind === "report" ? 0 : 1) - (b.kind === "report" ? 0 : 1); });
  }

  // the trade-off chart: gates on a log scale across, the primary metric up (better is up)
  function drawChart() {
    var cv = $("#lvChart"); if (!cv || !V) return;
    var M = modelOf(V.id), wrap = $("#lvWrap"), Wd = Math.max(280, wrap.clientWidth), H = Math.round(clamp(Wd * 0.5, 280, 440)), dpr = Math.min(2, window.devicePixelRatio || 1);
    var key = primaryOf(M), meta = metaOf(key), sel = selected(M);
    var sig = [Wd, M.x.v, key, sel ? sel.id : "", V.hover, M.chosenId].join("|");
    if (sig === V.chartSig) return; V.chartSig = sig;
    if (cv.width !== Math.round(Wd * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(Wd * dpr); cv.height = Math.round(H * dpr); cv.style.height = H + "px"; }
    var g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, Wd, H);
    var narrow = Wd < 520, padL = narrow ? 44 : 54, padR = narrow ? 12 : M.budgets.length > 1 ? 128 : 28, padT = 30, padB = 44, x0 = padL, x1 = Wd - padR, y0 = padT, y1 = H - padB;
    var font = function (w, s) { return w + " " + s + "px Inter, system-ui, -apple-system, sans-serif"; };
    var ds = M.designs.filter(function (d) { return sizeOf(d) && val(d, key) != null; });
    var tgt = M.T.filter(function (t) { return t.metric === key; })[0];
    var per = key === "fa_per_hour" ? FAU[faUnit(M.spec)] : 1;
    var gs = ds.map(function (d) { return sizeOf(d).g; }), vals = ds.map(function (d) { return val(d, key) * per; });
    var gLo = gs.length ? Math.min.apply(null, gs) : 100, gHi = gs.length ? Math.max.apply(null, gs) : 10000;
    if (gHi / gLo < 4) { var mid = Math.sqrt(gLo * gHi); gLo = mid / 2.2; gHi = mid * 2.2; } else { gLo *= 0.8; gHi *= 1.15; }
    var vLo, vHi, tv = tgt ? tgt.value * per : null;
    if (meta.frac) { vLo = Math.max(0, Math.floor((Math.min.apply(null, vals.concat(tv != null ? [tv] : [1])) - 0.04) * 20) / 20); vHi = 1; }
    else { vLo = 0; vHi = Math.max.apply(null, vals.concat([tv != null ? tv * 1.3 : 0, 1e-9])) * 1.12 || 1; }
    if (!vals.length && tv == null) { vLo = meta.frac ? 0.5 : 0; vHi = 1; }
    var X = function (v) { return x0 + (Math.log(Math.max(v, gLo)) - Math.log(gLo)) / (Math.log(gHi) - Math.log(gLo)) * (x1 - x0); };
    var Yr = function (v) { return meta.up ? y1 - (v - vLo) / (vHi - vLo) * (y1 - y0) : y0 + (v - vLo) / (vHi - vLo) * (y1 - y0); };
    var Y = function (v) { return clamp(Yr(v), y0 - 6, y1 + 6); };
    // grid and axes
    g.font = font(500, 11.5); g.fillStyle = "#4a5062"; g.strokeStyle = "#eceef2"; g.lineWidth = 1;
    var ticks = [];
    for (var e = Math.floor(Math.log10(gLo)); e <= Math.ceil(Math.log10(gHi)); e++) [1, 2, 5].forEach(function (m) { var t = m * Math.pow(10, e); if (t >= gLo * 0.999 && t <= gHi * 1.001) ticks.push(t); });
    ticks.forEach(function (t) { var x = X(t); g.beginPath(); g.moveTo(x, y0); g.lineTo(x, y1); g.stroke(); g.textAlign = "center"; g.fillText(t >= 1000 ? (t / 1000) + "k" : String(t), x, y1 + 16); });
    var span = vHi - vLo, step = meta.frac ? (span > 0.4 ? 0.1 : 0.05) : Math.pow(10, Math.floor(Math.log10(span / 4 || 1))) * (span / Math.pow(10, Math.floor(Math.log10(span / 4 || 1))) > 20 ? 5 : 2);
    g.textAlign = "right"; g.textBaseline = "middle";
    for (var y = Math.ceil(vLo / step - 1e-9) * step; y <= vHi + 1e-9; y += step) { var yy = Yr(y); g.beginPath(); g.moveTo(x0, yy); g.lineTo(x1, yy); g.stroke(); g.fillText(meta.frac ? Math.round(y * 100) + "%" : +y.toFixed(2), x0 - 8, yy); }
    g.textBaseline = "alphabetic"; g.strokeStyle = "#b2b6c2"; g.beginPath(); g.moveTo(x0, y1); g.lineTo(x1, y1); g.stroke();
    var basis = ds.length ? ds[ds.length - 1].basis : null;
    g.fillStyle = "#262c40"; g.font = font(600, 12); g.textAlign = "left";
    g.fillText(meta.n + (key === "fa_per_hour" ? " per " + faUnit(M.spec) : "") + (basis ? ", " + basis + " set, pooled" : "") + (meta.up ? "" : ", fewer is higher"), x0 - (narrow ? 38 : 46), 16);
    g.textAlign = "right"; g.font = font(500, 11.5); g.fillStyle = "#4a5062"; g.fillText("Chip size, logic gates (log scale)", x1, H - 8);
    // frontier per budget, then dots: failing grey under passing in their budget colour; hollow = size estimated
    var shape = function (x, y, i, r) { g.beginPath(); if (i % 4 === 0) g.arc(x, y, r, 0, 7); else if (i % 4 === 1) g.rect(x - r * 0.9, y - r * 0.9, r * 1.8, r * 1.8); else if (i % 4 === 2) { g.moveTo(x, y - r * 1.15); g.lineTo(x + r * 1.1, y + r * 0.8); g.lineTo(x - r * 1.1, y + r * 0.8); g.closePath(); } else { g.moveTo(x, y - r * 1.2); g.lineTo(x + r * 1.2, y); g.lineTo(x, y + r * 1.2); g.lineTo(x - r * 1.2, y); g.closePath(); } };
    var labels = [];
    M.budgets.forEach(function (bk, bi) {
      var pts = ds.filter(function (d) { return budgetKey(d) === bk; }).sort(function (a, b) { return sizeOf(a).g - sizeOf(b).g; }), fr = [], best = -Infinity;
      pts.forEach(function (d) { var gv = meta.up ? val(d, key) : -val(d, key); if (gv > best + 1e-9) { fr.push(d); best = gv; } });
      if (fr.length >= 2) { g.strokeStyle = BCOL[bi % 4]; g.globalAlpha = 0.9; g.lineWidth = 1.8; g.beginPath(); fr.forEach(function (d, i) { var x = X(sizeOf(d).g), yv = Y(val(d, key) * per); if (i) g.lineTo(x, yv); else g.moveTo(x, yv); }); g.stroke(); g.globalAlpha = 1; }
      if (fr.length) { var last = fr[fr.length - 1]; labels.push({ y: Y(val(last, key) * per), x: X(sizeOf(last).g), t: budgetName(last), c: BCOL[bi % 4] }); }
    });
    var pts = [], big = narrow ? 5 : 6;
    ds.slice().sort(function (a, b) { return (passAll(M.T, a) ? 1 : 0) - (passAll(M.T, b) ? 1 : 0); }).forEach(function (d) {
      var s = sizeOf(d), x = X(s.g), yv = Y(val(d, key) * per), bi = budgetIdx(M, d), ok = !M.T.length || passAll(M.T, d), col = ok ? BCOL[bi % 4] : "#9aa0ae";
      shape(x, yv, bi, big);
      if (s.m) { g.globalAlpha = ok ? 0.9 : 0.75; g.fillStyle = ok ? col : "#c3c8d4"; g.fill(); g.globalAlpha = 1; }
      else { g.fillStyle = "#fff"; g.fill(); g.lineWidth = 1.8; g.strokeStyle = col; g.stroke(); }
      pts.push({ x: x, y: yv, d: d });
    });
    V.pts = pts;
    if (!narrow && labels.length > 1) {
      labels.sort(function (a, b) { return a.y - b.y; }); for (var i = 1; i < labels.length; i++) labels[i].y = Math.max(labels[i].y, labels[i - 1].y + 15);
      g.font = font(600, 11.5); g.textAlign = "left";
      labels.forEach(function (l) { g.strokeStyle = l.c; g.globalAlpha = 0.5; g.lineWidth = 1; g.beginPath(); g.moveTo(l.x + 8, l.y); g.lineTo(x1 + 6, l.y); g.stroke(); g.globalAlpha = 1; g.fillStyle = l.c; g.fillText(l.t, x1 + 10, l.y + 4); });
    }
    if (tgt) {
      var by = Y(tv); g.strokeStyle = "#141a2e"; g.setLineDash([6, 4]); g.lineWidth = 1.5; g.beginPath(); g.moveTo(x0, by); g.lineTo(x1, by); g.stroke(); g.setLineDash([]);
      g.font = font(700, 12); g.textAlign = "right"; var lt = "Your bar: " + fmtT(tgt, M.spec), tw = g.measureText(lt).width;
      g.fillStyle = "rgb(255 255 255 / .88)"; g.fillRect(x1 - tw - 8, by - 19, tw + 8, 15); g.fillStyle = "#141a2e"; g.fillText(lt, x1 - 4, by - 7);
    }
    var ring = function (d, r, col, w) { var p = null; pts.forEach(function (q) { if (q.d.id === d.id) p = q; }); if (!p) return null; g.strokeStyle = col; g.lineWidth = w; g.beginPath(); g.arc(p.x, p.y, r, 0, 7); g.stroke(); return p; };
    if (M.chosen) {
      var p = ring(M.chosen, 10.5, "#141a2e", 2.2);
      if (p) {
        var txt = "Chosen: " + fmt(sizeOf(M.chosen).g) + " gates"; g.font = font(700, 12); var tw2 = g.measureText(txt).width;
        // the label goes where it covers no other design and stays inside the plot: above or beside the ring, left or right
        var bxs = tgt ? [{ x: x1 - tw - 8, y: Y(tv) - 19, w: tw + 8, h: 15 }] : [];
        var hits = function (lx, ly) {
          var r = { x: lx - 4, y: ly - 14, w: tw2 + 8, h: 19 }, n = 0;
          if (r.x < x0 || r.x + r.w > x1 + 4 || r.y < 2 || r.y + r.h > y1) n += 100;
          pts.forEach(function (q) { if (q.d.id !== M.chosen.id && q.x > r.x - 7 && q.x < r.x + r.w + 7 && q.y > r.y - 7 && q.y < r.y + r.h + 7) n += 10; });
          bxs.forEach(function (b) { if (r.x < b.x + b.w && r.x + r.w > b.x && r.y < b.y + b.h && r.y + r.h > b.y) n += 5; });
          return n;
        };
        var cand = [[p.x - 16 - tw2, p.y - 18], [p.x + 16, p.y - 18], [p.x - 16 - tw2, p.y + 5], [p.x + 16, p.y + 5], [p.x - 16 - tw2, p.y + 28], [p.x + 16, p.y + 28], [p.x - tw2 / 2, p.y + 32], [p.x - tw2 / 2, p.y - 22]];
        var bestC = cand[0], bestN = Infinity;
        cand.forEach(function (c) { var n = hits(c[0], c[1]); if (n < bestN) { bestN = n; bestC = c; } });
        var lx = Math.max(4, Math.min(bestC[0], Wd - tw2 - 6)), ly = bestC[1];
        g.fillStyle = "rgb(255 255 255 / .92)"; g.fillRect(lx - 4, ly - 14, tw2 + 8, 19); g.fillStyle = "#141a2e"; g.textAlign = "left"; g.fillText(txt, lx, ly);
      }
    }
    if (sel && (!M.chosen || sel.id !== M.chosen.id)) ring(sel, 9, "#2b55d0", 2.2);
    if (V.hover) { var hd = null; ds.forEach(function (d) { if (d.id === V.hover) hd = d; }); if (hd) ring(hd, 8, "#141a2e", 1.2); }
    if (!ds.length) {
      g.fillStyle = "#4a5062"; g.font = font(500, 13); g.textAlign = "center";
      g.fillText(M.designs.length ? "Designs appear here once they have a size." : M.running ? "No designs scored yet." : "This run reported no design.", (x0 + x1) / 2, (y0 + y1) / 2);
    }
    cv.setAttribute("aria-label", "Trade-off chart: " + ds.length + " designs, chip size against " + meta.n.toLowerCase() + ". " + (M.chosen ? "Chosen chip " + M.chosen.id + "." : "No chip chosen yet.") + " Use the arrow keys to select designs.");
  }
  function legendHTML(M) {
    var shp = function (i, col, hollow) { var s = ['<circle cx="7" cy="7" r="4"/>', '<rect x="3" y="3" width="8" height="8"/>', '<path d="M7 2.5 11.5 11h-9z"/>', '<path d="M7 2 12 7 7 12 2 7z"/>'][i % 4]; return '<svg viewBox="0 0 14 14" ' + (hollow ? 'fill="#fff" stroke="' + col + '" stroke-width="1.6"' : 'fill="' + col + '"') + ">" + s + "</svg>"; };
    var bud = M.budgets.map(function (bk, i) { var d = M.designs.filter(function (x) { return budgetKey(x) === bk; })[0]; return "<span>" + shp(i, BCOL[i % 4]) + esc(budgetName(d)) + "</span>"; });
    var est = M.designs.some(function (d) { var s = sizeOf(d); return s && !s.m; });
    var out = (bud.length > 1 ? bud.join("") : bud.length ? "<span>" + shp(0, BCOL[0]) + (M.T.length ? "Passes every target" : esc(budgetName(M.designs[0]))) + "</span>" : "") +
      (M.T.length && M.designs.length ? "<span>" + shp(0, "#c3c8d4") + "Fails a target</span>" : "") +
      (M.designs.length ? "<span>" + shp(0, "#4a5062") + "Size measured by the chip lab</span>" + (est ? "<span>" + shp(0, "#4a5062", true) + "Size estimated</span>" : "") : "") +
      (M.T.some(function (t) { return t.metric === primaryOf(M); }) ? '<span><svg viewBox="0 0 14 14"><path d="M0 7h14" stroke="#141a2e" stroke-width="1.6" stroke-dasharray="3 2.5"/></svg>Your bar</span>' : "") +
      (M.chosen ? '<span><svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="5" fill="none" stroke="#141a2e" stroke-width="2"/></svg>Chosen chip</span>' : "");
    return out;
  }
  function unsizedHTML(M) {
    var key = primaryOf(M), list = M.designs.filter(function (d) { return !sizeOf(d) || val(d, key) == null; });
    if (!list.length) return "";
    return '<p class="lv-uns">Not on the chart yet (' + (list.some(function (d) { return !sizeOf(d); }) ? "no size reported" : "no " + esc(metaOf(key).n.toLowerCase()) + " reported") + "): " +
      list.map(function (d) { return '<button class="lnk3" data-sel="' + esc(d.id) + '">' + esc(d.id) + "</button>"; }).join(", ") + ".</p>";
  }

  /* ----- the log, in the order things arrive ----- */
  function rel(M, ts) { var t = tsMs(ts); return M.t0 != null && t != null ? clock((t - M.t0) / 1000) : ""; }
  function itemHTML(M, it, chat) {
    var w = '<span class="lv-w">' + rel(M, it.ts) + "</span>", who = it.agent ? '<span class="lv-ag">' + esc(it.agent) + "</span>" : "";
    switch (it.k) {
      case "msg":
        if (it.role === "user") {
          var mid = it.mid ? ' data-mid="' + esc(it.mid) + '"' : "", ust = it.dlv ? dlvHTML(it.dlv) : "";
          return chat ? '<div class="you lv-y"' + mid + "><p>" + esc(it.text) + "</p>" + ust + "</div>" : '<div class="lv-r lv-m lv-u"' + mid + '><div class="lv-mh"><b>You</b>' + ust + w + '</div><div class="lv-md">' + md(it.text) + "</div></div>";
        }
        return chat ? '<div class="msg lv-cm" style="--rc:#2b55d0"><span class="mav" style="background:#2b55d01a;color:#2b55d0">' + I("chip", "s16") + '</span><div><div class="who">' + esc(it.author || "ChipIn") + who + '<span class="when">' + rel(M, it.ts) + '</span></div><div class="mt lv-md">' + md(it.text) + "</div></div></div>"
          : '<div class="lv-r lv-m"><div class="lv-mh"><b>' + esc(it.author || "ChipIn") + "</b>" + who + w + '</div><div class="lv-md">' + md(it.text) + "</div></div>";
      case "status": return '<div class="lv-r lv-s"><i></i><span>' + who + esc(units(it.text)) + "</span>" + w + "</div>";
      case "tool": {
        var g = it.state === "done" ? I("check", "s12 lv-ok") : it.state === "failed" ? I("x", "s12 lv-bad") : M.running ? '<span class="spin"></span>' : I("minus", "s12");
        return '<div class="lv-r lv-t" data-tool="' + esc(it.id) + '"><button class="lv-th" aria-expanded="false">' + g + "<b>" + esc(it.name || "Tool") + "</b><span>" + who + esc(it.summary || "") + "</span>" + w + "</button></div>";
      }
      case "err": return '<div class="lv-r lv-e">' + I("x", "s12") + "<span>" + esc(it.text) + "</span>" + w + "</div>";
      case "stage": return '<div class="lv-r lv-g"><span>' + esc(STAGE_N[it.n] || it.n) + " " + (it.state === "started" ? "started" : it.state === "done" ? "done" : it.state === "skipped" ? "skipped" + (it.reason ? ": " + esc(it.reason) : "") : esc(it.state)) + "</span>" + w + "</div>";
      case "design": {
        var d = it.d, s = sizeOf(d), T = M.T.length ? M.T : [], vals = (T.length ? T.map(function (t) { return t.metric; }) : Object.keys(d.metrics).slice(0, 2)).map(function (k) { return metaOf(k).n.toLowerCase() + " " + fmtV(k, val(d, k), M.spec); });
        var what = d.verified ? "verified" : s && s.m ? "compiled, " + fmt(s.g) + " gates" : it.isNew ? "scored" : "updated";
        return '<div class="lv-r lv-d">' + I("chip", "s12") + "<span><b>Design " + esc(d.id) + "</b> " + what + (vals.length ? ": " + esc(vals.join(", ")) : "") + (d.basis ? " (" + esc(d.basis) + ")" : "") + "</span>" + w + "</div>";
      }
      case "chosen": return '<div class="lv-r lv-d lv-cho">' + I("check", "s12") + "<span><b>Chosen: chip " + esc(it.chip) + "</b></span>" + w + "</div>";
      case "art": return '<div class="lv-r lv-d">' + I("file", "s12") + '<span>Wrote <button class="lnk3" data-open="' + esc(it.path) + '">' + esc(it.name) + "</button></span>" + w + "</div>";
      case "sub": return '<div class="lv-r lv-s"><i></i><span>Subagent ' + esc(it.key) + " " + esc(it.state) + (it.strategy ? ": " + esc(clip(it.strategy, 80)) : "") + "</span>" + w + "</div>";
      case "merge": return '<div class="lv-r lv-d"><span><b>' + esc(STAGE_N[it.stage] || it.stage) + " merged</b>: kept " + esc(it.kept.join(", ") || "nothing") + (it.reason ? ". " + esc(it.reason) : "") + "</span>" + w + "</div>";
      case "fin": return '<div class="lv-r lv-g lv-f"><span>Run ' + esc(it.status) + "</span>" + w + "</div>";
      default: return "";
    }
  }
  function toggleTool(e) {
    var o = e.target.closest("[data-open]"); if (o) { openFile(o.dataset.open); return; }
    var b = e.target.closest(".lv-th"); if (!b) return;
    var row = b.parentNode, open = b.getAttribute("aria-expanded") === "true";
    b.setAttribute("aria-expanded", String(!open));
    var ex = $(".lv-td", row);
    if (open) { if (ex) ex.remove(); return; }
    var t = W[V.id].x.tools[row.dataset.tool]; if (!t) return;
    ex = document.createElement("div"); ex.className = "lv-td";
    ex.innerHTML = "<p>" + esc(t.summary || "") + "</p>" + (t.detail ? "<pre>" + esc(clip(t.detail, 6000)) + "</pre>" : '<p class="lv-mute">' + (t.state === "started" ? "Still running." : "No output was recorded.") + "</p>");
    row.appendChild(ex);
  }
  function paintFeed(M, el, chat, key) {
    var items = M.x.items, n = V[key], frag = "";
    if (chat) items = items.filter(function (it) { return it.k !== "design" || it.isNew; });
    for (var i = n; i < items.length; i++) frag += itemHTML(M, items[i], chat);
    if (frag) { el.insertAdjacentHTML("beforeend", frag); V[key] = items.length; }
    // tool rows whose state changed since they were drawn
    Object.keys(M.x.tools).forEach(function (id) {
      var t = M.x.tools[id]; if (!t.chg || t.drawn === t.chg + key) return;
      var row = el.querySelector('[data-tool="' + CSS.escape(id) + '"]'); if (!row) return;
      var head = $(".lv-th", row), tmp = document.createElement("div"); tmp.innerHTML = itemHTML(M, t, chat);
      var nh = $(".lv-th", tmp); if (nh) { nh.setAttribute("aria-expanded", head.getAttribute("aria-expanded")); row.replaceChild(nh, head); }
      t.drawn = t.chg + key;
    });
    if (!M.running) el.querySelectorAll(".lv-t .spin").forEach(function (s) { s.outerHTML = I("minus", "s12"); });
    return !!frag;
  }

  /* ----- files ----- */
  function artifacts(M) {
    var seen = {}, out = [];
    M.st.artifacts.slice().reverse().forEach(function (a) { if (a.path && !seen[a.path]) { seen[a.path] = 1; out.push(a); } });
    out.reverse();
    var rank = function (a) { return a.kind === "report" ? (a.path === "workspace/report.md" ? 0 : 1) : a.kind === "chip" ? 2 : 3; };
    return out.sort(function (a, b) { return rank(a) - rank(b); });
  }
  // files the page needs by name are read only once the file list names them (the backend lists
  // the report, final record, designs and spec first), so no request can miss on a run in
  // progress. After the run ends the list is read once more; a file it leaves out is read by
  // path only when that list was cut short (truncated). Each file is read once.
  var NAMED = [
    { path: "workspace/spec.json", ready: function () { return true; }, take: function (x, j) { if (!x.spec) x.spec = j; } },
    { path: "workspace/final_record.json", ready: function (M) { return !M.running; }, take: function (x, j) { x.final = F.scrubEvent(j); } }
  ];
  function readNamed(M) {
    var x = M.x; if (C.state !== "on") return;
    var got = x.named || (x.named = {});
    NAMED.forEach(function (n) {
      var listed = !!(x.files && x.files[n.path] != null), cut = !M.running && x.filesFin === true && x.filesTrunc;
      if (got[n.path] || !n.ready(M) || !(listed || cut)) return;
      got[n.path] = "busy";
      L.readFile(M.id, n.path).then(function (r) {
        var j = null; try { j = JSON.parse(r.text); } catch (e) { /* not JSON: nothing taken from it */ }
        got[n.path] = "ok";
        if (j && typeof j === "object") { n.take(x, j); x.v++; }
      }).catch(function () { got[n.path] = "gone"; });
    });
  }
  function refreshSizes(M) {
    var x = M.x, st = M.st.stages || {}, fin = !M.running && !x.filesFin;
    // files added or a stage finished (the spec stage writes spec.json): the list may name something new
    var n = M.st.artifacts.length + "|" + Object.keys(st).filter(function (k) { return st[k] && st[k].state === "done"; }).length;
    readNamed(M);
    // when files were added, and once more when the run has ended (the update loop calls this every 250 ms)
    if (C.state !== "on" || x.filesBusy || (!fin && x.filesN === n) || Date.now() - x.filesAt < 2500) return;
    x.filesAt = Date.now(); x.filesN = n; x.filesBusy = true;
    L.listFiles(M.id).then(function (files) {
      x.filesBusy = false; x.files = {}; files.forEach(function (f) { x.files[f.path] = f.size; }); x.filesTrunc = !!files.truncated;
      if (fin) x.filesFin = true;
      x.v++; readNamed(M);
    }).catch(function () { x.filesBusy = false; x.filesN = -1; });
  }
  // a chip lab chip report is named by its chip, so it is not mistaken for the run's report
  var fname = function (a) { var m = /\/chips\/([^/]+)\/report\.md$/.exec(a.path || ""); return m ? "Chip report, " + m[1] : a.name; };
  function filesHTML(M) {
    var list = artifacts(M), sz = M.x.files || {};
    if (!list.length) return '<div class="lv-fh"><h2>Files</h2></div><p class="lv-mute lv-pad">' + (M.running ? "Files appear here as the agent writes them." : "This run wrote no files it reported.") + "</p>";
    var rep = list.filter(function (a) { return a.kind === "report"; }), other = list.filter(function (a) { return a.kind !== "report"; });
    var row = function (a) { return '<li><span class="lv-fn">' + I("file", "s14") + "<b>" + esc(fname(a)) + '</b><span class="lv-fp">' + esc(a.path.replace(/^workspace\//, "")) + "</span></span><span class=\"lv-fs\">" + esc(bytes(sz[a.path])) + '</span><button class="qbtn" data-open="' + esc(a.path) + '">' + (a.kind === "report" ? "Read" : "Open") + "</button></li>"; };
    return '<div class="lv-fh"><h2>Files</h2><span class="lv-mute">' + list.length + " from this run" + "</span></div>" + (rep.length ? '<ul class="lv-fl lv-rep">' + rep.map(row).join("") + "</ul>" : "") +
      (other.length ? '<details class="lv-more"' + (other.length <= 4 ? " open" : "") + "><summary>" + other.length + " other file" + (other.length === 1 ? "" : "s") + '</summary><ul class="lv-fl">' + other.map(row).join("") + "</ul></details>" : "");
  }
  var drawerEl = null;
  function closeDrawer() { if (drawerEl) { drawerEl.remove(); drawerEl = null; } var s = $(".lv-dscrim"); if (s) s.remove(); }
  function openFile(path) {
    if (!V) return;
    closeDrawer();
    var name = path.split("/").pop();
    var sc = document.createElement("div"); sc.className = "dscrim lv-dscrim"; sc.onclick = closeDrawer; document.body.appendChild(sc);
    drawerEl = document.createElement("aside"); drawerEl.className = "drawer lv-drawer"; drawerEl.setAttribute("role", "dialog"); drawerEl.setAttribute("aria-label", name);
    drawerEl.innerHTML = '<div class="dh"><h3>' + esc(name) + '</h3><button aria-label="Close">' + I("x", "s16") + '</button></div><div class="db"><p class="lv-mute">' + esc(path) + '</p><div id="lvDoc"><p class="lv-mute">Opening the file…</p></div></div>';
    document.body.appendChild(drawerEl);
    $(".dh button", drawerEl).onclick = closeDrawer;
    $(".dh button", drawerEl).focus();
    // an image shows as the image, a binary file is named: its bytes never show as text
    var vo = { base: C.base, token: C.token, id: V.id };
    if (F.fileView($("#lvDoc"), path, null, vo)) return;
    L.readFile(V.id, path).then(function (r) {
      var doc = $("#lvDoc"); if (!doc) return;
      if (F.fileView(doc, path, r.text, vo)) return;
      var t = r.text, html;
      if (/\.md$/i.test(path)) html = '<div class="lv-md lv-doc">' + md(t) + "</div>";
      else if (/\.json$/i.test(path)) { try { html = "<pre>" + esc(JSON.stringify(JSON.parse(t), null, 2)) + "</pre>"; } catch (e) { html = "<pre>" + esc(t) + "</pre>"; } }
      else html = "<pre>" + esc(t) + "</pre>";
      doc.innerHTML = (r.truncated ? '<p class="nopass">The file is long; the backend sent its first 512 KB.</p>' : "") + html;
    }).catch(function (e) { var doc = $("#lvDoc"); if (doc) doc.innerHTML = '<p class="nopass">The file could not be read: ' + esc(e.message) + "</p>"; });
  }
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && drawerEl) closeDrawer(); });
  addEventListener("hashchange", closeDrawer);

  /* ----- banner for failed, stopped and errors ----- */
  function banHTML(M) {
    var errs = M.x.items.filter(function (it) { return it.k === "err"; });
    if (M.status !== "failed" && M.status !== "stopped" && !errs.length) return "";
    var last = M.x.items.filter(function (it) { return (it.k === "msg" && it.role !== "user") || it.k === "status"; }).slice(-3);
    var sum = M.st.finished && M.st.finished.summary;
    var title = M.status === "failed" ? "The run failed." : M.status === "stopped" ? "The run was stopped." : "The agent reported an error; the run carries on.";
    return '<div class="lv-ban' + (M.status === "stopped" ? " lv-stp" : "") + '" role="alert"><b>' + title + "</b>" + (errs.length ? "<ul>" + errs.slice(-3).map(function (e) { return "<li>" + esc(clip(e.text, 400)) + "</li>"; }).join("") + "</ul>" : "") +
      (sum && !errs.some(function (e) { return e.text === sum; }) ? "<p>" + esc(clip(sum, 600)) + "</p>" : "") +
      (last.length && M.status !== "running" ? '<p class="lv-last">The agent\'s last lines:</p><ul class="lv-lastl">' + last.map(function (it) { return "<li>" + esc(clip(it.text, 300)) + "</li>"; }).join("") + "</ul>" : "") + "</div>";
  }

  /* ----- the update loop ----- */
  function update(force) {
    if (!V || V.waiting || !W[V.id]) return;
    var M = modelOf(V.id), x = M.x, ch = function (k, s) { if (force || V.sig[k] !== s) { V.sig[k] = s; return true; } return false; };
    // the run has ended (its stream sent run.finished): replace the timer view with the replay and its playback bar
    if (M.st.finished && ended(M.status) && C.state === "on" && window.ChipInPlayback) { location.replace(location.pathname + location.search + recHref(V.id, V.view)); return; }
    // top bar
    var stTxt = M.lost ? '<span class="spill paused">Disconnected</span>' : M.status === "running" ? '<span class="spill lv-run"><span class="spin"></span>Running</span>' : M.status === "succeeded" ? '<span class="spill done">Finished</span>' : M.status === "failed" ? '<span class="spill lv-fail">Failed</span>' : M.status === "stopped" ? '<span class="spill paused">Stopped</span>' : '<span class="spill paused">Connecting</span>';
    if (ch("st", stTxt)) $("#lvSt").innerHTML = stTxt;
    var clk = M.elapsed == null ? "–" : clock(M.elapsed); var ce = $("#lvClk"); if (ce.textContent !== clk) ce.textContent = clk; ce.classList.toggle("live", M.running && !M.lost);
    var lost = $("#lvLost"); lost.hidden = !M.gone;
    var lt = M.running ? "Connection to the backend was lost; the run may still be going on that computer. Retrying..." : "Connection to the backend was lost. This page shows what had arrived; files and follow-ups need the backend. Retrying...";
    if (lost.textContent !== lt) lost.textContent = lt;
    var co = F.cost(x.f), sm = co && num(co.summaries_usd) > 0 ? co.summaries_usd : 0, cost = co && num(co.usd) != null ? "Cost: $" + (co.usd + sm).toFixed(2) : ""; if (ch("cost", cost)) { $("#lvCost").textContent = cost; $("#lvCost").title = co ? (sm ? "Agent " + co.usd.toFixed(2) + ", summaries " + sm.toFixed(2) + "; " : "") + fmt(co.tokens_in || 0) + " tokens in, " + fmt(co.tokens_out || 0) + " out" : ""; }
    var cm = $("#lvCostM"); if (cm && cm.textContent !== cost) cm.textContent = cost; // the same figure, under the headline on phones
    var bt = M.running || M.status === "connecting" ? "Live run" : "Finished run"; if (ch("badge", bt)) { $("#lvBadge").textContent = bt; $("#lvBadge").className = "mk topbadge " + (bt === "Live run" ? "lv-live" : "no"); setDemo(bt); }
    var setT = (M.r.preset ? "Run size: " + runSize(M) + " · " : "") + "Model: " + usedModel(M); if (ch("set", setT)) $("#lvSetT").textContent = setT;
    var stop = $("#lvStop"); stop.hidden = !M.running;
    if (M.lost || V.wasLost) { var lb = [stop, $("#lvCxStop")].filter(Boolean); lb.forEach(function (b) { b.disabled = !!M.lost; if (!M.lost && b.lastChild.textContent === "Stopping") b.lastChild.textContent = b === stop ? "Stop" : "Stop the run"; }); V.wasLost = !!M.lost; }
    if (!M.running && stop.disabled) { stop.disabled = false; stop.lastChild.textContent = "Stop"; var cs = $("#lvCxStop"); if (cs) { cs.disabled = false; cs.lastChild.textContent = "Stop the run"; } }
    if (V.view === "overview") updOverview(M, ch, force);
    else if (V.view === "chat") updChat(M, ch);
    else if (ch("tab", V.view + "|" + x.v + "|" + (V.sel || "") + "|" + M.status)) paintTab(M);
    refreshSizes(M);
  }
  function updOverview(M, ch, force) {
    var x = M.x, key = x.v + "|" + M.status + "|" + !!M.lost + "|" + (V.sel || "") + "|" + (V.y || "") + "|" + (M.chosenId || "");
    if (ch("ban", banHTML(M))) $("#lvBan").innerHTML = V.sig.ban;
    if (ch("head", key)) $("#lvHead").innerHTML = headHTML(M);
    var stl = M.lost ? "Waiting for the backend to answer again" : M.running ? units(M.st.statusLine) || "Waiting for the agent's first step" : M.status === "succeeded" ? "Finished" + (M.elapsed != null ? " in " + clock(M.elapsed) : "") + "." : "";
    if (ch("status", stl)) { var s = $("#lvStatus"); s.className = "status" + (M.running ? "" : " done"); s.innerHTML = stl ? (M.running && !M.lost ? '<span class="spin"></span>' : "") + "<span>" + esc(stl) + "</span>" : ""; s.style.display = stl ? "" : "none"; }
    if (ch("stages", JSON.stringify(M.st.stages) + M.status)) $("#lvStages").innerHTML = stagesHTML(M);
    if (ch("subs", key)) $("#lvSubs").innerHTML = subsHTML(M);
    if (ch("tiles", key)) $("#lvTiles").innerHTML = tilesHTML(M);
    if (ch("insp", key + "|" + (x.files ? 1 : 0))) $("#lvInsp").innerHTML = inspHTML(M);
    if (ch("fun", key)) { $("#lvFun").innerHTML = funHTML(M); $("#lvFunN").textContent = M.designs.length ? "Counted from the design records this run reported; “clear your targets” is judged against your spec." : M.running ? "The funnel counts the designs the agent reports, as it reports them." : "This run reported no design records, so there is nothing to count."; }
    if (ch("files", key + "|" + M.st.artifacts.length + "|" + JSON.stringify(x.files || {}).length)) $("#lvFiles").innerHTML = filesHTML(M);
    if (ch("legend", key)) { $("#lvLegend").innerHTML = legendHTML(M); $("#lvUnsized").innerHTML = unsizedHTML(M); $("#lvChMark").innerHTML = dataMark(M.spec, M.designs); }
    if (ch("ysel", key)) {
      var keys = M.T.map(function (t) { return t.metric; });
      M.designs.forEach(function (d) { Object.keys(d.metrics).forEach(function (k) { if (keys.indexOf(k) < 0 && num(d.metrics[k]) != null && (MET[k] || /^[a-z_]+$/.test(k))) keys.push(k); }); });
      // a one-off screening run with no false-alarm target: no false-alarm option (as the Chip view and playback chart)
      if (F.screenOnly(M.spec, M.T)) keys = keys.filter(function (k) { return F.keyInfo(k).base !== "fa_per_hour"; });
      if (!keys.length) keys = [primaryOf(M)];
      var p = primaryOf(M); if (keys.indexOf(p) < 0) keys.unshift(p);
      $("#lvY").innerHTML = keys.map(function (k) { return '<option value="' + esc(k) + '"' + (k === p ? " selected" : "") + ">" + esc(metaOf(k).n) + (M.T.some(function (t) { return t.metric === k; }) ? "" : " (no target)") + "</option>"; }).join("");
    }
    var feed = $("#lvFeed");
    if (feed) { /* MESSAGES HOOK: no #lvFeed when ../i1-messages.js draws the log */
    if (paintFeed(M, feed, false, "logN")) { if (V.follow) feed.scrollTop = feed.scrollHeight; else $("#lvJump").hidden = false; }
    if (ch("logn", M.x.items.length + "|" + M.status)) $("#lvLogN").textContent = M.x.items.length ? (M.running ? "live" : M.x.items.length + " entries") : "";
    if (!M.x.items.length && !feed.firstChild) feed.innerHTML = '<p class="lv-wait">' + (M.running || M.status === "connecting" ? "Waiting for the agent's first message." : "Nothing was logged.") + "</p>";
    else if (M.x.items.length) { var w = $(".lv-wait", feed); if (w) w.remove(); }
    }
    updBox(M, ch);
    var foot = (C.base ? "Live run on " + hostOf() + ". " : "") + "Run " + M.id + ".";
    if (ch("foot", foot)) $("#lvFoot").textContent = foot;
    drawChart();
  }

  /* ----- chat: the same stream, full width ----- */
  function chatHTML() {
    return '<div class="chat"><div class="feed" id="lvChatFeed"><div class="fin" id="lvChatFin"><p class="cnote2" id="lvChatNote"></p></div></div>' +
      '<div class="comp lv-cxw">' + boxHTML() + "</div></div>";
  }
  function wireChat() {
    var feed = $("#lvChatFeed");
    feed.addEventListener("scroll", function () { V.follow = feed.scrollTop + feed.clientHeight >= feed.scrollHeight - 24; });
    $("#lvChatFin").addEventListener("click", toggleTool);
    wireBox();
  }
  function updChat(M, ch) {
    var fin = $("#lvChatFin"), feed = $("#lvChatFeed");
    if (!fin) { updBox(M, ch); return; } /* MESSAGES HOOK: ../i1-messages.js draws the chat */
    if (ch("cnote", M.status)) $("#lvChatNote").textContent = M.running ? "The agent's messages, status lines and tool calls as they arrive. Write below to steer it." : "The run's whole conversation, as it happened. A follow-up continues it with the same agent.";
    if (paintFeed(M, fin, true, "chatN") && V.follow) feed.scrollTop = feed.scrollHeight;
    updBox(M, ch);
  }

  /* ----- the message box: talk to the run's agent (Overview, under the log, and the Chat tab) ----- */
  var MAXMSG = 4000;
  var DLV = { sent: "Sent", waiting: "Waiting for the agent's current step", reached: "Reached the agent", sending: "Sending", failed: "Not sent" };
  function dlvHTML(d) { return '<span class="lv-ust" data-d="' + d + '"><i></i>' + DLV[d] + "</span>"; }
  function boxHTML() {
    return '<div class="lv-cx" id="lvCx" data-mode="off"><div class="lv-cxb"><textarea id="lvCxT" rows="1" maxlength="' + MAXMSG + '" aria-label="Message the agent" aria-describedby="lvCxN" data-voice data-voice-anchor="#lvCxSend"></textarea>' +
      '<button class="send lv-cxs" id="lvCxSend" aria-label="Send to the agent">' + I("up", "s16") + "</button></div>" +
      '<div class="lv-cxf"><span class="lv-cxn" id="lvCxN" role="status" aria-live="polite"></span><button class="lv-cxstop" id="lvCxStop" hidden>' + I("stop", "s12") + "Stop the run</button></div></div>";
  }
  // what the box offers for this run right now
  function boxMode(M) {
    if (C.state !== "on") return { m: "off", ph: "Message the agent", n: "No backend is connected, so the agent cannot be reached. Connect one under Configure." };
    if (M.status === "connecting") return { m: "off", ph: "Message the agent", n: "Connecting to the run…" };
    if (M.running) return { m: "live", ph: "Message the agent", n: "It reads your message when its current step ends." };
    if (M.status === "failed") return { m: "off", ph: "This run failed", n: "A failed run cannot take messages. Start a new run to go on." };
    return { m: "follow", ph: "Ask a follow-up", n: "The same agent picks up in the same workspace." };
  }
  function wireBox() {
    var ta = $("#lvCxT"), send = $("#lvCxSend");
    var grow = function () { ta.style.height = "auto"; ta.style.height = Math.min(160, ta.scrollHeight) + "px"; };
    ta.addEventListener("input", function () { send.classList.toggle("ready", !!ta.value.trim() && !ta.disabled); grow(); if (V.cxErr) { V.cxErr = ""; V.sig.box = ""; } });
    ta.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendBox(); } });
    send.onclick = sendBox;
    $("#lvCxStop").onclick = stopRun;
  }
  function errText(e) {
    var s = e && e.status;
    if (s === 413) return "The message is longer than 4,000 characters. Shorten it and send again.";
    if (s === 429) return "Too many runs are going on this backend. Stop one, then send again.";
    if (s === 404) return "The backend no longer knows this run.";
    if (s === 409) return cap(String(e.message || "the run cannot take messages now")) + ".";
    if (s === 401) return "The backend did not accept this page's token. Connect again under Configure.";
    if (s === 0) return "The backend did not answer. Check that it is still running.";
    return cap(String((e && e.message) || "the backend refused the message")).replace(/\.?$/, ".");
  }
  function sendBox() {
    if (!V || !W[V.id] || V.cxBusy) return;
    var ta = $("#lvCxT"), t = ta.value.trim(), rec = W[V.id], M = modelOf(V.id), mode = boxMode(M).m;
    if (!t || mode === "off") return;
    if (t.length > MAXMSG) { V.cxErr = errText({ status: 413 }); V.sig.box = ""; return; }
    // shown at once in the stream, marked as yours, until the stream's own record of it arrives
    var pend = { text: t, seq: M.st.lastSeq, id: null, el: [] };
    V.pend = pend; V.cxBusy = true; V.cxErr = ""; V.sig.box = "";
    drawPending(M);
    ta.value = ""; ta.style.height = "auto"; $("#lvCxSend").classList.remove("ready");
    L.sendMessage(V.id, t).then(function (r) {
      pend.id = r && r.id || null;
      if (mode === "follow" || (r && r.delivery === "follow_up")) { rec.x.wantLive = true; resume(rec); }
    }).catch(function (e) {
      if (V && V.pend === pend) { V.cxErr = "Not sent: " + errText(e); pend.el.forEach(function (el) { el.remove(); }); V.pend = null; }
      var box = $("#lvCxT"); if (box && !box.value) { box.value = t; box.dispatchEvent(new Event("input")); }
    }).then(function () { if (V) { V.cxBusy = false; V.sig.box = ""; } });
  }
  function drawPending(M) {
    var p = V.pend; if (!p) return;
    p.el.forEach(function (el) { el.remove(); }); p.el = [];
    var fake = { k: "msg", role: "user", text: p.text, dlv: "sending", ts: new Date().toISOString() };
    [["#lvFeed", false], ["#lvChatFin", true]].forEach(function (f) {
      var host = $(f[0]); if (!host) return;
      var tmp = document.createElement("div"); tmp.innerHTML = itemHTML(M, fake, f[1]);
      var el = tmp.firstChild; el.classList.add("lv-pend"); host.appendChild(el); p.el.push(el);
      var w = $(".lv-wait", host); if (w) w.remove();
      host = f[1] ? $("#lvChatFeed") : host; host.scrollTop = host.scrollHeight;
    });
  }
  function stopRun() {
    var top = $("#lvStop"), btns = [top, $("#lvCxStop")].filter(Boolean);
    btns.forEach(function (x) { x.disabled = true; x.lastChild.textContent = "Stopping"; });
    L.stopRun(V.id).catch(function (e) { btns.forEach(function (x) { x.disabled = false; x.lastChild.textContent = x === top ? "Stop" : "Stop the run"; }); note("The run did not stop: " + e.message); });
  }
  function updBox(M, ch) {
    var box = $("#lvCx"); if (!box) return;
    var x = M.x, p = V.pend;
    // the pending copy goes once the stream holds the message
    if (p && x.items.some(function (it) { return it.k === "msg" && it.role === "user" && it.seq > p.seq && ((p.id && it.mid === p.id) || it.text === p.text); })) { p.el.forEach(function (el) { el.remove(); }); V.pend = null; }
    if (x.wantLive) resume(W[V.id]);
    // delivery marks that changed since they were drawn
    Object.keys(x.umsg).forEach(function (id) {
      var u = x.umsg[id]; if (!u.chg || u.drawn === u.chg) return;
      document.querySelectorAll('[data-mid="' + CSS.escape(id) + '"] .lv-ust').forEach(function (s) { s.outerHTML = dlvHTML(u.dlv); });
      u.drawn = u.chg;
    });
    var bm = boxMode(M), sg = bm.m + "|" + bm.n + "|" + (V.cxErr || "") + "|" + (V.cxBusy ? 1 : 0) + "|" + M.status;
    if (!ch("box", sg)) return;
    var ta = $("#lvCxT"), send = $("#lvCxSend"), n = $("#lvCxN"), stop = $("#lvCxStop");
    box.dataset.mode = bm.m;
    ta.disabled = bm.m === "off"; ta.placeholder = bm.ph; ta.setAttribute("aria-label", bm.m === "follow" ? "Ask the agent a follow-up" : "Message the agent");
    var mic = $(".cv-mic", box); if (mic) mic.disabled = ta.disabled;
    send.disabled = ta.disabled || !!V.cxBusy; send.classList.toggle("ready", !ta.disabled && !!ta.value.trim());
    send.setAttribute("aria-label", bm.m === "follow" ? "Send the follow-up" : "Send to the agent");
    n.className = "lv-cxn" + (V.cxErr ? " err" : "");
    n.innerHTML = V.cxErr ? esc(V.cxErr) : V.cxBusy ? "Sending…" : esc(bm.n) + (bm.m === "off" && C.state !== "on" ? ' <a href="#/configure">Open Configure</a>' : "");
    stop.hidden = !M.running;
  }

  /* ----- the other tabs ----- */
  function paintTab(M) {
    var el = $("#lvTab"); if (!el) return;
    if (V.view === "chip") el.innerHTML = chipHTML(M);
    else el.innerHTML = sourcesHTML(M);
    // DESIGNS HOOK: the designs tried so far, drawn small above the chip's table (../i1-designs.js)
    if (V.view === "chip" && window.ChipInDesigns) window.ChipInDesigns.paintRun($("#lvDz"), { key: "live:" + M.id, n: M.x.v, f: M.x.f, chosen: M.chosenId, ended: !M.running, T: M.T, spec: M.spec, files: null, arts: M.st.artifacts });
    el.onclick = function (e) { var b = e.target.closest("[data-open]"); if (b) { openFile(b.dataset.open); return; } var s = e.target.closest("[data-pick]"); if (s) { V.sel = s.dataset.pick; keepPrefs(); V.sig.tab = ""; update(true); } };
  }
  function filesBlock(M, pred, title) {
    var list = artifacts(M).filter(pred); if (!list.length) return "";
    var sz = M.x.files || {};
    return '<div class="stage"><h3 class="lv-h3">' + esc(title) + '</h3><ul class="lv-fl">' + list.map(function (a) { return '<li><span class="lv-fn">' + I("file", "s14") + "<b>" + esc(fname(a)) + '</b><span class="lv-fp">' + esc(a.path.replace(/^workspace\//, "")) + '</span></span><span class="lv-fs">' + esc(bytes(sz[a.path])) + '</span><button class="qbtn" data-open="' + esc(a.path) + '">Open</button></li>'; }).join("") + "</ul></div>";
  }
  function chipHTML(M) {
    var id = M.chosenId || (selected(M) && selected(M).id);
    return F.chipHTML({ f: M.x.f, spec: M.spec, T: M.T, id: id, chosenId: M.chosenId, running: M.running }) + (id ? filesBlock(M, function (a) { return a.path.indexOf("/chips/" + id + "/") >= 0 || a.kind === "chip"; }, "Chip files") : "");
  }
  function specRows(spec) {
    if (!spec) return [];
    var T = targetsOf(spec), k = spec.constraints || {}, dt = spec.data || {};
    return [
      ["Device", [spec.device, spec.signal].filter(Boolean).join("; ") || "not given"],
      ["Detects", (spec.detect || "not given") + (spec.task_types && spec.task_types.length ? " (" + spec.task_types.join(", ") + ")" : "")],
      ["Who and where", [spec.patient_group, spec.place].filter(Boolean).join(", ") + (spec.fa_unit ? "; false alarms per " + spec.fa_unit : "")],
      ["Targets", T.length ? T.map(function (t) { return metaOf(t.metric).n + " " + fmtT(t, spec) + (t.metric === spec.primary ? " (on the chart)" : ""); }).join("; ") : "none"],
      ["Constraints", (k.find_best ? "find the best channel budget" : k.channels != null ? k.channels + (k.channels === 1 ? " channel or sensor" : " channels or sensors") : "channels not given") + (k.battery_hours != null ? "; battery at least " + k.battery_hours + " hours" : "") + (k.reusable === true ? "; reusable" : k.reusable === false ? "; disposable" : "")],
      ["Data", dt.mode === "simulate" ? "Synthetic data, generated by the agent" : dt.mode === "public" ? "Public" + (dt.dataset ? ": " + dt.dataset : ", no dataset named") : dt.mode === "own" ? "Own recordings (not available in this build)" : "not given"]
    ];
  }
  function sourcesHTML(M) {
    if (window.ChipInSources) return window.ChipInSources.liveHTML(M); /* SOURCES HOOK: the data the run's record names, as a list (../i1-sources.js) */
    var ev = M.x.evidence, evRows = "";
    if (ev) Object.keys(ev).forEach(function (k) { if (["seq", "ts", "run_id", "type"].indexOf(k) < 0 && typeof ev[k] === "string") evRows += '<div class="src"><div class="sn">' + esc(cap(k.replace(/_/g, " "))) + '</div><div class="sk lv-md">' + md(clip(ev[k], 3000)) + "</div></div>"; });
    var notes = (M.r.notes || []).map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("");
    return '<div class="srcp srcpage"><div class="vh"><h2>Sources</h2><p class="vs">Where this run\'s numbers come from: the spec you gave, the backend that ran it and the files it wrote.</p></div>' +
      "<h4>Your spec" + (M.x.spec ? ", as the backend holds it" : M.r.spec ? ", as sent with the run" : "") + "</h4>" + (M.spec ? specRows(M.spec).map(function (r) { return '<div class="kv"><span>' + esc(r[0]) + "</span><span>" + esc(r[1]) + "</span></div>"; }).join("") : '<p class="sk">No spec arrived for this run.</p>') +
      (M.r.brief || (M.spec && M.spec.brief) ? '<h4>The brief</h4><p class="sk">' + esc(M.r.brief || M.spec.brief) + "</p>" : "") +
      "<h4>The run</h4>" + '<div class="kv"><span>Run</span><span>' + esc(M.id) + '</span></div><div class="kv"><span>Backend</span><span>' + esc(hostOf() || "not connected") + (C.defaults && C.defaults.agent ? ", " + esc(AGN[C.defaults.agent] || C.defaults.agent) + " agent" : "") + "</span></div>" +
      (notes ? '<ul class="sk">' + notes + "</ul>" : "") +
      (evRows ? "<h4>Run evidence</h4>" + evRows : "") +
      (artifacts(M).length ? "<h4>Files</h4>" + filesBlock(M, function () { return true; }, "Everything the agent reported writing") : "") + "</div>";
  }
  function settingsModal(M) {
    var bg = document.createElement("div"); bg.className = "mbg";
    var rows = [["Run", M.id], ["Backend", hostOf() || "not connected"], ["Run size", M.r.preset ? runSize(M) : "the backend's default"], ["Model", usedModel(M)]].concat(specRows(M.spec));
    bg.innerHTML = '<div class="modal" role="dialog" aria-label="Run settings"><button class="mx" aria-label="Close">' + I("x", "s16") + '</button><h3>Run settings</h3><p style="margin:0 0 10px">Sent with the run when it started.</p>' +
      rows.map(function (r) { return '<div class="kv"><span>' + esc(r[0]) + "</span><span>" + esc(r[1]) + "</span></div>"; }).join("") + ((M.r.notes || []).length ? '<p class="lv-mute">' + esc(M.r.notes.join(" ")) + "</p>" : "") + "</div>";
    bg.onclick = function (e) { if (e.target === bg || e.target.closest(".mx")) bg.remove(); };
    document.body.appendChild(bg);
    $(".mx", bg).focus();
  }

  // an example run's Chat tab: the same box, disabled, saying why
  function exampleBox() {
    var t = C.state === "on" ? "Example run: no agent works on it. Start a new run to talk to its agent." : "Example run: connect a backend to talk to the agent.";
    return '<div class="comp lv-cxw"><div class="lv-cx" data-mode="off"><div class="lv-cxb"><textarea rows="1" disabled placeholder="Message the agent" aria-label="Message the agent" aria-describedby="lvExN"></textarea>' +
      '<button class="send lv-cxs" disabled aria-label="Send to the agent">' + I("up", "s16") + '</button></div><div class="lv-cxf"><span class="lv-cxn" id="lvExN">' + esc(t) +
      (C.state === "on" ? ' <a href="#/">New run</a>' : ' <a href="#/configure">Open Configure</a>') + "</span></div></div></div>";
  }

  /* ---------- Configure: the Backend section ---------- */
  function configure(panel) {
    if (!panel || !panel.parentNode) return;
    var sec = document.createElement("section"); sec.className = "lv-cfg"; sec.id = "lvCfg";
    panel.parentNode.insertBefore(sec, panel.nextSibling);
    V = V && !V.waiting && owns() ? V : { cfgMounted: true };
    V.cfgMounted = true;
    paintConfigure(true);
  }
  function paintConfigure(full) {
    var sec = $("#lvCfg"); if (!sec) { if (V) V.cfgMounted = false; return; }
    var chip = connChip();
    if (!full && $("#lvCfgState", sec)) { $("#lvCfgState", sec).innerHTML = chip; var tb = $("#lvTest", sec); if (tb) tb.disabled = C.state === "checking"; return; }
    var saved = lsGet(K_CONN) || {}, base = (C.pub ? "" : C.base) || saved.base || (loopback ? location.origin : "");
    sec.innerHTML = '<h2 class="lv-ch">Backend</h2><p class="lead2" data-tip="Runs started here go to a ChipIn backend on your computer. Without one, runs are examples on demo data. The address and token stay in this browser.">Your local ChipIn backend. Without one, runs are demo examples.</p>' +
      '<div class="cpanel"><div class="crow2"><div class="l"><b>Server address</b><span>' + (C.same ? "This page is served by the backend itself." : "The address the backend printed when it started.") + '</span></div><input class="fin2 lv-in" id="lvBase" value="' + esc(base) + '" placeholder="http://127.0.0.1:port" spellcheck="false" autocomplete="off" aria-label="Server address"></div>' +
      '<div class="crow2"><div class="l"><b>Token</b><span data-tip="From the link the backend printed; paste the whole link or just the token.">Paste the backend\'s link or just its token.</span></div><input class="fin2 lv-in" id="lvTok" type="password" value="' + esc((C.pub ? "" : C.token) || saved.token || "") + '" placeholder="Token" spellcheck="false" autocomplete="off" aria-label="Token"></div>' +
      '<div class="crow2"><div class="l" id="lvCfgState">' + chip + '</div><button class="btn s" id="lvForget">Forget</button><button class="btn p" id="lvTest">Test</button></div></div>';
    $("#lvTest", sec).onclick = function () {
      var raw = $("#lvTok", sec).value.trim(), tok = L.tokenFromLink(raw) || raw || null, b = $("#lvBase", sec).value.trim();
      var m = raw.match(/^(https?:\/\/[^/#?\s]+)/); if (m && !b) b = m[1];
      $("#lvTok", sec).value = tok || "";
      connect(b, tok);
    };
    $("#lvForget", sec).onclick = function () { lsSet(K_CONN, null); C.state = "off"; C.kind = ""; C.token = null; C.msg = ""; C.base = C.same ? location.origin : null; if (C.same) C.state = "found"; paintConfigure(true); bump(); if (!C.same) connectPublic(); };
  }
  function liveOpen() { return !!(V && V.id && owns()); }
  function connChip() {
    var s = C.state, t = C.pub && s !== "checking" ? (s === "on" ? "Live" : "Live runs offline: examples only") : s === "on" ? "Connected to local backend" + (C.defaults && C.defaults.agent ? ", " + (AGN[C.defaults.agent] || C.defaults.agent) + " agent" : "") : s === "checking" ? "Checking the backend…" : s === "found" ? "Backend found on this page's address: add its token" : s === "bad" ? (liveOpen() || C.lost ? "Not connected to the backend" : "Not connected: runs are examples") : "Not connected: runs are examples";
    return '<span class="lv-cs" data-s="' + s + '"><i></i><b>' + esc(t) + "</b></span>" + (C.msg && s !== "on" ? '<span class="lv-cm2">' + esc(C.msg) + "</span>" : "");
  }

  /* ---------- sidebar: the chip and the backend's runs, under Recents ---------- */
  // a finished run is replayed by ../i1-playback.js (#/rec/mac/<id>), with the playback bar; only a running one opens here
  // any final state (interrupted or cancelled by a backend restart included) opens the replay with its bar
  var ended = function (s) { return !!s && !/^(running|queued|starting|pending|connecting)$/.test(s); };
  var recHref = function (id, view) { return "#/rec/mac/" + encodeURIComponent(id) + "/" + (view === "chip" ? "chip" : view === "chat" ? "log" : "overview"); };
  function recents() {
    var cur = parse(), s = C.state, recId = (location.hash.match(/^#\/rec\/mac\/([^/?]+)/) || [])[1];
    var kt = s !== "on" && s !== "checking" && C.kind === "expired" ? "Backend link expired" : s !== "on" && s !== "checking" && C.kind === "unreachable" ? "Backend not reachable" : "";
    var host = ""; try { host = C.base && !C.pub ? new URL(C.base).hostname : ""; } catch (e) { /* no host to show */ }
    var txt = kt ? kt : C.pub && s === "on" ? "Live" : C.pub && s !== "checking" && !((liveOpen() || C.lost) && s === "bad") ? "Live runs offline: examples only" : s === "on" ? "Connected to local backend" : s === "checking" ? "Checking the backend" : s === "found" ? "Backend found: add its token" : (liveOpen() || C.lost) && C.base ? "Not connected to the backend" : "Not connected to a backend";
    var rows = shownRuns().slice(0, 8).map(function (r) {
      var g = r.status === "running" ? '<span class="spin"></span>' : ended(r.status) ? I("check", "s12 ok") : ""; // every ended run gets the tick (owner, 22 Nov)
      var on = (cur && cur.id === r.id) || (recId && decodeURIComponent(recId) === r.id);
      return '<a class="rrow lv-rrow' + (on ? " on" : "") + '" href="' + (ended(r.status) ? recHref(r.id, cur && cur.view) : "#/live/" + encodeURIComponent(r.id) + "/" + (cur ? cur.view : "overview")) + '" title="' + esc(r.title + " (run " + r.id + ", " + r.status + ")") + '"><span class="g">' + g + '</span><span class="t">' + esc(r.title || r.id) + "</span></a>";
    }).join("");
    return '<a class="lv-conn hc" href="#/configure" data-s="' + s + '"' + (kt ? ' data-k="' + C.kind + '"' : "") + ' title="' + esc(kt ? kt + (host ? " (" + host + ")" : "") : C.msg || (host ? host : C.pub ? (s === "on" ? "Runs started here run for real" : "Runs started here are examples on demo data") : "Set up a backend under Configure")) + '"><i></i><span>' + esc(txt) + "</span></a>" + rows;
  }
  function sig() { var cur = parse(); return C.state + C.kind + "|" + (cur ? cur.id + cur.view : "") + "|" + shownRuns().map(function (r) { return r.id + r.status + r.title; }).join(","); }

  /* ---------- the "Your spec" card: say where Run goes ---------- */
  function specNote() {
    if (location.hash !== "#/new/spec") return;
    var b = $('.gfa [data-a="run"]'); if (!b) return;
    var t = C.state === "on" ? (C.pub ? "Runs for real on the live backend" : "Runs on your local backend") : C.pub ? "Example run on demo data: live runs offline" : "Example run on demo data: no backend connected";
    var n = $(".lv-runnote", b.parentNode);
    if (!n) { n = document.createElement("span"); n.className = "lv-runnote"; b.parentNode.insertBefore(n, b); }
    if (n.dataset.s !== C.state || n.dataset.p !== String(C.pub)) { n.dataset.s = C.state; n.dataset.p = String(C.pub); n.innerHTML = "<i></i>" + esc(t); }
  }

  /* ---------- styles: the page's tokens, a few additions ---------- */
  var css = document.createElement("style");
  css.textContent = [
    ".lv-conn{display:flex;align-items:center;gap:7px;margin:0 10px 6px;padding:5px 9px;border-radius:7px;font-size:11.5px;color:var(--i600);text-decoration:none;background:var(--i100);line-height:1.3}",
    ".lv-conn:hover{color:var(--i900)}.lv-conn i,.lv-cs i,.lv-runnote i{width:7px;height:7px;border-radius:50%;background:#9aa0ae;flex:none}",
    ".lv-conn[data-s=on] i,.lv-cs[data-s=on] i,.lv-runnote[data-s=on] i{background:#15803d}.lv-conn[data-s=on]{background:#eef8f2;color:#0b5a3f}",
    ".lv-conn[data-k]{background:#fdf3e3;color:#7a4208}.lv-conn[data-k] i{background:#b45309}.lv-conn[data-s=checking] i,.lv-cs[data-s=checking] i{background:#b45309}.lv-conn[data-s=found] i,.lv-cs[data-s=found] i{background:var(--blue7)}",
    ".lv-rrow .lv-bad,.lv-bad{color:var(--missed)}.lv-ok{color:var(--okt)}",
    ".mk.lv-live{color:#1e3a8a;background:#e8eefc}",
    ".spill.lv-run{display:inline-flex;align-items:center;gap:6px;background:#eef3fe;color:var(--blue7);box-shadow:inset 0 0 0 1px #d6e1fb}.spill.lv-fail{background:var(--badbg);color:#9f2a20;box-shadow:inset 0 0 0 1px #f3c9c3}",
    ".lv-cost{font-size:11.5px;color:var(--i600);white-space:nowrap;font-variant-numeric:tabular-nums}",
    ".lv-costm{display:none;margin:2px 0 6px;font-size:12px;color:var(--i600);font-variant-numeric:tabular-nums}.lv-costm:empty{display:none!important}",
    ".lv-lost{margin:8px 16px 0;background:var(--badbg);border:1px solid #f3c9c3;border-radius:12px;padding:9px 14px;font-size:13px;color:#7a2018;line-height:1.5}.lv-lost[hidden]{display:none}",
    ".lv-stop:disabled{opacity:.5;cursor:not-allowed}",
    ".lv-stop{height:26px;padding:0 10px;margin-left:4px}.lv-stop[hidden]{display:none}",
    ".lv-mute{color:var(--i600)}.lv-pad{padding:0 16px 14px;margin:0;font-size:12.5px}",
    ".lv-stages{background:#fff;border:1px solid rgb(0 0 0/.07);border-radius:14px;padding:12px 6px 10px}",
    ".lv-stages ol{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(7,minmax(0,1fr))}",
    ".lv-stages li{position:relative;display:flex;flex-direction:column;align-items:center;gap:3px;text-align:center;min-width:0}",
    ".lv-stages li::before{content:'';position:absolute;top:5px;left:-50%;width:100%;height:1.5px;background:var(--i150)}.lv-stages li:first-child::before{display:none}",
    ".lv-stages li.done::before,.lv-stages li.now::before,.lv-stages li.skip::before,.lv-stages li.fail::before,.lv-stages li.halt::before{background:#b9c8f2}",
    ".lv-stages i{position:relative;z-index:1;width:11px;height:11px;border-radius:50%;background:#fff;border:1.6px solid var(--i300)}",
    ".lv-stages .done i{background:var(--okt);border-color:var(--okt)}.lv-stages .now i{background:var(--blue7);border-color:var(--blue7);box-shadow:0 0 0 3px rgb(43 85 208/.15)}",
    ".lv-stages .skip i{background:var(--i150);border-color:var(--i300)}.lv-stages .fail i{background:var(--missed);border-color:var(--missed)}.lv-stages .halt i{background:var(--i300);border-color:var(--i300)}",
    ".lv-stages span{font-size:12px;font-weight:600;color:var(--i800);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}.lv-stages li:not(.done):not(.now):not(.fail) span{color:var(--i550);font-weight:500}",
    ".lv-stages small{font-size:11px;color:var(--i550);font-variant-numeric:tabular-nums;white-space:nowrap;min-height:14px}",
    ".lv-log{display:flex;flex-direction:column;padding:12px 0 0;min-height:260px}",
    /* wide screens: as in playback, tiles straight above the chart and the side column beside it, here
       the compact batches first, then the agent log at a fixed height and the inspector; the column may
       run past the chart, so the headline, tiles, batches and the whole chart fit a laptop screen */
    "@media (min-width:1101px){.lv-ov .cgrid2:has(.side){align-items:start}.lv-ov .cgrid2:has(.side) .side{contain:none;overflow:visible}" +
      ".lv-ov .side .lv-log{flex:none;height:min(440px,max(320px,calc(100vh - 440px)));min-height:0}.lv-ov .side .insp{flex:none;max-height:none;min-height:0;overflow:visible}" +
      ".lv-ov .side .cf-sb summary{grid-template-columns:78px auto minmax(0,1fr);gap:4px 8px}.lv-ov .side .cf-sbb{padding-left:0}}",
    ".lv-lh{display:flex;align-items:baseline;gap:8px;padding:0 16px 8px;border-bottom:1px solid var(--hair)}.lv-lh h2{font-size:13px;font-weight:650;margin:0}.lv-n{font-size:11.5px;color:var(--i550)}",
    ".lv-feed{flex:1;overflow:auto;min-height:0;padding:6px 10px 10px 12px;overscroll-behavior:contain}",
    "@media (max-width:1100px){.lv-feed{max-height:340px}.lv-log{min-height:0}}",
    ".lv-r{display:grid;grid-template-columns:14px minmax(0,1fr) auto;gap:8px;align-items:baseline;padding:3px 2px;font-size:12.5px;line-height:1.45;color:var(--i700)}",
    ".lv-r .lv-w,.lv-mh .lv-w{font-size:10.5px;color:var(--i550);font-variant-numeric:tabular-nums;white-space:nowrap}",
    ".lv-s i{width:5px;height:5px;border-radius:50%;background:var(--i300);justify-self:center;align-self:center}.lv-s span{color:var(--i600)}",
    ".lv-m{display:block;padding:8px 2px 6px}.lv-mh{display:flex;align-items:baseline;gap:8px;font-size:12px}.lv-mh b{font-weight:650;color:var(--i900)}.lv-mh .lv-w{margin-left:auto}",
    ".lv-md{font-size:13px;line-height:1.55;color:var(--i900);overflow-wrap:anywhere}.lv-md p{margin:3px 0}.lv-md ul,.lv-md ol{margin:4px 0;padding-left:18px}.lv-md code{font-family:var(--mono);font-size:.88em;background:var(--i100);border-radius:4px;padding:0 3px}",
    ".lv-md pre{font-family:var(--mono);font-size:11.5px;background:var(--i100);border-radius:8px;padding:8px 10px;overflow:auto;white-space:pre}.lv-md h3,.lv-md h4,.lv-md h5,.lv-md h6{font-size:13.5px;margin:10px 0 4px}",
    ".lv-u .lv-mh b{color:var(--blue7)}",
    ".lv-t{display:block;padding:0}.lv-th{display:grid;grid-template-columns:14px auto minmax(0,1fr) auto;gap:8px;align-items:center;width:100%;padding:3px 2px;border-radius:6px;font-size:12.5px;color:var(--i700)}",
    ".lv-th:hover{background:var(--i100)}.lv-th b{font-weight:600;color:var(--i800)}.lv-th>span:not(.spin):not(.lv-w){overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--i600)}.lv-th .spin{width:10px;height:10px}",
    ".lv-td{margin:2px 0 6px 7px;padding:4px 0 4px 12px;border-left:2px solid var(--i150);font-size:12px;color:var(--i700)}.lv-td p{margin:0 0 4px;overflow-wrap:anywhere}",
    ".lv-td pre{margin:0;font-family:var(--mono);font-size:11px;line-height:1.45;background:var(--i100);border-radius:6px;padding:6px 8px;max-height:220px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere}",
    ".lv-e{color:#9f2a20;background:var(--badbg);border-radius:6px;padding:4px 6px}.lv-g{grid-template-columns:minmax(0,1fr) auto;margin:6px 0 2px;padding-top:6px;border-top:1px solid var(--hair);font-size:11.5px;font-weight:600;color:var(--i550)}",
    ".lv-g.lv-f{color:var(--i800)}.lv-d{color:var(--i800)}.lv-d svg{color:var(--blue7);align-self:center}.lv-d b{font-weight:650}.lv-cho svg{color:var(--okt)}.lv-ag{font-weight:600;color:#6b46c1;margin-right:6px}",
    ".lv-jump{position:absolute;left:50%;bottom:10px;transform:translateX(-50%);display:inline-flex;align-items:center;gap:5px;height:26px;padding:0 11px;border-radius:99px;background:var(--i900);color:#fff;font-size:11.5px;font-weight:600;box-shadow:0 4px 14px rgb(0 0 0/.18)}.lv-jump[hidden]{display:none}",
    ".lv-wait{font-size:12.5px;color:var(--i550);margin:8px 4px}",
    ".lv-uns{font-size:12px;color:var(--i600);margin:8px 2px 0;line-height:1.5}.lv-wide{grid-column:1/-1}",
    ".lv-files{padding:12px 0 6px}.lv-fh{display:flex;align-items:baseline;gap:10px;padding:0 16px 8px}.lv-fh h2{font-size:13px;font-weight:650;margin:0}.lv-fh span{font-size:11.5px}",
    ".lv-fl{list-style:none;margin:0;padding:0 8px}.lv-fl li{display:flex;align-items:center;gap:10px;padding:6px 8px;border-top:1px solid var(--hair);font-size:12.5px}",
    ".lv-fn{display:flex;align-items:center;gap:8px;min-width:0;flex:1}.lv-fn b{font-weight:600;white-space:nowrap}.lv-fp{color:var(--i550);font-size:11.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}",
    ".lv-fs{color:var(--i600);font-size:11.5px;font-variant-numeric:tabular-nums;white-space:nowrap}.lv-fl .qbtn{height:26px;padding:0 10px}",
    ".lv-more summary{cursor:pointer;font-size:12px;color:var(--i600);padding:6px 16px;list-style-position:inside}.lv-more[open] summary{color:var(--i800)}",
    ".lv-ban{background:var(--badbg);border:1px solid #f3c9c3;border-radius:12px;padding:11px 14px;font-size:13px;color:#7a2018;line-height:1.5}.lv-ban b{font-weight:650}.lv-ban ul{margin:4px 0 0;padding-left:18px}.lv-ban p{margin:6px 0 0}",
    ".lv-ban.lv-stp{background:var(--i100);border-color:var(--i150);color:var(--i800)}.lv-last{font-weight:600}.lv-lastl{color:var(--i700)}",
    ".lv-subs{padding:12px 16px}.lv-subs h2{font-size:13px;font-weight:650;margin:0 0 6px}.lv-sb{display:grid;grid-template-columns:90px minmax(0,1fr);gap:4px 12px;padding:6px 0;border-top:1px solid var(--hair);font-size:12.5px}",
    ".lv-sb>span{grid-column:1;font-size:11.5px}.lv-sb>b{font-weight:600}.lv-sl{grid-column:2;grid-row:1/span 2;display:flex;flex-wrap:wrap;gap:6px}",
    ".lv-sc{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 9px;border-radius:8px;border:1px solid rgb(0 0 0/.09);background:#fff;font-size:12px;max-width:100%}.lv-sc>span:not(.spin){overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.lv-sc em{font-style:normal;color:var(--i600);font-variant-numeric:tabular-nums}",
    ".lv-mg{grid-column:2;margin:2px 0 0;font-size:12px;color:var(--i700)}",
    ".lv-k{font-size:12.5px;color:var(--i600);margin:0 0 4px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}.lv-h3{font-size:13px;font-weight:650;margin:0 0 6px}",
    ".lv-pp{padding:10px 16px}.lv-pr{display:grid;grid-template-columns:64px minmax(0,1fr) 170px 150px;gap:12px;align-items:center;padding:5px 0;border-top:1px solid var(--hair);font-size:12.5px}.lv-pr:first-child{border-top:0}",
    ".lv-pid{font-weight:600}.lv-pb{position:relative;height:12px;border-radius:3px;background:var(--i100)}.lv-pb i{position:absolute;left:0;top:0;bottom:0;border-radius:3px}.lv-pb s{position:absolute;top:-4px;bottom:-4px;border-left:1.5px dashed var(--i900)}",
    ".lv-pv,.lv-pf{color:var(--i700);font-variant-numeric:tabular-nums}.lv-pf{color:var(--falsea-t)}",
    ".lv-chipm{padding:6px 16px 10px;max-width:560px}",
    ".lv-doc{font-size:14px;line-height:1.6}.lv-doc h3{font-family:var(--serif);font-weight:400;font-size:22px;margin:14px 0 6px}.lv-doc h4{font-size:15px;margin:16px 0 6px}",
    ".lv-tw{overflow:auto;margin:8px 0}.lv-md table{border-collapse:collapse;font-size:12.5px}.lv-md th,.lv-md td{border-bottom:1px solid var(--hair);padding:5px 8px;text-align:left;vertical-align:top}.lv-md th{font-weight:600;color:var(--i700);white-space:nowrap}",
    ".lv-drawer{width:min(640px,100%)}.lv-drawer pre{font-family:var(--mono);font-size:11.5px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere;background:var(--i100);border-radius:8px;padding:10px}",
    ".lv-cfg{margin-top:28px}.lv-ch{font-family:var(--serif);font-weight:400;font-size:22px;margin:0}.lv-cfg .lead2{margin:6px 0 14px}",
    ".lv-in{max-width:320px}.lv-cs{display:inline-flex;align-items:center;gap:8px}.lv-cs b{font-size:13.5px;font-weight:600}.lv-cm2{display:block;font-size:12.5px;color:var(--i600);margin-top:3px}",
    ".lv-runnote{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;color:var(--i600);margin-right:12px}",
    ".lv-runerr{flex-basis:100%;margin:8px 0 0;font-size:12.5px;color:#9f2a20}",
    ".lv-empty{padding-top:60px}",
    "#lvBan:empty,#lvSubs:empty{display:none}",
    /* the message box */
    ".lv-fw{position:relative;flex:1;min-height:0;display:flex;flex-direction:column}",
    ".lv-log .lv-cx{border-top:1px solid var(--hair);padding:10px 12px 10px}",
    ".lv-cxb{display:flex;align-items:flex-end;gap:6px;background:#fff;border:1px solid rgb(0 0 0/.1);border-radius:14px;padding:5px 5px 5px 12px;transition:border-color .15s,box-shadow .15s}",
    ".lv-cxb:focus-within{border-color:var(--blue7);box-shadow:0 0 0 3px rgb(61 109 240/.14)}",
    ".lv-cxb textarea{flex:1;min-width:0;border:0;outline:0;resize:none;background:transparent;font:inherit;font-size:13.5px;line-height:1.5;padding:5px 0;min-height:22px;max-height:160px;color:var(--i900);display:block}",
    ".lv-cxb textarea::placeholder{color:var(--i500)}.lv-cxb textarea:disabled{cursor:not-allowed}",
    ".lv-cx[data-mode=off] .lv-cxb{background:var(--i100);border-color:var(--i150)}.lv-cx[data-mode=off] textarea::placeholder{color:var(--i550)}",
    ".lv-cxs{width:30px;height:30px}.lv-cxs:disabled{cursor:not-allowed}.lv-cxs.ready{background:var(--blue7);color:#fff;box-shadow:none}.lv-cxs.ready:hover{background:#2347b3}",
    ".lv-cxs:focus-visible,.lv-cxstop:focus-visible,.lv-cxn a:focus-visible{outline:2px solid var(--blue7);outline-offset:2px}",
    ".lv-cxf{display:flex;align-items:baseline;gap:10px;margin:6px 2px 0;font-size:11.5px;line-height:1.45;color:var(--i550)}",
    ".lv-cxn{flex:1;min-width:0}.lv-cxn.err{color:#9f2a20}.lv-cxn a{color:var(--blue7);white-space:nowrap}",
    ".lv-cxstop{display:inline-flex;align-items:center;gap:5px;flex:none;font-size:11.5px;font-weight:600;color:var(--i600);padding:2px 7px;border-radius:6px}.lv-cxstop:hover{background:var(--i100);color:var(--i900)}.lv-cxstop[hidden]{display:none}",
    ".lv-cxw .lv-cx{max-width:760px;margin:0 auto}.lv-cxw .lv-cxb{border-radius:22px;padding:8px 8px 8px 18px;box-shadow:0 1px 2px rgb(0 0 0/.04),0 8px 28px -14px rgb(30 40 90/.16)}.lv-cxw .lv-cxb textarea{font-size:14px;padding:7px 0}.lv-cxw .lv-cxs{width:36px;height:36px}.lv-cxw .lv-cxf{margin:7px 18px 0}",
    ".lv-ust{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;font-weight:500;color:var(--i550);white-space:nowrap}",
    ".lv-ust i{width:6px;height:6px;border-radius:50%;border:1.3px solid var(--i300);box-sizing:border-box}",
    ".lv-ust[data-d=reached]{color:var(--blue7)}.lv-ust[data-d=reached] i{background:var(--blue7);border-color:var(--blue7)}.lv-ust[data-d=waiting] i{border-color:#b45309}.lv-ust[data-d=failed]{color:#9f2a20}",
    "@media (prefers-reduced-motion:no-preference){.lv-ust[data-d=sending] i{animation:lvpulse 1s ease-in-out infinite alternate}@keyframes lvpulse{to{background:var(--i300)}}}",
    ".lv-mh .lv-ust{margin-left:2px}.you.lv-y{flex-direction:column;align-items:flex-end;gap:4px}.you.lv-y .lv-ust{margin-right:6px}.lv-pend{opacity:.75}",
    "@media (max-width:1100px){.lv-fw{flex:none}}",
    "@media (max-width:767px){.lv-stages small{display:none}.lv-stages span{font-size:10.5px;overflow:visible;text-overflow:clip;max-width:none}.lv-stages li:nth-child(even) span{margin-top:13px}.lv-pr{grid-template-columns:44px minmax(0,1fr);row-gap:2px}.lv-pv,.lv-pf{grid-column:2;font-size:11.5px}.lv-sb{grid-template-columns:1fr}.lv-sl,.lv-mg{grid-column:1;grid-row:auto}.lv-cost{display:none}.lv-costm{display:block}.lv-in{max-width:none}.lv-cfg .crow2{flex-wrap:wrap}.lv-runnote{flex-basis:100%;margin:0 0 8px}}"
  ].join("\n");
  document.head.appendChild(css);

  /* ---------- loop ---------- */
  var lastW = innerWidth;
  setInterval(function () {
    specNote();
    if (V && !V.waiting && V.id && owns()) update(false);
    else if (V && V.waiting && C.state === "on" && owns()) render();
  }, 250);
  addEventListener("resize", function () { if (V && V.view === "overview" && innerWidth !== lastW) { lastW = innerWidth; V.chartSig = ""; drawChart(); } });

  L.i1 = {
    owns: owns,
    render: render,
    start: start,
    configure: configure,
    recents: recents,
    sig: sig,
    buildSpec: buildSpec,
    exampleBox: exampleBox,
    connection: function () { return { state: C.state, lost: !!C.lost, base: C.base }; },
    state: function () {
      // chart: the points the open run's chart drew (id, gates, measured, the plotted metric and its value)
      var chart = V && V.pts && V.id && W[V.id] ? V.pts.map(function (p) { var s = sizeOf(p.d), k = primaryOf(modelOf(V.id)); return { id: p.d.id, budget: budgetName(p.d), gates: s.g, measured: s.m, metric: k, value: val(p.d, k) }; }) : null;
      return { connection: C.state, base: C.base, message: C.msg, runs: RUNS.map(function (r) { return { id: r.id, status: r.status, title: r.title }; }), chart: chart };
    }
  };
  init();
})();
