/* ChipIn message view: every agent message and tool call of a run, with its summary, and the
 * summaries of summaries above them, opening level by level.
 *
 * Classic script, no dependencies; works with or without ../i1-live.js. Everything shown comes
 * from the backend's own events (the run stream, or GET /api/runs/{id}/summaries once a run has
 * finished); nothing is invented. Text from a run is always shown as plain text.
 *
 *   ChipInMessages.mount(container, options)  draw one run's view into container
 *       options.runId   the run whose events to show (events carry run_id)
 *       options.mode    "panel": the view keeps its own scroll area and fills the container
 *                       "page":  the container itself scrolls; the run summary stays pinned on top
 *       options.title   heading of the panel (default "Messages")
 *   ChipInMessages.feed(event, runId?)        one stream event (any type; unknown ones are ignored)
 *   ChipInMessages.reset()                    forget every run and clear the view
 *   ChipInMessages.state(runId?)              counts per level and what is open (for tests)
 *
 * Levels, top down (the backend's "summary" events: id, level, covers, parent, agent, stage,
 * text, final, source): run, stage, batch (one fan-out of subagents), agent (one subagent),
 * group (consecutive steps of one agent with one aim), item (one message, or one tool call with
 * its result, metric, file, chosen chip or error), and under an item the events it covers.
 * A newer summary with the same id replaces the older one. Steps whose summary has not arrived
 * show their own first line, marked, and swap the summary in on the same line. A group that has
 * not closed yet is the live tail: its steps show as plain rows until its title arrives. */
(function () {
  "use strict";

  var STAGES = ["spec", "reference", "propose", "finetune", "compile", "verify", "report"];
  var STAGE_N = { spec: "Spec", reference: "Reference", propose: "Propose", finetune: "Fine-tune", compile: "Compile", verify: "Verify", report: "Report" };
  var RANK = { stage: 1, batch: 2, agent: 3, group: 4, item: 5 };
  var LADDER = [["stage", "Stages", "stages"], ["batch", "Batches", "batches"], ["agent", "Subagents", "subagents"], ["group", "Groups", "groups"], ["item", "Steps", "steps"]];
  var LAB_KEYS = [["gates", "gates"], ["luts_ice40", "LUTs"], ["luts", "LUTs"], ["area_um2", "um2"], ["mismatches", "mismatches"], ["vectors_checked", "vectors"], ["verification_level", "level"], ["depth", "depth"], ["transistors", "transistors"], ["timing_slack_ns", "ns slack"], ["power_uw_at_rate", "uW"], ["cost_eur", "EUR"]];

  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var clip = function (s, n) { s = String(s == null ? "" : s); return s.length > n ? s.slice(0, n - 1) + "\u2026" : s; };
  var firstLine = function (s) { var l = String(s == null ? "" : s).split(/\r?\n/).map(function (x) { return x.trim(); }).filter(Boolean)[0] || ""; return clip(l.replace(/^#+\s*/, ""), 240); };
  var tsMs = function (ts) { var t = Date.parse(ts || ""); return isNaN(t) ? null : t; };
  var clock = function (s) { s = Math.max(0, Math.floor(s)); var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = String(s % 60).padStart(2, "0"); return h ? h + ":" + String(m).padStart(2, "0") + ":" + x : m + ":" + x; };
  var plural = function (n, one, many) { return n + " " + (n === 1 ? one : many || one + "s"); };
  var eSeq = function (id) { var m = /^e(\d+)$/.exec(id || ""); return m ? +m[1] : null; };

  var SVG = {
    chev: '<path d="M9 6l6 6-6 6"/>',
    msg: '<path d="M4 5h16v11H9l-5 4z"/>',
    tool: '<path d="M4 6l5 5-5 5M12 17h8"/>',
    lab: '<rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4"/>',
    metric: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    file: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
    chosen: '<path d="M5 12.5l4.5 4.5L19 7"/>',
    error: '<path d="M6 6l12 12M18 6L6 18"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
    agent: '<circle cx="12" cy="12" r="3.2"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/>',
    down: '<path d="M12 5v14M6 13l6 6 6-6"/>'
  };
  var ico = function (n, c) { return '<svg class="cm-i ' + (c || "") + '" viewBox="0 0 24 24" aria-hidden="true">' + SVG[n] + "</svg>"; };
  var KIND = {
    msg: ["msg", "var(--c-lead,#6b46c1)", "Message"], tool: ["tool", "var(--blue7,#2b55d0)", "Tool call"], lab: ["lab", "var(--c-chip,#a04812)", "Chip lab call"],
    metric: ["metric", "var(--c-test,#0f7a55)", "Metric"], file: ["file", "var(--i600,#4a5062)", "File"], chosen: ["chosen", "var(--okt,#047857)", "Chosen chip"],
    error: ["error", "var(--missed,#c2362b)", "Error"], user: ["user", "var(--blue7,#2b55d0)", "You"]
  };

  /* ---------------- the store: one per run, fed by events ---------------- */
  var RUNS = {};
  function store(id) {
    id = id || "";
    if (!RUNS[id]) RUNS[id] = {
      id: id, v: 0, ev: {}, raw: {}, rawOrder: [], eToRaw: {}, sums: {}, sumOrder: 0, stages: {}, stageSeq: {}, cur: null,
      subs: {}, merges: {}, mergeN: {}, t0: null, prompt: "", status: null, finished: false, fetched: false, limit: null,
      ui: { over: {}, level: null, stage: "", agent: "", more: false, opened: {} }
    };
    return RUNS[id];
  }
  function newer(old, s) {
    if (!old) return true;
    var a = typeof old.seq === "number", b = typeof s.seq === "number";
    if (a && b) return s.seq >= old.seq;
    if (a) return !!s.final && !old.final; // a file line (no seq) never undoes the stream's own
    return !!s.final || !old.final;
  }
  function feed(ev, runId) {
    if (!ev || typeof ev !== "object" || !ev.type) return;
    var S = store(runId != null ? runId : ev.run_id);
    var seq = typeof ev.seq === "number" ? ev.seq : null;
    if (ev.type === "summary") {
      if (typeof ev.id !== "string" || !ev.level) return;
      if (!newer(S.sums[ev.id], ev)) return;
      var o = S.sums[ev.id];
      S.sums[ev.id] = { s: ev, at: o ? o.at : ++S.sumOrder };
      S.v++; dirty(S); return;
    }
    if (ev.type === "summary.limit") { S.limit = ev; S.v++; dirty(S); return; }
    if (seq != null) { if (S.ev[seq]) return; S.ev[seq] = ev; }
    var agent = typeof ev.agent === "string" && ev.agent ? ev.agent : null;
    switch (ev.type) {
      case "run.started": S.t0 = tsMs(ev.ts); S.prompt = ev.prompt || ""; S.status = "running"; break;
      case "stage": {
        var n = ev.stage || ev.name; if (!n) break;
        var st = S.stages[n] || (S.stages[n] = { state: null, reason: "", seq: seq });
        st.state = ev.state; st.reason = ev.reason || st.reason || "";
        if (st.seq == null) st.seq = seq;
        if (ev.state === "started") S.cur = n;
        break;
      }
      case "subagent.started": {
        var k = ev.agent || ev.id; if (!k) break;
        var stg = ev.stage || S.cur || "";
        S.subs[k] = { id: k, name: ev.name || "", strategy: ev.strategy || ev.brief || "", stage: stg, seq: seq, state: "running", batch: "batch:" + stg + ":" + ((S.mergeN[stg] || 0) + 1), model: ev.model || "", result: "" };
        break;
      }
      case "subagent.finished": {
        var sb = S.subs[ev.agent || ev.id];
        if (sb) { sb.state = ev.state || ev.status || "done"; sb.result = ev.result || ev.summary || ""; sb.endSeq = seq; sb.seconds = ev.seconds; }
        break;
      }
      case "stage.merged": {
        var ms = ev.stage || S.cur || "";
        S.mergeN[ms] = (S.mergeN[ms] || 0) + 1;
        S.merges["batch:" + ms + ":" + S.mergeN[ms]] = ev;
        break;
      }
      case "run.finished": S.finished = true; S.status = ev.status || "finished"; break;
      case "message": case "metric": case "artifact": case "chosen": case "error": {
        if (seq == null) break;
        var kind = ev.type === "message" ? (ev.role === "user" ? "user" : "msg") : ev.type === "artifact" ? "file" : ev.type;
        addRaw(S, "e" + seq, kind, ev, agent, seq);
        break;
      }
      case "tool": {
        if (seq == null) break;
        var key = "c:" + (ev.call_id || seq), r = S.raw[key];
        if (!r) r = addRaw(S, key, "tool", ev, agent, seq);
        else { r.seqs.push(seq); r.last = seq; S.eToRaw[seq] = key; }
        if (ev.name) r.name = ev.name; if (ev.summary) r.call = ev.summary; if (ev.detail) r.detail = ev.detail;
        r.state = ev.state || r.state;
        if (/\bchiplab\s+[a-z]/.test(r.call || "")) r.kind = "lab";
        break;
      }
      default: return;
    }
    S.v++; dirty(S);
    if (ev.type === "run.finished") fetchSummaries(S);
  }
  function addRaw(S, key, kind, ev, agent, seq) {
    var sub = agent && S.subs[agent];
    var r = { key: key, kind: kind, seqs: [seq], first: seq, last: seq, agent: agent, stage: sub ? sub.stage : S.cur, name: ev.name || "", call: ev.summary || "", detail: ev.detail || "", state: ev.state || "" };
    S.raw[key] = r; S.rawOrder.push(key); S.eToRaw[seq] = key;
    return r;
  }
  // A run summarised after it ran (chipin-backend summarise) has its levels only in summaries.jsonl.
  function fetchSummaries(S) {
    var L = window.ChipInLive;
    if (S.fetched || !L || !L.base || !L.token || !S.id) return;
    S.fetched = true;
    fetch(L.base + "/api/runs/" + encodeURIComponent(S.id) + "/summaries", { headers: { "X-ChipIn-Token": L.token }, cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : { summaries: [] }; })
      .then(function (j) { (j.summaries || []).forEach(function (s) { if (s && s.type === "summary") feed(s, S.id); }); })
      .catch(function () { S.fetched = false; });
  }

  /* ---------------- deriving the tree ---------------- */
  function rawText(r) { return (r.kind === "lab" ? labName(r) : r.name || "Tool") + ": " + firstLine(r.call); }
  function labName(r) { var m = /\bchiplab\s+([a-z][a-z0-9-]*)/.exec(r.call || ""); return m ? "chiplab " + m[1] : r.name || "chiplab"; }
  function labNumber(r) {
    if (r.kind !== "lab" || !r.detail) return "";
    for (var i = 0; i < LAB_KEYS.length; i++) {
      var m = new RegExp('"' + LAB_KEYS[i][0] + '"\\s*:\\s*(-?\\d+(?:\\.\\d+)?)').exec(r.detail);
      if (m) { var v = +m[1], u = LAB_KEYS[i][1]; return u === "level" ? "level " + m[1] : u === "depth" ? "depth " + m[1] : (Math.abs(v) >= 1000 ? Math.round(v).toLocaleString("en-GB") : m[1]) + " " + u; }
    }
    return "";
  }
  function itemFirst(S, r) {
    var e = S.ev[r.first] || {};
    switch (r.kind) {
      case "msg": case "user": return firstLine(e.text);
      case "tool": case "lab": return rawText(r);
      case "metric": return String(e.key || "metric").replace(/_/g, " ") + " " + e.value + (e.unit ? " " + e.unit : "") + (e.chip ? " (chip " + e.chip + ")" : "");
      case "file": return "Wrote " + (e.path || e.name || "a file");
      case "chosen": return "Chose chip " + (e.chip || "");
      case "error": return firstLine(e.message || e.text || "Error");
      default: return "";
    }
  }
  function derive(S) {
    var N = {}, kids = {}, i, k;
    var node = function (id, level, extra) { var n = N[id]; if (!n) { n = N[id] = { id: id, level: level, k: Infinity, items: 0 }; } if (extra) for (var x in extra) n[x] = extra[x]; return n; };
    var link = function (child, parent) { child.parent = parent; (kids[parent] || (kids[parent] = [])).push(child.id); };
    var sum = function (id) { return S.sums[id] ? S.sums[id].s : null; };
    var stageId = function (n) { return n ? "stage:" + n : "run"; };
    node("run", "run", { sum: sum("run") });
    // stages known from their own events
    STAGES.concat(Object.keys(S.stages)).forEach(function (n) { if (S.stages[n] && !N["stage:" + n]) node("stage:" + n, "stage", { name: n, k: S.stages[n].seq == null ? Infinity : S.stages[n].seq }); });
    // subagents and their batches, from the fan-out events
    Object.keys(S.subs).forEach(function (a) { var sb = S.subs[a]; node("agent:" + a, "agent", { agent: a, sub: sb, k: sb.seq, stage: sb.stage }); });
    // summaries
    var groupsOf = {};
    Object.keys(S.sums).forEach(function (id) {
      var s = S.sums[id].s;
      if (s.level === "run") return;
      if (s.level === "item") return;
      var n = node(id, s.level, { sum: s, stage: s.stage || (N[id] && N[id].stage), agent: s.agent || (N[id] && N[id].agent) });
      if (s.level === "stage" && !n.name) n.name = s.stage || id.replace(/^stage:/, "");
      if (s.level === "agent" && !n.agent) n.agent = id.replace(/^agent:/, "");
      if (s.level === "group") groupsOf[id] = n;
    });
    // items: summarised ones by their covers, the rest from the raw events
    var covered = {}, itemNodes = [];
    Object.keys(S.sums).forEach(function (id) {
      var s = S.sums[id].s; if (s.level !== "item") return;
      var raws = [], seqs = [];
      (s.covers || []).forEach(function (c) { var q = eSeq(c); if (q == null) return; seqs.push(q); var rk = S.eToRaw[q]; if (rk && raws.indexOf(rk) < 0) raws.push(rk); });
      raws.forEach(function (rk) { covered[rk] = id; });
      var r = raws.length ? S.raw[raws[0]] : null;
      var n = node(id, "item", { sum: s, raw: r, raws: raws, seqs: seqs, agent: s.agent || (r && r.agent) || null, stage: s.stage || (r && r.stage) || null, k: seqs.length ? Math.min.apply(null, seqs) : Infinity, last: seqs.length ? Math.max.apply(null, seqs) : null });
      itemNodes.push(n);
    });
    S.rawOrder.forEach(function (rk) {
      if (covered[rk]) return;
      var r = S.raw[rk];
      itemNodes.push(node(rk, "item", { sum: null, raw: r, raws: [rk], seqs: r.seqs.slice(), agent: r.agent, stage: r.stage, k: r.first, last: r.last }));
    });
    var ownerOf = function (agent, stage) { return agent ? "agent:" + agent : stageId(stage); };
    var ensure = function (id) {
      if (N[id]) return N[id];
      if (id === "run") return N.run;
      if (/^stage:/.test(id)) return node(id, "stage", { name: id.slice(6) });
      if (/^batch:/.test(id)) return node(id, "batch", { stage: id.split(":")[1] });
      if (/^agent:/.test(id)) return node(id, "agent", { agent: id.slice(6) });
      return null;
    };
    itemNodes.forEach(function (n) {
      var p = n.sum && n.sum.parent && groupsOf[n.sum.parent] ? n.sum.parent : ownerOf(n.agent, n.stage);
      if (!ensure(p)) p = "run";
      link(n, p);
    });
    Object.keys(groupsOf).forEach(function (id) { var n = groupsOf[id], p = n.sum.parent || ownerOf(n.agent, n.stage); if (!ensure(p)) p = "run"; link(n, p); });
    Object.keys(N).forEach(function (id) {
      var n = N[id];
      if (n.level === "agent") { var p = (n.sum && n.sum.parent) || (n.sub && n.sub.batch) || stageId(n.stage); if (!ensure(p)) p = stageId(n.stage); link(n, p); }
    });
    Object.keys(N).forEach(function (id) {
      var n = N[id];
      if (n.level === "batch") { var p = (n.sum && n.sum.parent) || stageId(n.stage); if (!ensure(p)) p = "run"; link(n, p); }
    });
    Object.keys(N).forEach(function (id) { var n = N[id]; if (n.level === "stage") link(n, "run"); });
    // order keys and step counts, bottom up
    var visit = function (id) {
      var n = N[id], list = kids[id] || [];
      var lastSeq = n.last || null;
      list.forEach(function (c) { visit(c); var cn = N[c]; if (cn.k < n.k && !(n.level === "stage" && S.stages[n.name] && S.stages[n.name].seq != null)) n.k = cn.k; n.items += cn.level === "item" ? 1 : cn.items; if (cn.lastSeq != null && (lastSeq == null || cn.lastSeq > lastSeq)) lastSeq = cn.lastSeq; });
      if (n.level === "stage" && n.k === Infinity) n.k = list.reduce(function (m, c) { return Math.min(m, N[c].k); }, Infinity);
      n.lastSeq = lastSeq;
      list.sort(function (a, b) { var x = N[a], y = N[b]; return (x.k - y.k) || (x.k === Infinity ? STAGES.indexOf(x.name) - STAGES.indexOf(y.name) : 0); });
      n.kids = list;
    };
    visit("run");
    // the newest step of each subtree, for rows whose own summary has not come yet
    var newest = function (id) {
      var n = N[id], best = null;
      (n.kids || []).forEach(function (c) { var cn = N[c], cand = cn.level === "item" || (cn.level === "group" && cn.sum) ? cn : newest(c); if (cand && (!best || (cand.lastSeq || cand.k) >= (best.lastSeq || best.k))) best = cand; });
      return best;
    };
    var counts = { stage: 0, batch: 0, agent: 0, group: 0, item: 0 };
    Object.keys(N).forEach(function (id) { var l = N[id].level; if (counts[l] != null) counts[l]++; });
    return { N: N, counts: counts, newest: newest };
  }

  /* ---------------- the view ---------------- */
  var MV = null; // { el, root, scroll, list, opts, S, T, follow, sig }
  var timer = 0;
  function dirty(S) { if (MV && MV.S === S && !timer) timer = setTimeout(function () { timer = 0; paint(); }, 90); }

  function mount(container, opts) {
    if (!container) return null;
    opts = opts || {};
    var S = store(opts.runId);
    if (MV && MV.el !== container && MV.root && MV.root.parentNode) MV.root.parentNode.removeChild(MV.root);
    var page = opts.mode === "page";
    container.innerHTML = "";
    container.classList.add("cm-host", page ? "cm-host-page" : "cm-host-panel");
    var root = document.createElement("section");
    root.className = "cm" + (page ? " cm-page" : " cm-panel");
    root.setAttribute("aria-label", opts.title || "Messages");
    root.innerHTML =
      '<div class="cm-top"><div class="cm-head"><h2>' + esc(opts.title || "Messages") + '</h2><span class="cm-live" hidden></span><span class="cm-grow"></span>' +
      '<span class="cm-filt"><label class="cm-f"><span class="cm-vh">Stage</span><select class="cm-fs" aria-label="Show one stage"></select></label>' +
      '<label class="cm-f"><span class="cm-vh">Agent</span><select class="cm-fa" aria-label="Show one agent"></select></label></span></div>' +
      '<div class="cm-ladder" role="group" aria-label="Open every row down to a level"></div>' +
      '<div class="cm-sum" aria-live="polite"></div></div>' +
      '<div class="cm-scroll"><div class="cm-list" role="tree" aria-label="Run messages, by level"></div><p class="cm-empty" hidden></p></div>' +
      '<button type="button" class="cm-jump" hidden>' + ico("down") + "Back to latest</button>";
    container.appendChild(root);
    var scroll = page ? container : root.querySelector(".cm-scroll");
    scroll.classList.add("cm-scroller");
    MV = { el: container, root: root, scroll: scroll, list: root.querySelector(".cm-list"), opts: opts, S: S, follow: true, sig: {}, prog: false, page: page, at: Date.now(), wasDone: S.finished };
    wire(MV);
    paint();
    if (!S.finished && S.rawOrder.length) toBottom();
    if (S.finished) fetchSummaries(S);
    return { runId: S.id };
  }
  function reset() {
    RUNS = {};
    if (MV && MV.root) { MV.list.innerHTML = ""; MV.sig = {}; MV.S = store(MV.opts.runId); paint(); }
  }

  function wire(M) {
    var root = M.root;
    M.scroll.addEventListener("scroll", function () {
      if (M.prog) { M.prog = false; return; }
      M.follow = M.scroll.scrollTop + M.scroll.clientHeight >= M.scroll.scrollHeight - 24;
      jumpState();
    }, { passive: true });
    root.querySelector(".cm-jump").addEventListener("click", function () { M.follow = true; toBottom(); jumpState(); });
    root.addEventListener("click", function (e) {
      var t = e.target.closest("[data-act]");
      if (!t || !root.contains(t)) return;
      var a = t.getAttribute("data-act"), ui = M.S.ui;
      if (a === "toggle") { var id = t.closest(".cm-n").getAttribute("data-id"); ui.over[id] = t.getAttribute("aria-expanded") !== "true"; M.keepFocus = id; paint(); }
      else if (a === "level") { var lv = t.getAttribute("data-level"); ui.level = ui.level === lv ? null : lv; ui.over = {}; paint(); }
      else if (a === "more") { ui.more = !ui.more; paint(); }
      else if (a === "raw") { var p = t.parentNode.querySelector(".cm-raw"); var open = t.getAttribute("aria-expanded") === "true"; t.setAttribute("aria-expanded", String(!open)); t.textContent = open ? "Show the raw events" : "Hide the raw events"; if (p) p.hidden = open; }
    });
    root.querySelector(".cm-fs").addEventListener("change", function (e) { M.S.ui.stage = e.target.value; M.S.ui.level = null; M.S.ui.over = {}; paint(); });
    root.querySelector(".cm-fa").addEventListener("change", function (e) { M.S.ui.agent = e.target.value; M.S.ui.level = null; M.S.ui.over = {}; paint(); });
    root.addEventListener("keydown", function (e) {
      var b = e.target.closest && e.target.closest(".cm-row");
      if (!b || !root.contains(b)) return;
      var rows = Array.prototype.slice.call(root.querySelectorAll(".cm-list .cm-row")).filter(function (x) { return x.offsetParent !== null; });
      var i = rows.indexOf(b), go = null;
      if (e.key === "ArrowDown") go = rows[i + 1];
      else if (e.key === "ArrowUp") go = rows[i - 1];
      else if (e.key === "Home") go = rows[0];
      else if (e.key === "End") go = rows[rows.length - 1];
      else if (e.key === "ArrowRight" && b.hasAttribute("aria-expanded")) { if (b.getAttribute("aria-expanded") !== "true") { b.click(); } else go = rows[i + 1]; }
      else if (e.key === "ArrowLeft") {
        if (b.getAttribute("aria-expanded") === "true") b.click();
        else { var up = b.closest(".cm-n").parentNode.closest(".cm-n"); if (up) go = up.querySelector(".cm-row"); }
      } else return;
      e.preventDefault();
      if (go) go.focus();
    });
  }
  function toBottom() { if (!MV) return; MV.prog = true; MV.scroll.scrollTop = MV.scroll.scrollHeight; }
  function jumpState() { if (!MV) return; var j = MV.root.querySelector(".cm-jump"); j.hidden = MV.follow || MV.S.finished || !MV.S.rawOrder.length; }

  function isOpen(S, T, n) {
    var ui = S.ui;
    if (ui.over[n.id] != null) return ui.over[n.id];
    if (n.level === "item") return false;
    if (ui.level) return RANK[n.level] < RANK[ui.level];
    if (ui.agent) { if (n.level === "stage" || n.level === "batch") return has(T, n, ui.agent); return n.level === "agent" && n.agent === ui.agent; }
    if (ui.stage && n.level === "stage") return true;
    if (S.finished) return false;
    // live: the stage at work is open, with its batches; everything else stays one line
    var cur = S.cur && S.stages[S.cur] && S.stages[S.cur].state === "started" ? S.cur : null;
    if (n.level === "stage") return n.name === cur;
    if (n.level === "batch") return n.stage === cur && batchRunning(S, T, n);
    return false;
  }
  function batchRunning(S, T, n) { return (n.kids || []).some(function (c) { var a = T.N[c]; return a.level === "agent" && a.sub && a.sub.state === "running"; }); }
  function has(T, n, agent) {
    if (agent === "-") return n.level === "group" || n.level === "item" ? !n.agent : n.level !== "agent" && n.level !== "batch" && (n.kids || []).some(function (c) { return has(T, T.N[c], agent); });
    if (n.level === "agent") return n.agent === agent;
    if (n.level === "group" || n.level === "item") return n.agent === agent;
    return (n.kids || []).some(function (c) { return has(T, T.N[c], agent); });
  }
  function shown(S, T, n) {
    var ui = S.ui;
    if (ui.stage && n.parent === "run" && !(n.level === "stage" && n.name === ui.stage)) return false;
    if (ui.agent && !has(T, n, ui.agent)) return false;
    return true;
  }

  function paint() {
    if (!MV) return;
    var M = MV, S = M.S, T = derive(S), ui = S.ui;
    M.T = T;
    var anchor = M.follow && !S.finished ? null : takeAnchor(M);
    // header: live mark, filters, ladder
    var live = M.root.querySelector(".cm-live");
    var lv = S.finished ? (S.status === "succeeded" ? "Finished" : S.status ? cap(S.status) : "Finished") : S.rawOrder.length || S.t0 ? "Live" : "";
    if (live.textContent !== lv) { live.textContent = lv; live.hidden = !lv; live.className = "cm-live" + (S.finished ? " cm-done" : ""); }
    var stages = Object.keys(T.N).filter(function (id) { return T.N[id].level === "stage"; }).map(function (id) { return T.N[id]; }).sort(function (a, b) { return STAGES.indexOf(a.name) - STAGES.indexOf(b.name); });
    var fsHTML = '<option value="">All stages</option>' + stages.map(function (n) { return '<option value="' + esc(n.name) + '"' + (ui.stage === n.name ? " selected" : "") + ">" + esc(STAGE_N[n.name] || n.name) + "</option>"; }).join("");
    setHTML(M, "fs", M.root.querySelector(".cm-fs"), fsHTML);
    var agents = Object.keys(T.N).filter(function (id) { return T.N[id].level === "agent"; }).map(function (id) { return T.N[id]; }).sort(function (a, b) { return a.k - b.k; });
    var faHTML = '<option value="">All agents</option><option value="-"' + (ui.agent === "-" ? " selected" : "") + ">ChipIn (lead)</option>" + agents.map(function (n) { return '<option value="' + esc(n.agent) + '"' + (ui.agent === n.agent ? " selected" : "") + ">" + esc(n.agent + (n.sub && n.sub.name ? ", " + n.sub.name : "")) + "</option>"; }).join("");
    setHTML(M, "fa", M.root.querySelector(".cm-fa"), faHTML);
    M.root.querySelector(".cm-fa").closest(".cm-f").hidden = !agents.length;
    var lad = '<span class="cm-lt">Open to</span>' + LADDER.filter(function (l) { return T.counts[l[0]] || l[0] === "stage" || l[0] === "item"; }).map(function (l) {
      return '<button type="button" class="cm-lv' + (ui.level === l[0] ? " on" : "") + '" data-act="level" data-level="' + l[0] + '" aria-pressed="' + (ui.level === l[0]) + '" title="Open every row down to the ' + l[2] + '"><b>' + T.counts[l[0]] + "</b> " + l[1] + "</button>";
    }).join("") + (M.opts.more ? '<a class="cm-all-l" href="' + esc(M.opts.more) + '">Open in full</a>' : "");
    setHTML(M, "lad", M.root.querySelector(".cm-ladder"), lad);
    // the run summary, pinned
    var rs = T.N.run.sum, sumHTML;
    if (rs) sumHTML = '<p class="cm-sl">' + (rs.final ? "Run summary" : "Run summary so far") + srcMark(rs) + '</p><p class="cm-st' + (ui.more ? " cm-all" : "") + '">' + esc(rs.text) + "</p>" + (rs.text.length > 160 ? '<button type="button" class="cm-more" data-act="more" aria-expanded="' + ui.more + '">' + (ui.more ? "Show less" : "Show all") + "</button>" : "");
    else if (S.prompt) sumHTML = '<p class="cm-sl">Run summary</p><p class="cm-st cm-pend" title="The run summary comes after the first stage closes; this is the brief\'s first line">' + pendDot() + esc(firstLine(S.prompt)) + "</p>";
    else sumHTML = "";
    if (S.limit) sumHTML += '<p class="cm-lim">Summaries stopped at a limit (' + esc(S.limit.reason || "limit") + "); later rows show their own first line.</p>";
    setHTML(M, "sum", M.root.querySelector(".cm-sum"), sumHTML);
    M.root.querySelector(".cm-sum").hidden = !sumHTML;
    // the tree
    reconcile(M, M.list, (T.N.run.kids || []).map(function (id) { return T.N[id]; }).filter(function (n) { return shown(S, T, n); }), 0);
    // empty state
    var empty = M.root.querySelector(".cm-empty"), et = "";
    if (!T.N.run.kids || !T.N.run.kids.length) {
      var L = window.ChipInLive;
      et = S.finished ? "This run logged no messages or tool calls." : S.t0 ? "Waiting for the agent's first message." :
        L && (L.status === "connected" || L.token) ? "Waiting for the run's stream." :
        "No run is connected. Start the backend on this computer with chipin-backend serve, open the link it prints, then start a run or open one of its runs: every message and tool call appears here with its summary as it streams.";
    } else if (!M.list.firstChild) et = "Nothing here matches the filter.";
    if (empty.textContent !== et) empty.textContent = et;
    empty.hidden = !et;
    // scroll: follow the newest while live, else keep what the reader looks at in place
    if (S.finished && !M.wasDone) { M.wasDone = true; if (Date.now() - M.at < 4000) { M.prog = true; M.scroll.scrollTop = 0; M.follow = false; anchor = null; } } // a recorded run replayed on opening starts at the top
    if (M.follow && !S.finished) toBottom();
    else if (anchor) keepAnchor(M, anchor);
    if (M.keepFocus) { var f = M.list.querySelector('.cm-n[data-id="' + cssEsc(M.keepFocus) + '"] > .cm-row'); if (f && document.activeElement !== f) f.focus({ preventScroll: true }); M.keepFocus = null; }
    jumpState();
  }
  function setHTML(M, key, el, html) { if (M.sig[key] !== html) { M.sig[key] = html; el.innerHTML = html; } }
  var cap = function (s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; };
  var cssEsc = function (s) { return window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/["\\]/g, "\\$&"); };
  function pendDot() { return '<span class="cm-pd" aria-hidden="true"></span><span class="cm-vh">Summary on its way; first line: </span>'; }
  function srcMark(s) { return s && s.source === "fallback" ? '<span class="cm-src" title="No model answer: the text\'s own first line">first line</span>' : ""; }

  function takeAnchor(M) {
    var r = M.scroll.getBoundingClientRect(), top = r.top;
    if (M.page) { var tp = M.root.querySelector(".cm-top"); top = Math.max(top, tp.getBoundingClientRect().bottom); }
    var el = document.elementFromPoint(r.left + Math.min(60, r.width / 2), top + 3);
    var n = el && el.closest ? el.closest(".cm-n") : null;
    if (!n || !M.list.contains(n)) return null;
    return { id: n.getAttribute("data-id"), y: n.getBoundingClientRect().top };
  }
  function keepAnchor(M, a) {
    var n = M.list.querySelector('.cm-n[data-id="' + cssEsc(a.id) + '"]');
    if (!n) return;
    var d = n.getBoundingClientRect().top - a.y;
    if (Math.abs(d) >= 1) { M.prog = true; M.scroll.scrollTop += d; }
  }

  // keyed update of one container's children: elements are reused by id, only changed rows rewritten
  function reconcile(M, box, nodes, depth) {
    var have = {}, i, c;
    for (c = box.firstElementChild; c; c = c.nextElementSibling) if (c.dataset && c.dataset.id) have[c.dataset.id] = c;
    var keep = {};
    nodes.forEach(function (n, idx) {
      var el = have[n.id];
      if (!el) { el = document.createElement("div"); el.className = "cm-n"; el.dataset.id = n.id; }
      keep[n.id] = 1;
      drawNode(M, el, n, depth);
      var at = box.children[idx];
      if (at !== el) box.insertBefore(el, at || null);
    });
    for (i = box.children.length - 1; i >= 0; i--) { c = box.children[i]; if (!keep[c.dataset.id]) box.removeChild(c); }
  }

  function drawNode(M, el, n, depth) {
    var S = M.S, T = M.T;
    var expandable = n.level === "item" || (n.kids && n.kids.length) || (n.level === "batch" && S.merges[n.id]);
    var open = expandable && isOpen(S, T, n);
    var head = rowHTML(M, n, open, expandable);
    var row = el.firstElementChild;
    if (!row || !row.classList.contains("cm-row")) {
      row = document.createElement(expandable ? "button" : "div");
      el.insertBefore(row, el.firstChild);
    } else if ((row.tagName === "BUTTON") !== !!expandable) {
      var nr = document.createElement(expandable ? "button" : "div"); el.replaceChild(nr, row); row = nr; row._h = null;
    }
    if (row._h !== head.html) { row.innerHTML = head.html; row._h = head.html; }
    row.className = "cm-row cm-" + n.level + (head.cls ? " " + head.cls : "");
    if (expandable) { row.type = "button"; row.setAttribute("data-act", "toggle"); row.setAttribute("aria-expanded", String(!!open)); if (head.label) row.setAttribute("aria-label", head.label); }
    el.className = "cm-n cm-n-" + n.level + (n.raw && n.raw.kind === "user" ? " cm-n-you" : "");
    el.setAttribute("role", "treeitem");
    if (expandable) el.setAttribute("aria-expanded", String(!!open)); else el.removeAttribute("aria-expanded");
    var box = row.nextElementSibling;
    if (!open) { if (box) el.removeChild(box); return; }
    if (n.level === "item") {
      var key = "b|" + n.seqs.join(",") + "|" + n.raws.map(function (rk) { var r = S.raw[rk]; return r ? r.state + (r.detail || "").length : ""; }).join(",");
      if (!box || box._k !== key) { var nb = document.createElement("div"); nb.className = "cm-body"; nb.setAttribute("role", "group"); nb.innerHTML = bodyHTML(S, n); nb._k = key; if (box) el.replaceChild(nb, box); else el.appendChild(nb); }
      return;
    }
    if (!box) { box = document.createElement("div"); box.className = "cm-kids"; box.setAttribute("role", "group"); el.appendChild(box); }
    var list = [];
    // a group that has not closed yet shows its steps as rows of its owner, in place
    (n.kids || []).forEach(function (id) { var c = T.N[id]; if (shown(S, T, c)) list.push(c); });
    if (n.level === "batch" && S.merges[n.id]) list.push({ id: n.id + ":merge", level: "merge", ev: S.merges[n.id], kids: [] });
    reconcile(M, box, list, depth + 1);
  }

  function rel(S, seq) { var e = S.ev[seq]; var t = e ? tsMs(e.ts) : null; return S.t0 != null && t != null ? clock((t - S.t0) / 1000) : ""; }
  function rowHTML(M, n, open, expandable) {
    var S = M.S, T = M.T, chev = expandable ? ico("chev", "cm-chev") : '<span class="cm-chev-x"></span>';
    var text, pend = false, meta = "", glyph = "", cls = "", sub = "", label = "";
    switch (n.level) {
      case "stage": {
        var st = S.stages[n.name] || {}, state = st.state || (n.sum ? "done" : "");
        var g = state === "done" ? '<span class="cm-sd cm-ok" title="Done"></span>' : state === "started" ? (S.finished ? '<span class="cm-sd cm-halt" title="Ended before it was marked done"></span>' : '<span class="cm-spin" title="Running"></span>') : state === "skipped" ? '<span class="cm-sd cm-skip" title="Skipped"></span>' : state === "failed" ? '<span class="cm-sd cm-bad" title="Failed"></span>' : '<span class="cm-sd"></span>';
        glyph = g;
        if (n.sum) { text = n.sum.text; if (!n.sum.final) cls = "cm-interim"; }
        else if (state === "skipped") text = "Skipped" + (st.reason ? ": " + st.reason : "");
        else { var nw = T.newest(n.id); text = nw ? lineOf(S, nw) : state === "started" ? "Started" : "No activity yet"; pend = !!nw; }
        var na = 0, ng = 0; (n.kids || []).forEach(function (c) { var x = T.N[c]; if (x.level === "batch") na += (x.kids || []).filter(function (k) { return T.N[k].level === "agent"; }).length; if (x.level === "group") ng++; });
        meta = [ng ? plural(ng, "group") : "", na ? plural(na, "subagent") : "", n.items ? plural(n.items, "step") : ""].filter(Boolean).join(", ");
        text = '<b class="cm-nm">' + esc(STAGE_N[n.name] || n.name) + "</b>" + (n.sum && !n.sum.final ? '<span class="cm-tag">so far</span>' : "") + '<span class="cm-tx' + (pend ? " cm-pend" : "") + '">' + (pend ? pendDot() : "") + esc(text) + srcMark(n.sum) + "</span>";
        label = (STAGE_N[n.name] || n.name) + " stage";
        return { html: chev + glyph + '<span class="cm-main">' + text + "</span>" + metaHTML(meta), cls: cls, label: null };
      }
      case "batch": {
        var ags = (n.kids || []).filter(function (c) { return T.N[c].level === "agent"; }), running = ags.filter(function (c) { var a = T.N[c]; return a.sub && a.sub.state === "running"; }).length;
        var k = n.id.split(":")[2] || "1";
        if (n.sum) text = n.sum.text; else { text = plural(ags.length, "subagent") + (running && !S.finished ? ", " + running + " running" : ""); pend = true; }
        glyph = '<span class="cm-gl" style="--k:var(--c-lead,#6b46c1)">' + ico("agent") + "</span>";
        meta = plural(ags.length, "subagent");
        return { html: chev + glyph + '<span class="cm-main"><b class="cm-nm">Batch ' + esc(k) + '</b><span class="cm-tx' + (pend ? " cm-pend" : "") + '">' + (pend ? pendDot() : "") + esc(text) + srcMark(n.sum) + "</span></span>" + metaHTML(meta), cls: "" };
      }
      case "agent": {
        var sb = n.sub || {}, state2 = sb.state || (n.sum ? "done" : "running");
        var g2 = state2 === "running" ? (S.finished ? '<span class="cm-sd cm-halt" title="Ended without a finish event"></span>' : '<span class="cm-spin" title="Running"></span>') : /fail|error/.test(state2) ? '<span class="cm-sd cm-bad" title="Failed"></span>' : '<span class="cm-sd cm-ok" title="Done"></span>';
        if (n.sum) text = n.sum.text;
        else { var nw2 = T.newest(n.id); text = nw2 ? lineOf(S, nw2) : firstLine(sb.strategy) || "Starting"; pend = true; }
        var strat = firstLine(String(sb.strategy || "").replace(/^Strategy:\s*/i, ""));
        meta = (state2 === "running" && !S.finished ? "running" : state2 === "running" ? "ended" : state2) + (n.items ? ", " + plural(n.items, "step") : "");
        return {
          html: chev + g2 + '<span class="cm-main"><span class="cm-l1"><b class="cm-nm">' + esc(sb.name || n.agent) + '</b><span class="cm-id">' + esc(n.agent) + '</span><span class="cm-tx' + (pend ? " cm-pend" : "") + '">' + (pend ? pendDot() : "") + esc(text) + srcMark(n.sum) + "</span></span>" +
            (strat ? '<span class="cm-l2">' + esc(strat) + "</span>" : "") + "</span>" + metaHTML(meta), cls: strat ? "cm-two" : ""
        };
      }
      case "group": {
        text = n.sum.text;
        meta = plural(n.items, "step");
        return { html: chev + '<span class="cm-gd"></span><span class="cm-main"><span class="cm-tx">' + esc(text) + srcMark(n.sum) + "</span></span>" + metaHTML(meta, n.lastSeq != null ? rel(S, n.lastSeq) : ""), cls: "" };
      }
      case "merge": {
        var ev = n.ev, kept = Array.isArray(ev.kept) ? ev.kept : [];
        return { html: '<span class="cm-chev-x"></span><span class="cm-sd cm-mg"></span><span class="cm-main"><b class="cm-nm">Merged</b><span class="cm-tx">kept ' + esc(kept.join(", ") || "none") + (ev.why || ev.reason ? ": " + esc(ev.why || ev.reason) : "") + "</span></span>" + metaHTML("", rel(S, ev.seq)), cls: "" };
      }
      case "item": {
        var r = n.raw, kind = r ? r.kind : "msg", K = KIND[kind] || KIND.msg;
        if (n.sum) text = n.sum.text; else { text = r ? itemFirst(S, r) : ""; pend = true; }
        var nm = r && (kind === "tool" || kind === "lab") ? (kind === "lab" ? labName(r) : r.name || "Tool") : "";
        var stt = r && (kind === "tool" || kind === "lab") ? (r.state === "done" ? "" : r.state === "failed" ? '<span class="cm-fail">failed</span>' : S.finished ? '<span class="cm-fail cm-mute">no result</span>' : '<span class="cm-spin cm-sm" title="Running"></span>') : "";
        var num = r ? labNumber(r) : "";
        if (kind === "user") return { html: chev + '<span class="cm-you"><span class="cm-yw">You</span><span class="cm-tx">' + esc(r ? itemFirst(S, r) : text) + "</span></span>", cls: "cm-user", label: "Your message" };
        glyph = '<span class="cm-gl" style="--k:' + K[1] + '" title="' + K[2] + '">' + ico(K[0]) + "</span>";
        var lead = nm && text.indexOf(nm) !== 0 ? '<b class="cm-tn">' + esc(nm) + "</b>" : "";
        return { html: chev + glyph + '<span class="cm-main">' + lead + stt + '<span class="cm-tx' + (pend ? " cm-pend" : "") + '">' + (pend ? pendDot() : "") + esc(text) + srcMark(n.sum) + "</span></span>" + metaHTML(num, rel(S, n.last != null ? n.last : n.k)), cls: "cm-k-" + kind + (r && r.state === "failed" ? " cm-failed" : "") };
      }
      default: return { html: esc(n.id), cls: "" };
    }
  }
  function lineOf(S, n) { return n.sum ? n.sum.text : n.raw ? itemFirst(S, n.raw) : ""; }
  function metaHTML(a, t) { return '<span class="cm-meta">' + (a ? "<span>" + esc(a) + "</span>" : "") + (t ? '<span class="cm-t">' + esc(t) + "</span>" : "") + "</span>"; }

  function pre(t, cls) { return '<pre class="cm-pre' + (cls ? " " + cls : "") + '">' + esc(t) + "</pre>"; }
  function bodyHTML(S, n) {
    var out = [], evs = n.seqs.slice().sort(function (a, b) { return a - b; }).map(function (q) { return S.ev[q]; }).filter(Boolean);
    if (n.sum) out.push('<p class="cm-bs"><span>Summary</span>' + esc(n.sum.text) + (n.sum.source === "verbatim" ? ' <em>(its own words)</em>' : n.sum.source === "fallback" ? " <em>(first line, no model answer)</em>" : "") + "</p>");
    var tool = null;
    evs.forEach(function (e) { if (e.type === "tool") tool = tool || {}; });
    if (tool) {
      var r = n.raw || {};
      var call = null, done = null;
      evs.forEach(function (e) { if (e.type !== "tool") return; if (e.state === "started") call = e; else done = e; });
      var c = call || done || {};
      out.push('<div class="cm-sec"><h4>Call' + (c.seq ? '<span>event ' + c.seq + "</span>" : "") + "</h4>" + pre((c.name || r.name || "Tool") + "\n" + (c.summary || r.call || "")) + "</div>");
      if (done) out.push('<div class="cm-sec"><h4>' + (done.state === "failed" ? "Output, failed" : "Output") + '<span>event ' + done.seq + "</span></h4>" + (done.detail ? pre(done.detail) : '<p class="cm-mute">No output was recorded.</p>') + "</div>");
      else out.push('<p class="cm-mute">' + (S.finished ? "No result was recorded for this call." : "Still running.") + "</p>");
    }
    evs.forEach(function (e) {
      if (e.type === "tool") return;
      var h = e.type === "message" ? (e.role === "user" ? "Your message" : (e.author || "Agent") + (e.agent ? ", " + e.agent : "")) : e.type === "metric" ? "Metric" : e.type === "artifact" ? "File" : e.type === "chosen" ? "Chosen chip" : e.type === "error" ? "Error" : e.type;
      var t = e.type === "message" ? e.text : e.type === "metric" ? e.key + " = " + e.value + (e.unit ? " " + e.unit : "") + (e.chip ? "\nchip " + e.chip : "") : e.type === "artifact" ? (e.name || "") + "\n" + (e.path || "") + (e.kind ? "\n" + e.kind : "") : e.type === "chosen" ? "chip " + e.chip : e.type === "error" ? e.message || e.text || "" : JSON.stringify(e);
      out.push('<div class="cm-sec"><h4>' + esc(h) + '<span>event ' + e.seq + "</span></h4>" + pre(t || "") + "</div>");
    });
    if (!evs.length) out.push('<p class="cm-mute">The events this line covers have not reached this page.</p>');
    else out.push('<button type="button" class="cm-rawb" data-act="raw" aria-expanded="false">Show the raw events</button><div class="cm-raw" hidden>' + pre(evs.map(function (e) { return JSON.stringify(e, null, 2); }).join("\n\n"), "cm-json") + "</div>");
    return out.join("");
  }

  function state(runId) {
    var S = runId != null ? RUNS[runId] : MV && MV.S;
    if (!S) return null;
    var T = derive(S), sums = {};
    Object.keys(S.sums).forEach(function (id) { var l = S.sums[id].s.level; sums[l] = (sums[l] || 0) + 1; });
    return { runId: S.id, counts: T.counts, summaries: sums, events: Object.keys(S.ev).length, finished: S.finished, level: S.ui.level, follow: MV ? MV.follow : null };
  }

  /* ---------------- styles: the page's tokens ---------------- */
  var css = document.createElement("style");
  css.textContent = [
    ".cm-host-panel{display:flex;flex-direction:column;padding:0!important;min-height:0}",
    ".cm{position:relative;display:flex;flex-direction:column;min-height:0;font-size:12.5px;color:var(--i700,#3a4052)}",
    "@media (min-width:1101px){.lv-ov .side .lv-log:has(.cm-host-panel){flex:2.6 1 0}}",
    ".cm-panel .cm-live{display:none}.cm-panel .cm-head{padding:0 12px 5px}.cm-panel .cm-ladder{padding:0 12px 6px;gap:1px 8px}.cm-panel .cm-sum{display:flex;align-items:baseline;gap:6px;padding:6px 12px 7px}.cm-panel .cm-sl{flex:none;margin:0}.cm-panel .cm-st{flex:1;min-width:0;line-height:1.4;-webkit-line-clamp:1!important}.cm-panel .cm-st.cm-all{-webkit-line-clamp:unset!important}.cm-panel .cm-more{flex:none;padding:0}.cm-panel .cm-sum:has(.cm-all){flex-wrap:wrap}.cm-panel .cm-lt{display:none}",
    ".cm-all-l{margin-left:auto;font-size:11.5px;color:var(--blue7,#2b55d0);text-decoration:none;white-space:nowrap}.cm-all-l:hover{text-decoration:underline}",
    ".cm-panel{flex:1;padding-top:10px}.cm-panel .cm-scroll{flex:1;overflow:auto;min-height:0;padding:4px 10px 14px 10px;overscroll-behavior:contain}",
    "@media (max-width:1100px){.cm-panel .cm-scroll{max-height:440px}}",
    ".cm-host-page{padding-top:0!important}.cm-page{max-width:780px;margin:0 auto;padding:0 2px 24px}.cm-page .cm-top{position:sticky;top:0;z-index:3;background:var(--page,#f5f6f8);padding-top:18px}",
    ".cm-scroller{overflow-anchor:none}",
    ".cm-head{display:flex;align-items:center;gap:8px;padding:0 14px 6px}.cm-page .cm-head{padding:0 2px 6px}",
    ".cm-head h2{font-size:13px;font-weight:650;margin:0;color:var(--i900,#141a2e);white-space:nowrap}.cm-grow{flex:1}",
    ".cm-live{font-size:11px;font-weight:600;color:var(--blue7,#2b55d0);background:#eef3fe;border-radius:99px;padding:1px 8px}.cm-live.cm-done{color:var(--i600);background:var(--i100,#f1f2f6)}",
    ".cm-panel .cm-f select{max-width:96px}.cm-f select{font:inherit;font-size:11.5px;color:var(--i800);height:24px;max-width:150px;border:1px solid rgb(0 0 0/.1);border-radius:6px;background:#fff;padding:0 4px}",
    ".cm-f[hidden]{display:none}.cm-filt{display:flex;gap:6px}",
    "@container (max-width:300px){.cm-head{flex-wrap:wrap;row-gap:6px}.cm-filt{flex-basis:100%}.cm-filt .cm-f{flex:1;min-width:0}.cm-filt .cm-f select,.cm-panel .cm-f select{width:100%;max-width:none}}",
    ".cm-ladder{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px;padding:2px 14px 8px;border-bottom:1px solid var(--hair,rgb(0 0 0/.07))}.cm-page .cm-ladder{padding:2px 2px 8px}",
    ".cm-lt{font-size:11px;color:var(--i550,#555b6d)}",
    ".cm-lv{font:inherit;font-size:11.5px;color:var(--i600);background:none;border:0;padding:1px 0;border-bottom:1.5px solid transparent;cursor:pointer}",
    ".cm-lv b{font-weight:650;color:var(--i900);font-variant-numeric:tabular-nums}.cm-lv:hover{color:var(--i900)}.cm-lv.on{border-bottom-color:var(--blue7,#2b55d0);color:var(--i900)}",
    ".cm-sum{padding:9px 14px 10px;border-bottom:1px solid var(--hair,rgb(0 0 0/.07))}.cm-page .cm-sum{padding:10px 2px 12px}.cm-sum[hidden]{display:none}",
    ".cm-sl{margin:0 0 3px;font-size:11px;font-weight:600;color:var(--i550)}",
    ".cm-st{margin:0;font-family:var(--serif,Georgia,serif);font-size:14.5px;line-height:1.5;color:var(--i900);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}.cm-st.cm-all{display:block}.cm-panel .cm-st{font-size:13.5px;-webkit-line-clamp:2}",
    ".cm-more{font:inherit;font-size:11.5px;color:var(--blue7);background:none;border:0;padding:2px 0 0;cursor:pointer}",
    ".cm-lim{margin:6px 0 0;font-size:11.5px;color:var(--amb,#b45309)}",
    ".cm-list{padding-top:4px}",
    ".cm-n{min-width:0}",
    ".cm-row{display:grid;grid-template-columns:14px 16px minmax(0,1fr) auto;gap:7px;align-items:start;width:100%;min-height:26px;padding:4px 4px;border:0;border-radius:6px;background:none;font:inherit;font-size:12.5px;line-height:1.4;color:var(--i700);text-align:left}",
    "button.cm-row{cursor:pointer}button.cm-row:hover{background:var(--i100,#f1f2f6)}",
    ".cm-row:focus-visible,.cm-lv:focus-visible,.cm-more:focus-visible,.cm-rawb:focus-visible,.cm-jump:focus-visible{outline:2px solid var(--blue7,#2b55d0);outline-offset:1px}",
    ".cm-chev{margin-top:3px;width:12px;height:12px;fill:none;stroke:var(--i550);stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;transition:transform .14s var(--ease,ease)}",
    ".cm-row[aria-expanded=true] .cm-chev{transform:rotate(90deg)}.cm-chev-x{width:12px}",
    "@media (prefers-reduced-motion:reduce){.cm-chev{transition:none}.cm-spin{animation-duration:3s!important}}",
    ".cm-main{display:flex;align-items:baseline;gap:7px;min-width:0;overflow:hidden}",
    ".cm-tx{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--i700)}",
    ".cm-row[aria-expanded=true]>.cm-main .cm-tx{white-space:normal;overflow-wrap:anywhere}",
    ".cm-nm{font-weight:650;color:var(--i900);white-space:nowrap;flex:none}.cm-id{font-size:11px;color:var(--i550);flex:none}.cm-tn{font-weight:600;color:var(--i800);white-space:nowrap;flex:none}",
    ".cm-tag{font-size:10.5px;color:var(--i550);flex:none}",
    ".cm-meta{display:flex;align-items:baseline;gap:8px;font-size:11px;color:var(--i550);white-space:nowrap;font-variant-numeric:tabular-nums}.cm-t{min-width:30px;text-align:right}",
    ".cm-stage{padding-top:7px;padding-bottom:7px}.cm-stage .cm-nm{min-width:68px}",
    ".cm-n-stage{border-top:1px solid var(--hair,rgb(0 0 0/.07))}.cm-n-stage:first-child{border-top:0}.cm-n-group+.cm-n-stage,.cm-n-item+.cm-n-stage{margin-top:2px}",
    ".cm-kids{margin:0 0 4px 10px;padding-left:9px;border-left:1px solid var(--i150,#e7e9ee)}",
    ".cm-two .cm-main{flex-direction:column;align-items:stretch;gap:0}",
    ".cm-l1{display:flex;align-items:baseline;gap:7px;min-width:0}.cm-l2{font-size:11.5px;color:var(--i550);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}",
    ".cm-sd{margin-top:5px;width:8px;height:8px;border-radius:50%;justify-self:center;background:#fff;box-shadow:inset 0 0 0 1.5px var(--i300,#b2b6c2)}",
    ".cm-sd.cm-ok{background:var(--okt,#047857);box-shadow:none}.cm-sd.cm-skip{background:var(--i150);box-shadow:inset 0 0 0 1.5px var(--i300)}.cm-sd.cm-bad{background:var(--missed,#c2362b);box-shadow:none}",
    ".cm-sd.cm-halt{background:var(--i300);box-shadow:none}.cm-sd.cm-mg{width:7px;height:7px;border-radius:2px;background:var(--c-lead,#6b46c1);box-shadow:none}",
    ".cm-gd{margin-top:6px;width:5px;height:5px;border-radius:50%;justify-self:center;background:var(--i300)}",
    ".cm-spin{margin-top:4px;width:10px;height:10px;justify-self:center;border-radius:50%;border:1.6px solid rgb(43 85 208/.25);border-top-color:var(--blue7,#2b55d0);animation:cmspin .9s linear infinite;flex:none}.cm-main .cm-spin{margin-top:0;align-self:center;width:9px;height:9px}",
    "@keyframes cmspin{to{transform:rotate(360deg)}}",
    ".cm-gl{margin-top:1px;display:grid;place-items:center;width:16px;height:16px;border-radius:50%;background:color-mix(in srgb,var(--k) 12%,transparent);color:var(--k)}",
    ".cm-i{width:10px;height:10px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}",
    ".cm-pend{color:var(--i550)}.cm-pd{display:inline-block;width:6px;height:6px;margin-right:6px;border-radius:50%;box-shadow:inset 0 0 0 1.3px var(--i300);vertical-align:1px}",
    ".cm-interim .cm-tx{color:var(--i600)}",
    ".cm-src{margin-left:6px;font-size:10.5px;color:var(--i550)}",
    ".cm-fail{font-size:11px;font-weight:600;color:var(--missed,#c2362b);flex:none}.cm-fail.cm-mute{color:var(--i550);font-weight:500}",
    ".cm-failed .cm-tx{color:var(--i800)}",
    ".cm-n-you>.cm-row{display:flex;justify-content:flex-end;gap:6px}.cm-n-you>.cm-row .cm-chev{order:2;margin-top:2px}",
    ".cm-you{display:flex;flex-direction:column;align-items:flex-end;max-width:min(78%,560px);min-width:0;padding:6px 11px;border-radius:12px 12px 4px 12px;background:#e8eefc;color:var(--i900)}",
    ".cm-yw{font-size:10.5px;font-weight:650;color:var(--blue7)}.cm-you .cm-tx{color:var(--i900);max-width:100%}",
    ".cm-body{margin:2px 0 8px 30px;padding:2px 0 2px 12px;border-left:2px solid var(--i150,#e7e9ee);font-size:12px;color:var(--i700)}",
    ".cm-bs{margin:2px 0 8px;line-height:1.5;overflow-wrap:anywhere}.cm-bs span{display:block;font-size:11px;font-weight:600;color:var(--i550)}.cm-bs em{font-style:normal;color:var(--i550)}",
    ".cm-sec{margin:0 0 8px}.cm-sec h4{display:flex;align-items:baseline;gap:8px;margin:0 0 3px;font-size:11px;font-weight:600;color:var(--i600)}.cm-sec h4 span{font-weight:500;color:var(--i550);font-variant-numeric:tabular-nums}",
    ".cm-pre{margin:0;font-family:var(--mono,ui-monospace,monospace);font-size:11.5px;line-height:1.5;background:var(--i100,#f1f2f6);border-radius:6px;padding:7px 9px;max-height:320px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;color:var(--i900)}",
    ".cm-json{font-size:10.5px;max-height:260px}",
    ".cm-rawb{font:inherit;font-size:11.5px;color:var(--blue7);background:none;border:0;padding:0;margin:0 0 4px;cursor:pointer}",
    ".cm-mute{color:var(--i550);margin:0 0 6px}",
    ".cm-empty{margin:14px 6px;font-size:12.5px;line-height:1.55;color:var(--i600);max-width:56ch}.cm-empty[hidden]{display:none}",
    ".cm-jump{position:absolute;right:14px;bottom:12px;display:inline-flex;align-items:center;gap:5px;height:26px;padding:0 11px;border:1px solid rgb(0 0 0/.1);border-radius:99px;background:#fff;color:var(--i800);font:inherit;font-size:11.5px;font-weight:600;box-shadow:0 2px 10px rgb(0 0 0/.08);cursor:pointer}",
    ".cm-page .cm-jump{position:sticky;right:auto;bottom:12px;align-self:flex-end;margin-top:-26px}",
    ".cm-jump[hidden]{display:none}.cm-jump .cm-i{width:11px;height:11px}",
    ".cm-vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}",
    ".cm{container-type:inline-size}",
    "@container (max-width:600px){.cm-row[aria-expanded=true] .cm-main,.cm-row[aria-expanded=true] .cm-l1{flex-wrap:wrap;row-gap:1px}.cm-row[aria-expanded=true] .cm-main>.cm-tx,.cm-row[aria-expanded=true] .cm-l1>.cm-tx{flex-basis:100%}.cm-stage .cm-meta{display:none}.cm-stage .cm-nm{min-width:0}}",
    "@container (max-width:400px){.cm-row{grid-template-columns:12px 14px minmax(0,1fr) auto;gap:6px}.cm-t{display:none}.cm-kids{margin-left:6px;padding-left:7px}.cm-body{margin-left:12px}.cm-l1{flex-wrap:wrap}.cm-l1>.cm-tx{flex-basis:100%}}",
    "@media (max-width:767px){.cm-head{flex-wrap:wrap}}"
  ].join("\n");
  document.head.appendChild(css);

  window.ChipInMessages = { mount: mount, feed: feed, reset: reset, state: state, version: 1 };
})();
