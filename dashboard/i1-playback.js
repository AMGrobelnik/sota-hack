/* ChipIn i1 playback: one clock and one playback bar for every run the dashboard can replay.
 *
 * Classic script, no dependencies; dashboard/variants/i1.html loads it and calls it from a few lines
 * marked PLAYBACK HOOK. It adds window.ChipInPlayback.
 *
 *   ChipInPlayback.owns()                true when the address is a recorded run (#/rec/<site|mac>/<id>/<view>)
 *   ChipInPlayback.render()              draws that run into #main
 *   ChipInPlayback.mountExample(run, P)  puts the bar under an example run's header; P gives the page's
 *                                        elapsed(run), timeline(run), tick() and saveRuns()
 *   ChipInPlayback.pastLink(where)       the quiet "Past runs" button for the start page or a run header
 *   ChipInPlayback.cleanHash(h)          the address without its ?t=&speed= part (the page routes on the rest)
 *   ChipInPlayback.state()               what the open recorded run shows now (for tests)
 *
 * The design follows the run viewer of an earlier product by one of the team, rewritten for this page:
 *   - The clock stores an anchor (time at the last play, pause, seek or speed change, and the wall clock
 *     then), a speed and a playing flag. Now = anchor + wall time since the anchor x speed. A speed change
 *     re-anchors, so changing speed never jumps.
 *   - 1x is real time between the recorded events. Silences longer than 30 minutes are idle, not work:
 *     the clock steps over them in zero seconds and the track marks each with a notch.
 *   - Speeds 1x (default), 2x, 4x, 10x, 50x, 100x, 200x, 500x, 1000x.
 *   - At time T the page shows exactly the state after every event up to T. Scrubbing back rebuilds that
 *     state from the nearest snapshot at or before T (one every 64 events, taken on the way forward),
 *     never by undoing, so nothing from the future is left on screen.
 *   - A finished replay stops at its end; Play there starts again from the beginning. A run still going
 *     follows its live edge (red Live), speed is fixed at 1x there, scrubbing back leaves live, and the
 *     Live button returns to it. A seek that lands within 2 s of the live edge rejoins it.
 *   - Keys: Space plays or pauses; < and > (or , and .) step the speed; J and L scrub 10 s back and on
 *     (Shift: 60 s). On the focused track: arrows 1 s (Shift 10 s), Page Up/Down 30 s, Home and End.
 *   - The address keeps the run, the view and, on pause or after a seek, ?t=<seconds> (and &speed= when
 *     it is not 1x), so a moment can be linked. While playing the address stays still.
 * Fast speeds stay smooth by batching: every animation frame folds all events up to the new time in one
 * pass and redraws the bar; the views redraw at most ten times a second, each part only when its own
 * signature changed, and the log adds its new rows in one batch (the newest 400 are kept on screen). */
(function () {
  "use strict";

  /* ---------- constants and helpers ---------- */
  var SPEEDS = [1, 2, 4, 10, 50, 100, 200, 500, 1000];
  var IDLE_GAP_MS = 30 * 60 * 1000;
  var SNAP_TO_LIVE_S = 2;
  var SNAP_EVERY = 64;
  var VIEW_MS = 100;
  var LOG_MAX = 400;
  var STAGES = ["spec", "reference", "propose", "finetune", "compile", "verify", "report"];
  var STAGE_N = { spec: "Spec", reference: "Reference", propose: "Propose", finetune: "Fine-tune", compile: "Compile", verify: "Verify", report: "Report" };
  var VIEWS = [["overview", "Overview"], ["log", "Log"], ["files", "Files"]];
  var K_CONN = "chipin-i1-backend";
  var RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var fmtN = function (n) { return Math.round(n).toLocaleString("en-GB"); };
  var clamp = function (x, a, b) { return Math.max(a, Math.min(b, x)); };
  var num = function (v) { return typeof v === "number" && isFinite(v) ? v : null; };
  var clip = function (s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n - 1) + "…" : s; };
  var tsMs = function (ts) { var t = Date.parse(ts || ""); return isNaN(t) ? null : t; };
  function clock(s) {
    s = Math.max(0, Math.floor(s));
    var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = String(s % 60).padStart(2, "0");
    return h ? h + ":" + String(m).padStart(2, "0") + ":" + x : m + ":" + x;
  }
  function fmtIdle(ms) { var m = Math.round(ms / 60000); return m < 60 ? m + "m" : m < 1440 ? Math.floor(m / 60) + "h " + (m % 60) + "m" : Math.floor(m / 1440) + "d " + Math.floor(m % 1440 / 60) + "h"; }
  function dateTxt(ts) { var t = tsMs(ts); if (t == null) return ""; var d = new Date(t); return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) + ", " + d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }); }
  function durTxt(s) { s = Math.round(s || 0); return s < 60 ? s + " s" : s < 3600 ? Math.floor(s / 60) + " min " + (s % 60 ? (s % 60) + " s" : "") : Math.floor(s / 3600) + " h " + Math.floor(s % 3600 / 60) + " min"; }
  var SVG = {
    play: '<path d="M7 5v14l11-7z"/>', pause: '<rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/>',
    prev: '<path d="M6 5v14"/><path d="M19 5 9 12l10 7z"/>', next: '<path d="M18 5v14"/><path d="M5 5l10 7-10 7z"/>',
    end: '<path d="M5 5l9 7-9 7z"/><path d="M18 5v14"/>', hist: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>', file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>'
  };
  var icon = function (n, fill) { return '<svg viewBox="0 0 24 24" aria-hidden="true" class="' + (fill ? "pb-fi" : "pb-si") + '">' + SVG[n] + "</svg>"; };

  /* ---------- styles (spare: hairlines, the page's ink and its indigo track) ---------- */
  var css = document.createElement("style");
  css.textContent = [
    ".pb-row [hidden]{display:none!important}",
    ".top:has(+ .pb-row) #stp .spill.paused{display:none}",
    "@media (max-width:767px){.rv-st{flex-wrap:wrap;gap:6px 0}.rv-st li{flex:0 0 33%;min-width:0}}",
    ".pb-row{flex:none;display:flex;align-items:center;gap:6px;min-height:40px;padding:0 14px 0 12px;border-bottom:1px solid var(--hair);background:rgb(255 255 255/.66)}",
    ".pb-b{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;color:var(--i700);flex:none}",
    ".pb-b:hover{background:var(--i100)}.pb-b[disabled]{opacity:.35;cursor:default;background:none}",
    ".pb-b svg{width:14px;height:14px}.pb-b svg.pb-fi{fill:currentColor;stroke:none}.pb-b svg.pb-si{fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}",
    ".pb-b.pb-main svg{width:15px;height:15px}",
    ".pb-b:focus-visible,.pb-spd:focus-visible,.pb-live:focus-visible,.pb-trk:focus-visible{outline:2px solid var(--blue);outline-offset:2px}",
    ".pb-time{font-family:var(--mono);font-size:11px;color:var(--i700);font-variant-numeric:tabular-nums;white-space:nowrap;flex:none;margin:0 4px 0 2px}",
    ".pb-time .now{padding:2px 6px;border-radius:5px;background:var(--i100)}.pb-row.live .pb-time .now{background:rgb(239 68 68/.09);color:var(--badt)}",
    ".pb-time .tot{color:var(--i500)}",
    ".pb-spdw{position:relative;flex:none}",
    ".pb-spd{height:24px;min-width:38px;padding:0 7px;border-radius:7px;font-size:11.5px;font-weight:600;color:var(--i600);font-variant-numeric:tabular-nums}",
    ".pb-spd:hover{background:var(--i100);color:var(--i900)}.pb-spd[disabled]{opacity:.4;cursor:default;background:none}",
    ".pb-menu{position:absolute;top:calc(100% + 4px);left:50%;transform:translateX(-50%);z-index:60;background:#fff;border:1px solid rgb(0 0 0/.08);border-radius:10px;box-shadow:var(--sh-menu);padding:4px;min-width:64px}",
    ".pb-menu button{display:block;width:100%;text-align:right;padding:4px 10px;border-radius:6px;font-size:12px;color:var(--i700);font-variant-numeric:tabular-nums}",
    ".pb-menu button:hover,.pb-menu button:focus-visible{background:var(--i100);outline:0}.pb-menu button[aria-selected=true]{color:var(--blue7);font-weight:650}",
    ".pb-trk{flex:1;min-width:60px;height:28px;position:relative;cursor:pointer;touch-action:none;display:flex;align-items:center;margin:0 6px}",
    ".pb-rail{position:relative;width:100%;height:4px;border-radius:2px;background:var(--i150)}",
    ".pb-fill{position:absolute;left:0;top:0;bottom:0;border-radius:2px;background:linear-gradient(90deg,#818cf8,#6366f1)}",
    ".pb-row.live .pb-fill{background:#ef4444}",
    ".pb-mark{position:absolute;top:50%;width:2px;height:10px;margin-left:-1px;transform:translateY(-50%);background:#fff;box-shadow:0 0 0 .5px var(--i300);border-radius:1px;pointer-events:none}",
    ".pb-gap{position:absolute;top:50%;width:4px;height:10px;margin-left:-2px;transform:translateY(-50%);background:#fff;border-left:1px solid rgb(0 0 0/.3);border-right:1px solid rgb(0 0 0/.3);pointer-events:none}",
    ".pb-thumb{position:absolute;top:50%;width:12px;height:12px;border-radius:50%;background:#fff;border:1px solid rgb(0 0 0/.18);box-shadow:0 1px 2px rgb(0 0 0/.12);transform:translate(-50%,-50%);pointer-events:none}",
    ".pb-row.live .pb-thumb{border:2px solid #ef4444}.pb-trk.drag .pb-thumb{transform:translate(-50%,-50%) scale(1.3)}",
    ".pb-tip{position:absolute;bottom:calc(100% + 2px);transform:translateX(-50%);background:var(--i900);color:#fff;font-size:11px;font-weight:600;padding:2px 7px;border-radius:7px;white-space:nowrap;pointer-events:none;font-variant-numeric:tabular-nums;z-index:5}",
    ".pb-live{height:24px;display:inline-flex;align-items:center;gap:6px;padding:0 9px;border-radius:99px;font-size:11.5px;font-weight:600;color:var(--i600);border:1px solid var(--i200);flex:none}",
    ".pb-live i{width:7px;height:7px;border-radius:50%;background:var(--i300)}",
    ".pb-live.on{color:var(--badt);background:rgb(239 68 68/.08);border-color:transparent}.pb-live.on i{background:#ef4444}",
    ".pb-live:not(.on):hover{border-color:var(--i300);color:var(--i900)}",
    ".pb-past{display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 10px;border-radius:8px;font-size:12px;font-weight:500;color:var(--i600);flex:none;white-space:nowrap}",
    ".pb-past:hover{background:var(--i100);color:var(--i900)}.pb-past svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}",
    ".pb-pastw{display:flex;justify-content:center;margin:14px 0 0}.pb-pastw .pb-past{font-size:13px;color:var(--i600)}",
    ".pb-scrim{position:fixed;inset:0;background:rgb(14 21 48/.28);z-index:80;display:flex;align-items:flex-start;justify-content:center;padding:9vh 16px 16px}",
    ".pb-dlg{background:#fff;border-radius:16px;box-shadow:0 24px 64px -24px rgb(0 0 0/.45);width:min(600px,100%);max-height:80vh;display:flex;flex-direction:column;outline:0}",
    ".pb-dlg header{display:flex;align-items:flex-start;gap:10px;padding:18px 18px 10px}",
    ".pb-dlg h2{font-family:var(--serif);font-weight:400;font-size:22px;margin:0;letter-spacing:-.01em}",
    ".pb-dlg header p{margin:3px 0 0;font-size:12.5px;color:var(--i600);line-height:1.45}",
    ".pb-list{overflow:auto;padding:0 8px 10px}",
    ".pb-run{display:grid;grid-template-columns:1fr auto;gap:2px 12px;width:100%;text-align:left;padding:10px 10px;border-radius:10px;border-top:1px solid var(--hair)}",
    ".pb-run:first-child{border-top:0}.pb-run:hover,.pb-run:focus-visible{background:var(--i100);outline:0}",
    ".pb-run .t{font-size:13.5px;font-weight:550;color:var(--i900);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}",
    ".pb-run .d{font-size:12px;color:var(--i600);text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}",
    ".pb-run .m{grid-column:1/-1;font-size:12px;color:var(--i600);display:flex;gap:6px 12px;flex-wrap:wrap;align-items:center}",
    ".pb-run .m b{font-weight:600;color:var(--i800);font-family:var(--mono);font-size:11px}",
    ".pb-note{font-size:12.5px;color:var(--i600);padding:8px 12px 14px;line-height:1.5}",
    ".pb-src{font-size:11.5px;color:var(--i500);padding:10px 12px 4px}",
    /* recorded run view */
    ".rv{max-width:1320px;margin:0 auto;padding:18px 24px 72px;display:flex;flex-direction:column;gap:14px}",
    ".rv-st{display:flex;gap:0;list-style:none;margin:0;padding:10px 6px;background:#fff;border:1px solid rgb(0 0 0/.07);border-radius:14px;overflow-x:auto}",
    ".rv-st li{flex:1;min-width:84px;padding:0 10px;font-size:12px;color:var(--i500);display:flex;align-items:center;gap:7px;white-space:nowrap}",
    ".rv-st li i{width:9px;height:9px;border-radius:50%;border:1.5px solid var(--i300);flex:none}",
    ".rv-st li.started{color:var(--blue7);font-weight:600}.rv-st li.started i{border-color:var(--blue6);background:rgb(61 109 240/.15)}",
    ".rv-st li.done{color:var(--i800)}.rv-st li.done i{border-color:var(--okt);background:var(--okt)}",
    ".rv-st li.skipped{color:var(--i500);text-decoration:line-through}.rv-st li.skipped i{border-style:dashed}",
    ".rv-st .r{color:var(--i500);font-weight:400;text-decoration:none;font-size:11px}",
    ".rv-grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:14px;align-items:start}",
    ".rv-side{display:flex;flex-direction:column;gap:14px;min-width:0}",
    ".rv-pan{padding:12px 14px}.rv-pan h2{font-size:13.5px;font-weight:650;margin:0 0 6px}",
    ".rv-pan .sub{font-size:12px;color:var(--i600);margin:0 0 8px;line-height:1.45}",
    ".rv-chip{font-family:var(--mono);font-size:11.5px;color:var(--i800)}",
    ".rv-sab .row{display:flex;align-items:center;gap:8px;padding:6px 0;border-top:1px solid var(--hair);font-size:12px;color:var(--i700)}",
    ".rv-sab .row:first-of-type{border-top:0}.rv-sab .row b{font-weight:600;min-width:72px}",
    ".rv-sab .dots{display:flex;gap:4px;flex-wrap:wrap}",
    ".rv-sab .dots i{width:10px;height:10px;border-radius:50%;border:1.5px solid var(--blue6)}",
    ".rv-sab .dots i.done{background:var(--blue6)}.rv-sab .dots i.failed{background:#ef4444;border-color:#ef4444}",
    ".rv-sab .dots i.kept{box-shadow:0 0 0 2px #fff,0 0 0 3.5px var(--i900)}",
    ".rv-sab .why{font-size:12px;color:var(--i600);line-height:1.45;margin:2px 0 4px 80px}",
    ".rv-log{list-style:none;margin:0;padding:0;font-size:13px;line-height:1.5}",
    ".rv-log li{display:grid;grid-template-columns:48px 1fr;gap:10px;padding:6px 0;border-top:1px solid var(--hair)}",
    ".rv-log li:first-child{border-top:0}.rv-log .at{font-family:var(--mono);font-size:10.5px;color:var(--i500);padding-top:2px}",
    ".rv-log .k-status,.rv-log .k-tool,.rv-log .k-stage{color:var(--i600);font-size:12.5px}",
    ".rv-log .k-err{color:var(--badt)}.rv-log .k-msg b{font-weight:600}",
    ".rv-log .k-fin{background:var(--i100);border-radius:10px;padding:10px 12px;border:0;margin:6px 0}",
    ".rv-log .k-fin p{margin:0 0 6px}.rv-log .k-fin ul{margin:4px 0 0;padding-left:18px}",
    ".rv-logp{max-width:860px;margin:0 auto;padding:18px 24px 72px}",
    ".rv-logp h2,.rv-files h2{font-family:var(--serif);font-weight:400;font-size:22px;margin:0 0 4px}",
    ".rv-logp>p,.rv-files>p{font-size:12.5px;color:var(--i600);margin:0 0 12px}",
    ".rv-files{max-width:860px;margin:0 auto;padding:18px 24px 72px}",
    ".rv-f{display:flex;gap:10px;align-items:center;width:100%;text-align:left;padding:9px 10px;border-top:1px solid var(--hair);font-size:13px}",
    ".rv-f:hover{background:var(--i100)}.rv-f svg{width:15px;height:15px;fill:none;stroke:var(--i500);stroke-width:2;flex:none}",
    ".rv-f .p{font-family:var(--mono);font-size:11.5px;color:var(--i600);margin-left:auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:55%}",
    ".rv-pre{white-space:pre-wrap;font-family:var(--mono);font-size:12px;line-height:1.55;margin:0;padding:0 18px 18px;overflow:auto;color:var(--i800)}",
    ".rv-cw{position:relative}.rv-cw canvas{display:block;width:100%;border-radius:8px}",
    ".rv-brief{font-size:13px;color:var(--i700);margin:6px 0 0;line-height:1.5;max-width:860px}",
    ".rv-empty{font-size:12.5px;color:var(--i500)}",
    "@media (max-width:1100px){.rv-grid{grid-template-columns:1fr}}",
    "@media (max-width:767px){.pb-row{padding:0 6px;gap:2px}.pb-time .tot,.pb-time .sl{display:none}.pb-trk{margin:0 4px}.rv{padding:12px 12px 72px}.rv-logp,.rv-files{padding:12px 12px 72px}.pb-past .lbl{display:none}}",
    "@media (prefers-reduced-motion:reduce){.pb-trk.drag .pb-thumb{transform:translate(-50%,-50%)}}"
  ].join("\n");
  document.head.appendChild(css);

  /* ---------- the clock: an anchor, a speed, a playing flag; now is derived ---------- */
  function Clock(o) {
    this.total = o.total || 0;      // seconds on the bar (active time)
    this.live = !!o.live;           // the run is still going
    this.anchorT = o.t != null ? o.t : this.total;
    this.anchorWall = performance.now();
    this.speed = SPEEDS.indexOf(o.speed) >= 0 ? o.speed : 1;
    this.playing = !!o.playing;
    this.atLive = this.live && o.t == null;
  }
  Clock.prototype.now = function () {
    if (this.atLive) return this.total;
    var t = this.playing ? this.anchorT + (performance.now() - this.anchorWall) * this.speed / 1000 : this.anchorT;
    return clamp(t, 0, this.total);
  };
  Clock.prototype.rebase = function () { this.anchorT = this.now(); this.anchorWall = performance.now(); };
  Clock.prototype.play = function () {
    if (this.atLive) { this.atLive = false; this.anchorT = this.total; }
    if (!this.live && this.now() >= this.total - 1e-6) this.anchorT = 0; // at the end, Play starts over
    this.anchorWall = performance.now(); this.playing = true;
  };
  Clock.prototype.pause = function () { this.rebase(); this.playing = false; };
  Clock.prototype.toggle = function () { if (this.playing || this.atLive) { this.atLive = false; this.pause(); } else this.play(); };
  Clock.prototype.seek = function (t, snap) {
    var b = clamp(t, 0, this.total);
    if (this.live && snap !== false && b >= this.total - SNAP_TO_LIVE_S) { this.goLive(); return; }
    this.atLive = false; this.anchorT = b; this.anchorWall = performance.now();
  };
  Clock.prototype.goLive = function () { if (!this.live) { this.seek(this.total); this.playing = false; return; } this.atLive = true; this.playing = false; this.speed = 1; };
  Clock.prototype.setSpeed = function (s) { if (SPEEDS.indexOf(s) < 0 || (this.live && this.atLive)) return; this.rebase(); this.speed = s; };
  // one frame: a finished replay stops at its end, a live one rejoins its edge
  Clock.prototype.step = function () {
    if (this.playing && !this.atLive && this.now() >= this.total - 1e-6) {
      if (this.live) this.goLive(); else { this.anchorT = this.total; this.playing = false; }
      return true;
    }
    return false;
  };
  Clock.prototype.advancing = function () { return this.playing || (this.live && this.atLive); };

  /* ---------- the bar ---------- */
  // ctl: { clock, marks: [{t, label}], gaps: [{t, ms}], onFrame(), onCommit(), label, kind }
  var BAR = null; // the one bar on screen
  function barHTML() {
    return '<div class="pb-row" id="pbRow" role="group" aria-label="Playback">' +
      '<button class="pb-b" id="pbPrev" aria-label="Previous stage" title="Previous stage">' + icon("prev", false) + "</button>" +
      '<button class="pb-b pb-main" id="pbPlay" aria-label="Play" aria-keyshortcuts="Space">' + icon("play", true) + "</button>" +
      '<button class="pb-b" id="pbNext" aria-label="Next stage" title="Next stage">' + icon("next", false) + "</button>" +
      '<span class="pb-time"><span class="now" id="pbNow">0:00</span><span class="sl"> / </span><span class="tot" id="pbTot">0:00</span></span>' +
      '<span class="pb-spdw"><button class="pb-spd" id="pbSpd" aria-haspopup="listbox" aria-expanded="false" aria-keyshortcuts="< >" title="Playback speed (< and >)">1x</button></span>' +
      '<div class="pb-trk" id="pbTrk" role="slider" tabindex="0" aria-label="Playback position" aria-valuemin="0" aria-keyshortcuts="J L"><div class="pb-rail" id="pbRail"><div class="pb-fill" id="pbFill"></div><div class="pb-thumb" id="pbThumb"></div></div></div>' +
      '<button class="pb-b" id="pbEnd" aria-label="Jump to the end" title="Jump to the end">' + icon("end", false) + "</button>" +
      '<button class="pb-live" id="pbLive" hidden><i></i><span>Live</span></button>' +
      "</div>";
  }
  function mountBar(after, ctl) {
    unmountBar();
    var host = document.createElement("div");
    host.innerHTML = barHTML();
    var row = host.firstChild;
    after.after(row);
    BAR = { row: row, ctl: ctl, raf: 0, lastView: 0, drag: null, hover: null, menu: null, sig: "" };
    drawMarks();
    wireBar();
    frame();
    return BAR;
  }
  function unmountBar() {
    if (!BAR) return;
    cancelAnimationFrame(BAR.raf);
    closeMenu();
    if (BAR.row.isConnected) BAR.row.remove();
    BAR = null;
  }
  function drawMarks() {
    var c = BAR.ctl, T = c.clock.total || 1, rail = $("#pbRail", BAR.row);
    Array.prototype.slice.call(rail.querySelectorAll(".pb-mark,.pb-gap")).forEach(function (n) { n.remove(); });
    var thumb = $("#pbThumb", BAR.row);
    (c.marks || []).forEach(function (m) {
      if (m.t <= 0.01 || m.t >= T - 0.01) return;
      var d = document.createElement("div"); d.className = "pb-mark"; d.style.left = (m.t / T * 100) + "%"; rail.insertBefore(d, thumb);
    });
    (c.gaps || []).forEach(function (g) {
      var d = document.createElement("div"); d.className = "pb-gap"; d.style.left = clamp(g.t / T * 100, 0, 100) + "%"; rail.insertBefore(d, thumb);
    });
    BAR.marksT = T;
  }
  function frame() {
    if (!BAR) return;
    if (!BAR.row.isConnected) { unmountBar(); return; } // the page drew another screen over it
    var c = BAR.ctl, ck = c.clock;
    if (c.refreshTotal) c.refreshTotal();
    if (BAR.marksT !== ck.total && (c.marks || []).length) drawMarks();
    var ended = ck.step();
    var t = ck.now(), T = ck.total, p = T > 0 ? t / T * 100 : 0;
    var row = BAR.row, live = ck.live && ck.atLive;
    row.classList.toggle("live", live);
    $("#pbFill", row).style.width = p + "%";
    $("#pbThumb", row).style.left = p + "%";
    setText($("#pbNow", row), clock(t)); setText($("#pbTot", row), clock(T));
    var trk = $("#pbTrk", row);
    trk.setAttribute("aria-valuemax", String(Math.round(T))); trk.setAttribute("aria-valuenow", String(Math.round(t)));
    trk.setAttribute("aria-valuetext", clock(t) + " of " + clock(T) + (live ? ", live" : "") + (stageAt(c, t) ? ", " + stageAt(c, t) : ""));
    var adv = ck.advancing(), key = [adv, ck.speed, live, ck.live, t >= T - 1e-6, (c.marks || []).length].join("|");
    if (key !== BAR.sig) {
      BAR.sig = key;
      var pb = $("#pbPlay", row); pb.innerHTML = icon(adv ? "pause" : "play", true);
      pb.setAttribute("aria-label", adv ? "Pause" : t >= T - 1e-6 && !ck.live ? "Play from the start" : "Play");
      pb.title = (adv ? "Pause" : "Play") + " (Space)";
      var sp = $("#pbSpd", row); setText(sp, ck.speed + "x"); sp.disabled = live;
      sp.title = live ? "The live edge plays in real time. Scrub back to change the speed." : "Playback speed (< and >)";
      var lv = $("#pbLive", row); lv.hidden = !ck.live; lv.classList.toggle("on", live);
      lv.setAttribute("aria-label", live ? "Live: following the run as it happens" : "Back to live"); lv.title = live ? "Following the run as it happens" : "Back to live";
      $("#pbEnd", row).hidden = ck.live;
      $("#pbPrev", row).disabled = !(c.marks || []).length; $("#pbNext", row).disabled = !(c.marks || []).length;
    }
    var nowMs = performance.now();
    if (ended || BAR.force || nowMs - BAR.lastView >= VIEW_MS || !adv) {
      if (BAR.force || ended || adv || BAR.lastT !== t) { BAR.force = false; BAR.lastView = nowMs; BAR.lastT = t; if (c.onFrame) c.onFrame(t, ended); }
    }
    if (ended && c.onCommit) c.onCommit();
    BAR.raf = requestAnimationFrame(frame);
  }
  function setText(el, s) { if (el && el.textContent !== s) el.textContent = s; }
  function stageAt(c, t) { var l = ""; (c.marks || []).forEach(function (m) { if (m.t <= t + 1e-6) l = m.label; }); return l; }
  function kick() { if (BAR) BAR.force = true; }
  function commit() { kick(); if (BAR && BAR.ctl.onCommit) BAR.ctl.onCommit(); }
  function jumpMark(dir) {
    if (!BAR) return;
    var c = BAR.ctl, t = c.clock.now(), ms = (c.marks || []).map(function (m) { return m.t; }).concat([0]).sort(function (a, b) { return a - b; });
    var target = null;
    if (dir < 0) { for (var i = ms.length - 1; i >= 0; i--) if (ms[i] < t - 1.5) { target = ms[i]; break; } if (target == null) target = 0; }
    else { for (var j = 0; j < ms.length; j++) if (ms[j] > t + 0.05) { target = ms[j]; break; } if (target == null) target = c.clock.total; }
    c.clock.seek(target, dir < 0 ? false : undefined); commit();
  }
  function stepSpeed(dir) {
    if (!BAR) return;
    var ck = BAR.ctl.clock, i = SPEEDS.indexOf(ck.speed) + dir;
    if (i < 0 || i >= SPEEDS.length) return;
    ck.setSpeed(SPEEDS[i]); commit(); announce(ck.speed + "x");
  }
  function scrubBy(s) { if (!BAR) return; var ck = BAR.ctl.clock; ck.seek(ck.now() + s, s < 0 ? false : undefined); commit(); }
  function wireBar() {
    var row = BAR.row, trk = $("#pbTrk", row);
    $("#pbPlay", row).onclick = function () { BAR.ctl.clock.toggle(); commit(); };
    $("#pbPrev", row).onclick = function () { jumpMark(-1); };
    $("#pbNext", row).onclick = function () { jumpMark(1); };
    $("#pbEnd", row).onclick = function () { var ck = BAR.ctl.clock; ck.seek(ck.total); ck.playing = false; commit(); };
    $("#pbLive", row).onclick = function () { BAR.ctl.clock.goLive(); commit(); };
    $("#pbSpd", row).onclick = function (e) { if (BAR.menu) closeMenu(); else openMenu(e.currentTarget); };
    var tAt = function (x) { var r = BAR.drag ? BAR.drag.rect : trk.getBoundingClientRect(); return clamp((x - r.left) / r.width, 0, 1) * BAR.ctl.clock.total; };
    trk.addEventListener("pointerdown", function (e) {
      if (e.button !== 0) return;
      BAR.drag = { rect: trk.getBoundingClientRect(), was: BAR.ctl.clock.playing }; // pinned for the gesture
      trk.setPointerCapture(e.pointerId); trk.classList.add("drag"); hideTip();
      var ck = BAR.ctl.clock; if (ck.playing) ck.pause();
      ck.seek(tAt(e.clientX)); kick();
    });
    trk.addEventListener("pointermove", function (e) {
      if (BAR.drag) { BAR.ctl.clock.seek(tAt(e.clientX)); kick(); return; }
      if (e.pointerType === "mouse") showTip(e.clientX);
    });
    var up = function (e) {
      if (!BAR || !BAR.drag) return;
      var was = BAR.drag.was; BAR.drag = null; trk.classList.remove("drag");
      try { trk.releasePointerCapture(e.pointerId); } catch (err) { /* already released */ }
      if (was && !BAR.ctl.clock.atLive) BAR.ctl.clock.play();
      commit();
    };
    trk.addEventListener("pointerup", up); trk.addEventListener("pointercancel", up);
    trk.addEventListener("pointerleave", hideTip);
    trk.addEventListener("keydown", function (e) {
      var ck = BAR.ctl.clock, t = ck.now(), big = e.shiftKey ? 10 : 1, n = null;
      if (e.key === "ArrowLeft" || e.key === "ArrowDown") n = t - big;
      else if (e.key === "ArrowRight" || e.key === "ArrowUp") n = t + big;
      else if (e.key === "PageDown") n = t - 30; else if (e.key === "PageUp") n = t + 30;
      else if (e.key === "Home") n = 0; else if (e.key === "End") n = ck.total;
      else if (e.key === " ") { e.preventDefault(); ck.toggle(); commit(); return; }
      if (n == null) return;
      e.preventDefault(); ck.seek(n, n < t ? false : undefined); commit();
    });
  }
  function showTip(x) {
    var trk = $("#pbTrk", BAR.row), r = trk.getBoundingClientRect(), f = clamp((x - r.left) / r.width, 0, 1), t = f * BAR.ctl.clock.total;
    var tip = BAR.tip || (BAR.tip = document.createElement("div")); tip.className = "pb-tip";
    var st = stageAt(BAR.ctl, t), gap = (BAR.ctl.gaps || []).find(function (g) { return Math.abs(g.t / (BAR.ctl.clock.total || 1) * r.width - f * r.width) <= 4; });
    tip.textContent = clock(t) + (st ? " · " + st : "") + (gap ? " · " + fmtIdle(gap.ms) + " idle, skipped" : "");
    tip.style.left = (f * 100) + "%";
    if (!tip.isConnected) trk.appendChild(tip);
  }
  function hideTip() { if (BAR && BAR.tip && BAR.tip.isConnected) BAR.tip.remove(); }
  function openMenu(btn) {
    var ck = BAR.ctl.clock, m = document.createElement("div");
    m.className = "pb-menu"; m.setAttribute("role", "listbox"); m.setAttribute("aria-label", "Playback speed");
    m.innerHTML = SPEEDS.map(function (s) { return '<button role="option" data-s="' + s + '" aria-selected="' + (s === ck.speed) + '" tabindex="' + (s === ck.speed ? 0 : -1) + '">' + s + "x</button>"; }).join("");
    btn.parentNode.appendChild(m); btn.setAttribute("aria-expanded", "true"); BAR.menu = m;
    var opts = Array.prototype.slice.call(m.querySelectorAll("button"));
    (opts.find(function (b) { return +b.dataset.s === ck.speed; }) || opts[0]).focus();
    m.addEventListener("click", function (e) { var b = e.target.closest("[data-s]"); if (!b) return; ck.setSpeed(+b.dataset.s); closeMenu(true); commit(); });
    m.addEventListener("keydown", function (e) {
      var i = opts.indexOf(document.activeElement), j = null;
      if (e.key === "ArrowDown" || e.key === "ArrowRight") j = (i + 1) % opts.length;
      else if (e.key === "ArrowUp" || e.key === "ArrowLeft") j = (i - 1 + opts.length) % opts.length;
      else if (e.key === "Home") j = 0; else if (e.key === "End") j = opts.length - 1;
      else if (e.key === "Escape" || e.key === "Tab") { e.preventDefault(); closeMenu(true); return; }
      if (j == null) return; e.preventDefault(); opts[j].focus();
    });
    setTimeout(function () { document.addEventListener("pointerdown", outside, true); }, 0);
  }
  function outside(e) { if (BAR && BAR.menu && !BAR.menu.contains(e.target) && e.target.id !== "pbSpd") closeMenu(false); }
  function closeMenu(refocus) {
    document.removeEventListener("pointerdown", outside, true);
    if (!BAR || !BAR.menu) return;
    BAR.menu.remove(); BAR.menu = null;
    var b = $("#pbSpd", BAR.row); if (b) { b.setAttribute("aria-expanded", "false"); if (refocus) b.focus(); }
  }
  var liveRegion = null;
  function announce(s) {
    if (!liveRegion) { liveRegion = document.createElement("p"); liveRegion.setAttribute("aria-live", "polite"); liveRegion.style.cssText = "position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)"; document.body.appendChild(liveRegion); }
    liveRegion.textContent = s;
  }

  // keys anywhere on a run page: Space, < >, J L (not while typing, not on a control that owns the key)
  document.addEventListener("keydown", function (e) {
    if (!BAR || e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || $(".pb-scrim")) return;
    var tg = e.target, tag = tg && tg.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (tg && tg.isContentEditable) || $(".mbg, .pop, .dscrim")) return;
    if (BAR.menu && BAR.menu.contains(tg)) return;
    var k = e.key;
    if (k === " ") {
      if (tag === "BUTTON" || tag === "A" || (tg && tg.getAttribute && tg.getAttribute("role") === "slider")) return;
      e.preventDefault(); BAR.ctl.clock.toggle(); commit();
    } else if (k === ">" || k === ".") { e.preventDefault(); stepSpeed(1); }
    else if (k === "<" || k === ",") { e.preventDefault(); stepSpeed(-1); }
    else if (k === "j" || k === "J") { e.preventDefault(); scrubBy(e.shiftKey ? -60 : -10); }
    else if (k === "l" || k === "L") { e.preventDefault(); scrubBy(e.shiftKey ? 60 : 10); }
  });

  /* ---------- the address: #/<route>?t=<s>&speed=<x> ---------- */
  function hashParts() {
    var h = location.hash, i = h.indexOf("?");
    var q = new URLSearchParams(i >= 0 ? h.slice(i + 1) : "");
    return { path: i >= 0 ? h.slice(0, i) : h, t: q.has("t") ? parseFloat(q.get("t")) : null, speed: q.has("speed") ? parseFloat(q.get("speed")) : null };
  }
  function cleanHash(h) { h = h == null ? location.hash : h; var i = h.indexOf("?"); return i >= 0 ? h.slice(0, i) : h; }
  function writeHash(ck) {
    var p = hashParts(), q = [];
    if (!(ck.live && ck.atLive) && !(!ck.live && ck.now() >= ck.total - 1e-6)) q.push("t=" + (Math.round(ck.now() * 10) / 10));
    if (ck.speed !== 1) q.push("speed=" + ck.speed);
    var next = p.path + (q.length ? "?" + q.join("&") : "");
    if (next !== location.hash) { try { history.replaceState(history.state, "", location.pathname + location.search + next); } catch (e) { /* file:// */ } }
  }

  /* ---------- example runs: the same bar on the page's own clock ---------- */
  var exSpeed = {};
  function exampleMarks(tl) {
    var m = [];
    if (tl.af) {
      m.push({ t: tl.SPEC, label: "Search" });
      tl.af.steps.forEach(function (s, i) { if (i > 0) m.push({ t: s, label: "Decision step " + (i + 1) }); });
    } else if (tl.rounds && tl.rounds.length) {
      tl.rounds.forEach(function (r) { m.push({ t: r.start, label: "Round " + r.r }); });
      m.push({ t: tl.rounds[tl.rounds.length - 1].end, label: "Report" });
    }
    return m;
  }
  function mountExample(run, P) {
    var top = $("#main .top");
    if (!top) return;
    var tl = P.timeline(run), T = tl.T, p = hashParts();
    var t0 = P.elapsed(run), playing = !!(run.clock && run.clock.playing) && t0 < T - 1e-6;
    if (p.t != null && isFinite(p.t)) { t0 = clamp(p.t, 0, T); playing = false; }
    var sp = p.speed != null && SPEEDS.indexOf(p.speed) >= 0 ? p.speed : exSpeed[run.id] || 1;
    var ck = new Clock({ total: T, t: t0, speed: sp, playing: playing });
    var wrote = null, lastTick = 0;
    var push = function () { // the page reads run.clock: write the bar's time there, then let it redraw
      wrote = run.clock = { base: ck.now(), anchor: Date.now(), playing: ck.playing };
    };
    push();
    mountBar(top, {
      clock: ck, marks: exampleMarks(tl), gaps: [], kind: "example",
      refreshTotal: function () {
        if (run.clock !== wrote) { // the page restarted the run ("Play this run again")
          ck.anchorT = P.elapsed(run); ck.anchorWall = performance.now(); ck.playing = !!run.clock.playing; push();
        }
      },
      onFrame: function (t, ended) {
        push();
        var n = performance.now();
        if (ended || !ck.playing || n - lastTick >= VIEW_MS) { lastTick = n; P.tick(); }
      },
      onCommit: function () { push(); exSpeed[run.id] = ck.speed; P.saveRuns(); P.tick(); writeHash(ck); }
    });
  }

  /* ---------- recorded runs: sources ---------- */
  var REC = { site: null, siteErr: "", mac: null, macErr: "", loading: false };
  function conn() {
    var L = window.ChipInLive, base = null, token = null;
    try { if (L && L.base && L.token) { base = L.base; token = L.token; } } catch (e) { /* older reader */ }
    if (!token) { try { var s = JSON.parse(localStorage.getItem(K_CONN) || "null"); if (s && s.base && s.token) { base = s.base; token = s.token; } } catch (e) { /* storage off */ } }
    if (!token) {
      var api = null; try { api = new URLSearchParams(location.search).get("api"); } catch (e) { /* none */ }
      var loop = /^https?:$/.test(location.protocol) && /^(127\.0\.0\.1|localhost)$/.test(location.hostname);
      base = api ? api.replace(/\/+$/, "") : loop ? location.origin : null;
      if (base) { try { token = sessionStorage.getItem("chipin.token:" + base); } catch (e) { /* storage off */ } }
    }
    return base && token ? { base: base.replace(/\/+$/, ""), token: token } : null;
  }
  // a one-time #token=... (the link the backend prints) is kept for this tab, as the stream reader keeps it
  (function takeToken() {
    var h = location.hash.replace(/^#/, "");
    if (!/(^|&)token=/.test(h) || /^\//.test(h)) return;
    var q = new URLSearchParams(h), tok = q.get("token"), api = null;
    try { api = new URLSearchParams(location.search).get("api"); } catch (e) { /* none */ }
    var loop = /^(127\.0\.0\.1|localhost)$/.test(location.hostname), base = api ? api.replace(/\/+$/, "") : loop ? location.origin : null;
    if (tok && base) { try { sessionStorage.setItem("chipin.token:" + base, tok); } catch (e) { /* storage off */ } }
  })();
  function api(path) {
    var c = conn();
    if (!c) return Promise.reject(new Error("no backend"));
    return fetch(c.base + path, { headers: { "X-ChipIn-Token": c.token }, cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }
  var siteBase = function () { return new URL("../data/runs/", location.href).href; };
  function loadLists() {
    var jobs = [];
    jobs.push(fetch(siteBase() + "index.json", { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (j) { REC.site = (j.runs || []).map(function (r) { r.src = "site"; return r; }); REC.siteErr = ""; })
      .catch(function () { REC.site = []; REC.siteErr = "The site's recorded runs could not be read."; }));
    if (conn()) {
      jobs.push(api("/api/history").then(function (j) { REC.mac = (j.runs || []).map(function (r) { r.src = "mac"; return r; }); REC.macErr = ""; })
        .catch(function (e) { REC.mac = []; REC.macErr = /404/.test(e.message) ? "This backend is too old to list recorded runs; update it." : "The backend on this computer did not answer."; }));
    } else { REC.mac = null; }
    return Promise.all(jobs);
  }

  /* ---------- the picker ---------- */
  function pastLink(where) {
    var b = '<button type="button" class="pb-past" data-past-runs title="Play back a recorded run">' + '<svg viewBox="0 0 24 24" aria-hidden="true">' + SVG.hist + '</svg><span class="lbl">Past runs</span></button>';
    return where === "start" ? '<div class="pb-pastw">' + b + "</div>" : b;
  }
  document.addEventListener("click", function (e) { if (e.target.closest && e.target.closest("[data-past-runs]")) { e.preventDefault(); openPicker(e.target.closest("[data-past-runs]")); } });
  var pickerFrom = null;
  function openPicker(from) {
    closePicker();
    pickerFrom = from || null;
    var s = document.createElement("div");
    s.className = "pb-scrim";
    s.innerHTML = '<div class="pb-dlg" role="dialog" aria-modal="true" aria-labelledby="pbDlgH" tabindex="-1"><header><div style="flex:1"><h2 id="pbDlgH">Past runs</h2><p>Recorded runs, played back from their own events. Nothing is run again and no model is called.</p></div><button class="pb-b" data-x aria-label="Close">' + icon("x", false) + '</button></header><div class="pb-list" id="pbList"><p class="pb-note">Reading the recorded runs…</p></div></div>';
    document.body.appendChild(s);
    $(".pb-dlg", s).focus();
    s.addEventListener("click", function (e) {
      if (e.target === s || e.target.closest("[data-x]")) { closePicker(); return; }
      var r = e.target.closest("[data-open]"); if (r) { closePicker(true); location.hash = "#/rec/" + r.dataset.src + "/" + encodeURIComponent(r.dataset.open) + "/overview"; }
    });
    s.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.stopPropagation(); closePicker(); return; }
      if (e.key === "Tab") { var f = s.querySelectorAll("button"), a = f[0], z = f[f.length - 1]; if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); } else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); } }
    });
    loadLists().then(paintPicker);
  }
  function closePicker(nav) { var s = $(".pb-scrim"); if (s) s.remove(); if (!nav && pickerFrom && pickerFrom.isConnected) pickerFrom.focus(); pickerFrom = null; }
  function rowHTML(r) {
    var c = r.counts || {}, bits = [];
    bits.push('<span class="mk mea">recorded</span>');
    bits.push("<span>" + (r.src === "mac" ? "on this computer" + (r.alsoSite ? ", copy on the site" : "") : "copy on this site") + "</span>");
    if (r.state && r.state !== "succeeded") bits.push("<span>" + esc(r.state) + "</span>");
    if (r.preset) bits.push("<span>" + esc(String(r.preset).charAt(0).toUpperCase() + String(r.preset).slice(1)) + (r.agent ? " · " + esc(r.agent === "claude" ? "Claude" : r.agent) : "") + "</span>");
    if (r.chosen) bits.push("<span>chosen <b>" + esc(clip(r.chosen, 18)) + "</b></span>");
    if (c.designs) bits.push("<span>" + fmtN(c.designs) + " designs</span>");
    if (c.subagents) bits.push("<span>" + fmtN(c.subagents) + " subagents</span>");
    if (c.events) bits.push("<span>" + fmtN(c.events) + " events</span>");
    return '<button class="pb-run" data-open="' + esc(r.id) + '" data-src="' + r.src + '"><span class="t">' + esc(r.title || r.id) + '</span><span class="d">' + esc(dateTxt(r.started_at)) + " · " + esc(durTxt(r.duration_s)) + '</span><span class="m">' + bits.join("") + "</span></button>";
  }
  function paintPicker() {
    var el = $("#pbList"); if (!el) return;
    var macIds = {}; (REC.mac || []).forEach(function (r) { macIds[r.id] = r; });
    var all = (REC.mac || []).concat((REC.site || []).filter(function (r) { if (macIds[r.id]) { macIds[r.id].alsoSite = true; return false; } return true; }));
    all.sort(function (a, b) { return String(b.started_at || "").localeCompare(String(a.started_at || "")); });
    var html = all.length ? all.map(rowHTML).join("") : '<p class="pb-note">No recorded runs yet.</p>';
    var notes = [];
    if (REC.mac == null) notes.push("Runs on this computer appear here once the page is connected to its ChipIn backend.");
    if (REC.macErr) notes.push(REC.macErr);
    if (REC.siteErr) notes.push(REC.siteErr);
    el.innerHTML = html + (notes.length ? '<p class="pb-note">' + esc(notes.join(" ")) + "</p>" : "");
  }

  /* ---------- a recorded run: events, active time, snapshots ---------- */
  var RUNS = {}; // key "site:<id>" | "mac:<id>" -> rec
  function prepare(rec, events) {
    rec.events = events.filter(function (e) { return e && tsMs(e.ts) != null; }).sort(function (a, b) { return (a.seq || 0) - (b.seq || 0); });
    var gaps = [], skipped = 0, prev = null, w0 = rec.events.length ? tsMs(rec.events[0].ts) : 0;
    rec.events.forEach(function (e) {
      var w = tsMs(e.ts);
      if (prev != null && w - prev > IDLE_GAP_MS) { gaps.push({ t: (prev - w0 - skipped) / 1000, ms: w - prev }); skipped += w - prev; }
      e._a = Math.max(0, (w - w0 - skipped) / 1000); prev = w;
    });
    rec.w0 = w0; rec.wLast = prev; rec.skipped = skipped; rec.gaps = gaps;
    rec.snaps = [{ n: 0, st: newState() }];
    rec.marks = [];
    var seen = {};
    rec.events.forEach(function (e) {
      if (e.type === "stage" && e.state === "started") {
        var s = e.stage || e.name, k = s + "|" + (e.round || "");
        if (!seen[k]) { seen[k] = 1; rec.marks.push({ t: e._a, label: (STAGE_N[s] || s) + (e.round ? " " + e.round : "") }); }
      }
    });
    rec.cur = { n: 0, st: rec.snaps[0].st };
    rec.cur.st = cloneState(rec.snaps[0].st);
  }
  function addEvents(rec, more) {
    var known = {}; rec.events.forEach(function (e) { known[e.seq] = 1; });
    var fresh = more.filter(function (e) { return e && !known[e.seq] && tsMs(e.ts) != null; });
    if (!fresh.length) return false;
    var prev = rec.wLast;
    fresh.sort(function (a, b) { return a.seq - b.seq; }).forEach(function (e) {
      var w = tsMs(e.ts);
      if (prev != null && w - prev > IDLE_GAP_MS) { rec.gaps.push({ t: (prev - rec.w0 - rec.skipped) / 1000, ms: w - prev }); rec.skipped += w - prev; }
      e._a = Math.max(0, (w - rec.w0 - rec.skipped) / 1000); prev = w; rec.events.push(e);
      if (e.type === "stage" && e.state === "started") rec.marks.push({ t: e._a, label: STAGE_N[e.stage || e.name] || e.stage || e.name });
    });
    rec.wLast = prev;
    return true;
  }
  function activeTotal(rec) {
    if (!rec.events.length) return 0;
    var last = rec.events[rec.events.length - 1]._a;
    if (!rec.running) return last;
    var since = Date.now() - rec.wLast; // a live run's clock runs to now (an idle stretch is still skipped)
    return last + (since > IDLE_GAP_MS ? 0 : since / 1000);
  }
  function countAt(rec, t) { var lo = 0, hi = rec.events.length; while (lo < hi) { var mid = (lo + hi) >>> 1; if (rec.events[mid]._a <= t + 1e-9) lo = mid + 1; else hi = mid; } return lo; }

  /* the state after the first n events; pure fold, the same rules the scrub check recomputes */
  function newState() {
    var stages = {}; STAGES.forEach(function (s) { stages[s] = { state: "pending", reason: "" }; });
    return { n: 0, stages: stages, status: "", items: [], messages: 0, tools: {}, toolN: 0, designs: {}, order: [], chips: {}, chipOrder: [], run: {}, chosen: null,
      artifacts: [], cost: null, costSum: 0, subs: {}, subOrder: [], merged: {}, mergedOrder: [], errors: 0, finished: null, evidence: null };
  }
  function cloneState(s) { return JSON.parse(JSON.stringify(s)); }
  function chipOf(st, id) { if (!st.chips[id]) { st.chips[id] = {}; st.chipOrder.push(id); } return st.chips[id]; }
  function apply(st, ev, i) {
    st.n = i + 1;
    switch (ev.type) {
      case "stage": {
        var s = ev.stage || ev.name; if (!st.stages[s]) st.stages[s] = { state: "pending", reason: "" };
        st.stages[s] = { state: ev.state, reason: ev.reason || "", round: ev.round || null };
        st.items.push(i); break;
      }
      case "status": st.status = ev.text || ""; st.items.push(i); break;
      case "message": st.messages++; st.items.push(i); break;
      case "tool": if (!st.tools[ev.call_id]) { st.tools[ev.call_id] = { i: i, state: ev.state }; st.toolN++; st.items.push(i); } else st.tools[ev.call_id].state = ev.state; break;
      case "error": st.errors++; st.items.push(i); break;
      case "design": {
        var d = ev.design || ev.record; if (!d || typeof d.id !== "string") break;
        if (d.prev_id && d.prev_id !== d.id && st.designs[d.prev_id]) { delete st.designs[d.prev_id]; st.order = st.order.filter(function (x) { return x !== d.prev_id; }); }
        if (!st.designs[d.id]) st.order.push(d.id);
        st.designs[d.id] = d; break;
      }
      case "metric": {
        if (typeof ev.chip === "string" && ev.chip) chipOf(st, ev.chip)[ev.key] = ev.value;
        else st.run[ev.key] = ev.value;
        break;
      }
      case "chosen": if (typeof ev.chip === "string" && ev.chip) { st.chosen = ev.chip; st.items.push(i); } break;
      case "artifact": st.artifacts.push(i); if (ev.kind === "report") st.items.push(i); break;
      case "cost": st.cost = { usd: ev.usd, tin: ev.tokens_in, tout: ev.tokens_out }; st.costSum += num(ev.usd) || 0; break;
      case "subagent.started": { var k = ev.agent || ev.id || "s" + ev.seq; if (!st.subs[k]) st.subOrder.push(k); st.subs[k] = { stage: ev.stage, name: ev.name || ev.strategy || k, state: "running" }; st.items.push(i); break; }
      case "subagent.finished": { var a = st.subs[ev.agent || ev.id]; if (a) a.state = ev.state === "failed" || ev.status === "failed" ? "failed" : "done"; break; }
      case "stage.merged": if (!st.merged[ev.stage]) st.mergedOrder.push(ev.stage); st.merged[ev.stage] = { kept: Array.isArray(ev.kept) ? ev.kept : [], why: ev.why || ev.reason || "" }; st.items.push(i); break;
      case "evidence": st.evidence = i; break;
      case "run.finished": st.finished = { status: ev.status, i: i }; st.items.push(i); break;
      default: break;
    }
  }
  // the state at n events: from the nearest snapshot at or before n, never by undoing
  function stateAt(rec, n) {
    var cur = rec.cur;
    if (n < cur.n) {
      var sn = rec.snaps[0];
      for (var k = 0; k < rec.snaps.length; k++) if (rec.snaps[k].n <= n) sn = rec.snaps[k];
      cur = rec.cur = { n: sn.n, st: cloneState(sn.st) };
    }
    for (var i = cur.n; i < n; i++) {
      apply(cur.st, rec.events[i], i);
      if ((i + 1) % SNAP_EVERY === 0 && !rec.snaps.some(function (s) { return s.n === i + 1; })) rec.snaps.push({ n: i + 1, st: cloneState(cur.st) });
    }
    cur.n = n;
    return cur.st;
  }

  /* ---------- loading a recorded run ---------- */
  function loadRun(src, id) {
    var key = src + ":" + id;
    if (RUNS[key]) return RUNS[key].ready;
    var rec = RUNS[key] = { key: key, src: src, id: id, facts: null, files: null, events: [], running: false, err: "" };
    if (src === "site") {
      rec.ready = fetch(siteBase() + "index.json", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : { runs: [] }; }).then(function (j) {
        var line = (j.runs || []).find(function (r) { return r.id === id; });
        if (!line) throw new Error("This recorded run is not on the site.");
        return fetch(siteBase() + line.file, { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("The run's file could not be read."); return r.json(); });
      }).then(function (doc) {
        rec.facts = doc.run || {}; rec.summary = doc.summary || ""; rec.bullets = doc.bullets || ""; rec.files = doc.files || [];
        prepare(rec, doc.events || []);
        return rec;
      }).catch(function (e) { rec.err = e.message || "The run could not be read."; return rec; });
    } else {
      rec.ready = Promise.all([api("/api/runs/" + encodeURIComponent(id) + "/history"), api("/api/history").catch(function () { return { runs: [] }; })]).then(function (r) {
        var page = r[0], facts = (r[1].runs || []).find(function (x) { return x.id === id; }) || { id: id };
        rec.facts = facts; rec.running = !page.finished && (page.state === "running" || facts.state === "running");
        prepare(rec, page.events || []);
        if (rec.running) follow(rec);
        return rec;
      }).catch(function (e) { rec.err = conn() ? "The backend did not return this run (" + e.message + ")." : "This run is on a ChipIn backend that is not connected."; return rec; });
    }
    return rec.ready;
  }
  function follow(rec) {
    clearTimeout(rec.poll);
    rec.poll = setTimeout(function () {
      api("/api/runs/" + encodeURIComponent(rec.id) + "/history?from=" + ((rec.events.length ? rec.events[rec.events.length - 1].seq : 0) + 1)).then(function (page) {
        addEvents(rec, page.events || []);
        if (page.finished) { rec.running = false; if (V && V.rec === rec) { V.clock.live = false; V.clock.total = activeTotal(rec); if (V.clock.atLive) { V.clock.atLive = false; V.clock.anchorT = V.clock.total; } kick(); } }
        else follow(rec);
      }).catch(function () { follow(rec); });
    }, 1500);
  }

  /* ---------- the recorded run view ---------- */
  var V = null; // { rec, view, clock, sig: {}, logN }
  function parse() {
    var m = cleanHash().match(/^#\/rec\/(site|mac)\/([^/]+)(?:\/([a-z]+))?/);
    if (!m) return null;
    var view = VIEWS.some(function (v) { return v[0] === m[3]; }) ? m[3] : "overview";
    return { src: m[1], id: decodeURIComponent(m[2]), view: view };
  }
  function owns() { return !!parse(); }
  function render() {
    var r = parse(); if (!r) return false;
    var main = $("#main"); if (!main) return false;
    document.body.classList.add("inrun");
    var demo = $("#demo"); if (demo) { demo.textContent = "Recorded run, real events"; demo.className = "demo mea"; }
    var same = V && V.rec && V.rec.key === r.src + ":" + r.id;
    if (!same) { unmountBar(); main.innerHTML = '<div class="body"><div class="rv"><p class="rv-empty">Reading the recorded run…</p></div></div>'; }
    loadRun(r.src, r.id).then(function (rec) {
      if (!parse() || parse().id !== r.id) return;
      if (rec.err) { unmountBar(); V = null; main.innerHTML = '<div class="body"><div class="rv"><h1 style="font-family:var(--serif);font-weight:400;font-size:24px;margin:0">This run could not be opened</h1><p class="rv-brief">' + esc(rec.err) + "</p><p>" + pastLink("run") + "</p></div></div>"; return; }
      mountView(rec, r.view, same);
    });
    return true;
  }
  function mountView(rec, view, same) {
    var main = $("#main"), p = hashParts();
    var keep = same && V && V.clock;
    if (!keep) {
      var total = activeTotal(rec), t = p.t != null && isFinite(p.t) ? clamp(p.t, 0, total) : null;
      var ck = new Clock({ total: total, live: rec.running, t: rec.running ? t : t == null ? total : t, speed: p.speed, playing: false });
      if (rec.running && t == null) ck.atLive = true;
      V = { rec: rec, view: view, clock: ck, sig: {}, logN: 0 };
    } else { V.view = view; V.sig = {}; V.logN = 0; }
    main.innerHTML = '<div class="top"><nav class="tabs" aria-label="Run views">' + VIEWS.map(function (v) {
      return '<a class="tab' + (v[0] === view ? " on" : "") + '" href="#/rec/' + rec.src + "/" + encodeURIComponent(rec.id) + "/" + v[0] + '">' + v[1] + "</a>";
    }).join("") + '</nav><span class="grow" style="flex:1"></span><div class="tright">' + pastLink("run") + '<span class="mk ' + (rec.running ? "sim" : "mea") + ' topbadge">' + (rec.running ? "Live run" : "Recorded run") + (rec.src === "mac" ? ", this computer" : "") + "</span></div></div>" +
      '<div class="body" id="rvBody">' + (view === "overview" ? overviewHTML() : view === "log" ? '<div class="rv-logp"><h2>Log</h2><p>What the run said and did, up to the time on the bar. Tool calls are one line each.</p><ul class="rv-log" id="rvLog"></ul></div>' : '<div class="rv-files"><h2>Files</h2><p>Files the run had written by the time on the bar.</p><div id="rvFiles"></div></div>') + "</div>";
    var ctl = {
      clock: V.clock, marks: rec.marks, gaps: rec.gaps, kind: "recorded",
      refreshTotal: function () { if (rec.running || V.clock.live) { V.clock.total = activeTotal(rec); } },
      onFrame: function (t) { paint(t); },
      onCommit: function () { writeHash(V.clock); }
    };
    mountBar($(".top", main), ctl);
    if (view === "overview") wireOverview();
    if (view === "files") $("#rvFiles").addEventListener("click", function (e) { var b = e.target.closest("[data-path]"); if (b) openFile(b.dataset.path); });
    kick();
  }

  function overviewHTML() {
    return '<div class="rv"><header class="ovh"><div class="tx"><p class="k0" id="rvK0"></p><h1 id="rvH1"></h1><p class="rv-brief" id="rvBrief"></p></div></header>' +
      '<div class="status" id="rvStatus" role="status"></div>' +
      '<ol class="rv-st" id="rvStages" aria-label="Stages"></ol>' +
      '<div class="tiles" id="rvTiles"></div>' +
      '<section class="rv-grid"><div class="pan chartp"><div class="chh"><h2 id="rvChH">Designs: chip size against</h2><select class="ys" id="rvY" aria-label="Metric on the chart"></select><span class="grow"></span></div>' +
      '<div class="rv-cw"><canvas id="rvChart" role="img" aria-label="Designs found so far"></canvas></div><div class="legend" id="rvLegend"></div></div>' +
      '<div class="rv-side"><section class="pan rv-pan rv-sab" id="rvSab"></section><section class="pan rv-pan" id="rvLast"></section></div></section>' +
      '<div class="fun" id="rvFun"></div><p class="funn" id="rvFunn"></p></div>';
  }
  function wireOverview() {
    $("#rvY").onchange = function (e) { V.y = e.target.value; V.sig.chart = ""; kick(); };
  }
  addEventListener("resize", function () { if (V) { V.sig.chart = ""; kick(); } });

  // what the page shows at time t, from the state after every event up to t
  function model(rec, t) {
    var n = countAt(rec, t), st = stateAt(rec, n);
    var pts = {}, add = function (id) { return pts[id] || (pts[id] = { id: id, m: {} }); };
    st.order.forEach(function (id) {
      var d = st.designs[id], p = add(id);
      p.label = d.label || ""; p.gates = num(d.gates) || null; p.est = num(d.gates_est) || null;
      var dm = d.metrics || {}; for (var k in dm) if (num(dm[k]) != null) p.m[k] = dm[k];
      if (d.verified && num(d.verified.mismatches) === 0) p.ver = true;
    });
    st.chipOrder.forEach(function (id) {
      var c = st.chips[id], p = add(id);
      if (num(c.gates) != null) p.gates = c.gates;
      for (var k in c) if (k !== "gates" && num(c[k]) != null) p.m[k] = c[k];
      if (num(c.mismatches) === 0 || c.verification_level != null) p.ver = true;
    });
    var list = Object.keys(pts).map(function (k) { return pts[k]; });
    var chosen = st.chosen ? pts[st.chosen] || { id: st.chosen, m: {} } : null;
    return { n: n, st: st, t: t, pts: list, chosen: chosen, ended: !!st.finished };
  }
  var NOT_Y = { gates: 1, ge: 1, transistors: 1, area_um2: 1, depth: 1, tt_tiles: 1, luts_ice40: 1, luts_xc7: 1, round: 1, candidates: 1, vectors_checked: 1, mismatches: 1, cost_eur: 1, verification_level: 1, timing_slack_ns: 1 };
  var PREF_Y = ["sensitivity", "test_accuracy", "accuracy", "specificity", "fa_per_hour", "synthetic_sensitivity_pct", "train_accuracy"];
  var LABEL = { sensitivity: "Sensitivity", specificity: "Specificity", fa_per_hour: "False alarms per hour", test_accuracy: "Test accuracy", train_accuracy: "Train accuracy", accuracy: "Accuracy", power_uw_at_rate: "Power (µW)" };
  var label = function (k) { return LABEL[k] || (k.charAt(0).toUpperCase() + k.slice(1)).replace(/_/g, " "); };
  var isFrac = function (k, pts) { return /accuracy|sensitivity|specificity|agreement/.test(k) && pts.every(function (p) { return p.m[k] == null || p.m[k] <= 1.0001; }); };
  function fmtM(k, v, pts) { if (v == null) return "not reported"; if (isFrac(k, pts || [])) return (v * 100).toFixed(1) + "%"; return Math.abs(v) >= 100 ? fmtN(v) : String(+(+v).toFixed(3)); }
  function niceTicks(a, b, keep) {
    var span = b - a, raw = span / 4, mag = Math.pow(10, Math.floor(Math.log10(raw))), st = [1, 2, 5, 10].map(function (k) { return k * mag; }).find(function (k) { return k >= raw; }) || raw;
    var out = []; for (var v = Math.ceil(a / st - 1e-9) * st; v <= b + 1e-9; v += st) out.push(keep ? +v.toPrecision(6) : Math.round(v));
    return out;
  }
  // the agent writes a little markdown; on the page it reads as plain text
  var plain = function (s) { return String(s || "").replace(/\*\*([^*]+)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1").replace(/^#+\s*/gm, ""); };
  function sizeOf(p) { return p.gates != null ? p.gates : p.est; }

  function paint(t) {
    if (!V) return;
    var M = model(V.rec, t);
    V.last = M;
    if (V.view === "overview") paintOverview(M);
    else if (V.view === "log") paintLog(M);
    else paintFiles(M);
  }
  function once(key, sig, fn) { if (V.sig[key] !== sig) { V.sig[key] = sig; fn(); } }
  function paintOverview(M) {
    var rec = V.rec, f = rec.facts || {}, st = M.st, ck = V.clock;
    once("head", [st.chosen, M.ended, st.finished && st.finished.status, M.pts.length, M.n > 0, ck.live].join("|"), function () {
      var k0 = ['<span class="mk mea">recorded</span>', "<span>" + esc(dateTxt(f.started_at)) + "</span>"];
      if (f.preset) k0.push("<span>" + esc(String(f.preset).charAt(0).toUpperCase() + String(f.preset).slice(1)) + (f.agent ? " · " + esc(f.agent === "claude" ? "Claude" : f.agent) : "") + "</span>");
      if (rec.running || ck.live) k0[0] = '<span class="mk sim">still running</span>';
      $("#rvK0").innerHTML = k0.join("");
      var h1;
      if (M.chosen) h1 = "Chosen chip " + esc(M.chosen.id) + (sizeOf(M.chosen) != null ? ", " + fmtN(sizeOf(M.chosen)) + " gates" : "") + ".";
      else if (st.finished) h1 = st.finished.status === "succeeded" ? "The run finished without naming a chosen chip." : "The run ended: " + esc(st.finished.status) + ".";
      else if (M.pts.length) h1 = "Searching: " + fmtN(M.pts.length) + " design" + (M.pts.length === 1 ? "" : "s") + " so far, no chip chosen yet.";
      else h1 = M.n ? "No design yet. The run is working through its brief." : "Before the first event.";
      $("#rvH1").innerHTML = h1;
      $("#rvBrief").textContent = clip(f.prompt || f.title || "", 420);
    });
    once("status", st.status + "|" + M.n, function () { var s = $("#rvStatus"); s.textContent = st.status ? st.status : ""; s.className = "status" + (st.finished ? " done" : ""); s.dataset.n = String(M.n); });
    once("stages", JSON.stringify(st.stages), function () {
      $("#rvStages").innerHTML = STAGES.map(function (s) {
        var x = st.stages[s] || { state: "pending" };
        return '<li class="' + x.state + '" data-stage="' + s + '" data-state="' + x.state + '"' + (x.state === "started" ? ' aria-current="step"' : "") + ' title="' + esc(STAGE_N[s] + ": " + (x.state === "started" ? "in progress" : x.state) + (x.reason ? ", " + x.reason : "")) + '"><i></i><span>' + STAGE_N[s] + (x.state === "skipped" ? ' <span class="r">skipped</span>' : "") + "</span></li>";
      }).join("");
    });
    var costTxt = st.costSum ? "$" + st.costSum.toFixed(2) : "–";
    once("tiles", [M.pts.length, st.chosen, M.chosen && sizeOf(M.chosen), st.messages, st.toolN, st.artifacts.length, costTxt, st.subOrder.length].join("|"), function () {
      var ch = M.chosen, yk = pickY(M);
      var tiles = [
        ["designs", "Designs so far", M.pts.length ? fmtN(M.pts.length) : "–", M.pts.filter(function (p) { return p.gates != null; }).length + " compiled to gates"],
        ["chosen", "Chosen chip", ch ? '<span class="rv-chip">' + esc(clip(ch.id, 16)) + "</span>" : "–", ch ? (sizeOf(ch) != null ? fmtN(sizeOf(ch)) + " gates" : "size not reported") + (yk && ch.m[yk] != null ? ", " + label(yk).toLowerCase() + " " + fmtM(yk, ch.m[yk], M.pts) : "") : "not chosen yet"],
        ["tools", "Tool calls", fmtN(st.toolN), fmtN(st.messages) + " messages, " + fmtN(st.artifacts.length) + " files"],
        ["cost", "Agent cost", costTxt, st.cost ? fmtN((st.cost.tin || 0) + (st.cost.tout || 0)) + " tokens" : "reported at the end"]
      ];
      $("#rvTiles").innerHTML = tiles.map(function (x) {
        return '<div class="tile' + (x[2] === "–" ? " empty" : "") + '" data-k="' + x[0] + '"><div class="tl">' + x[1] + '</div><div class="tv">' + x[2] + '</div><div class="ts">' + x[3] + "</div></div>";
      }).join("") + '<span class="mk mea" style="position:absolute;right:12px;top:-9px">recorded</span>';
      $("#rvTiles").style.position = "relative";
      $("#rvTiles").dataset.designs = String(M.pts.length); $("#rvTiles").dataset.chosen = st.chosen || "";
    });
    paintChart(M);
    once("sab", JSON.stringify([st.subs, st.merged]), function () { $("#rvSab").innerHTML = sabHTML(st); });
    once("last", [st.items.length, st.finished && 1].join("|"), function () { $("#rvLast").innerHTML = lastHTML(M); });
    once("fun", [M.pts.length, M.chosen && M.chosen.id, M.pts.filter(function (p) { return p.ver; }).length, M.pts.filter(function (p) { return p.gates != null; }).length].join("|"), function () {
      var compiled = M.pts.filter(function (p) { return p.gates != null; }).length, ver = M.pts.filter(function (p) { return p.ver; }).length;
      var S = [["Designs proposed", M.pts.length], ["Compiled to gates", compiled], ["Verified against the model", ver], ["Chosen", st.chosen ? 1 : 0]];
      $("#rvFun").innerHTML = S.map(function (s, i) { return '<div class="fs' + (i === S.length - 1 ? " last" : "") + (!s[1] ? " mute" : "") + '" data-f="' + i + '"><div class="fn">' + fmtN(s[1]) + '</div><div class="fl">' + s[0] + "</div></div>"; }).join("");
      $("#rvFunn").textContent = "Counted from this run's recorded events up to the time on the bar.";
    });
  }
  function sabHTML(st) {
    if (!st.subOrder.length) return '<h2>Subagent batches</h2><p class="rv-empty">This run used no subagents' + (V && V.last && V.last.ended ? "." : " so far.") + "</p>";
    var by = {}, order = [];
    st.subOrder.forEach(function (k) { var a = st.subs[k], s = a.stage || "other"; if (!by[s]) { by[s] = []; order.push(s); } by[s].push(k); });
    var kept = {}; st.mergedOrder.forEach(function (s) { (st.merged[s].kept || []).forEach(function (k) { kept[k] = 1; }); });
    var fin = st.subOrder.filter(function (k) { return st.subs[k].state !== "running"; }).length;
    return '<h2>Subagent batches</h2><p class="sub">' + fin + " of " + st.subOrder.length + " finished. Hollow: running. Filled: done. Red: failed. Ringed: kept at the merge.</p>" + order.map(function (s) {
      var m = st.merged[s];
      return '<div class="row" data-batch="' + esc(s) + '"><b>' + esc(STAGE_N[s] || s) + '</b><span class="dots">' + by[s].map(function (k) {
        var a = st.subs[k]; return '<i class="' + (kept[k] ? "kept " : "") + (a.state === "running" ? "" : a.state) + '" title="' + esc(clip(a.name, 120) + ": " + a.state + (kept[k] ? ", kept" : "")) + '"></i>';
      }).join("") + "</span></div>" + (m ? '<p class="why">Kept ' + esc(m.kept.join(", ") || "none") + (m.why ? ": " + esc(clip(m.why, 160)) : "") + "</p>" : "");
    }).join("");
  }
  function lastHTML(M) {
    var rec = V.rec, st = M.st, ev = rec.events;
    if (st.finished) {
      var fe = ev[st.finished.i], b = String(fe.bullets || rec.bullets || "").split("\n").map(function (s) { return s.replace(/^[-*]\s*/, "").trim(); }).filter(Boolean);
      return "<h2>Summary</h2><p class=\"sub\">The run's own last word, written when it ended (" + esc(st.finished.status) + ").</p><p style=\"font-size:12.5px;line-height:1.5;margin:0\">" + esc(clip(plain(fe.summary || rec.summary || ""), 520)) + "</p>" + (b.length ? '<ul style="font-size:12px;color:var(--i700);line-height:1.5;padding-left:16px;margin:8px 0 0">' + b.map(function (x) { return "<li>" + esc(clip(plain(x), 200)) + "</li>"; }).join("") + "</ul>" : "");
    }
    var msgs = st.items.filter(function (i) { return ev[i].type === "message"; }).slice(-2);
    return "<h2>Latest from the agent</h2>" + (msgs.length ? msgs.map(function (i) { return '<p style="font-size:12.5px;line-height:1.5;margin:0 0 8px;color:var(--i800)">' + esc(clip(plain(ev[i].text), 320)) + "</p>"; }).join("") : '<p class="rv-empty">No message yet.</p>') + '<p style="margin:6px 0 0"><a class="qbtn" href="#/rec/' + rec.src + "/" + encodeURIComponent(rec.id) + '/log">Open the log</a></p>';
  }
  function pickY(M) {
    var seen = {};
    M.pts.forEach(function (p) { for (var k in p.m) if (!NOT_Y[k] && num(p.m[k]) != null && sizeOf(p) != null) seen[k] = (seen[k] || 0) + 1; });
    var keys = Object.keys(seen);
    V.yKeys = PREF_Y.filter(function (k) { return seen[k]; }).concat(keys.filter(function (k) { return PREF_Y.indexOf(k) < 0; }).sort());
    if (V.y && seen[V.y]) return V.y;
    return V.yKeys[0] || null;
  }
  function paintChart(M) {
    var yk = pickY(M), cv = $("#rvChart"); if (!cv) return;
    var W = cv.clientWidth || 600, H = Math.max(220, Math.min(340, Math.round(W * 0.42)));
    var shown = M.pts.filter(function (p) { return sizeOf(p) != null; });
    var sig = [W, yk, shown.length, M.chosen && M.chosen.id, shown.map(function (p) { return p.id + ":" + sizeOf(p) + ":" + (yk ? p.m[yk] : ""); }).join(",")].join("|");
    var sel = $("#rvY"), opts = (V.yKeys || []).join(",");
    if (sel.dataset.o !== opts) {
      sel.dataset.o = opts; sel.innerHTML = (V.yKeys || []).map(function (k) { return '<option value="' + esc(k) + '">' + esc(label(k)) + "</option>"; }).join("");
      sel.hidden = !(V.yKeys || []).length; $("#rvChH").textContent = sel.hidden ? "Designs by chip size" : "Designs: chip size against";
    }
    if (yk && sel.value !== yk) sel.value = yk;
    if (V.sig.chart === sig) return; V.sig.chart = sig;
    var dpr = devicePixelRatio || 1; cv.width = W * dpr; cv.height = H * dpr; cv.style.height = H + "px";
    var g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    var x0 = 54, x1 = W - 14, y0 = 12, y1 = H - 34;
    g.font = "500 11px Inter, system-ui, sans-serif"; g.fillStyle = "#4a5062"; g.strokeStyle = "rgba(0,0,0,.07)"; g.lineWidth = 1;
    if (!shown.length) {
      g.textAlign = "center"; g.fillText(M.n ? "No design has a size yet at this point in the run." : "Designs appear here as the run finds them.", (x0 + x1) / 2, (y0 + y1) / 2);
      $("#rvLegend").innerHTML = ""; cv.dataset.n = "0"; return;
    }
    var xs = shown.map(sizeOf), xmin = Math.min.apply(null, xs), xmax = Math.max.apply(null, xs), logx = xmax / Math.max(1, xmin) > 20;
    var lx = function (v) { return logx ? Math.log10(Math.max(1, v)) : v; };
    var a = lx(xmin), b = lx(xmax); if (b - a < 1e-9) { a -= 1; b += 1; } var pad = (b - a) * 0.08; a -= pad; b += pad;
    var X = function (v) { return x0 + (lx(v) - a) / (b - a) * (x1 - x0); };
    var withY = yk ? shown.filter(function (p) { return p.m[yk] != null; }) : [];
    var ys = withY.map(function (p) { return p.m[yk]; }), frac = yk && isFrac(yk, shown);
    var c = ys.length ? Math.min.apply(null, ys) : 0, d = ys.length ? Math.max.apply(null, ys) : 1;
    if (frac) { c = Math.max(0, Math.min(c, 1) - 0.05); d = Math.min(1.0, d + 0.03); }
    if (d - c < 1e-9) { c -= 0.5; d += 0.5; }
    var Y = function (v) { return y1 - (v - c) / (d - c) * (y1 - y0); };
    // axes
    g.textAlign = "right";
    if (yk) niceTicks(c, d, true).forEach(function (v) { var yy = Y(v); g.beginPath(); g.moveTo(x0, yy); g.lineTo(x1, yy); g.stroke(); g.fillText(frac ? Math.round(v * 100) + "%" : String(+v.toPrecision(3)), x0 - 6, yy + 4); });
    else { g.beginPath(); g.moveTo(x0, (y0 + y1) / 2); g.lineTo(x1, (y0 + y1) / 2); g.stroke(); }
    g.textAlign = "center";
    var ticks = logx ? [1, 10, 100, 1000, 10000, 100000].filter(function (v) { return lx(v) >= a && lx(v) <= b; }) : niceTicks(a, b);
    ticks.forEach(function (v) { if (v <= 0 && logx) return; g.fillText(fmtN(v), X(v), y1 + 16); });
    g.fillText("Chip size, gates" + (logx ? " (log scale)" : ""), (x0 + x1) / 2, H - 4);
    // points: solid where the size was measured, hollow where only estimated; the chosen chip ringed
    shown.forEach(function (p) {
      var x = X(sizeOf(p)), y = yk && p.m[yk] != null ? Y(p.m[yk]) : yk ? y1 - 2 : (y0 + y1) / 2, est = p.gates == null, ch = M.chosen && M.chosen.id === p.id;
      g.beginPath(); g.arc(x, y, ch ? 5.5 : 4.5, 0, Math.PI * 2);
      if (est) { g.strokeStyle = "#6366f1"; g.lineWidth = 1.5; g.stroke(); } else { g.fillStyle = yk && p.m[yk] == null ? "#c3c8d4" : "#6366f1"; g.fill(); }
      if (ch) { g.beginPath(); g.arc(x, y, 9, 0, Math.PI * 2); g.strokeStyle = "#141a2e"; g.lineWidth = 2; g.stroke(); }
    });
    cv.dataset.n = String(shown.length);
    cv.setAttribute("aria-label", shown.length + " designs with a size" + (M.chosen ? ", chosen chip " + M.chosen.id : ""));
    var noY = shown.length - withY.length;
    $("#rvLegend").innerHTML = '<span><svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="4" fill="#6366f1"/></svg>Size measured</span><span><svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="3.5" fill="none" stroke="#6366f1" stroke-width="1.5"/></svg>Size estimated</span><span><svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="5" fill="none" stroke="#141a2e" stroke-width="2"/></svg>Chosen chip</span>' + (noY && yk ? '<span><svg viewBox="0 0 14 14"><circle cx="7" cy="7" r="4" fill="#c3c8d4"/></svg>' + noY + " without " + esc(label(yk).toLowerCase()) + ", on the floor</span>" : "");
  }
  function logRow(rec, i, st) {
    var e = rec.events[i], at = '<span class="at">' + clock(e._a) + "</span>";
    switch (e.type) {
      case "message": return '<li class="k-msg">' + at + "<span><b>" + esc(e.role === "user" ? "You" : e.author || "Agent") + ".</b> " + esc(clip(plain(e.text), 1200)) + "</span></li>";
      case "status": return '<li class="k-status">' + at + "<span>" + esc(e.text) + "</span></li>";
      case "stage": return '<li class="k-stage">' + at + "<span>" + esc(STAGE_N[e.stage || e.name] || e.stage) + ": " + esc(e.state === "started" ? "started" : e.state) + (e.reason ? ", " + esc(e.reason) : "") + "</span></li>";
      case "tool": { var s = st.tools[e.call_id]; return '<li class="k-tool">' + at + "<span>" + esc(clip(e.summary || e.name, 200)) + (s && s.state === "failed" ? ", failed" : s && s.state === "started" ? ", running" : "") + "</span></li>"; }
      case "error": return '<li class="k-err">' + at + "<span>" + esc(e.message) + "</span></li>";
      case "chosen": return '<li class="k-status">' + at + "<span>Chosen chip: <b>" + esc(e.chip) + "</b></span></li>";
      case "artifact": return '<li class="k-status">' + at + "<span>Wrote the report, " + esc(e.path || e.name) + "</span></li>";
      case "subagent.started": return '<li class="k-tool">' + at + "<span>Subagent " + esc(e.agent || e.id || "") + " started on " + esc(STAGE_N[e.stage] || e.stage || "") + ": " + esc(clip(e.name || e.strategy || "", 140)) + "</span></li>";
      case "stage.merged": return '<li class="k-stage">' + at + "<span>" + esc(STAGE_N[e.stage] || e.stage) + " merged: kept " + esc((e.kept || []).join(", ")) + (e.why ? ", " + esc(clip(e.why, 200)) : "") + "</span></li>";
      case "run.finished": {
        var b = String(e.bullets || rec.bullets || "").split("\n").map(function (x) { return x.replace(/^[-*]\s*/, "").trim(); }).filter(Boolean);
        return '<li class="k-fin">' + at + "<div><p><b>Run " + esc(e.status) + ".</b> " + esc(plain(e.summary)) + "</p>" + (b.length ? "<ul>" + b.map(function (x) { return "<li>" + esc(plain(x)) + "</li>"; }).join("") + "</ul>" : "") + "</div></li>";
      }
      default: return "";
    }
  }
  function paintLog(M) {
    var ul = $("#rvLog"); if (!ul) return;
    var st = M.st, items = st.items, rec = V.rec;
    var toolSig = Object.keys(st.tools).filter(function (k) { return st.tools[k].state !== "done"; }).join(",");
    if (items.length < V.logN || V.logTools !== toolSig) V.logN = 0; // back in time, or a tool's state moved: redraw
    V.logTools = toolSig;
    var start = Math.max(V.logN, items.length - LOG_MAX);
    if (V.logN === 0 || start > V.logN) ul.innerHTML = "";
    if (items.length > start) {
      var atBottom = $("#rvBody") && $("#rvBody").scrollHeight - $("#rvBody").scrollTop - $("#rvBody").clientHeight < 40;
      var html = ""; for (var i = start; i < items.length; i++) html += logRow(rec, items[i], st);
      ul.insertAdjacentHTML("beforeend", html);
      while (ul.children.length > LOG_MAX) ul.firstChild.remove();
      if (atBottom && V.clock.advancing()) $("#rvBody").scrollTop = $("#rvBody").scrollHeight;
    }
    V.logN = items.length; ul.dataset.n = String(items.length);
    if (!items.length && !ul.children.length) ul.innerHTML = '<li><span class="at">0:00</span><span class="rv-empty">Nothing yet at this point in the run.</span></li>';
  }
  function paintFiles(M) {
    var el = $("#rvFiles"); if (!el) return;
    var st = M.st, rec = V.rec, seen = {}, rows = [];
    st.artifacts.forEach(function (i) { var e = rec.events[i]; if (e.path && !seen[e.path]) { seen[e.path] = 1; rows.push(e); } });
    once("files", rows.length + "", function () {
      el.dataset.n = String(rows.length);
      el.innerHTML = rows.length ? rows.map(function (e) {
        var have = rec.src === "mac" || (rec.files || []).some(function (f) { return f.path === e.path; });
        return '<button class="rv-f" data-path="' + esc(e.path) + '"' + (have ? "" : " disabled") + ">" + icon("file", false).replace('class="pb-si"', "") + "<span>" + esc(e.name || e.path) + (e.kind === "report" ? ' <span class="mk mea">report</span>' : "") + '</span><span class="p">' + esc(e.path) + (have ? "" : ", not in this copy") + "</span></button>";
      }).join("") : '<p class="rv-empty">No file written yet at this point in the run.</p>';
    });
  }
  function openFile(path) {
    var rec = V.rec, show = function (text, note) {
      closePicker();
      var s = document.createElement("div"); s.className = "pb-scrim";
      s.innerHTML = '<div class="pb-dlg" role="dialog" aria-modal="true" aria-label="' + esc(path) + '" tabindex="-1" style="width:min(820px,100%)"><header><div style="flex:1"><h2 style="font-size:18px">' + esc(path.split("/").pop()) + '</h2><p>' + esc(path) + (note ? ". " + esc(note) : "") + '</p></div><button class="pb-b" data-x aria-label="Close">' + icon("x", false) + '</button></header><pre class="rv-pre"></pre></div>';
      $(".rv-pre", s).textContent = text; document.body.appendChild(s); $(".pb-dlg", s).focus();
      s.addEventListener("click", function (e) { if (e.target === s || e.target.closest("[data-x]")) s.remove(); });
      s.addEventListener("keydown", function (e) { if (e.key === "Escape") { e.stopPropagation(); s.remove(); } });
    };
    if (rec.src === "site") { var f = (rec.files || []).find(function (x) { return x.path === path; }); if (f) show(f.text, f.truncated ? "Cut to its first part in this copy" : ""); return; }
    var c = conn(); if (!c) return;
    fetch(c.base + "/api/runs/" + encodeURIComponent(rec.id) + "/file?path=" + encodeURIComponent(path), { headers: { "X-ChipIn-Token": c.token }, cache: "no-store" })
      .then(function (r) { return r.ok ? r.text() : Promise.reject(new Error("HTTP " + r.status)); })
      .then(function (t) { show(t, ""); }, function (e) { show("This file could not be read (" + e.message + ").", ""); });
  }

  // leaving a recorded run (or a run page) takes the bar down
  addEventListener("hashchange", function () { if (!owns()) { if (V) { V = null; } if (BAR && BAR.ctl.kind === "recorded") unmountBar(); } });

  /* ---------- for tests: what the open recorded run shows now ---------- */
  function state() {
    if (!V || !V.last) return null;
    var M = V.last, st = M.st, stages = {};
    STAGES.forEach(function (s) { stages[s] = st.stages[s].state; });
    return {
      key: V.rec.key, t: Math.round(V.clock.now() * 1000) / 1000, total: V.clock.total, speed: V.clock.speed, playing: V.clock.playing, live: V.clock.live && V.clock.atLive,
      events: M.n, stages: stages, status: st.status, designs: M.pts.length, chosen: st.chosen, messages: st.messages, tools: st.toolN, artifacts: st.artifacts.length,
      subagents: st.subOrder.length, subagentsDone: st.subOrder.filter(function (k) { return st.subs[k].state !== "running"; }).length, merged: st.mergedOrder.slice(), finished: st.finished ? st.finished.status : null
    };
  }

  window.ChipInPlayback = {
    version: 1, SPEEDS: SPEEDS.slice(), owns: owns, render: render, mountExample: mountExample, pastLink: pastLink, cleanHash: cleanHash,
    state: state, openPicker: openPicker,
    clock: function () { return BAR ? { t: BAR.ctl.clock.now(), total: BAR.ctl.clock.total, speed: BAR.ctl.clock.speed, playing: BAR.ctl.clock.playing, live: BAR.ctl.clock.live && BAR.ctl.clock.atLive, kind: BAR.ctl.kind } : null; }
  };
})();
