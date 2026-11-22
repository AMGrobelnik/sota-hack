/* ChipInLive: browser adapter between the static dashboard pages and the
 * ChipIn backend running on this computer (contract version 1).
 * Dependency-free, classic script tag; load it before voice.js.
 * Exposes one global, window.ChipInLive. The session token is never logged
 * and never written to localStorage: it lives in sessionStorage, this tab only.
 *
 * A page should call connect() only when wanted() is true, so a page opened
 * without a backend makes no request to 127.0.0.1 at all. */
(function () {
  "use strict";

  var DEFAULT_BASE = "http://127.0.0.1:8797";
  var STORE_PREFIX = "chipin.token:";
  var STAGES = ["spec", "reference", "propose", "finetune", "compile", "verify", "report"];

  var conn = { base: null, token: null, status: "idle", defaults: null, health: null };
  var statusListeners = [];
  var watchers = [];

  function setStatus(s) {
    if (conn.status === s) return;
    conn.status = s;
    statusListeners.slice().forEach(function (fn) {
      try { fn(s); } catch (e) { /* a listener must not break the adapter */ }
    });
  }

  function onStatus(fn) {
    statusListeners.push(fn);
    return function off() {
      var i = statusListeners.indexOf(fn);
      if (i >= 0) statusListeners.splice(i, 1);
    };
  }

  function isLocalPage() {
    var h = location.hostname;
    return (location.protocol === "http:" || location.protocol === "https:") &&
      (h === "127.0.0.1" || h === "localhost");
  }

  function apiParam() {
    try { return new URLSearchParams(location.search).get("api"); } catch (e) { return null; }
  }

  function pickBase(given) {
    if (given) return String(given).replace(/\/+$/, "");
    var api = apiParam();
    if (api) return api.replace(/\/+$/, "");
    return isLocalPage() ? location.origin : DEFAULT_BASE;
  }

  function hashToken() {
    var hash = location.hash.replace(/^#/, "");
    return hash ? new URLSearchParams(hash).get("token") : null;
  }

  // Take #token=... out of the fragment (and the address bar), keeping any
  // other fragment parameters. Returns the token or null.
  function takeTokenFromHash() {
    var tok = hashToken();
    if (!tok) return null;
    var params = new URLSearchParams(location.hash.replace(/^#/, ""));
    params.delete("token");
    var rest = params.toString();
    try {
      history.replaceState(history.state, "", location.pathname + location.search + (rest ? "#" + rest : ""));
    } catch (e) { /* replaceState can fail on file:// pages; the token is still used */ }
    return tok;
  }

  function storage() {
    try { return window.sessionStorage; } catch (e) { return null; }
  }

  function storedToken(base) {
    var store = storage();
    try { return store ? store.getItem(STORE_PREFIX + base) : null; } catch (e) { return null; }
  }

  // Whether this page was opened to talk to a backend: a token in the
  // address, ?api=..., or a token this tab already holds for that backend.
  function wanted() {
    return !!(hashToken() || apiParam() || storedToken(pickBase()));
  }

  function ApiError(status, message) {
    var err = new Error(message);
    err.status = status;
    return err;
  }

  function api(method, path, body, as) {
    if (!conn.base) return Promise.reject(ApiError(0, "Call ChipInLive.connect() first"));
    var init = { method: method, headers: {}, cache: "no-store" };
    if (conn.token) init.headers["X-ChipIn-Token"] = conn.token;
    if (body !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
    return fetch(conn.base + path, init).then(function (res) {
      if (res.status === 401) {
        setStatus("disconnected");
        throw ApiError(401, "The backend did not accept this page's session; open the link it printed again.");
      }
      if (!res.ok) {
        // The backend answers errors as {"error": "..."}: pass its words on.
        return res.json().catch(function () { return {}; }).then(function (j) {
          throw ApiError(res.status, (j && j.error) || (method + " " + path + " failed with HTTP " + res.status));
        });
      }
      if (as === "text") {
        return res.text().then(function (text) {
          return { text: text, truncated: res.headers.get("X-ChipIn-Truncated") === "true" };
        });
      }
      var type = res.headers.get("Content-Type") || "";
      return type.indexOf("json") >= 0 ? res.json().catch(function () { return {}; }) : {};
    }, function () {
      setStatus("disconnected");
      throw ApiError(0, "The backend is not reachable at " + conn.base);
    });
  }

  function connect(opts) {
    opts = opts || {};
    var base = pickBase(opts.base);
    var store = storage();
    var key = STORE_PREFIX + base;
    var tok = opts.token || takeTokenFromHash();
    if (tok && store) store.setItem(key, tok);
    if (!tok) tok = storedToken(base);
    conn.base = base;
    conn.token = tok || null;

    return fetch(base + "/api/health", { cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error("health HTTP " + res.status);
      return res.json();
    }).then(function (health) {
      if (!health || health.ok !== true) return fail("unhealthy");
      if (health.version !== 1) return fail("version-mismatch");
      conn.defaults = health.defaults || null;
      conn.health = health;
      if (!conn.token) return fail("no-token");
      // Health needs no token, so prove the token with one authorised call.
      return fetch(base + "/api/runs", { headers: { "X-ChipIn-Token": conn.token }, cache: "no-store" }).then(function (res) {
        if (res.status === 401) {
          if (store) store.removeItem(key);
          conn.token = null;
          return fail("bad-token");
        }
        if (!res.ok) return fail("http-" + res.status);
        setStatus("connected");
        watchers.slice().forEach(function (w) { w.kick(); });
        return { ok: true, defaults: conn.defaults, health: health };
      });
    }, function () {
      return fail("unreachable");
    });

    function fail(reason) {
      setStatus("disconnected");
      return { ok: false, reason: reason };
    }
  }

  // Pull the token out of a pasted start link (or take a bare token).
  function tokenFromLink(text) {
    text = String(text || "").trim();
    var m = text.match(/[#&?]token=([^&\s#]+)/);
    if (m) return decodeURIComponent(m[1]);
    return /^[A-Za-z0-9_-]{16,}$/.test(text) ? text : null;
  }

  function startRun(o) {
    o = o || {};
    var body = { prompt: o.prompt };
    ["preset", "machine", "answers", "files"].forEach(function (k) {
      if (o[k] !== undefined && o[k] !== null && o[k] !== "") body[k] = o[k];
    });
    return api("POST", "/api/runs", body).then(function (r) { return { id: r.id }; });
  }
  function listRuns() { return api("GET", "/api/runs").then(function (r) { return r.runs || []; }); }
  function getRun(id) { return api("GET", "/api/runs/" + encodeURIComponent(id)); }
  function listFiles(id) {
    return api("GET", "/api/runs/" + encodeURIComponent(id) + "/files").then(function (r) { return r.files || []; });
  }
  function readFile(id, path) {
    return api("GET", "/api/runs/" + encodeURIComponent(id) + "/file?path=" + encodeURIComponent(path), undefined, "text");
  }
  function sendMessage(id, text) {
    // resolves to the backend's answer, { accepted, id, delivery } (truthy as before)
    return api("POST", "/api/runs/" + encodeURIComponent(id) + "/messages", { text: text }).then(function (r) { return r || true; });
  }
  function stopRun(id) {
    return api("POST", "/api/runs/" + encodeURIComponent(id) + "/stop").then(function () { return true; });
  }

  function newState() {
    var stages = {};
    STAGES.forEach(function (n) { stages[n] = { state: "pending", round: null, reason: null, at: null }; });
    return {
      status: "connecting", stages: stages, round: null, statusLine: "", messages: [], tools: [],
      items: [], metrics: {}, metricUnits: {}, artifacts: [],
      runMetrics: {}, runMetricUnits: {}, metricsByChip: {}, metricUnitsByChip: {},
      chosenChip: null, shownChip: null, lastMetricChip: null, cost: null, errors: [], finished: null,
      lastSeq: 0, startedAt: null, finishedAt: null,
    };
  }

  function call(handlers, name, arg, state) {
    var fn = handlers[name];
    if (typeof fn !== "function") return;
    try { fn(arg, state); } catch (e) { setTimeout(function () { throw e; }); }
  }

  // st.metrics is one consistent view: run-level metrics plus ONE chip's
  // metrics, the chosen chip, else the chip of the latest chip-tagged metric.
  // With no chip-tagged event at all it is the last value per key, as before.
  function showMetrics(st) {
    var chip = st.chosenChip || st.lastMetricChip || null;
    st.shownChip = chip;
    [["metrics", "runMetrics", "metricsByChip"], ["metricUnits", "runMetricUnits", "metricUnitsByChip"]].forEach(function (p) {
      var view = st[p[0]], own = (chip && st[p[2]][chip]) || {}, k;
      for (k in view) delete view[k];
      for (k in st[p[1]]) view[k] = st[p[1]][k];
      for (k in own) view[k] = own[k];
    });
  }

  // Apply one event to the derived state; returns [handlerName, argument] or null.
  function reduce(st, ev) {
    switch (ev.type) {
      case "run.started":
        st.status = "running";
        st.prompt = ev.prompt; st.agent = ev.agent; st.runner = ev.runner;
        st.startedAt = ev.ts || null;
        return null;
      case "stage": {
        var sname = ev.stage || ev.name;
        var s = st.stages[sname] || (st.stages[sname] = { state: "pending", round: null });
        s.state = ev.state;
        s.reason = ev.state === "skipped" ? (ev.reason || "") : null;
        s.at = ev.ts || null;
        if (typeof ev.round === "number") { s.round = ev.round; st.round = ev.round; }
        return ["onStage", { name: sname, state: ev.state, reason: s.reason, round: s.round, event: ev }];
      }
      case "status":
        st.statusLine = ev.text || "";
        return ["onStatus", st.statusLine];
      case "message": {
        var m = { seq: ev.seq, ts: ev.ts, role: ev.role, author: ev.author, text: ev.text || "" };
        st.messages.push(m);
        st.items.push({ kind: "message", item: m });
        return ["onMessage", m];
      }
      case "tool": {
        var t = null;
        for (var i = 0; i < st.tools.length; i++) if (st.tools[i].call_id === ev.call_id) t = st.tools[i];
        if (!t) {
          t = { call_id: ev.call_id, name: ev.name, summary: ev.summary, state: ev.state, detail: ev.detail || null, started_at: ev.ts, finished_at: null };
          st.tools.push(t);
          st.items.push({ kind: "tool", item: t });
        } else {
          if (ev.name) t.name = ev.name;
          if (ev.summary) t.summary = ev.summary;
          if (ev.detail) t.detail = ev.detail;
          t.state = ev.state;
        }
        if (ev.state === "done" || ev.state === "failed") t.finished_at = ev.ts;
        return ["onTool", t];
      }
      case "metric": {
        var chip = typeof ev.chip === "string" && ev.chip ? ev.chip : null;
        var vals = st.runMetrics, units = st.runMetricUnits;
        if (chip) {
          st.lastMetricChip = chip;
          vals = st.metricsByChip[chip] || (st.metricsByChip[chip] = {});
          units = st.metricUnitsByChip[chip] || (st.metricUnitsByChip[chip] = {});
        }
        vals[ev.key] = ev.value;
        if (ev.unit) units[ev.key] = ev.unit;
        showMetrics(st);
        return ["onMetric", { key: ev.key, value: ev.value, unit: ev.unit }];
      }
      case "chosen":
        if (typeof ev.chip === "string" && ev.chip) { st.chosenChip = ev.chip; showMetrics(st); }
        return null;
      case "artifact": {
        var a = { name: ev.name, kind: ev.kind, path: ev.path };
        st.artifacts.push(a);
        return ["onArtifact", a];
      }
      case "cost":
        st.cost = { usd: ev.usd, tokens_in: ev.tokens_in, tokens_out: ev.tokens_out, summaries_usd: ev.summaries_usd };
        return ["onCost", st.cost];
      case "error":
        st.errors.push(ev.message);
        st.items.push({ kind: "error", item: { seq: ev.seq, ts: ev.ts, text: ev.message || "" } });
        return ["onError", { message: ev.message }];
      case "run.finished":
        st.status = ev.status;
        st.finishedAt = ev.ts || null;
        st.finished = { status: ev.status, summary: ev.summary || null, bullets: ev.bullets || null };
        return ["onFinished", st.finished];
      default:
        return null; // unknown types are ignored
    }
  }

  // opts.state: carry on from an earlier watcher's state (the stream reopens at its next seq),
  // as a follow-up message does after the stream closed at run.finished.
  function watch(id, handlers, opts) {
    handlers = handlers || {};
    var state = (opts && opts.state) || newState();
    var es = null, timer = null, closed = false, attempt = 0;
    var self = { state: state, close: stop, kick: kick, isClosed: function () { return closed; } };

    function open() {
      timer = null;
      if (closed || es) return;
      var url = conn.base + "/api/runs/" + encodeURIComponent(id) + "/events?token=" +
        encodeURIComponent(conn.token || "") + "&from=" + (state.lastSeq + 1);
      es = new EventSource(url);
      es.onopen = function () { attempt = 0; setStatus("connected"); };
      es.onmessage = function (msg) {
        var ev;
        try { ev = JSON.parse(msg.data); } catch (e) { return; }
        if (!ev || typeof ev.seq !== "number" || ev.seq <= state.lastSeq) return; // never twice
        if (window.ChipInFold) window.ChipInFold.scrubEvent(ev); /* FOLD HOOK: no absolute home path reaches the page (../i1-fold.js) */
        state.lastSeq = ev.seq;
        if (state.finished && ev.type !== "run.finished") {
          // A follow-up: the run went back to running after its run.finished.
          state.status = "running"; state.finished = null; state.finishedAt = null;
        }
        var out = reduce(state, ev);
        if (out) call(handlers, out[0], out[1], state);
        call(handlers, "onEvent", ev, state);
      };
      es.onerror = function () {
        // Reconnect ourselves so the stream resumes from the last seq seen.
        if (es) es.close();
        es = null;
        // The server ends the stream after the log's last run.finished (follow-ups included).
        if (state.finished) { stop(); return; }
        if (closed) return;
        setStatus("reconnecting");
        if (attempt >= 3) {
          // Long outage: say so plainly while the retries continue.
          fetch(conn.base + "/api/runs", { headers: { "X-ChipIn-Token": conn.token || "" }, cache: "no-store" }).then(function (r) {
            if (!closed && r.status === 401) setStatus("disconnected");
          }, function () { if (!closed && !es) setStatus("disconnected"); });
        }
        var delay = Math.min(10000, 500 * Math.pow(2, attempt++)) * (0.8 + Math.random() * 0.4);
        timer = setTimeout(open, delay);
      };
    }
    // After a fresh connect(): retry now instead of waiting out the back-off.
    function kick() {
      if (closed || es) return;
      if (timer) clearTimeout(timer);
      attempt = 0;
      open();
    }
    function stop() {
      closed = true;
      if (timer) clearTimeout(timer);
      if (es) es.close();
      es = null;
      var i = watchers.indexOf(self);
      if (i >= 0) watchers.splice(i, 1);
    }
    watchers.push(self);
    open();
    return self;
  }

  var BADGE = {
    connected: { text: "Live on this Mac", dot: "#15803d", hint: "" },
    reconnecting: { text: "Reconnecting", dot: "#b45309", hint: "" },
    disconnected: {
      text: "Not connected", dot: "#6b7280",
      hint: "Start the ChipIn backend on this Mac, then open the link it prints.",
    },
  };

  function badge(el) {
    if (!el) return function () {};
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    function render(s) {
      var b = BADGE[s] || BADGE.disconnected;
      el.textContent = "";
      el.setAttribute("data-state", s);
      el.style.cssText = "display:inline-flex;align-items:center;gap:6px;font:13px/1.4 system-ui,sans-serif;" +
        "color:#1f2937;background:#f3f4f6;border:1px solid #d1d5db;border-radius:999px;padding:2px 10px;";
      var dot = document.createElement("span");
      dot.style.cssText = "width:8px;height:8px;border-radius:50%;background:" + b.dot + ";";
      var label = document.createElement("span");
      label.textContent = b.text;
      el.appendChild(dot);
      el.appendChild(label);
      if (b.hint) {
        var hint = document.createElement("span");
        hint.style.cssText = "color:#374151;";
        hint.textContent = "· " + b.hint;
        el.appendChild(hint);
      }
    }
    render(conn.status === "idle" ? "disconnected" : conn.status);
    return onStatus(render);
  }

  window.ChipInLive = {
    version: 1,
    STAGES: STAGES.slice(),
    wanted: wanted,
    connect: connect,
    tokenFromLink: tokenFromLink,
    startRun: startRun,
    listRuns: listRuns,
    getRun: getRun,
    listFiles: listFiles,
    readFile: readFile,
    sendMessage: sendMessage,
    stopRun: stopRun,
    watch: watch,
    onStatus: onStatus,
    badge: badge,
    get status() { return conn.status; },
    get base() { return conn.base; },
    get defaults() { return conn.defaults; },
    get health() { return conn.health; },
  };
})();
