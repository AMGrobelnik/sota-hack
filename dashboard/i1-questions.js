/* ChipIn i1 dashboard: follow-up questions, one extra intake step (#/new/more).
 *
 * With a local backend connected, after the five fixed steps and before the "Your spec" card the
 * flow asks POST /api/questions for at most three questions written from the brief, the answers so
 * far and the user's past runs, each with a default and a one-line why. They show as one more step
 * in the style of the others; the answers appear on the spec card as editable rows and go with the
 * run as follow_up. While the questions load (under 12 s) a Skip control is shown; an empty list,
 * an error or no answer in time skips the step without a word. With no backend (the public site)
 * nothing changes: no extra step and no questions.
 *
 * The page calls (the hooks in variants/i1.html and ../i1-live.js):
 *   ChipInQuestions.dot(i, spec)        progress dot 6, or "" when the step is not offered
 *   ChipInQuestions.after(spec)         where Next on step 5 goes: "more", or null for the spec card
 *   ChipInQuestions.has(spec)           whether there are questions to go back to from the spec card
 *   ChipInQuestions.render(spec, ctx)   draws #/new/more; ctx = { prog, go, save }; true when drawn
 *   ChipInQuestions.cardRows(spec, save) the answers as rows of the spec card
 *   ChipInQuestions.payload(spec)       { id, answers: [{ id, question, answer }] } for POST /api/runs, or null
 * State lives on the flow's spec object (spec.fq), so the flow's own sessionStorage keeps it. */
(function () {
  "use strict";
  var WAIT_MS = 11500; // the page gives up before 12 s; the server stops at 11 s
  var BACK_ICON = '<svg class="i s16" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>'; // the steps' own Back arrow
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var live = function () { return window.ChipInLive && window.ChipInLive.i1; };
  var here = false, seq = 0, S = null, saveFn = null;

  // the backend, when this page is connected to one
  function conn() {
    var l = live(), c = l && l.connection ? l.connection() : null;
    return c && c.state === "on" && c.base ? c : null;
  }
  // the fixed steps' answers, named as the run's spec names them (the brief goes on its own)
  function answersOf(s) {
    var l = live(), a = {};
    try { a = l && l.buildSpec ? l.buildSpec(s) : {}; } catch (e) { a = {}; }
    delete a.brief;
    return a;
  }
  var sigOf = function (s) { return JSON.stringify([s.brief || "", answersOf(s)]); };
  var ready = function (s) { return !!(s && s.fq && s.fq.state === "ready" && s.fq.questions && s.fq.questions.length); };
  var declined = function (s) { return !!(s && s.fq && (s.fq.state === "empty" || s.fq.state === "skipped") && s.fq.sig === sigOf(s)); };
  function offered(s) { return !!(s && conn() && !declined(s)); }
  function save() { if (typeof saveFn === "function") saveFn(); }

  // the questions are asked inside the intake chat now (../i1-intake.js), so the steps get no sixth dot
  function dot(i, s) {
    if (!offered(s) || window.ChipInIntake) return "";
    var now = here, cls = now ? "now" : i >= 5 ? "done" : "";
    return '<li class="' + cls + '"><button type="button" data-go="more"' + (now ? ' aria-current="step"' : "") + ' aria-label="Step 6: A few more"><span class="gpn">6</span><span class="gpl">A few more</span></button></li>';
  }
  function after(s) { return offered(s) && !window.ChipInIntake ? "more" : null; }
  // for the chat: the backend's questions for this spec, fetched once; cb([]) when there are none
  function ask(s, saveIt, cb) {
    S = s; saveFn = saveIt;
    if (!offered(s)) { cb([]); return; }
    if (ready(s) && s.fq.sig === sigOf(s)) { cb(s.fq.questions); return; }
    fetchQuestions(s, function () { cb(ready(s) ? s.fq.questions : []); });
  }
  function answer(s, id, v) { if (!ready(s)) return; s.fq.answers[id] = v; save(); }
  function has(s) { return !!conn() && ready(s); }

  // an option written as a raw key ("missed_event") read as words ("Missed event"); the value sent stays the option
  var label = function (o) { o = String(o == null ? "" : o); return /^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$/.test(o) ? o.charAt(0).toUpperCase() + o.slice(1).replace(/_/g, " ") : o; };
  // the answer to one question: what the user set, else its default
  var answerOf = function (s, q) { var a = s.fq.answers || {}; return Object.prototype.hasOwnProperty.call(a, q.id) ? a[q.id] : q["default"]; };

  function qHTML(s, q) {
    var cur = answerOf(s, q), ctl;
    if (q.kind === "choice") {
      ctl = '<div class="gch" role="radiogroup" aria-label="' + esc(q.question) + '">' + q.options.map(function (o) {
        return '<button type="button" role="radio" aria-checked="' + (o === cur) + '" data-fq-q="' + esc(q.id) + '" data-fq-v="' + esc(o) + '"><span>' + esc(label(o)) + "</span></button>";
      }).join("") + "</div>";
    } else {
      ctl = '<div class="gfw"><input class="gfin" data-fq-in="' + esc(q.id) + '" value="' + esc(cur) + '" aria-label="' + esc(q.question) + '" data-voice></div>';
    }
    return '<section class="gfq"><h2 class="gl">' + esc(q.question) + '</h2><p class="gw">' + esc(q.why) + "</p>" + ctl + "</section>";
  }
  function bodyHTML(s) {
    if (ready(s)) return s.fq.questions.map(function (q) { return qHTML(s, q); }).join("");
    // STAGE HOOK: the wait as the shared loading stage's list; the request is real, so it ticks when the answer comes
    if (window.ChipInStage) return '<section class="gfq">' + window.ChipInStage.inline([
      { t: "Brief and answers sent to the backend" },
      { p: "Writing questions for this brief", w: "The model reads what the five steps leave open" },
      { p: "Checking them against your answers" }
    ], 1) + '<button type="button" class="btn s fq-skip" data-fq="skip" style="margin-top:14px">Skip</button></section>';
    return '<section class="gfq"><p class="gw fq-wait" role="status"><span class="fq-dot" aria-hidden="true"></span>Writing a few questions for this brief.</p><button type="button" class="btn s fq-skip" data-fq="skip">Skip</button></section>';
  }

  function onMore() { return /^#\/?new\/more(\/|$)/.test(location.hash); }
  function toSpec() { if (onMore()) location.replace(location.pathname + location.search + "#/new/spec"); }

  function fetchQuestions(s, done) {
    var fin = function () { if (typeof done === "function") done(); };
    var c = conn(), my = ++seq, sig = sigOf(s), keep = (s.fq && s.fq.answers) || {};
    s.fq = { sig: sig, state: "loading", questions: [], answers: {} };
    save();
    var ctl = typeof AbortController === "function" ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctl) ctl.abort(); }, WAIT_MS);
    var token = (window.ChipInLive && window.ChipInLive.token) || "";
    var size = s.preset ? String(s.preset).toLowerCase() : null;
    fetch(c.base + "/api/questions", {
      method: "POST", cache: "no-store", signal: ctl ? ctl.signal : undefined,
      headers: { "Content-Type": "application/json", "X-ChipIn-Token": token },
      body: JSON.stringify({ brief: s.brief, answers: answersOf(s), run_size: size })
    }).then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; })
      .then(function (j) {
        clearTimeout(timer);
        if (my !== seq || !s.fq || s.fq.sig !== sig) { fin(); return; }
        var qs = j && Array.isArray(j.questions) ? j.questions.filter(valid).slice(0, 3) : [];
        if (!qs.length) { s.fq = { sig: sig, state: "empty" }; save(); toSpec(); fin(); return; }
        var answers = {};
        qs.forEach(function (q) { if (Object.prototype.hasOwnProperty.call(keep, q.id)) answers[q.id] = keep[q.id]; });
        s.fq = { sig: sig, state: "ready", id: typeof j.id === "string" ? j.id : null, questions: qs, answers: answers };
        save();
        if (onMore() && $("#gfBody")) paintBody(s);
        fin();
      });
  }
  function valid(q) {
    if (!q || typeof q.id !== "string" || typeof q.question !== "string" || !q.question || typeof q.why !== "string") return false;
    if (q.kind === "choice") return Array.isArray(q.options) && q.options.length >= 2 && q.options.every(function (o) { return typeof o === "string" && o; });
    return q.kind === "text" && typeof q["default"] === "string";
  }
  function paintBody(s) {
    var b = $("#gfBody"); if (!b) return;
    b.innerHTML = bodyHTML(s);
    var n = $("#gfNext"); if (n) n.textContent = "Review your spec";
  }

  function render(s, ctx) {
    if (!s) return false;
    S = s; saveFn = ctx && ctx.save;
    var l = live(), c = l && l.connection ? l.connection() : null, checking = !!(c && c.state === "checking");
    if (checking) setTimeout(function () { if (onMore()) render(s, ctx); }, 300); // a reload: the connection is still being tested
    else if (!offered(s)) { toSpec(); return true; }
    else if (!s.fq || s.fq.sig !== sigOf(s) || (s.fq.state !== "ready" && s.fq.state !== "loading") || (s.fq.state === "loading" && !seq)) fetchQuestions(s);
    here = true;
    var prog = ctx && ctx.prog ? ctx.prog(5) : "";
    here = false;
    var main = $("#main");
    main.innerHTML = '<div class="gf" id="gf"><div class="gfc">' + prog + '<header class="gfh"><p class="gfn">Step 6 of 6</p><h1 tabindex="-1" id="gfH">A few more for this device</h1></header><div id="gfBody">' + bodyHTML(s) + '</div><div class="gfa"><button type="button" class="btn s" data-fq-go="prev">' + BACK_ICON + 'Back</button><span class="grow"></span><button type="button" class="btn p" id="gfNext" data-fq-go="next">Review your spec</button></div></div></div>';
    var root = $("#gf"), go = ctx && ctx.go;
    root.addEventListener("click", function (e) {
      var g = e.target.closest("[data-go]");
      if (g && go) { go(g.dataset.go); return; }
      var f = e.target.closest("[data-fq-go]");
      if (f && go) {
        var back = f.dataset.fqGo === "prev";
        // leaving while the questions load: Next skips them, Back drops the request (Next asks again)
        if (s.fq && s.fq.state === "loading") { seq++; s.fq = back ? null : { sig: s.fq.sig, state: "skipped" }; save(); }
        go(back ? 5 : "spec"); return;
      }
      if (e.target.closest('[data-fq="skip"]')) { seq++; s.fq = { sig: sigOf(s), state: "skipped" }; save(); if (go) go("spec"); return; }
      var c = e.target.closest("[data-fq-q]");
      if (c && ready(s)) {
        s.fq.answers[c.dataset.fqQ] = c.dataset.fqV; save();
        c.parentNode.querySelectorAll("[data-fq-q]").forEach(function (b) { b.setAttribute("aria-checked", String(b === c)); });
      }
    });
    var h = $("#gfH"); if (h) h.focus({ preventScroll: true });
    return true;
  }

  // which: "capped" for the ones past the intake's cap (shown under Assumed with their default), else the asked
  // ones; a question the intake covers already (s.fq.drop, ../i1-intake.js) is not shown
  var dropped = function (s, q) { return !!(s.fq.drop && s.fq.drop[q.id]); };
  var capped = function (s, q) { return !!(s.fq.capped && s.fq.capped[q.id]); };
  function cardRows(s, saveIt, which) {
    if (!has(s)) return "";
    S = s; saveFn = saveIt;
    return s.fq.questions.filter(function (q) { return !dropped(s, q) && capped(s, q) === (which === "capped"); }).map(function (q) {
      return '<div class="gsr fq-row"><span class="k">' + (which === "capped" ? "Assumed" : "A few more") + '</span><div class="v"><small class="fq-q">' + esc(q.question) + '</small><div class="gie sm"><textarea data-fq-card="' + esc(q.id) + '" rows="1" aria-label="' + esc(q.question) + '" data-voice>' + esc(label(answerOf(s, q))) + '</textarea></div></div><button type="button" class="gchg" data-go="' + (window.ChipInIntake ? "ask" : "more") + '" aria-label="Change: ' + esc(q.question) + '">Change</button></div>';
    }).join("");
  }

  function payload(s) {
    if (!has(s)) return null;
    // a question the intake covers is answered from the spec card's own row, or left out
    var II = window.ChipInIntake, cov = function (q) { var k = s.fq.drop && s.fq.drop[q.id]; return k ? (II && II.coveredAnswer ? II.coveredAnswer(s, k) : null) : undefined; };
    var answers = s.fq.questions.map(function (q) { var c = cov(q), v = c === undefined ? answerOf(s, q) : c; return { id: q.id, question: q.question, answer: String(v == null ? "" : v).trim() }; }).filter(function (a) { return a.answer; });
    return answers.length ? { id: s.fq.id, answers: answers } : null;
  }

  // typing an answer, on the step or on the spec card
  document.addEventListener("input", function (e) {
    var el = e.target, id = el && el.dataset && (el.dataset.fqIn || el.dataset.fqCard);
    if (!id || !ready(S)) return;
    S.fq.answers[id] = el.value.replace(/\s*\n\s*/g, " ");
    save();
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Enter" && e.target && e.target.dataset && e.target.dataset.fqCard) e.preventDefault(); });

  // a few additions to the page's styles: a sixth progress dot on the same grid, the loading line
  var css = document.createElement("style");
  css.textContent = ".gfp ol:has(>li:nth-child(6)){grid-template-columns:repeat(6,minmax(0,1fr))}" +
    ".fq-wait{display:flex;align-items:center;gap:10px;margin:0 0 14px}" +
    ".fq-dot{width:8px;height:8px;border-radius:50%;background:var(--blue7);animation:fqp 1.2s ease-in-out infinite}" +
    "@keyframes fqp{0%,100%{opacity:.25}50%{opacity:1}}@media (prefers-reduced-motion:reduce){.fq-dot{animation:none}}" +
    ".fq-skip{height:36px;padding:0 16px}.gsr .v small.fq-q{margin:0 0 2px}";
  document.head.appendChild(css);

  window.ChipInQuestions = { dot: dot, after: after, has: has, render: render, cardRows: cardRows, payload: payload, ask: ask, answer: answer, label: label };
})();
