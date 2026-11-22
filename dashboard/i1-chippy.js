/* ChipIn i1 Chippy: the helper panel of dashboard/variants/i1.html.
 *
 * Classic script, no dependencies; i1.html loads it from one line marked CHIPPY HOOK. It adds
 * window.ChipInChippy and draws everything it needs itself (a round avatar at the bottom right and a
 * chat card above it, a sheet on phones), outside #main, so the page underneath is not touched while it is closed.
 *
 *   ChipInChippy.open() / close() / toggle()   the panel (also Ctrl or Cmd + /, Escape closes)
 *   ChipInChippy.ask(text)                     sends a question as if typed
 *   ChipInChippy.view()                        the view context sent with every message
 *   ChipInChippy.state()                       what the panel shows now (for tests)
 *
 * Chippy is the user's guide to the product and its results, served by the backend
 * (POST /api/helper/messages, a stream; POST /api/helper/suggestions, the example prompts). It is not
 * the agent that designs chips: that one is talked to through a run's own Chat tab.
 *
 * What it does on the page. The server streams checked ACTIONS (go_to, open_run, switch_tab,
 * select_design, set_playback, open_file, new_spec, highlight); this file carries each out with the
 * page's own controls, writes one line saying what changed and offers Undo, which returns to the view
 * before it. PROPOSALS (start a run, message the running agent, stop it) only become a button: the
 * request is sent, with the token, when the user presses it, never before. Run and design ids in an
 * answer are links that open or select them.
 *
 * Text from the model and from run data is always set as text (textContent): paragraphs, list lines,
 * **bold** and `code` are the only formatting, built as elements, never parsed as markup.
 *
 * Connection: the same as the page's live and playback modules (the backend's address and token kept
 * by i1-live.js). The public site with no backend makes no request at all: the panel says what
 * Chippy needs. Backend runs are opened on the live view (#/live/<id>/<tab>), or on the recorded view
 * (#/rec/<src>/<id>/<tab>) when that run is open there or the action moves its playback clock.
 * Selecting a design and moving the clock use the live and playback modules' select() and seek() when
 * they offer them, else the same keys a user would press on the chart and on the playback track. */
(function () {
  "use strict";
  if (window.ChipInChippy) return;

  /* ---------- helpers ---------- */
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var K_CONN = "chipin-i1-backend", K_VIEW = "chipin-i1-live-view", K_FLOW = "chipin-i1-flow";
  var K_CONV = "chipin-chippy-conv", K_ITEMS = "chipin-chippy-items";
  var RUN_RE = /\b\d{8}-\d{6}-[0-9a-f]{6}\b/;
  // a removed or unknown tab name falls back to the overview wherever TABS is consulted
  var TABS = { overview: "Overview", chip: "Chip", chat: "Chat", sources: "Sources" };
  var STEPS = { "1": "The device", "2": "Who and where", "3": "Targets", "4": "Constraints", "5": "Data", spec: "Your spec" };
  var el = function (tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = window.ChipInFold ? window.ChipInFold.scrub(String(text)) : text; return n; };
  var ssGet = function (k) { try { return JSON.parse(sessionStorage.getItem(k) || "null"); } catch (e) { return null; } };
  var ssSet = function (k, v) { try { if (v == null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage off: kept in memory only */ } };
  var lsGet = function (k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } };
  var shortId = function (id) { return String(id).length > 14 ? "…" + String(id).slice(-6) : String(id); };
  var wait = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  function until(test, ms) {
    var t0 = Date.now();
    return new Promise(function (res) {
      (function poll() { var v = null; try { v = test(); } catch (e) { v = null; } if (v) return res(v); if (Date.now() - t0 > (ms || 6000)) return res(null); setTimeout(poll, 60); })();
    });
  }
  // Chippy himself: a small blue chip with two pins a side and a face on its white die (blinks and hops in CSS)
  var FACE_INNER =
    '<g fill="#dfe6fb" stroke="#1d2756" stroke-width="1.5"><rect x="4" y="16.4" width="6.5" height="4.4" rx="2.2"/><rect x="4" y="27.2" width="6.5" height="4.4" rx="2.2"/>' +
    '<rect x="37.5" y="16.4" width="6.5" height="4.4" rx="2.2"/><rect x="37.5" y="27.2" width="6.5" height="4.4" rx="2.2"/><rect x="16.4" y="4" width="4.4" height="6.5" rx="2.2"/>' +
    '<rect x="27.2" y="4" width="4.4" height="6.5" rx="2.2"/><rect x="16.4" y="37.5" width="4.4" height="6.5" rx="2.2"/><rect x="27.2" y="37.5" width="4.4" height="6.5" rx="2.2"/></g>' +
    '<rect x="8.5" y="8.5" width="31" height="31" rx="8.5" fill="#3d6df0" stroke="#1d2756" stroke-width="2"/>' +
    '<rect x="12.5" y="12.5" width="23" height="23" rx="6.5" fill="#fff"/>' +
    '<g class="eyes"><ellipse cx="19.4" cy="22.4" rx="2.4" ry="3" fill="#141a2e"/><ellipse cx="28.6" cy="22.4" rx="2.4" ry="3" fill="#141a2e"/>' +
    '<circle cx="20.2" cy="21.3" r=".8" fill="#fff"/><circle cx="29.4" cy="21.3" r=".8" fill="#fff"/></g>' +
    '<g fill="#ff8aa6" opacity=".55"><ellipse cx="16" cy="28" rx="2" ry="1.25"/><ellipse cx="32" cy="28" rx="2" ry="1.25"/></g>' +
    '<path d="M20.8 27.9q3.2 2.8 6.4 0" fill="none" stroke="#141a2e" stroke-width="2.1" stroke-linecap="round"/>';
  var face = function (cls) { return '<svg class="chp-face' + (cls ? " " + cls : "") + '" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" aria-hidden="true" focusable="false">' + FACE_INNER + "</svg>"; };
  var MARK = face();
  var FACE_URL = 'url("data:image/svg+xml,' + encodeURIComponent(face()) + '")';
  var K_HELLO = "chipin-chippy-hello";
  var SVG = {
    x: '<path d="M18 6 6 18M6 6l12 12"/>', send: '<path d="M12 19V5M5 12l7-7 7 7"/>', stop: '<rect x="7" y="7" width="10" height="10" rx="2"/>',
    fresh: '<path d="M12 5v14M5 12h14"/>', undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>'
  };
  var icon = function (n) { return '<svg class="chp-i" viewBox="0 0 24 24" aria-hidden="true">' + SVG[n] + "</svg>"; };
  var MOD = /Mac|iPhone|iPad/.test(navigator.platform || "") ? "⌘" : "Ctrl";

  /* ---------- the backend connection (the live module's, read only) ---------- */
  function conn() {
    var L = window.ChipInLive, base = null, token = null;
    try { if (L && L.base && L.token) { base = L.base; token = L.token; } } catch (e) { /* older reader */ }
    if (!token) { var s = lsGet(K_CONN); if (s && s.base && s.token) { base = s.base; token = s.token; } }
    if (!token) {
      var api = null; try { api = new URLSearchParams(location.search).get("api"); } catch (e) { /* none */ }
      var loop = /^https?:$/.test(location.protocol) && /^(127\.0\.0\.1|localhost)$/.test(location.hostname);
      base = api ? api.replace(/\/+$/, "") : loop ? location.origin : null;
      if (base) { try { token = sessionStorage.getItem("chipin.token:" + base); } catch (e) { /* storage off */ } }
    }
    return base && token ? { base: base.replace(/\/+$/, ""), token: token } : null;
  }
  var HEALTH = { base: null, helper: null };
  function checkHealth(c) {
    if (HEALTH.base === c.base && HEALTH.helper != null) return Promise.resolve(HEALTH.helper);
    var h = null; try { h = window.ChipInLive && window.ChipInLive.health; } catch (e) { h = null; }
    if (h && typeof h.helper === "boolean" && window.ChipInLive.base === c.base) { HEALTH.base = c.base; HEALTH.helper = h.helper; return Promise.resolve(h.helper); }
    return fetch(c.base + "/api/health", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      HEALTH.base = c.base; HEALTH.helper = j ? j.helper !== false : null; return HEALTH.helper;
    }).catch(function () { HEALTH.base = c.base; HEALTH.helper = null; return null; });
  }
  function post(c, path, body, signal) {
    return fetch(c.base + path, { method: "POST", cache: "no-store", signal: signal, headers: { "Content-Type": "application/json", "X-ChipIn-Token": c.token }, body: JSON.stringify(body || {}) });
  }

  /* ---------- where the page is: the view context sent with every message ---------- */
  function hashPath() { var h = location.hash || ""; var i = h.indexOf("?"); return i >= 0 ? h.slice(0, i) : h; }
  function where() {
    var h = hashPath(), m;
    if ((m = h.match(/^#\/live\/([^/?]+)(?:\/([a-z]+))?/))) return { kind: "live", id: decodeURIComponent(m[1]), tab: TABS[m[2]] ? m[2] : "overview" };
    if ((m = h.match(/^#\/rec\/(site|mac)\/([^/?]+)(?:\/([a-z]+))?/))) return { kind: "rec", src: m[1], id: decodeURIComponent(m[2]), tab: TABS[m[3]] ? m[3] : "overview" };
    if ((m = h.match(/^#\/run\/([^/?]+)(?:\/(?:visual\/)?([a-z]+))?/))) return { kind: "example", id: decodeURIComponent(m[1]), tab: TABS[m[2]] ? m[2] : "overview" };
    if ((m = h.match(/^#\/new\/([1-5]|spec)/))) return { kind: "new", step: m[1] };
    if (/^#\/configure/.test(h)) return { kind: "configure" };
    return { kind: "start" };
  }
  function liveSel(id) { var p = lsGet(K_VIEW); return p && p[id] && p[id].sel || null; }
  function clockNow() { try { var c = window.ChipInPlayback && window.ChipInPlayback.clock(); return c ? c : null; } catch (e) { return null; } }
  function specDraft() {
    var s = ssGet(K_FLOW); if (!s || typeof s !== "object") return null;
    var out = {}, keys = ["brief", "device", "signal", "detect", "task", "group", "place", "who", "targets", "primary", "cons", "data", "preset", "agent", "touched"];
    keys.forEach(function (k) { if (s[k] != null && s[k] !== "") out[k] = s[k]; });
    if (Array.isArray(s.files)) out.files = s.files.map(function (f) { return f && f.name; }).filter(Boolean).slice(0, 10);
    var j = JSON.stringify(out);
    for (var i = keys.length - 1; j.length > 3800 && i > 0; i--) { delete out[keys[i]]; j = JSON.stringify(out); }
    if (j.length > 3800) out = { brief: String(s.brief || "").slice(0, 3000) };
    return out;
  }
  function view() {
    var w = where(), v = {};
    if (w.kind === "live" || w.kind === "rec" || w.kind === "example") {
      v.route = "#/run/" + w.id + "/" + w.tab; v.run_id = w.id; v.tab = w.tab;
      var sel = w.kind === "live" ? liveSel(w.id) || (w.tab === "overview" ? inspId() : null) : null; if (sel) v.design_id = sel;
      var ck = clockNow(); if (ck && w.kind !== "live") v.playback_s = Math.round(ck.t * 10) / 10;
    } else if (w.kind === "new") {
      v.route = "#/new/" + w.step; v.flow_step = w.step;
      var d = specDraft(); if (d) v.spec_draft = d;
    } else if (w.kind === "configure") v.route = "#/configure";
    else v.route = "#/";
    return v;
  }
  function viewKey() { var v = view(); return [v.route, v.design_id || "", v.flow_step || ""].join("|"); }

  /* ---------- styles: the page's tokens, a round avatar at the bottom right, a chat card above it ---------- */
  var W = 380, GAP = 20, BUB = 52;
  var STYLE = [
    // the avatar: above the page (its column, sidebar and phone header) and below every scrim, drawer and dialog
    ".chp-btn{position:fixed;right:" + GAP + "px;bottom:" + GAP + "px;z-index:34;width:" + BUB + "px;height:" + BUB + "px;padding:0;display:grid;place-items:center;border-radius:50%;border:1px solid rgb(61 109 240/.2);background:#fff;box-shadow:0 6px 18px rgb(14 21 48/.15),0 1px 3px rgb(14 21 48/.1);cursor:pointer;transition:box-shadow .15s,border-color .15s}",
    ".chp-btn:hover{border-color:rgb(61 109 240/.45);box-shadow:0 8px 24px rgb(14 21 48/.2),0 1px 3px rgb(14 21 48/.1)}",
    ".chp-btn:focus-visible,.chp-p button:focus-visible,.chp-p a:focus-visible{outline:2px solid var(--blue,#3d6df0);outline-offset:2px}",
    ".chp-btn[aria-expanded=true]{border-color:var(--blue,#3d6df0);box-shadow:0 0 0 3px rgb(61 109 240/.16),0 6px 18px rgb(14 21 48/.15)}",
    ".chp-btn .chp-face{width:40px;height:40px}",
    ".chp-face{display:block;flex:none;overflow:visible}",
    ".chp-face .eyes{transform-box:fill-box;transform-origin:center;animation:chpBlink 5.2s infinite}",
    "@keyframes chpBlink{0%,93%,100%{transform:none}95.5%{transform:scaleY(.12)}}",
    ".chp-btn:hover .chp-face{animation:chpHop .55s var(--ease,ease)}",
    "@keyframes chpHop{0%,100%{transform:none}35%{transform:translateY(-4px)}65%{transform:translateY(1px)}}",
    ".chp-busy .chp-h .chp-face{animation:chpBob 1.1s ease-in-out infinite}",
    "@keyframes chpBob{0%,100%{transform:none}50%{transform:translateY(-2px)}}",
    // a hello beside the avatar, once a session
    ".chp-hello{position:fixed;right:" + (GAP + BUB + 12) + "px;bottom:" + (GAP + BUB / 2 - 15) + "px;z-index:34;height:30px;display:flex;align-items:center;padding:0 12px;border-radius:10px;background:#fff;border:1px solid rgb(61 109 240/.2);box-shadow:0 6px 18px rgb(14 21 48/.12);font:500 12.5px/1 var(--sans,system-ui);color:var(--i800,#262c40);white-space:nowrap;pointer-events:none;opacity:0;transform:translateX(6px);transition:opacity .35s,transform .35s}",
    ".chp-hello::after{content:'';position:absolute;right:-5px;top:50%;width:8px;height:8px;margin-top:-4px;background:#fff;border:solid rgb(61 109 240/.2);border-width:1px 1px 0 0;transform:rotate(45deg)}",
    ".chp-hello.on{opacity:1;transform:none}",
    "body.chp-open .chp-hello{display:none}",
    ".chp-i{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;flex:none}",
    // the panel: a chat card anchored above the avatar that grows upward with the conversation
    ".chp-p{position:fixed;right:" + GAP + "px;bottom:" + (GAP + BUB + 12) + "px;width:" + W + "px;max-width:calc(100vw - " + 2 * GAP + "px);min-height:min(360px,70vh);max-height:70vh;z-index:60;background:#fff;border:1px solid rgb(0 0 0/.08);border-radius:16px;overflow:hidden;box-shadow:0 18px 50px rgb(14 21 48/.18),0 2px 8px rgb(14 21 48/.07);display:flex;flex-direction:column;font-family:var(--sans,system-ui);color:var(--i900,#141a2e);transform-origin:100% 100%;animation:chpIn .18s var(--ease,ease)}",
    "@keyframes chpIn{from{transform:translateY(10px) scale(.97);opacity:0}to{transform:none;opacity:1}}",
    ".chp-scrim{display:none}",
    // the page's file drawer and the card coexist: the drawer (and its scrim) stop at the card's column
    "@media (min-width:768px){body.chp-open .drawer{right:" + (W + 2 * GAP) + "px;max-width:calc(100vw - " + (W + 2 * GAP) + "px)}body.chp-open .dscrim{right:" + (W + 2 * GAP) + "px}}",
    // the page's demo label sits at the bottom right on wide screens: it moves left of the avatar
    "@media (min-width:768px){.demo{right:" + (GAP + BUB + 12) + "px}}",
    // the page's scrolling column ends with room for the avatar, so its last line can scroll clear of it
    // (not the Chat tab: it fills the column with its own composer at the bottom)
    ".main .body:not(:has(> .chat))::after{content:'';display:block;height:" + (BUB + 12) + "px}",
    // no backend: nothing can be asked, so no new conversation and no microphone
    ".chp-p.chp-nomode #chpNew,.chp-p.chp-nomode .cv-mic{display:none}",
    ".chp-p[hidden],.chp-scrim[hidden]{display:none!important}",
    ".chp-h{display:flex;align-items:center;gap:9px;padding:11px 10px 10px 14px;border-bottom:1px solid var(--hair,rgb(0 0 0/.07))}",
    ".chp-h .chp-face{width:26px;height:26px}",
    ".chp-h h2{font:400 18px/1.1 var(--serif,Georgia,serif);margin:0;letter-spacing:-.01em}",
    ".chp-h .grow{flex:1}",
    ".chp-ib{width:30px;height:30px;border-radius:8px;display:grid;place-items:center;color:var(--i600,#4a5062);background:none;border:0;cursor:pointer}",
    ".chp-ib:hover{background:var(--i100,#f1f2f6);color:var(--i900,#141a2e)}",
    ".chp-log{flex:1 1 auto;min-height:0;overflow:auto;padding:14px 16px 8px;display:flex;flex-direction:column;gap:12px;overscroll-behavior:contain}",
    // his own lines carry his face at 20 px
    ".chp-hi,.chp-a,.chp-off{position:relative;padding-left:28px}",
    ".chp-hi::before,.chp-a::before,.chp-off::before{content:'';position:absolute;left:0;top:0;width:20px;height:20px;background:" + FACE_URL + " center/contain no-repeat}",
    ".chp-hi{font-size:13px;line-height:1.5;color:var(--i600,#4a5062);margin:0}",
    ".chp-u{align-self:flex-end;max-width:86%;background:var(--i100,#f1f2f6);border-radius:12px 12px 4px 12px;padding:8px 11px;font-size:13.5px;line-height:1.45;white-space:pre-wrap;overflow-wrap:anywhere}",
    ".chp-a{font-size:13.5px;line-height:1.55;color:var(--i800,#262c40);overflow-wrap:anywhere}",
    ".chp-a p{margin:0 0 8px}.chp-a p:last-child{margin-bottom:0}",
    ".chp-a ul{margin:0 0 8px;padding-left:18px}.chp-a li{margin:2px 0}",
    ".chp-a code{font:12px/1.4 var(--mono,ui-monospace,monospace);background:var(--i100,#f1f2f6);border-radius:4px;padding:0 4px}",
    ".chp-a strong{font-weight:600;color:var(--i900,#141a2e)}",
    ".chp-lk{font:inherit;color:var(--blue7,#2b55d0);background:none;border:0;padding:0;cursor:pointer;text-decoration:underline;text-decoration-color:rgb(43 85 208/.35);text-underline-offset:2px}",
    ".chp-lk:hover{text-decoration-color:currentColor}",
    ".chp-t{font-size:11.5px;color:var(--i500,#5c6276);display:flex;align-items:center;gap:6px}",
    ".chp-t::before{content:'';width:5px;height:5px;border-radius:50%;background:var(--i300,#b2b6c2)}",
    ".chp-w{font-size:12px;color:var(--i500,#5c6276)}",
    ".chp-did{display:flex;align-items:center;gap:8px;font-size:12px;line-height:1.4;color:var(--i700,#3a4052);border-left:2px solid var(--blue,#3d6df0);padding:2px 0 2px 9px}",
    ".chp-did span{flex:1}",
    ".chp-did.undone{border-left-color:var(--i300,#b2b6c2);color:var(--i500,#5c6276)}",
    ".chp-did.pending{opacity:.6}",
    ".chp-did.bad{border-left-color:var(--amb,#b45309)}",
    ".chp-undo{display:inline-flex;align-items:center;gap:4px;font:500 12px/1 var(--sans,system-ui);color:var(--blue7,#2b55d0);background:none;border:0;padding:4px 2px;cursor:pointer}",
    ".chp-undo .chp-i{width:13px;height:13px}",
    ".chp-pr{border:1px solid rgb(0 0 0/.1);border-radius:10px;padding:10px 11px;display:flex;flex-direction:column;gap:8px;background:#fff}",
    ".chp-pr p{margin:0;font-size:12.5px;line-height:1.45;color:var(--i700,#3a4052);white-space:pre-wrap;overflow-wrap:anywhere}",
    ".chp-pr .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}",
    ".chp-go{height:30px;padding:0 12px;border-radius:8px;border:0;background:var(--navy,#0e1530);color:#fff;font:500 12.5px/1 var(--sans,system-ui);cursor:pointer}",
    ".chp-go:hover{background:var(--navy2,#16204a)}.chp-go:disabled{opacity:.45;cursor:default}",
    ".chp-no{height:30px;padding:0 8px;border:0;background:none;color:var(--i600,#4a5062);font:500 12.5px/1 var(--sans,system-ui);cursor:pointer}",
    ".chp-pr .res{font-size:12px;color:var(--i600,#4a5062)}",
    ".chp-err{font-size:12.5px;line-height:1.45;color:var(--badt,#b91c1c);background:var(--badbg,#fdf0ee);border-radius:8px;padding:8px 10px;white-space:pre-wrap}",
    ".chp-err.lim{color:var(--amb,#b45309);background:var(--amb-bg,#fff8eb)}",
    ".chp-err button{display:block;margin-top:6px}",
    ".chp-off{display:flex;flex-direction:column;gap:10px;font-size:13px;line-height:1.55;color:var(--i700,#3a4052)}",
    ".chp-off p{margin:0}",
    ".chp-off a{color:var(--blue7,#2b55d0)}",
    ".chp-ex{display:flex;flex-wrap:wrap;gap:6px;padding:8px 16px 0}",
    ".chp-ex:empty{display:none}",
    ".chp-ex button{max-width:100%;height:28px;padding:0 10px;border-radius:99px;border:1px solid rgb(0 0 0/.09);background:#fff;color:var(--i700,#3a4052);font:500 12px/1 var(--sans,system-ui);cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".chp-ex button:hover{border-color:rgb(61 109 240/.45);color:var(--i900,#141a2e);background:rgb(61 109 240/.04)}",
    ".chp-ex button:disabled{opacity:.5;cursor:default}",
    ".chp-c{padding:10px 12px 12px;display:flex;align-items:flex-end;gap:6px}",
    ".chp-box{flex:1;display:flex;align-items:flex-end;gap:4px;border:1px solid rgb(0 0 0/.12);border-radius:12px;padding:5px 5px 5px 11px;background:#fff}",
    ".chp-box:focus-within{border-color:rgb(61 109 240/.55);box-shadow:0 0 0 3px rgb(61 109 240/.1)}",
    ".chp-box textarea{flex:1;border:0;outline:0;resize:none;font:13.5px/1.45 var(--sans,system-ui);color:var(--i900,#141a2e);max-height:140px;min-height:20px;padding:4px 0;background:none}",
    ".chp-box textarea:disabled{background:none;color:var(--i500,#5c6276)}",
    ".chp-send{width:30px;height:30px;border-radius:8px;border:0;display:grid;place-items:center;background:var(--i150,#e7e9ee);color:var(--i600,#4a5062);cursor:pointer;flex:none}",
    ".chp-send.ready{background:var(--navy,#0e1530);color:#fff}",
    ".chp-send:disabled{cursor:default;opacity:.6}",
    ".chp-foot{padding:0 16px 10px;font-size:11px;color:var(--i500,#5c6276)}",
    ".chp-ring{position:fixed;z-index:58;pointer-events:none;border:2px solid var(--blue,#3d6df0);border-radius:10px;box-shadow:0 0 0 4px rgb(61 109 240/.16);animation:chpRing 2.6s var(--ease,ease) forwards}",
    "@keyframes chpRing{0%{opacity:0}10%{opacity:1}75%{opacity:1}100%{opacity:0}}",
    "@media (max-width:767px){",
    "  .chp-btn{right:14px;bottom:calc(14px + env(safe-area-inset-bottom,0px))}",
    "  .chp-hello{right:" + (14 + BUB + 12) + "px;bottom:calc(" + (14 + BUB / 2 - 15) + "px + env(safe-area-inset-bottom,0px))}",
    // a run's Chat tab pins its composer to the bottom of the screen: the avatar rises above it
    "  body:has(.main .lv-cxw) .chp-btn{bottom:calc(128px + env(safe-area-inset-bottom,0px))}",
    "  body:has(.main .lv-cxw) .chp-hello{bottom:calc(" + (128 + BUB / 2 - 15) + "px + env(safe-area-inset-bottom,0px))}",
    // the sidebar drawer is open: the avatar steps aside until it closes
    "  body.drawer .chp-btn,body.drawer .chp-hello{display:none}",
    "  .chp-p{top:auto;left:0;right:0;bottom:0;width:auto;max-width:none;min-height:0;max-height:none;height:min(78vh,680px);border:0;border-radius:16px 16px 0 0;box-shadow:0 -10px 40px rgb(14 21 48/.16);padding-bottom:env(safe-area-inset-bottom,0px);animation:chpUp .2s var(--ease,ease)}",
    "  .chp-scrim{display:block;position:fixed;inset:0;z-index:59;background:rgb(20 20 40/.14)}",
    // a file was opened by Chippy: the sheet shrinks to a bar under the drawer that keeps the line and its Undo
    "  .chp-p.chp-mini{height:auto;max-height:30vh;z-index:80;animation:none}",
    "  .chp-p.chp-mini .chp-h,.chp-p.chp-mini .chp-ex,.chp-p.chp-mini .chp-c,.chp-p.chp-mini .chp-log>:not(.chp-keep){display:none}",
    "  .chp-p.chp-mini .chp-log{flex:none;padding:10px 14px;gap:0}",
    "  .chp-scrim.chp-mini{display:none}",
    "  body.chp-mini .drawer{bottom:var(--chp-bar,64px)}body.chp-mini .dscrim{bottom:var(--chp-bar,64px)}",
    "  .chp-h{padding-top:10px}",
    "}",
    "@keyframes chpUp{from{transform:translateY(24px);opacity:0}to{transform:none;opacity:1}}",
    "@media (prefers-reduced-motion:reduce){.chp-p,.chp-ring,.chp-face,.chp-face .eyes,.chp-btn:hover .chp-face,.chp-busy .chp-h .chp-face{animation:none}.chp-hello{transition:none;transform:none}}"
  ].join("\n");

  /* ---------- state ---------- */
  var S = {
    open: false, busy: false, conv: ssGet(K_CONV), items: (ssGet(K_ITEMS) || []).map(function (it) { if (it && it.pending) { it.pending = false; it.undo = false; } if (it) delete it.keep; return it; }), abort: null,
    sugg: [], suggKey: null, mode: "off", turn: null, undo: [], lastActionAt: 0
  };
  var UI = {};

  /* ---------- the avatar at the bottom right ---------- */
  function mountButton() {
    var b = el("button", "chp-btn"); b.type = "button"; b.id = "chpBtn";
    b.setAttribute("aria-label", "Open Chippy");
    b.title = "Chippy, the guide to ChipIn (" + MOD + " /)";
    b.innerHTML = MARK;
    b.setAttribute("aria-expanded", "false"); b.setAttribute("aria-controls", "chpPanel");
    b.onclick = function () { toggle(); };
    document.body.appendChild(b);
    UI.btn = b;
    hello();
  }
  // the first page load of a session: a short "Ask Chippy" beside the avatar that fades out by itself
  function hello() {
    if (ssGet(K_HELLO)) return;
    ssSet(K_HELLO, 1);
    var h = el("div", "chp-hello", "Ask Chippy"); h.setAttribute("aria-hidden", "true");
    document.body.appendChild(h);
    setTimeout(function () { h.classList.add("on"); }, 700);
    setTimeout(function () { h.classList.remove("on"); setTimeout(function () { h.remove(); }, 400); }, 5200);
  }

  /* ---------- the panel ---------- */
  function mountPanel() {
    var scrim = el("div", "chp-scrim"); scrim.onclick = function () { close(); };
    var p = el("aside", "chp-p"); p.id = "chpPanel"; p.setAttribute("role", "dialog"); p.setAttribute("aria-label", "Chippy");
    p.innerHTML = '<div class="chp-h">' + MARK + '<h2>Chippy</h2><span class="grow"></span>' +
      '<button class="chp-ib" id="chpNew" type="button" title="New conversation" aria-label="New conversation">' + icon("fresh") + "</button>" +
      '<button class="chp-ib" id="chpX" type="button" title="Close (Esc)" aria-label="Close Chippy">' + icon("x") + "</button></div>" +
      '<div class="chp-log" id="chpLog" role="log" aria-live="polite"></div>' +
      '<div class="chp-ex" id="chpEx" role="group" aria-label="Example questions"></div>' +
      '<div class="chp-c"><div class="chp-box"><textarea id="chpIn" rows="1" aria-label="Ask Chippy" placeholder="Ask about ChipIn or a run" data-voice data-voice-anchor="#chpSend"></textarea>' +
      '<button class="chp-send" id="chpSend" type="button" aria-label="Send">' + icon("send") + "</button></div></div>";
    document.body.appendChild(scrim); document.body.appendChild(p);
    UI.scrim = scrim; UI.p = p; UI.log = $("#chpLog", p); UI.ex = $("#chpEx", p); UI.in = $("#chpIn", p); UI.send = $("#chpSend", p);
    $("#chpX", p).onclick = function () { close(); };
    $("#chpNew", p).onclick = function () { fresh(); };
    UI.in.addEventListener("input", function () { fit(); syncSend(); });
    UI.in.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!S.busy) submit(); }
    });
    UI.send.onclick = function () { if (S.busy) stopAnswer(); else submit(); };
    UI.ex.addEventListener("click", function (e) { var b = e.target.closest("button[data-i]"); if (b && !S.busy) ask(S.sugg[+b.dataset.i].prompt); });
    UI.log.addEventListener("click", onLogClick);
    p.addEventListener("click", function (e) { if (p.classList.contains("chp-mini") && !e.target.closest(".chp-undo")) mini(false); });
    p.addEventListener("keydown", function (e) { if (e.key === "Escape" && !document.querySelector(".pop,.mbg")) { e.stopPropagation(); close(); } });
    if (window.ChipVoice && window.ChipVoice.attach) { try { window.ChipVoice.attach(p); } catch (e) { /* voice optional */ } }
  }
  function fit() { var t = UI.in; t.style.height = "auto"; t.style.height = Math.min(140, Math.max(20, t.scrollHeight)) + "px"; }
  function syncSend() {
    var b = UI.send; if (!b) return;
    b.classList.toggle("ready", S.busy || !!UI.in.value.trim());
    b.innerHTML = icon(S.busy ? "stop" : "send");
    b.setAttribute("aria-label", S.busy ? "Stop the answer" : "Send");
    b.disabled = !S.busy && S.mode !== "on";
    UI.in.disabled = S.mode !== "on";
    UI.p.classList.toggle("chp-busy", S.busy);
    UI.p.classList.toggle("chp-nomode", S.mode !== "on");
    UI.ex.querySelectorAll("button").forEach(function (x) { x.disabled = S.busy; });
  }

  function open() {
    if (S.open) { UI.in && !UI.in.disabled && UI.in.focus(); return; }
    S.open = true;
    if (!UI.p) mountPanel();
    UI.p.hidden = false; UI.scrim.hidden = false;
    document.body.classList.add("chp-open"); UI.btn.setAttribute("aria-expanded", "true");
    refresh();
  }
  function close() {
    if (!S.open) return;
    S.open = false;
    UI.p.hidden = true; UI.scrim.hidden = true;
    mini(false);
    document.body.classList.remove("chp-open"); UI.btn.setAttribute("aria-expanded", "false");
    if (UI.btn) UI.btn.focus({ preventScroll: true });
  }
  function toggle() { if (S.open) close(); else open(); }
  // phones: the sheet becomes a small bar showing the line that carries Undo; a tap on the bar restores the sheet
  function mini(on, idx) {
    if (!UI.p) return;
    S.items.forEach(function (it) { delete it.keep; });
    if (on && idx != null && S.items[idx]) S.items[idx].keep = true;
    UI.log.querySelectorAll(":scope > [data-k]").forEach(function (n, i) { n.classList.toggle("chp-keep", !!(S.items[i] && S.items[i].keep)); });
    var m = !!on && matchMedia("(max-width:767px)").matches && S.open;
    UI.p.classList.toggle("chp-mini", m); UI.scrim.classList.toggle("chp-mini", m); document.body.classList.toggle("chp-mini", m);
    if (m) requestAnimationFrame(function () { document.documentElement.style.setProperty("--chp-bar", UI.p.offsetHeight + "px"); });
  }

  /* ---------- the panel's state: connected, no backend, no model on the backend ---------- */
  function refresh() {
    var c = conn();
    if (!c) { setMode("off"); return; }
    if (S.mode !== "on") setMode("checking");
    checkHealth(c).then(function (ok) {
      if (!S.open) return;
      if (ok === false) setMode("nokey"); else if (ok === null) setMode("down"); else setMode("on");
    });
  }
  function setMode(m) {
    var changed = S.mode !== m; S.mode = m;
    if (changed || !UI.log.childNodes.length) drawLog();
    syncSend();
    if (m === "on") loadSuggestions(); else { S.sugg = []; S.suggKey = null; drawSuggestions(); }
    if (S.open && m === "on" && !matchMedia("(max-width:767px)").matches) UI.in.focus({ preventScroll: true });
  }
  function offHTML(m) {
    if (m === "checking") return '<div class="chp-off"><p>Connecting to the backend…</p></div>';
    if (m === "nokey") return '<div class="chp-off"><p>The connected backend has no model key for Chippy, so it cannot answer yet.</p><p>Start the backend with the OpenRouter key set in its environment (the variable named in its settings), then open Chippy again.</p></div>';
    if (m === "down") return '<div class="chp-off"><p>The backend did not answer. Check that it is still running on this computer, then open Chippy again.</p><p><a href="#/configure">Open Configure</a></p></div>';
    // short lines; the full sentences show on hover, focus or tap (../i1-tip.js)
    return '<div class="chp-off"><p data-tip="Chippy is the guide to ChipIn and your runs: it answers questions about the product and your results, and moves this page to what it is talking about.">Answers questions about ChipIn and your runs.</p>' +
      '<p data-tip="It needs a ChipIn backend running on your computer, which reads your runs and asks the model. This page has none connected, so Chippy cannot answer here. The example runs on this page work without it.">Needs a ChipIn backend; none is connected here.</p>' +
      '<p><a href="#/configure">Set up a backend under Configure</a></p></div>';
  }
  var GREET = "I’m Chippy, your guide to ChipIn. Ask about the product or any of your runs; I can read their results and files, and open the run, tab or design I am talking about. To steer a run’s agent, use its Chat tab.";

  /* ---------- the transcript ---------- */
  function keep() { if (S.items.length > 60) S.items = S.items.slice(-60); ssSet(K_ITEMS, S.items); ssSet(K_CONV, S.conv); }
  function drawLog() {
    var log = UI.log; log.textContent = "";
    if (S.mode !== "on") { log.innerHTML = offHTML(S.mode); return; }
    log.appendChild(el("p", "chp-hi", GREET));
    S.items.forEach(function (it, i) { log.appendChild(itemNode(it, i)); });
    scrollEnd(true);
  }
  function itemNode(it, i) {
    var n;
    if (it.k === "u") n = el("div", "chp-u", it.text);
    else if (it.k === "a") { n = el("div", "chp-a"); renderText(n, it.text, it.ctx || {}); }
    else if (it.k === "t") n = el("div", "chp-t", it.text);
    else if (it.k === "did") {
      n = el("div", "chp-did" + (it.undone ? " undone" : "") + (it.bad ? " bad" : "") + (it.pending ? " pending" : ""));
      if (it.keep) n.classList.add("chp-keep");
      n.appendChild(el("span", null, it.text + (it.undone ? " Undone." : "")));
      if (it.undo && !it.undone && !it.bad && !it.pending) { var u = el("button", "chp-undo"); u.type = "button"; u.dataset.undo = String(i); u.innerHTML = icon("undo"); u.appendChild(document.createTextNode("Undo")); n.appendChild(u); }
    } else if (it.k === "pr") {
      n = el("div", "chp-pr");
      n.appendChild(el("p", null, proposalText(it.p)));
      var row = el("div", "row");
      if (it.state === "open") {
        var go = el("button", "chp-go", it.p.label || "Do it"); go.type = "button"; go.dataset.press = String(i); row.appendChild(go);
        var no = el("button", "chp-no", "Not now"); no.type = "button"; no.dataset.skip = String(i); row.appendChild(no);
      } else row.appendChild(el("span", "res", it.result || ""));
      n.appendChild(row);
    } else if (it.k === "err") {
      n = el("div", "chp-err" + (it.limit ? " lim" : ""), it.text);
      if (it.limit && /conversation/i.test(it.text)) { var f = el("button", "chp-go", "Start a new conversation"); f.type = "button"; f.dataset.fresh = "1"; n.appendChild(f); }
    } else n = el("div", "chp-w", it.text || "");
    n.dataset.k = it.k;
    return n;
  }
  function add(it) { S.items.push(it); var n = itemNode(it, S.items.length - 1); UI.log.appendChild(n); keep(); scrollEnd(); return n; }
  function redraw(i) { var old = UI.log.querySelectorAll(":scope > [data-k]")[i]; if (old) old.replaceWith(itemNode(S.items[i], i)); keep(); }
  function scrollEnd(force) { var l = UI.log; if (force || l.scrollHeight - l.scrollTop - l.clientHeight < 120) l.scrollTop = l.scrollHeight; }

  // plain text with minimal formatting, built from elements; ids of runs and designs become links.
  // A design id belongs to the run named before it in the answer; with none named, to the open run (or the run an action
  // of this turn opened) and only when that run's chart has the design, else it stays plain text.
  function renderText(root, text, ctx) {
    root.textContent = "";
    var blocks = String(text || "").replace(/\r/g, "").split(/\n{2,}/);
    var run = ctx.run || null;
    NAMED = false;
    blocks.forEach(function (b) {
      var lines = b.split("\n").filter(function (l) { return l.trim() !== ""; });
      if (!lines.length) return;
      var isList = lines.every(function (l) { return /^\s*(?:[-*•]|\d+[.)])\s+/.test(l); });
      if (isList) {
        var ul = el("ul");
        lines.forEach(function (l) { var li = el("li"); run = inline(li, l.replace(/^\s*(?:[-*•]|\d+[.)])\s+/, ""), run); ul.appendChild(li); });
        root.appendChild(ul);
      } else {
        var p = el("p");
        lines.forEach(function (l, k) { if (k) p.appendChild(el("br")); run = inline(p, l.replace(/^#{1,6}\s+/, ""), run); });
        root.appendChild(p);
      }
    });
  }
  // a bare design id (no run named in the answer) is linked only when the open run's chart has that design
  var NAMED = false;
  function knownDesign(run, d) {
    var w = where(); if (w.kind !== "live" || w.id !== run) return false;
    if (liveSel(run) === d || inspId() === d) return true;
    try { var st = window.ChipInLive.i1.state(); return !!(st.chart && st.chart.some(function (p) { return p.id === d; })); } catch (e) { return false; }
  }
  function inline(parent, line, run) {
    var re = /\*\*([^*]+)\*\*|`([^`]+)`/g, last = 0, m;
    while ((m = re.exec(line))) {
      if (m.index > last) run = linkify(parent, line.slice(last, m.index), run);
      var n = el(m[1] != null ? "strong" : "code"); run = linkify(n, m[1] != null ? m[1] : m[2], run); parent.appendChild(n);
      last = re.lastIndex;
    }
    if (last < line.length) run = linkify(parent, line.slice(last), run);
    return run;
  }
  function linkify(parent, s, run) {
    var re = /\b(\d{8}-\d{6}-[0-9a-f]{6})\b|\b((?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{12})\b/g, last = 0, m;
    while ((m = re.exec(s))) {
      if (m.index > last) parent.appendChild(document.createTextNode(s.slice(last, m.index)));
      var b = el("button", "chp-lk", m[0]); b.type = "button";
      if (m[1]) { run = m[1]; NAMED = true; b.dataset.run = m[1]; b.title = "Open run " + m[1]; }
      else if (run && (NAMED || knownDesign(run, m[2]))) { b.dataset.design = m[2]; b.dataset.run = run; b.title = "Select design " + m[2]; }
      else { parent.appendChild(document.createTextNode(m[0])); last = re.lastIndex; continue; }
      parent.appendChild(b); last = re.lastIndex;
    }
    if (last < s.length) parent.appendChild(document.createTextNode(s.slice(last)));
    return run;
  }
  function proposalText(p) {
    var b = p.request && p.request.body || {};
    if (p.kind === "start_run") return "Start a new " + cap(String(b.preset || "lite").replace(/^pro$/i, "large")) + " run with this brief:\n" + (b.prompt || "");
    if (p.kind === "message_agent") return "Send this to the agent of run " + shortId(p.run_id) + ":\n" + (b.text || "");
    if (p.kind === "stop_run") return "Stop run " + shortId(p.run_id) + ". What it has done so far stays.";
    return p.label || "A proposed action";
  }
  var cap = function (s) { s = String(s || ""); return s.charAt(0).toUpperCase() + s.slice(1); };

  function onLogClick(e) {
    var t = e.target.closest("button"); if (!t) return;
    if (t.dataset.undo) return undo(+t.dataset.undo);
    if (t.dataset.press) return press(+t.dataset.press);
    if (t.dataset.skip) { var it = S.items[+t.dataset.skip]; it.state = "skipped"; it.result = "Not sent."; redraw(+t.dataset.skip); return; }
    if (t.dataset.fresh) return fresh();
    if (t.dataset.design) return local({ kind: "select_design", run_id: t.dataset.run, design_id: t.dataset.design });
    if (t.dataset.run) return local({ kind: "open_run", run_id: t.dataset.run, tab: "overview" });
  }

  /* ---------- example prompts for the current view ---------- */
  var suggTmo = null;
  function loadSuggestions() {
    var c = conn(); if (!c || S.mode !== "on") return;
    var key = viewKey(); if (key === S.suggKey) return;
    S.suggKey = key;
    var v = view();
    post(c, "/api/helper/suggestions", { view: v }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      if (S.suggKey !== key) return;
      S.sugg = j && Array.isArray(j.suggestions) ? j.suggestions.filter(function (s) { return s && s.label && s.prompt; }).slice(0, 4) : [];
      drawSuggestions();
    }).catch(function () { if (S.suggKey === key) { S.sugg = []; drawSuggestions(); } });
  }
  function drawSuggestions() {
    if (!UI.ex) return;
    UI.ex.textContent = "";
    S.sugg.forEach(function (s, i) { var b = el("button", null, s.label); b.type = "button"; b.dataset.i = String(i); b.dataset.id = s.id || ""; b.title = s.prompt; b.disabled = S.busy; UI.ex.appendChild(b); });
  }
  addEventListener("hashchange", function () {
    if (!S.open) return;
    if (S.mode !== "on" && conn()) { HEALTH.helper = null; refresh(); return; }
    clearTimeout(suggTmo); suggTmo = setTimeout(loadSuggestions, 250);
  });
  // the live module connects after the page loads: an open panel follows it
  try { if (window.ChipInLive && window.ChipInLive.onStatus) window.ChipInLive.onStatus(function () { if (S.open && UI.p) setTimeout(function () { var c = conn(); if (c && S.mode !== "on") { HEALTH.helper = null; refresh(); } else if (!c && S.mode !== "off") setMode("off"); }, 0); }); } catch (e) { /* older reader */ }

  /* ---------- asking: one turn, streamed ---------- */
  function submit() { var t = UI.in.value.trim(); if (!t) return; UI.in.value = ""; fit(); ask(t); }
  function ask(text) {
    text = String(text || "").trim(); if (!text) return;
    if (!S.open) open();
    if (S.busy || S.mode !== "on") return;
    var c = conn(); if (!c) { setMode("off"); return; }
    add({ k: "u", text: text });
    var v = view();
    var turn = { node: null, item: null, tools: [], toolItem: -1, waitN: null, t0: Date.now(), text: "", ctx: { run: v.run_id || null }, timer: null, finish: null, cost: null, model: null };
    S.turn = turn; S.busy = true; syncSend();
    turn.waitN = add({ k: "w", text: "Asking Chippy…" });
    turn.timer = setInterval(function () { if (turn.waitN && turn.waitN.isConnected) turn.waitN.textContent = "Asking Chippy… " + Math.round((Date.now() - turn.t0) / 1000) + " s"; }, 1000);
    var ac = new AbortController(); S.abort = ac;
    var body = { text: text, view: v }; if (S.conv) body.conversation_id = S.conv;
    post(c, "/api/helper/messages", body, ac.signal).then(function (r) {
      if (r.status === 401 || r.status === 403) throw new Error("The backend did not accept this page's token. Reconnect it under Configure.");
      if (r.status === 429) throw new Error("Chippy is still answering in this conversation. Wait for it, or start a new conversation.");
      if (r.status === 503) throw new Error("Chippy is turned off on this backend.");
      if (!r.ok || !r.body) return r.json().catch(function () { return {}; }).then(function (j) { throw new Error(j && j.error ? String(j.error) : "The backend answered " + r.status + "."); });
      var rd = r.body.getReader(), dec = new TextDecoder(), buf = "";
      return (function pump() {
        return rd.read().then(function (x) {
          if (x.done) return;
          buf += dec.decode(x.value, { stream: true });
          var parts = buf.split(/\n\n/); buf = parts.pop();
          parts.forEach(function (chunk) {
            chunk.split("\n").forEach(function (line) {
              if (line.indexOf("data:") !== 0) return;
              var f = null; try { f = JSON.parse(line.slice(5).trim()); } catch (e) { f = null; }
              if (f) frame(turn, f);
            });
          });
          return pump();
        });
      })();
    }).catch(function (e) {
      if (e && e.name === "AbortError") { endText(turn); add({ k: "t", text: "Stopped." }); return; }
      endText(turn);
      add({ k: "err", text: e && e.message && !/fetch|network|load failed/i.test(e.message) ? e.message : "Chippy could not reach the backend. Check that it is still running, then try again." });
    }).then(function () { finishTurn(turn); });
  }
  function dropWait(turn) { if (turn.waitN) { var i = S.items.length - 1; if (S.items[i] && S.items[i].k === "w") { S.items.pop(); } turn.waitN.remove(); turn.waitN = null; clearInterval(turn.timer); keep(); } }
  function endText(turn) { dropWait(turn); turn.node = null; turn.item = null; }
  function frame(turn, f) {
    switch (f.type) {
      case "start": if (f.conversation_id) { S.conv = String(f.conversation_id); keep(); } break;
      case "text":
        dropWait(turn);
        if (!turn.node) { turn.item = { k: "a", text: "", ctx: { run: turn.ctx.run } }; turn.node = add(turn.item); turn.idx = S.items.length - 1; }
        turn.item.text += String(f.delta || "");
        renderText(turn.node, turn.item.text, turn.item.ctx);
        scrollEnd();
        break;
      case "tool":
        dropWait(turn); turn.node = null;
        if (/^(ui_|propose_)/.test(f.name || "")) break; // shown by its own line
        turn.tools.push(toolLabel(f.name, f.ok));
        var txt = "Looked at " + uniq(turn.tools).join(", ");
        if (turn.toolItem >= 0 && turn.toolItem === S.items.length - 1) { S.items[turn.toolItem].text = txt; redraw(turn.toolItem); }
        else { add({ k: "t", text: txt }); turn.toolItem = S.items.length - 1; }
        break;
      case "action": dropWait(turn); turn.node = null; if (f.run_id) turn.ctx.run = f.run_id; perform(f); break;
      case "proposal": dropWait(turn); turn.node = null; add({ k: "pr", p: sanitizeProposal(f), state: "open" }); break;
      case "error": endText(turn); add({ k: "err", text: String(f.message || "Chippy could not answer."), limit: /limit/i.test(String(f.message || "")) }); break;
      case "done": turn.finish = f.finish_reason || null; turn.cost = f.cost_usd; turn.model = f.model; turn.convUsd = f.conversation_usd; break;
    }
  }
  function uniq(a) { return a.filter(function (x, i) { return a.indexOf(x) === i; }); }
  var TOOL_WORDS = {
    list_runs: "your runs", get_run: "the run", get_spec: "the spec", get_stages: "the stages", get_designs: "the designs", get_design: "a design",
    get_chosen: "the chosen chip", get_metrics: "the numbers", get_summaries: "the summaries", get_report: "the report", list_files: "the files",
    read_file: "a file", search_messages: "the messages", compare_runs: "two runs", product_facts: "the fact sheet"
  };
  function toolLabel(n, ok) { return (TOOL_WORDS[n] || String(n || "a tool").replace(/_/g, " ")) + (ok === false ? " (failed)" : ""); }
  function finishTurn(turn) {
    dropWait(turn); clearInterval(turn.timer);
    S.busy = false; S.abort = null; syncSend();
    S.lastTurn = { finish: turn.finish, cost_usd: turn.cost, model: turn.model, conversation_usd: turn.convUsd, ms: Date.now() - turn.t0 };
    S.suggKey = null; loadSuggestions();
  }
  function stopAnswer() { if (S.abort) S.abort.abort(); }
  function fresh() {
    if (S.abort) S.abort.abort();
    S.conv = null; S.items = []; keep(); drawLog();
  }

  /* ---------- proposals: a button, sent only when pressed ---------- */
  function sanitizeProposal(f) {
    var r = f.request || {}, ok = r.method === "POST" && typeof r.path === "string" && /^\/api\/runs(?:\/[A-Za-z0-9._-]+\/(?:messages|stop))?$/.test(r.path);
    return { id: f.id, kind: f.kind, run_id: f.run_id || null, label: String(f.label || "Do it").slice(0, 60), request: ok ? { method: "POST", path: r.path, body: r.body && typeof r.body === "object" ? r.body : {} } : null };
  }
  function press(i) {
    var it = S.items[i], c = conn(); if (!it || it.state !== "open") return;
    if (!it.p.request) { it.state = "failed"; it.result = "This action was not in a form the page can send."; redraw(i); return; }
    if (!c) { it.result = "No backend is connected."; it.state = "failed"; redraw(i); return; }
    it.state = "sending"; it.result = "Sending…"; redraw(i);
    post(c, it.p.request.path, it.p.request.body).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok) throw new Error(j && j.error ? String(j.error) : "The backend answered " + r.status + "."); return j; });
    }).then(function (j) {
      it.state = "done";
      if (it.p.kind === "start_run") {
        it.result = j && j.id ? "Started run " + j.id + "." : "Started.";
        if (j && j.id) { redraw(i); local({ kind: "open_run", run_id: j.id, tab: "overview" }, "Opened the new run."); return; }
      } else if (it.p.kind === "message_agent") it.result = "Sent to the agent.";
      else if (it.p.kind === "stop_run") it.result = "Asked the run to stop.";
      else it.result = "Done.";
      redraw(i);
    }).catch(function (e) { it.state = "failed"; it.result = "Not done: " + (e && e.message ? e.message : "the request failed."); redraw(i); });
  }

  /* ---------- actions: carried out on the page, each with Undo ---------- */
  function snapshot() { var w = where(), ck = clockNow(); return { hash: location.hash || "#/", sel: w.kind === "live" ? liveSel(w.id) : null, run: w.id || null, t: ck && w.kind !== "live" ? ck.t : null }; }
  function local(a, label) { perform(a, label); }
  function perform(a, label) {
    var snap = snapshot(), item = { k: "did", text: label || describe(a), undo: a.kind !== "highlight", snap: snap, a: a, pending: true };
    var idx = S.items.push(item) - 1; var node = itemNode(item, idx); UI.log && UI.log.appendChild(node); keep(); scrollEnd();
    S.lastActionAt = Date.now();
    run(a).then(function (res) {
      item.pending = false;
      if (res && res.bad) { item.bad = true; item.text = res.bad; item.undo = false; redraw(idx); }
      else if (res && res.text) { item.text = res.text; redraw(idx); }
      else redraw(idx);
    }).catch(function () { item.pending = false; item.bad = true; item.text = "Could not do this on the page: " + describe(a).replace(/\.$/, "").toLowerCase() + "."; redraw(idx); });
  }
  function describe(a) {
    var r = a.run_id ? "run " + shortId(a.run_id) : "the run";
    switch (a.kind) {
      case "go_to": return "Went to " + routeName(a.route) + ".";
      case "open_run": return "Opened " + r + (TABS[a.tab] && a.tab !== "overview" ? " on " + TABS[a.tab] : "") + ".";
      case "switch_tab": return "Switched to " + (TABS[a.tab] || "Overview") + ".";
      case "select_design": return "Selected design " + a.design_id + " in " + r + ".";
      case "set_playback": return "Moved the clock of " + r + " to " + clock(a.seconds) + ".";
      case "open_file": return "Opened " + String(a.path || "").split("/").pop() + " from " + r + ".";
      case "new_spec": return "Started a new spec with the brief filled in.";
      case "highlight": return "Pointed at " + (a.label || "an element") + ".";
    }
    return "Changed the view.";
  }
  function routeName(h) {
    var m;
    if (!h || h === "#/" || h === "#") return "the start page";
    if ((m = h.match(/^#\/new\/([1-5]|spec)/))) return m[1] === "spec" ? "Your spec" : "step " + m[1] + " of the guided flow, " + STEPS[m[1]];
    if (/^#\/configure/.test(h)) return "Configure";
    if ((m = h.match(/^#\/run\/([^/]+)\/([a-z]+)/))) return "run " + shortId(m[1]) + ", " + (TABS[m[2]] || "Overview");
    return h;
  }
  function clock(s) { s = Math.max(0, Math.round(+s || 0)); var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = String(s % 60).padStart(2, "0"); return h ? h + ":" + String(m).padStart(2, "0") + ":" + x : m + ":" + x; }
  // a backend run's place on this page: the recorded view if that run is open there, else the live view
  function runHash(id, tab, preferRec) {
    var w = where(), t = TABS[tab] ? tab : "overview";
    if (w.kind === "rec" && w.id === id) return "#/rec/" + w.src + "/" + encodeURIComponent(id) + "/" + t;
    if (preferRec) return "#/rec/mac/" + encodeURIComponent(id) + "/" + t;
    return "#/live/" + encodeURIComponent(id) + "/" + t;
  }
  function pageHash(route) {
    var m = String(route || "").match(/^#\/run\/([A-Za-z0-9._-]+)\/([a-z]+)$/);
    return m ? runHash(m[1], m[2]) : route;
  }
  function goHash(h) {
    if (hashPath() === h.split("?")[0] && location.hash === h) return Promise.resolve();
    location.hash = h;
    return until(function () { return document.querySelector("#main > *"); }, 4000);
  }
  function run(a) {
    switch (a.kind) {
      case "go_to": return goHash(pageHash(a.route));
      case "open_run": return goHash(runHash(a.run_id, a.tab || "overview"));
      case "switch_tab": return goHash(runHash(a.run_id || where().id, a.tab));
      case "select_design": return selectDesign(a.run_id, a.design_id, (String(a.route || "").match(/\/([a-z]+)$/) || [])[1]);
      case "set_playback": return setPlayback(a.run_id, +a.seconds || 0, typeof a.seq === "number" ? a.seq : null);
      case "open_file": return openFile(a.run_id, a.path);
      case "new_spec": return newSpec(a.brief);
      case "highlight": return highlight(a.element_id);
    }
    return Promise.resolve({ bad: "Chippy asked for something this page cannot do." });
  }

  // select a design on the live view: the module's select() when it has one, else the chart's own keys
  function selectDesign(id, design, tab) {
    var L = window.ChipInLive && window.ChipInLive.i1;
    var target = tab && TABS[tab] ? tab : "overview";
    return goHash("#/live/" + encodeURIComponent(id) + "/overview").then(function () {
      if (L && typeof L.select === "function") { L.select(design); return true; }
      return walkChart(design);
    }).then(function (ok) {
      var after = target !== "overview" ? goHash("#/live/" + encodeURIComponent(id) + "/" + target) : Promise.resolve();
      return after.then(function () { return ok ? null : { bad: "Design " + design + " is not on this run's chart, so it was not selected." }; });
    });
  }
  function inspId() { var h = $("#lvInsp h2"); var m = h && h.textContent.match(/^Design\s+(\S+)/); return m ? m[1] : null; }
  function walkChart(design) {
    return until(function () { return $("#lvChart") && inspId(); }, 8000).then(function (ready) {
      if (!ready) return false;
      if (inspId() === design) return true;
      // the chart's keys step through the sized designs, smallest first: go to the smallest, then walk up
      var cv = $("#lvChart"), key = function (k) { cv.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true })); };
      var prev = null, n;
      for (n = 0; n < 400 && inspId() !== prev; n++) { prev = inspId(); key("ArrowLeft"); }
      for (prev = null, n = 0; n < 400; n++) {
        if (inspId() === design) return true;
        prev = inspId(); key("ArrowRight");
        if (inspId() === prev) break;
      }
      return inspId() === design;
    });
  }
  // move the playback clock with the playback module's seek(): fractional seconds as sent, and the
  // event's seq when the action names one (exact: the page shows the state after that event)
  function setPlayback(id, s, seq) {
    var w = where();
    var onBar = function () { return $("#pbTrk") && clockNow(); };
    if (!((w.kind === "rec" || w.kind === "example") && w.id === id && onBar())) {
      return goHash(runHash(id, w.id === id ? w.tab : "overview", true) + "?t=" + s).then(function () {
        return until(onBar, 8000);
      }).then(function (ok) { return ok ? seek(s, seq) : { bad: "This backend does not serve the recorded view of run " + shortId(id) + ", so the clock could not move." }; });
    }
    return Promise.resolve(seek(s, seq));
  }
  function seek(s, seq) {
    var P = window.ChipInPlayback;
    if (!P || typeof P.seek !== "function" || !P.seek(s, seq)) return { bad: "No playback bar is on the page." };
    return null;
  }
  function openFile(id, path) {
    return goHash("#/live/" + encodeURIComponent(id) + "/overview").then(function () {
      return until(function () { return document.querySelector('#lvFiles [data-open="' + CSS.escape(path) + '"], #lvInsp [data-open="' + CSS.escape(path) + '"]'); }, 6000);
    }).then(function (b) {
      if (b) { b.click(); if (document.querySelector(".lv-drawer")) { var at = -1; S.items.forEach(function (it, k) { if (it.a && it.a.kind === "open_file") at = k; }); setTimeout(function () { mini(true, at); }, 0); } return null; }
      return { bad: "The live view does not list " + String(path).split("/").pop() + ", so it was not opened." };
    });
  }
  function newSpec(brief) {
    return goHash("#/").then(function () { return until(function () { return $("#prompt") && $("#go"); }, 4000); }).then(function (ok) {
      if (!ok) return { bad: "The start page did not open, so no spec was started." };
      var ta = $("#prompt"); ta.value = String(brief || ""); ta.dispatchEvent(new Event("input", { bubbles: true }));
      $("#go").click();
      return until(function () { return /^#\/new\/(?:1|ask)/.test(location.hash); }, 12000) /* the loading stage plays first (../i1-intake.js) */.then(function (on) { return on ? null : { bad: "The guided flow did not open." }; });
    });
  }
  var FIND = {
    prompt: ["#prompt"], go: ["#go"], pAg: ["#pAg"], gfH: ["#gfH", ".gfh h1"], tgts: ["#tgts", "#lvHead .tgts"], tchart: ["#tchart", "#lvChart", "#rvChart", ".chartp canvas"],
    ysel: ["#ysel", "#lvY", "#rvY"], legend: ["#legend", "#lvLegend"], insp: ["#insp", "#lvInsp"], alog: ["#alog", "#lvLog"], tiles: ["#tiles", "#lvTiles"],
    clk: ["#clk", "#pbNow"], trk: ["#trk", "#pbTrk"], pbtn: ["#pbtn", "#pbPlay"], chipK: ["#chipK"], sigc: ["#sigc"], feed: ["#feed", "#lvFeed"], msgs: ["#msgs"],
    sendN: ["#sendN"], nopass: ["#nopass"]
  };
  function highlight(id) {
    var list = FIND[id] || ["#" + id], t = null;
    for (var i = 0; i < list.length && !t; i++) { try { var n = document.querySelector(list[i]); if (n && n.getClientRects().length) t = n; } catch (e) { /* bad selector */ } }
    if (!t) return Promise.resolve({ bad: "That part of the page is not on screen here." });
    t.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion:reduce)").matches ? "auto" : "smooth" });
    return wait(350).then(function () {
      var r = t.getBoundingClientRect(), ring = el("div", "chp-ring");
      ring.style.left = r.left - 5 + "px"; ring.style.top = r.top - 5 + "px"; ring.style.width = r.width + 10 + "px"; ring.style.height = r.height + 10 + "px";
      document.body.appendChild(ring); setTimeout(function () { ring.remove(); }, 2700);
      return null;
    });
  }
  // close the page's file drawer the way a user does: its scrim, else its own close button
  function closeFile() {
    var sc = $(".lv-dscrim"), d = $(".lv-drawer");
    if (sc) sc.click(); else if (d) { var x = $(".dh button", d); if (x) x.click(); }
    if ($(".lv-drawer")) { var l = $(".lv-drawer"); l.remove(); var q = $(".lv-dscrim"); if (q) q.remove(); }
    mini(false);
  }
  function undo(i) {
    var it = S.items[i]; if (!it || it.undone || !it.snap) return;
    var s = it.snap, cur = snapshot();
    var back = cur.hash !== s.hash ? goHash(s.hash) : Promise.resolve();
    back.then(function () {
      var w = where();
      if (it.a.kind === "select_design" && w.kind === "live" && w.id === s.run && liveSel(s.run) !== s.sel) {
        if (s.sel) return selectDesign(s.run, s.sel, w.tab);
        // no design was picked before: Home on the chart returns to the page's default (the chosen chip)
        var tab = w.tab;
        return goHash("#/live/" + encodeURIComponent(s.run) + "/overview").then(function () { return until(function () { return $("#lvChart"); }, 6000); }).then(function (cv) {
          if (cv) cv.dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true, cancelable: true }));
          return tab !== "overview" ? goHash("#/live/" + encodeURIComponent(s.run) + "/" + tab) : null;
        });
      }
      if (it.a.kind === "set_playback" && s.t != null && $("#pbTrk")) seek(s.t);
      if (it.a.kind === "open_file") closeFile();
    }).then(function () { it.undone = true; redraw(i); });
  }

  /* ---------- keys ---------- */
  document.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && !e.altKey && (e.key === "/" || e.code === "Slash")) { e.preventDefault(); toggle(); return; }
    if (e.key === "Escape" && S.open && !e.defaultPrevented && !document.querySelector(".pop,.mbg,.drawer,.pb-scrim")) close();
  });

  /* ---------- start ---------- */
  function boot() {
    var st = el("style"); st.id = "chpCss"; st.textContent = STYLE; document.head.appendChild(st);
    mountButton();
  }
  if (document.body) boot(); else document.addEventListener("DOMContentLoaded", boot);

  window.ChipInChippy = {
    version: 1, open: open, close: close, toggle: toggle, ask: ask, view: view,
    state: function () {
      return {
        open: S.open, mode: S.mode, busy: S.busy, conversation: S.conv, suggestions: S.sugg.map(function (s) { return s.id; }),
        items: S.items.map(function (it) { return { k: it.k, text: it.text || (it.p && it.p.label) || "", state: it.state || null, undone: !!it.undone, bad: !!it.bad, pending: !!it.pending, kind: it.a ? it.a.kind : it.p ? it.p.kind : null }; }),
        last: S.lastTurn || null, view: view()
      };
    }
  };
})();
