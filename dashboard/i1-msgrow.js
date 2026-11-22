/* ChipIn message rows: the run log as one row per message, each showing its one-line summary.
 *
 * Classic script, loaded after ../i1-messages.js, which keeps the store (events and summaries) and
 * calls in here while its Stream view is on (the default); its By stage view is the older tree of
 * stage, batch, subagent and group summaries. Nothing is invented: a row shows the backend's item
 * summary of that message or tool call, and until one arrives the message's own first line, lighter.
 *
 *   ChipInMsgRow.paint(M, H)         draw the stream into M.list; returns the number of rows
 *   ChipInMsgRow.controls(M, n)      the bar above the list: view switch, Expand all, Collapse all
 *   ChipInMsgRow.act(M, act, el)     one click on a data-act this module owns; true when handled
 *   ChipInMsgRow.rows(S, H)          the rows of one run store, in event order (for tests)
 *   ChipInMsgRow.withRecorded(base, line, doc)
 *       a recorded run's export plus its per-message summaries file, when its index.json line names
 *       one in "summaries" (data/runs/<id>.summaries.json): its lines become summary events placed right after the message.
 *
 * Who wrote a summary is never blurred: a model-written line carries a small model mark; a line made
 * by a rule (a short message in its own words, a first line when the model gave no answer, a tool
 * call's own command) carries none, and the first two say so in a quiet tag. */
(function () {
  "use strict";

  var SVG = {
    chev: '<path d="M9 6l6 6-6 6"/>',
    msg: '<path d="M4 5h16v11H9l-5 4z"/>',
    tool: '<path d="M4 6l5 5-5 5M12 17h8"/>',
    lab: '<rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4"/>',
    file: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
    chosen: '<path d="M5 12.5l4.5 4.5L19 7"/>',
    error: '<path d="M6 6l12 12M18 6L6 18"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
    spark: '<path d="M12 3l1.9 5.6L19.5 10.5l-5.6 1.9L12 18l-1.9-5.6L4.5 10.5l5.6-1.9z"/>'
  };
  var ico = function (n, c) { return '<svg class="cm-i ' + (c || "") + '" viewBox="0 0 24 24" aria-hidden="true">' + SVG[n] + "</svg>"; };
  var KIND = {
    msg: ["msg", "var(--c-lead,#6b46c1)", "Message"], user: ["user", "var(--blue7,#2b55d0)", "Your message"],
    tool: ["tool", "var(--blue7,#2b55d0)", "Tool call"], lab: ["lab", "var(--c-chip,#a04812)", "Chip lab call"],
    file: ["file", "var(--i600,#4a5062)", "File written"], chosen: ["chosen", "var(--okt,#047857)", "Chip chosen"], error: ["error", "var(--missed,#c2362b)", "Error"]
  };
  var STAGE_N = { spec: "Spec", reference: "Reference", propose: "Propose", finetune: "Fine-tune", compile: "Compile", verify: "Verify", report: "Report" };
  var eSeq = function (c) { if (typeof c === "number") return c; var m = /^e?(\d+)$/.exec(c == null ? "" : String(c)); return m ? +m[1] : null; };

  /* ---------------- rows ---------------- */
  // the event seqs a summary is about: its covers, or one message it names (a tolerant reader)
  function covers(s) {
    var out = [];
    (Array.isArray(s.covers) ? s.covers : []).concat([s.ref, s.of, s.message, s.message_seq, s.event]).forEach(function (c) { var q = eSeq(c); if (q != null && out.indexOf(q) < 0) out.push(q); });
    return out;
  }
  var isModel = function (s) { return !!s && s.source === "model"; };
  // a summary written inside the message event itself (a tool's "summary" is its command, not a summary)
  function inline(e) {
    if (!e || e.type !== "message") return null;
    var x = e.summary || e.llm_summary;
    if (typeof x === "string" && x.trim()) return { text: x.trim(), source: e.summary_source || "model", seq: e.seq };
    if (x && typeof x === "object" && typeof x.text === "string") return { text: x.text, source: x.source || "model", seq: e.seq };
    return null;
  }
  function rows(S, H) {
    var best = {};
    Object.keys(S.sums).forEach(function (id) {
      var s = S.sums[id].s; if (s.level !== "item") return;
      covers(s).forEach(function (q) {
        var rk = S.eToRaw[q]; if (!rk) return;
        var o = best[rk];
        if (!o || (isModel(s) && !isModel(o)) || (isModel(s) === isModel(o) && (s.seq || 0) >= (o.seq || 0))) best[rk] = s;
      });
    });
    var ui = S.ui, out = [];
    S.rawOrder.forEach(function (rk) {
      var r = S.raw[rk];
      if (!r || r.kind === "metric") return; // figures live in the Chip view; the stream is what the agents wrote and did
      if (ui.stage && r.stage !== ui.stage) return;
      if (ui.agent && (ui.agent === "-" ? !!r.agent : r.agent !== ui.agent)) return;
      var e = S.ev[r.first] || {}, s = best[rk] || inline(e);
      out.push({ id: rk, level: "item", raw: r, raws: [rk], sum: s, seqs: r.seqs.slice(), agent: r.agent, stage: r.stage, k: r.first, last: r.last });
    });
    return out;
  }

  /* ---------------- one row ---------------- */
  function who(S, r) {
    if (r.kind === "user") return { t: "You", tip: "Your message", c: "cm-mr-you" };
    if (!r.agent) return { t: "ChipIn", tip: "ChipIn, the lead agent", c: "cm-mr-lead" };
    var sb = S.subs[r.agent] || {};
    return { t: sb.name || r.agent, tip: "Subagent " + r.agent + (sb.name ? ", " + sb.name : "") + (sb.strategy ? "\n" + String(sb.strategy).replace(/^Strategy:\s*/i, "") : ""), c: "cm-mr-sub" };
  }
  // the row already names who wrote it, so a summary that opens with the same name drops it
  function bare(t, w, s) {
    var names = [w.t, s.author, w.t === "You" ? "User:" : null].filter(Boolean), x = String(t);
    for (var i = 0; i < names.length; i++) {
      var nm = names[i];
      if (x.indexOf(nm) === 0 && /^[\s:,]/.test(x.charAt(nm.length) || "") && x.length > nm.length + 3) { x = x.slice(nm.length).replace(/^[\s:,]+/, ""); return x.charAt(0).toUpperCase() + x.slice(1); }
    }
    return x;
  }
  function openOf(S, id) { var ui = S.ui; if (!ui.rows) ui.rows = {}; return ui.rows[id] != null ? ui.rows[id] : !!ui.allOpen; }
  function rowHTML(M, H, n, open) {
    var S = M.S, r = n.raw, kind = r.kind, K = KIND[kind] || KIND.msg, s = n.sum, w = who(S, r), esc = H.esc;
    var tool = kind === "tool" || kind === "lab", text, cls = "", tag = "", lead = "", mark = "", pend = false;
    if (s && s.text) {
      text = bare(H.sumText(S, n), w, s);
      if (isModel(s)) mark = '<span class="cm-mr-ai" title="Summary written by a model">' + ico("spark") + '<span class="cm-vh">Model summary</span></span>';
      else if (tool) cls = " cm-mr-rule";
      else if (kind !== "msg" && kind !== "error") { /* your own message, a file, a chosen chip: the line is the event itself */ }
      else if (s.source === "fallback") tag = '<span class="cm-mr-tag" title="The model gave no answer for this message, so this is its own first line">first line</span>';
      else tag = '<span class="cm-mr-tag" title="A short message, shown in its own words; no model summary was needed">as written</span>';
    } else {
      text = H.itemFirst(S, r);
      if (tool) { cls = " cm-mr-rule"; text = String(r.call || text); }
      else if (kind === "msg" && !S.finished) pend = true;
      else if (kind === "msg") tag = '<span class="cm-mr-tag" title="No summary was written for this message; this is its own first line">first line</span>';
    }
    if (tool) {
      var nm = kind === "lab" ? (/\bchiplab\s+([a-z][a-z0-9-]*)/.exec(r.call || "") || [])[1] : r.name;
      nm = kind === "lab" ? "chiplab " + (nm || "") : nm || "Tool";
      if (text.indexOf(nm) !== 0) lead = '<b class="cm-mr-tn">' + esc(nm) + "</b>";
      var st = r.state === "done" ? "" : r.state === "failed" ? '<span class="cm-fail">failed</span>' : S.finished ? '<span class="cm-fail cm-mute">no result</span>' : '<span class="cm-spin cm-sm" title="Running"></span>';
      lead += st;
    }
    var t = H.rel(S, n.k); // when it started, so times run down the list
    var label = w.t + ", " + K[2].toLowerCase() + ": " + text;
    return {
      html: H.ico("chev", "cm-chev") +
        '<span class="cm-gl" style="--k:' + K[1] + '" title="' + K[2] + '">' + ico(K[0]) + "</span>" +
        '<span class="cm-mr-main"><span class="cm-mr-who ' + w.c + '" title="' + esc(w.tip) + '">' + esc(w.t) + "</span>" + lead +
        '<span class="cm-mr-tx' + cls + (pend ? " cm-pend" : "") + '">' + (pend ? '<span class="cm-pd" aria-hidden="true"></span><span class="cm-vh">Summary on its way; first line: </span>' : "") + esc(text) + mark + tag + "</span></span>" +
        '<span class="cm-meta"><span class="cm-t">' + esc(t) + "</span></span>",
      cls: "cm-k-" + kind + (r.state === "failed" ? " cm-failed" : "") + (pend ? " cm-mr-pending" : ""),
      label: label
    };
  }

  /* ---------------- the full message, below an open row ---------------- */
  function pretty(t) {
    var s = String(t == null ? "" : t), x = s.trim();
    if (/^[[{]/.test(x)) { try { return { t: JSON.stringify(JSON.parse(x), null, 2), json: true }; } catch (e) { /* not JSON */ } }
    return { t: s, json: false };
  }
  function block(H, t, cls) { return '<pre class="cm-pre cm-mr-pre' + (cls ? " " + cls : "") + '" tabindex="0">' + H.esc(t) + "</pre>"; }
  // prose as written; fenced code and whole-JSON messages in monospace
  function prose(H, text) {
    var s = String(text == null ? "" : text), p = pretty(s);
    if (p.json) return block(H, p.t, "cm-json");
    return s.split(/```[a-zA-Z0-9_-]*\n?/).map(function (part, i) {
      if (i % 2) return block(H, part.replace(/\n$/, ""));
      return part.trim() ? '<div class="cm-mr-prose" tabindex="0">' + H.esc(part.replace(/^\n+|\n+$/g, "")) + "</div>" : "";
    }).join("");
  }
  function sec(H, title, seq, inner) { return '<div class="cm-sec"><h4>' + H.esc(title) + (seq != null ? "<span>event " + seq + "</span>" : "") + "</h4>" + inner + "</div>"; }
  function bodyHTML(M, H, n) {
    var S = M.S, r = n.raw, w = who(S, r), out = [];
    var evs = n.seqs.slice().sort(function (a, b) { return a - b; }).map(function (q) { return S.ev[q]; }).filter(Boolean);
    if (n.sum && n.sum.text && !isModel(n.sum) && (r.kind === "msg" || r.kind === "error")) out.push('<p class="cm-mr-note">' + (n.sum.source === "fallback" ? "The model gave no answer for this message; the row shows its first line." : "A short message: the row shows it in its own words, not a model summary.") + "</p>");
    if (r.kind === "tool" || r.kind === "lab") {
      var call = null, done = null;
      evs.forEach(function (e) { if (e.type !== "tool") return; if (e.state === "started") call = call || e; else done = e; });
      var c = call || done || {};
      out.push(sec(H, "Call: " + (c.name || r.name || "Tool") + ", by " + w.t, c.seq, block(H, c.summary || r.call || "(no arguments recorded)")));
      if (done) { var p = pretty(done.detail); out.push(sec(H, done.state === "failed" ? "Result, failed" : "Result", done.seq, done.detail ? block(H, p.t, p.json ? "cm-json" : "") : '<p class="cm-mute">No output was recorded.</p>')); }
      else out.push('<p class="cm-mute">' + (S.finished ? "No result was recorded for this call." : "Still running.") + "</p>");
    } else {
      evs.forEach(function (e) {
        if (e.type === "message") out.push(sec(H, e.role === "user" ? "Your message" : w.tip.split("\n")[0], e.seq, prose(H, e.text)));
        else if (e.type === "artifact") out.push(sec(H, "File written by " + w.t, e.seq, block(H, [e.path || e.name || "", e.kind ? "kind: " + e.kind : ""].filter(Boolean).join("\n"))));
        else if (e.type === "chosen") out.push(sec(H, "Chip chosen", e.seq, block(H, "chip " + (e.chip || ""))));
        else if (e.type === "error") out.push(sec(H, "Error", e.seq, prose(H, e.message || e.text || "")));
      });
    }
    if (!evs.length) out.push('<p class="cm-mute">The events of this row have not reached this page.</p>');
    else out.push('<button type="button" class="cm-rawb" data-act="raw" aria-expanded="false">Show the raw events</button><div class="cm-raw" hidden>' + block(H, evs.map(function (e) { return JSON.stringify(e, null, 2); }).join("\n\n"), "cm-json") + "</div>");
    return out.join("");
  }

  /* ---------------- drawing the stream ---------------- */
  function drawRow(M, H, el, n) {
    var S = M.S, open = openOf(S, n.id), head = rowHTML(M, H, n, open);
    var row = el.firstElementChild;
    if (!row || row.tagName !== "BUTTON") { row = document.createElement("button"); row.type = "button"; el.insertBefore(row, el.firstChild); }
    if (row._h !== head.html) { row.innerHTML = head.html; row._h = head.html; }
    row.className = "cm-row cm-mr " + head.cls;
    row.setAttribute("data-act", "mrow");
    row.setAttribute("aria-expanded", String(open));
    row.setAttribute("aria-label", head.label);
    el.className = "cm-n cm-n-mr" + (n.raw.kind === "user" ? " cm-n-mryou" : "");
    el.setAttribute("role", "listitem");
    var box = row.nextElementSibling;
    if (!open) { if (box) el.removeChild(box); return; }
    var key = n.seqs.join(",") + "|" + n.raw.state + "|" + (n.raw.detail || "").length + "|" + (n.sum ? n.sum.source + (n.sum.seq || "") : "") + "|" + S.finished;
    if (!box || box._k !== key) {
      var nb = document.createElement("div"); nb.className = "cm-body cm-mr-body"; nb.innerHTML = bodyHTML(M, H, n); nb._k = key;
      if (box) { var rawOpen = box.querySelector(".cm-raw:not([hidden])"); el.replaceChild(nb, box); if (rawOpen) { var b = nb.querySelector(".cm-rawb"); if (b) b.click(); } } else el.appendChild(nb);
    }
  }
  function divider(H, st) { return '<span class="cm-mr-dl">' + H.esc(STAGE_N[st] || st) + "</span>"; }
  function paint(M, H) {
    var S = M.S, list = rows(S, H), box = M.list, have = {}, keep = {}, c, i, idx = 0, prev = null;
    if (box.querySelector(":scope > .cm-n:not(.cm-n-mr):not(.cm-mr-div)")) box.innerHTML = ""; // coming from the By stage tree
    box.setAttribute("role", "list"); box.setAttribute("aria-label", "Run messages, one row each");
    for (c = box.firstElementChild; c; c = c.nextElementSibling) if (c.dataset && c.dataset.id) have[c.dataset.id] = c;
    var place = function (el) { var at = box.children[idx]; if (at !== el) box.insertBefore(el, at || null); idx++; };
    list.forEach(function (n) {
      if (n.stage && n.stage !== prev) {
        var did = "st:" + n.stage + ":" + n.id, d = have[did];
        if (!d) { d = document.createElement("div"); d.dataset.id = did; d.className = "cm-n cm-mr-div"; d.setAttribute("role", "presentation"); d.innerHTML = divider(H, n.stage); }
        keep[did] = 1; place(d);
      }
      prev = n.stage || prev;
      var el = have[n.id];
      if (!el) { el = document.createElement("div"); el.dataset.id = n.id; }
      keep[n.id] = 1; drawRow(M, H, el, n); place(el);
    });
    for (i = box.children.length - 1; i >= 0; i--) { c = box.children[i]; if (!keep[c.dataset.id]) box.removeChild(c); }
    M.mrCount = list.length;
    return list.length;
  }
  function controls(M, n) {
    var S = M.S, flat = S.ui.view !== "tree";
    var sw = '<span class="cm-mr-sw" role="group" aria-label="How the log is shown">' +
      '<button type="button" class="cm-lv' + (flat ? " on" : "") + '" data-act="mview" data-view="stream" aria-pressed="' + flat + '" title="One row per message, each with its one-line summary">Messages</button>' +
      '<button type="button" class="cm-lv' + (!flat ? " on" : "") + '" data-act="mview" data-view="tree" aria-pressed="' + !flat + '" title="Summaries by stage, subagent and group">By stage</button></span>';
    if (!flat) return sw;
    var any = S.ui.allOpen || Object.keys(S.ui.rows || {}).some(function (k) { return S.ui.rows[k]; });
    return sw + '<span class="cm-mr-n">' + (n != null ? n + (n === 1 ? " row" : " rows") : "") + "</span>" +
      '<span class="cm-mr-bt"><button type="button" class="cm-lv cm-mr-all" data-act="mall" data-open="1"' + (S.ui.allOpen && !Object.keys(S.ui.rows || {}).length ? ' aria-pressed="true"' : "") + ">Expand all</button>" +
      '<button type="button" class="cm-lv cm-mr-all" data-act="mall" data-open="0"' + (any ? "" : ' aria-pressed="true"') + ">Collapse all</button></span>";
  }
  function act(M, a, t) {
    var ui = M.S.ui;
    if (!ui.rows) ui.rows = {};
    if (a === "mrow") { var id = t.closest(".cm-n").getAttribute("data-id"); ui.rows[id] = t.getAttribute("aria-expanded") !== "true"; M.keepFocus = id; return true; }
    if (a === "mall") { ui.allOpen = t.getAttribute("data-open") === "1"; ui.rows = {}; return true; }
    if (a === "mview") { ui.view = t.getAttribute("data-view") === "tree" ? "tree" : "stream"; ui.level = null; return true; }
    return false;
  }

  /* ---------------- a recorded run's per-message summaries file ---------------- */
  function withRecorded(base, line, doc) {
    if (!doc || !Array.isArray(doc.events) || !line || typeof line.summaries !== "string") return Promise.resolve(doc);
    return fetch(base + line.summaries, { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var m = j && j.messages && typeof j.messages === "object" ? Object.keys(j.messages).map(function (k) { return j.messages[k]; }) : null;
        var list = !j ? [] : Array.isArray(j) ? j : m || j.summaries || j.items || j.events || [];
        if (!list.length) return doc;
        var bySeq = {}, idOf = {}, maxSeq = 0;
        doc.events.forEach(function (e) {
          if (typeof e.seq === "number" && e.seq > maxSeq) maxSeq = e.seq;
          if (e.type !== "summary") bySeq[e.seq] = e;
          else if (e.level === "item") covers(e).forEach(function (q) { if (!idOf[q]) idOf[q] = e.id; });
        });
        var add = [];
        list.forEach(function (x) {
          if (!x || typeof x.text !== "string" || !x.text.trim() || (x.source && x.source !== "model")) return;
          var cv = covers(x); if (!cv.length) return;
          var at = Math.max.apply(null, cv), on = bySeq[at]; if (!on) return;
          add.push({ seq: maxSeq + 1 + add.length, ts: on.ts, run_id: on.run_id, type: "summary", id: idOf[cv[0]] || x.id || "i" + at, level: "item", covers: cv.map(function (q) { return "e" + q; }), agent: x.agent || on.agent, stage: x.stage, text: x.text.trim(), model: x.model || j.model, final: true, source: "model", at: at });
        });
        if (add.length) doc.events = doc.events.concat(add);
        doc.msgSummaries = add.length;
        return doc;
      })
      .catch(function () { return doc; });
  }

  /* ---------------- styles ---------------- */
  var css = document.createElement("style");
  css.textContent = [
    ".cm-row.cm-mr{grid-template-columns:12px 16px minmax(0,1fr) auto;min-height:30px;padding:5px 6px}",
    ".cm-mr-main{display:flex;align-items:baseline;gap:7px;min-width:0}",
    ".cm-mr-who{flex:none;max-width:118px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;font-weight:600;line-height:17px;padding:0 6px;border-radius:4px;background:var(--i100,#f1f2f6);color:var(--i700,#3a4052)}",
    ".cm-mr-lead{background:color-mix(in srgb,var(--c-lead,#6b46c1) 11%,transparent);color:var(--c-lead,#6b46c1)}",
    ".cm-mr-you{background:#e8eefc;color:var(--blue7,#2b55d0)}",
    ".cm-mr-tn{flex:none;font-weight:600;color:var(--i800,#262c40);white-space:nowrap}",
    ".cm-mr-tx{min-width:0;flex:0 1 auto;color:var(--i900,#141a2e);line-height:1.45;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow-wrap:anywhere}",
    ".cm-mr-tx.cm-mr-rule{font-family:var(--mono,ui-monospace,monospace);font-size:11.5px;color:var(--i700,#3a4052);-webkit-line-clamp:1}",
    ".cm-mr-tx.cm-pend{color:var(--i550,#555b6d)}",
    ".cm-row.cm-mr[aria-expanded=true] .cm-mr-tx{-webkit-line-clamp:unset}",
    ".cm-mr-ai{display:inline-flex;margin-left:5px;vertical-align:0;color:var(--c-model,#2b55d0);opacity:.75}.cm-mr-ai .cm-i{width:10px;height:10px;fill:currentColor;stroke:none}",
    ".cm-mr-tag{margin-left:7px;font-size:10.5px;color:var(--i550,#555b6d);white-space:nowrap}",
    ".cm-row.cm-mr .cm-meta{padding-top:1px}",
    ".cm-row.cm-mr .cm-chev{margin-top:4px}",
    ".cm-mr-div{display:flex;align-items:center;gap:8px;margin:10px 0 2px;padding:0 6px;font-size:10.5px;font-weight:650;letter-spacing:.06em;text-transform:uppercase;color:var(--i550,#555b6d)}",
    ".cm-mr-div:first-child{margin-top:2px}.cm-mr-div::after{content:'';flex:1;height:1px;background:var(--hair,rgb(0 0 0/.07))}",
    ".cm-mr-body{margin-left:36px}",
    ".cm-mr-body .cm-sec h4{flex-wrap:wrap}",
    ".cm-mr-prose{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.55;color:var(--i900,#141a2e);max-height:26em;overflow:auto;padding:2px 2px 4px}",
    ".cm-mr-pre{max-height:24.5em}",
    ".cm-mr-prose+.cm-pre,.cm-pre+.cm-mr-prose{margin-top:6px}",
    ".cm-mr-note{margin:2px 0 8px;font-size:11.5px;color:var(--i550,#555b6d)}",
    ".cm-mr-sw{display:inline-flex;gap:10px}",
    ".cm-mr-n{font-size:11px;color:var(--i550,#555b6d);font-variant-numeric:tabular-nums}",
    ".cm-mr-bt{margin-left:auto;display:inline-flex;gap:10px}",
    ".cm-mr-all[aria-pressed=true]{color:var(--i550,#555b6d)}",
    ".cm-ladder:has(.cm-mr-sw){align-items:center}",
    ".cm-mr-pre:focus-visible,.cm-mr-prose:focus-visible{outline:2px solid var(--blue7,#2b55d0);outline-offset:1px}",
    ".cm-mr-gap{width:4px}",
    "@container (max-width:400px){.cm-row.cm-mr .cm-t{display:inline;min-width:0}.cm-row.cm-mr{grid-template-columns:10px 14px minmax(0,1fr) auto;gap:6px}.cm-mr-main{flex-wrap:wrap;row-gap:2px}.cm-mr-tx{flex-basis:100%}.cm-mr-who{max-width:150px}.cm-mr-body{margin-left:10px}}",
    ".cm-panel .cm-mr-n{display:none}"
  ].join("\n");
  document.head.appendChild(css);

  window.ChipInMsgRow = { paint: paint, controls: controls, act: act, rows: rows, withRecorded: withRecorded, version: 1 };
})();
