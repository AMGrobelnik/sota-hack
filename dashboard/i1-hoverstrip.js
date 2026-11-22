/*
 * i1-hoverstrip.js: two small additions to real runs (backend and recorded), copied from the examples.
 * Defines window.ChipInHoverStrip.
 *
 *   chart(cv, pts, get)  the replay's designs chart (../i1-playback.js): hover or tap a dot for its details, in the
 *                        examples' tooltip (.ctip). pts = [{ x, y, id }] as drawn; get() returns the current model.
 *   more(d, T, spec)     extra lines for the live view's existing tooltip (../i1-live.js): basis, specificity when it
 *                        is not a target, compiled and verified.
 *   strip(tilesEl, m)    the examples' green summary strip (../i1-summary.js markup and CSS) above a finished run's
 *                        tiles, from that run's chosen chip; cost and battery from ChipInWhyChip's ChipInModels path.
 * Every caller wraps its call in try/catch, so nothing here can stop the page's own render.
 */
(function () {
  "use strict";
  var F = function () { return window.ChipInFold; };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  var num = function (v) { return typeof v === "number" && isFinite(v) ? v : null; };
  var fmt = function (n) { return Math.round(n).toLocaleString("en-GB"); };
  var lc = function (s) { return String(s).toLowerCase(); };
  var onB = function (b) { return b === "validation" ? "on validation" : b === "test" ? "on the test set" : ""; };

  /* ---------- tooltip lines, shared by both charts ---------- */
  function checkLine(d) {
    var vf = d && d.verified && typeof d.verified === "object" ? d.verified : null, comp = d && num(d.gates) > 0;
    if (!comp) return "Not compiled to gates yet";
    if (!vf) return "Compiled to gates, not verified yet";
    if (num(vf.mismatches) > 0) return "Compiled; " + fmt(vf.mismatches) + " mismatches against its model";
    return "Compiled and verified" + (num(vf.vectors) != null ? ", " + fmt(vf.vectors) + " vectors" : "") + (num(vf.mismatches) === 0 ? ", 0 mismatches" : "");
  }
  function metricLine(k, d, spec, T) {
    var Fd = F(), v = d && d.metrics ? num(d.metrics[k]) : null;
    if (v == null) return "";
    var t = (T || []).filter(function (x) { return x.metric === k; })[0], ok = t ? Fd.meets(t, v) : null;
    return esc(Fd.metaOf(k).n) + ": " + esc(Fd.fmtV(k, v, spec)) + (t ? " (target " + esc(Fd.fmtT(t, spec)) + (ok === true ? ", pass" : ok === false ? ", fail" : "") + ")" : "");
  }
  function passLine(d, T) {
    var Fd = F(); if (!T || !T.length) return "";
    if (Fd.passAll(T, d)) return "Passes every target";
    var miss = T.filter(function (t) { return Fd.meets(t, d.metrics ? num(d.metrics[t.metric]) : null) === false; });
    return miss.length ? "Fails " + esc(miss.map(function (t) { return lc(Fd.metaOf(t.metric).n); }).join(" and ")) : "Not every target has a figure";
  }
  // the live tooltip already names the design, its size, the target figures and pass or fail
  function more(d, T, spec) {
    if (!d || !F()) return "";
    var keys = (T || []).map(function (t) { return t.metric; }), out = [];
    if (keys.indexOf("specificity") < 0) { var s = metricLine("specificity", d, spec, null); if (s) out.push(s); }
    if (onB(d.basis)) out.push("Figures " + onB(d.basis));
    out.push(checkLine(d));
    return '<span style="display:block;white-space:normal">' + out.join("<br>") + "</span>"; // wraps inside the tooltip's width
  }
  function tipHTML(d, M, files) {
    var Fd = F(), sz = Fd.sizeOf(d), nm = Fd.chipName ? Fd.chipName(M.f, d.id, { files: files }).name : d.id, lines = [];
    lines.push(sz ? (sz.m ? fmt(sz.g) + " gates, measured" : "about " + fmt(sz.g) + " gates, estimated") : "size not reported");
    var keys = ["sensitivity", "specificity"];
    (M.T || []).forEach(function (t) { if (keys.indexOf(t.metric) < 0) keys.push(t.metric); });
    keys.forEach(function (k) { var l = metricLine(k, d, M.spec, M.T); if (l) lines.push(l); });
    if (onB(d.basis)) lines.push("Figures " + onB(d.basis));
    var p = passLine(d, M.T); if (p) lines.push(p);
    lines.push(checkLine(d));
    if (M.chosen && M.chosen.id === d.id) lines.push("Chosen chip");
    return "<b>" + esc(nm) + "</b>" + lines.join("<br>");
  }

  /* ---------- the replay chart's hover ---------- */
  function chart(cv, pts, get, files) {
    if (!cv) return;
    cv._hsPts = pts || []; cv._hsGet = get; cv._hsFiles = files;
    if (cv._hsOn) return;
    cv._hsOn = true;
    var wrap = cv.parentNode, tip = document.createElement("div");
    tip.className = "ctip"; tip.setAttribute("role", "tooltip"); tip.style.whiteSpace = "normal"; tip.style.width = "max-content"; tip.style.maxWidth = "min(280px, calc(100% - 8px))"; wrap.appendChild(tip);
    var hit = function (e) {
      var r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top, best = null, bd = e.pointerType === "mouse" ? 13 : 20;
      cv._hsPts.forEach(function (p) { var dd = Math.hypot(p.x - x, p.y - y); if (dd < bd) { bd = dd; best = p; } });
      return best;
    };
    var hide = function () { tip.style.display = "none"; cv.style.cursor = "default"; };
    var show = function (e) {
      var p = hit(e), M = p && cv._hsGet ? cv._hsGet() : null, d = M && M.f && M.f.designs ? M.f.designs[p.id] : null;
      if (!d) { hide(); return; }
      tip.innerHTML = tipHTML(d, M, cv._hsFiles);
      tip.style.display = "block"; cv.style.cursor = "pointer";
      var Wd = cv.clientWidth, tw = tip.offsetWidth, th = tip.offsetHeight;
      tip.style.left = Math.max(4, Math.min(Wd - tw - 4, p.x + 12)) + "px";
      tip.style.top = (p.y - th - 10 >= 4 ? p.y - th - 10 : p.y + 14) + "px";
    };
    var safe = function (fn) { return function (e) { try { fn(e); } catch (x) { console.error(x); hide(); } }; };
    cv.addEventListener("pointermove", safe(function (e) { if (e.pointerType === "mouse") show(e); }));
    cv.addEventListener("pointerleave", safe(function (e) { if (e.pointerType === "mouse") hide(); }));
    cv.addEventListener("pointerdown", safe(function (e) { if (e.pointerType !== "mouse") show(e); }));
    document.addEventListener("pointerdown", function (e) { if (e.target !== cv && tip.isConnected) hide(); }, true);
  }

  /* ---------- the summary strip on a finished run ---------- */
  function strip(tiles, m) {
    if (!tiles || !tiles.parentNode) return;
    var el = document.getElementById("hsStrip");
    if (!el) { el = document.createElement("div"); el.id = "hsStrip"; el.style.marginBottom = "12px"; tiles.parentNode.insertBefore(el, tiles); }
    var sig = [m.ended ? 1 : 0, m.chosenId || "", m.n, m.final ? 1 : 0].join("|");
    if (el.dataset.sig === sig) return;
    el.dataset.sig = sig;
    var h = "";
    try { h = m.ended && m.chosenId ? stripHTML(m) : ""; } catch (x) { console.error(x); h = ""; }
    el.innerHTML = h; el.hidden = !h;
  }
  function stripHTML(m) {
    var Fd = F(), WC = window.ChipInWhyChip, S = window.ChipInSummary, f = m.f;
    if (!Fd || !f || !WC || !WC.gatesOf || !S) return "";
    var rec = f.designs[m.chosenId] || null, T = m.T || [], spec = m.spec;
    var g = WC.gatesOf(f, rec || { id: m.chosenId }), ge = rec && num(rec.gates_est) > 0 ? rec.gates_est : null;
    if (g == null && ge == null) return "";
    var val = function (t) { return rec && rec.metrics ? num(rec.metrics[t.metric]) : null; };
    var miss = [], ok = [], none = [];
    T.forEach(function (t) { var v = val(t), r = Fd.meets(t, v); (r === true ? ok : r === false ? miss : none).push({ t: t, v: v, held: false }); });
    // a target the chosen chip misses on the held-out patients counts as a miss, as the page's tiles and headline say
    var hd = rec && rec.basis !== "test" ? Fd.heldOut(f, m.chosenId, m.final) : null;
    if (hd) T.forEach(function (t) { var v = num(hd.pooled[t.metric]); if (v != null && Fd.meets(t, v) === false) miss.push({ t: t, v: v, held: true }); });
    var pass = T.length > 0 && !miss.length && ok.length === T.length;
    var nm = function (t) { return lc(Fd.metaOf(t.metric).n); }, tgt = function (t) { return Fd.fmtT(t, spec).replace(/^at (least|most) /, ""); };
    var cells = [], cell = function (l, v, c) { return '<div class="sm-c' + (c ? " " + c : "") + '"><span class="sm-l">' + l + '</span><span class="sm-v">' + v + "</span></div>"; };
    var size = g != null ? fmt(g) + " <small>gates</small>" : '<span class="est" title="Estimated by the agent; the chip lab has not compiled it">' + fmt(ge) + "</span> <small>gates, estimated</small>";
    cells.push(cell(pass ? "Recommended chip" : "Chosen chip", size, "chip"));
    var verdict;
    if (!T.length) verdict = '<span class="pf na">No targets set</span>';
    else if (pass) verdict = '<span class="pf ok">Passes all your targets</span>' + (onB(rec && rec.basis) ? " <small>" + onB(rec.basis) + "</small>" : "");
    else if (miss.length === 1) verdict = '<span class="pf no">Fails ' + esc(nm(miss[0].t)) + "</span> " + esc(Fd.fmtV(miss[0].t.metric, miss[0].v, spec)) + " <small>" + (miss[0].held ? "held-out, " : "") + "target " + esc(tgt(miss[0].t)) + "</small>";
    else if (miss.length) verdict = '<span class="pf no">Fails</span> ' + esc(miss.map(function (x) { return nm(x.t) + (x.held ? " (held-out)" : ""); }).join(", "));
    else verdict = '<span class="pf na">Not measured</span> <small>no figure for ' + esc(none.map(function (x) { return nm(x.t); }).join(", ")) + "</small>";
    cells.push(cell("Your targets", verdict, "tg"));
    // cost and battery: the Why this chip card's ChipInModels path, only for a compiled chip the battery model covers
    var kind = WC.kindOf(spec), ch = WC.chansOf(spec, rec), P = window.ChipInModels && kind && ch && g != null ? WC.power(kind, ch, g) : null;
    if (P) {
      var est = function (t, k) { return '<span class="est" title="' + esc(window.ChipInModels.describeEstimate(k)) + '">' + t + "</span>"; };
      cells.push(cell("Estimated cost", est("$" + WC.cost(g, P.cls.class).unit_cost.toFixed(2), "cost") + " <small>per unit</small>"));
      var c = P.cls, days = c.life_days, life = days >= 2 ? fmt(days) + " days" : (days * 24).toFixed(1) + " hours";
      var bx = c.class === "primary coin cell" ? [life, "on a coin cell"] : c.class === "rechargeable lithium" ? [life, "per charge, rechargeable"] : ["Larger pack", "or mains"];
      cells.push(cell("Estimated battery", est(esc(bx[0]), "battery_life") + " <small>" + esc(bx[1]) + "</small>"));
    }
    // main risk: the miss, else the target the chip clears by the least, with its numbers
    var risk = "";
    if (miss.length) risk = (miss[0].held ? "On the held-out patients, " : "") + nm(miss[0].t) + " " + Fd.fmtV(miss[0].t.metric, miss[0].v, spec) + ", target " + Fd.fmtT(miss[0].t, spec) + ".";
    else if (ok.length) {
      var norm = function (x) { return Fd.metaOf(x.t.metric).frac ? Math.abs(x.v - x.t.value) / 0.05 : Math.abs(x.v - x.t.value) / Math.max(0.5, x.t.value); };
      var thin = ok.reduce(function (a, x) { return norm(x) < norm(a) ? x : a; });
      risk = "Thinnest margin: " + nm(thin.t) + " " + Fd.fmtV(thin.t.metric, thin.v, spec) + ", target " + tgt(thin.t) + ".";
    }
    if (risk) cells.push(cell("Main risk", esc(risk.charAt(0).toUpperCase() + risk.slice(1)), "risk"));
    // why this size, in the run's own terms
    var others = Fd.designs(f).filter(function (d) { return d.id !== m.chosenId; });
    var smaller = others.some(function (d) { var dg = WC.gatesOf(f, d); return WC.verOK(d) && T.length && Fd.passAll(T, d) && dg != null && g != null && dg < g; });
    var lead = pass && g != null && WC.verOK(rec) && !smaller ? "the smallest verified design that clears all your targets." : pass ? "the design the run chose; it clears all your targets." : "the design the run chose; it does not clear all your targets.";
    var mark = Fd.dataMark(spec, rec ? [rec] : []);
    S.css();
    return '<section class="sm ' + (pass ? "ok" : "no") + '" aria-label="Summary">' + (mark ? '<span style="position:absolute;right:12px;top:-9px">' + mark + "</span>" : "") +
      '<p class="sm-r"><b>Why ' + fmt(g != null ? g : ge) + " gates:</b> " + lead + '</p><div class="sm-g">' + cells.join("") + "</div></section>";
  }

  window.ChipInHoverStrip = { chart: chart, more: more, strip: strip };
})();
