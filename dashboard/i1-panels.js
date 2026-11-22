/*
 * i1-panels.js: the secondary panels of the ChipIn dashboard (battery, confidence, cost,
 * measured so far) as one module. Defines window.ChipInPanels and injects its own scoped
 * styles (classes prefixed "cpn"). Depends only on window.ChipInModels (chipin-models.js,
 * loaded first). Every power, battery, interval and cost figure comes from ChipInModels;
 * this file only formats and lays them out.
 *
 * CONTEXT. Every call takes one context object:
 *   ctx = {
 *     caseKind: "ecg-patch" | "eeg-monitor" | "incubator-radar-thermal",
 *     budgets: [ { key, label, channels, sensors } ],   // the channel or sensor budgets of the case
 *     chosen: design | null,                            // the chip the page chose
 *     selected: design | null,                          // the dot the user selected
 *     targets: [ { metric, op, value } ],               // op ">=" | "<="; fractions for rates
 *     primary: metric name,                             // "sensitivity" (family) or a field such as
 *                                                       // "sensitivity_worst"; families resolve to the
 *                                                       // first field the design has: _worst, _pooled, plain
 *     batteryTargetHours: number | null,                // wear time the user asked for
 *     reusable: true | false | null,                    // false = disposable
 *     decisionsPerSecond: number,                       // passed to the chip power model
 *     dataSource: "simulated" | "measured",
 *     patientsUnseen: number,                           // held-out patients (or recordings)
 *     costInputs: object | null,                        // overrides of ChipInModels.COST_DEFAULTS
 *     who: string (optional, default "patients")        // plural noun for the unseen people
 *   }
 *   design = { id, channels, sensors?, gates, metrics: { ... },
 *              counts: { events_caught, events_total, negatives_correct, negatives_total, hours, patients },
 *              per_patient?: [ { id, caught, total, neg_correct, neg_total } ],
 *              source: "simulated" | "measured" }
 *
 * API
 *   ChipInPanels.mountBattery(el, ctx) -> { update(ctx) }
 *       "What this means for the battery": one row per budget (ChipInModels.classBoundaries,
 *       breakdown from deviceBudget): device power with the chip's share, battery class, life,
 *       judged against batteryTargetHours and reusable; class tips marked with
 *       ChipInModels.CONSEQUENCES; headline from ChipInModels.channelStory(caseKind,
 *       { budgets, gates, decisionsPerSecond }) when it exists (its first sentence leads, the
 *       rest sits under "More from the power model"); "the chip is never your battery
 *       bottleneck" only when the chip is under 1% of device power in every budget. The chip's
 *       gates are chosen.gates (else selected.gates, else the model's default 2,500).
 *   ChipInPanels.batteryClassFor(ctx, budgetKey) -> { class, label, color, hex } | null
 *       color is a CSS custom property name ("--okt" | "--amb" | "--badt"); hex its value.
 *   ChipInPanels.intervalFor(design, metric)
 *       -> { low, high, k, n, value, field, patient, derived } | null
 *       ChipInModels.wilson on the design's own counts. _worst fields use the worst patient in
 *       per_patient (patient = its id); pooled fields use counts. When a count is missing but
 *       the rate and total are given and k = rate x n is a whole number to 4 decimals, k is
 *       taken from them (derived: true). Rates such as false alarms per hour give null.
 *   ChipInPanels.mountConfidence(el, ctx) -> { update(ctx) }
 *       "How sure is this?": ChipInModels.confidenceHeadline, then three parts: the chosen
 *       design's interval on the primary metric, generalisation risk in plain words, and the
 *       engineering estimates; plus ChipInModels.cannotTellApart when selected and chosen differ.
 *   ChipInPanels.openCost(ctx, onChange) -> { close() }
 *       Drawer "Cost assumptions": every ChipInModels.COST_DEFAULTS input editable, live
 *       recomputation with costModel and costDelta; onChange(inputs) after each valid edit.
 *       The battery class follows the design unless the user picks one.
 *   ChipInPanels.costLine(ctx) -> { unit_cost_text, unit_cost_short, delta_text, delta_short, tip }
 *       Unit cost of selected (or chosen) and costDelta's sentence, chosen against selected.
 *   ChipInPanels.openMeasured(facts) -> { close() }
 *       Drawer "Measured so far" listing only the facts handed in:
 *       facts = [ { title, text, scope, source_name?, source_url? } ].
 *       After the facts it appends "Against a published AF chip", written from data/af-baseline.json.
 *   ChipInPanels.defaultFacts() -> facts that need no data file.
 *   ChipInPanels.footerCredit() -> the footer credit sentence.
 *
 * Conventions match dashboard/variants/i1.html: estimates are italic with a dotted underline
 * and a title naming the assumption (ChipInModels.describeEstimate); small marks "measured",
 * "simulated", "estimated"; pass and fail pills.
 */
(function (root) {
  "use strict";

  var M = function () {
    if (!root.ChipInModels) throw new Error("i1-panels.js needs chipin-models.js loaded first");
    return root.ChipInModels;
  };

  /* ---------------------------------------------------------------- styles */
  var CSS = [
    ".cpn{--cpn-ink:var(--i900,#141a2e);--cpn-ink2:var(--i700,#3a4052);--cpn-ink3:var(--i600,#4a5062);--cpn-mute:var(--i300,#b2b6c2);--cpn-line:var(--hair,rgb(0 0 0/.07));--cpn-soft:var(--i100,#f1f2f6);",
    "font-family:var(--sans,Inter,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif);color:var(--cpn-ink);font-size:13px;line-height:1.5;container-type:inline-size;min-width:0}",
    ".cpn *{box-sizing:border-box}",
    ".cpn .est{font-style:italic;text-decoration:underline dotted rgb(20 26 46/.5);text-underline-offset:3px;cursor:help}",
    ".cpn .mk{display:inline-flex;align-items:center;font-size:10.5px;font-weight:600;border-radius:99px;padding:1px 7px;white-space:nowrap;vertical-align:1px;font-style:normal;letter-spacing:0;line-height:1.5}",
    ".cpn .mk.sim{color:#7c3a06;background:#fff3e0}.cpn .mk.mea{color:#0b5a3f;background:#e6f5ed}.cpn .mk.no{color:var(--cpn-ink3);background:var(--cpn-soft)}",
    ".cpn .pf{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:650;border-radius:99px;padding:1px 8px;white-space:nowrap;line-height:1.5}",
    ".cpn .pf.ok{color:#0b5a3f;background:#e6f5ed}.cpn .pf.no{color:#9f2a20;background:var(--badbg,#fdf0ee)}.cpn .pf.na{color:var(--cpn-ink3);background:var(--cpn-soft)}",
    ".cpn a{color:var(--blue7,#2b55d0)}",
    ".cpn-pan{background:#fff;border:1px solid rgb(0 0 0/.07);border-radius:16px;box-shadow:var(--sh-hair,0 1px 3px rgb(0 0 0/.04));padding:16px 18px}",
    ".cpn-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 0 10px}",
    ".cpn-h h2{font-size:13.5px;font-weight:650;margin:0;color:var(--cpn-ink)}",
    ".cpn-h .cpn-sub{font-size:12px;color:var(--cpn-ink3)}",
    ".cpn-lede{font-family:var(--serif,'Source Serif 4',Georgia,serif);font-size:17px;line-height:1.4;color:var(--cpn-ink);margin:0 0 6px;text-wrap:pretty;max-width:64ch}",
    ".cpn-ask{font-size:12.5px;color:var(--cpn-ink3);margin:0 0 12px}",
    ".cpn-more{font-size:12.5px;color:var(--cpn-ink2);margin:0 0 8px;max-width:78ch}",
    ".cpn-more summary{cursor:pointer;color:var(--blue7,#2b55d0);font-weight:600;width:fit-content;max-width:100%}",
    ".cpn-more p{margin:6px 0 0;line-height:1.55}",
    ".cpn-ask b{font-weight:600;color:var(--cpn-ink2)}",
    /* battery rows */
    ".cpn-rows{border-top:1px solid var(--cpn-line)}",
    ".cpn-row{border-bottom:1px solid var(--cpn-line)}",
    ".cpn-row>summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:minmax(92px,1.1fr) minmax(110px,1fr) minmax(150px,1.3fr) minmax(120px,1.2fr) auto;gap:4px 14px;align-items:baseline;padding:9px 4px 9px 2px;border-radius:8px}",
    ".cpn-row>summary::-webkit-details-marker{display:none}",
    ".cpn-row>summary:hover{background:rgb(0 0 0/.02)}",
    ".cpn-row>summary:focus-visible{outline:2px solid var(--blue,#3d6df0);outline-offset:1px}",
    ".cpn-bl{font-weight:600;color:var(--cpn-ink);display:flex;align-items:baseline;gap:6px}",
    ".cpn-bl::before{content:'';width:6px;height:6px;border-right:1.5px solid var(--cpn-mute);border-bottom:1.5px solid var(--cpn-mute);transform:rotate(-45deg);flex:none;position:relative;top:-2px;transition:transform .15s}",
    ".cpn-row[open] .cpn-bl::before{transform:rotate(45deg)}",
    ".cpn-pw{font-variant-numeric:tabular-nums;color:var(--cpn-ink)}",
    ".cpn-pw small{display:block;font-size:11.5px;color:var(--cpn-ink3);font-style:normal}",
    ".cpn-cl{display:inline-flex;align-items:baseline;gap:7px;color:var(--cpn-ink2)}",
    ".cpn-dot{width:8px;height:8px;border-radius:50%;flex:none;align-self:center}",
    ".cpn-life{color:var(--cpn-ink2);font-variant-numeric:tabular-nums}",
    ".cpn-vd{justify-self:end}",
    ".cpn-row.out>summary .cpn-bl,.cpn-row.out>summary .cpn-pw,.cpn-row.out>summary .cpn-cl,.cpn-row.out>summary .cpn-life{opacity:.5}",
    ".cpn-why{font-size:12px;color:var(--cpn-ink3);grid-column:1/-1;margin:0;padding-left:12px}",
    ".cpn-lines{margin:0 0 10px 12px;padding:8px 12px;background:var(--cpn-soft);border-radius:10px;font-size:12px}",
    ".cpn-ln{display:grid;grid-template-columns:minmax(0,1fr) auto 64px;gap:12px;padding:3px 0;align-items:baseline}",
    ".cpn-ln span:nth-child(2),.cpn-ln span:nth-child(3){text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}",
    ".cpn-ln .src{display:block;font-size:11px;color:var(--cpn-ink3)}",
    ".cpn-ln.chip{color:var(--c-chip,#a04812)}",
    ".cpn-lines p{margin:6px 0 0;color:var(--cpn-ink3)}",
    ".cpn-tip{margin:0;padding:10px 0 10px 12px;border-bottom:1px solid var(--cpn-line);border-left:2px solid var(--cpn-tc,#b45309)}",
    ".cpn-tip>b{display:block;font-size:12.5px;font-weight:650;color:var(--cpn-ink)}",
    ".cpn-cons{list-style:none;margin:6px 0 0;padding:0;display:grid;gap:3px}",
    ".cpn-cons li{font-size:12.5px;color:var(--cpn-ink2);line-height:1.45}",
    ".cpn-cons .k{font-size:11px;color:var(--cpn-ink3);margin-left:6px}",
    ".cpn-same{font-size:12.5px;color:var(--cpn-ink2);margin:10px 0 0}",
    ".cpn-same summary{cursor:pointer;color:var(--blue7,#2b55d0);font-weight:600;width:fit-content;max-width:100%}",
    ".cpn-foot{font-size:11.5px;color:var(--cpn-ink3);margin:12px 0 0;line-height:1.5}",
    /* confidence */
    ".cpn-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 12px}",
    ".cpn-lvl{display:inline-flex;align-items:center;gap:3px}",
    ".cpn-lvl i{width:14px;height:6px;border-radius:3px;background:var(--i150,#e7e9ee)}",
    ".cpn-lvl.low i:nth-child(-n+1),.cpn-lvl.medium i:nth-child(-n+2),.cpn-lvl.high i{background:var(--cpn-ink2)}",
    ".cpn-head b{font-family:var(--serif,'Source Serif 4',Georgia,serif);font-weight:400;font-size:18px;line-height:1.3}",
    ".cpn-parts{display:grid;gap:0;border-top:1px solid var(--cpn-line)}",
    ".cpn-part{display:grid;grid-template-columns:128px minmax(0,1fr);gap:4px 14px;padding:10px 0;border-bottom:1px solid var(--cpn-line)}",
    ".cpn-part:last-child{border-bottom:0}",
    ".cpn-part>span{font-size:12px;color:var(--cpn-ink3);padding-top:1px}",
    ".cpn-part>div{font-size:12.5px;color:var(--cpn-ink2);min-width:0}",
    ".cpn-part>div b{font-weight:600;color:var(--cpn-ink);font-variant-numeric:tabular-nums}",
    ".cpn-rng{margin:8px 0 2px}",
    ".cpn-rr{display:grid;grid-template-columns:64px minmax(0,1fr);gap:10px;align-items:center;height:22px}",
    ".cpn-rr>span{font-size:11.5px;color:var(--cpn-ink3)}",
    ".cpn-trk{position:relative;height:22px}",
    ".cpn-trk::before{content:'';position:absolute;left:0;right:0;top:50%;height:1px;background:var(--i200,#d5d8e0)}",
    ".cpn-iv{position:absolute;top:calc(50% - 2px);height:4px;border-radius:2px;background:var(--blue7,#2b55d0);opacity:.35;min-width:2px}",
    ".cpn-pt{position:absolute;top:50%;width:9px;height:9px;margin:-4.5px 0 0 -4.5px;border-radius:50%;background:var(--blue7,#2b55d0);box-shadow:0 0 0 2px #fff}",
    ".cpn-rr.sel .cpn-iv{background:var(--i700,#3a4052)}.cpn-rr.sel .cpn-pt{background:var(--i700,#3a4052)}",
    ".cpn-tg{position:absolute;top:0;bottom:0;border-left:1.5px dashed var(--cpn-ink2)}",
    ".cpn-ax{display:grid;grid-template-columns:64px minmax(0,1fr);gap:10px;font-size:10.5px;color:var(--cpn-ink3)}",
    ".cpn-ax div{display:flex;justify-content:space-between;position:relative}",
    ".cpn-key{font-size:11px;color:var(--cpn-ink3);margin:4px 0 0}",
    ".cpn-key i{display:inline-block;width:0;height:10px;border-left:1.5px dashed var(--cpn-ink2);margin:0 5px -1px 0}",
    ".cpn-apart{margin:10px 0 0;font-size:12.5px;color:var(--cpn-ink);background:var(--cpn-soft);border-radius:10px;padding:8px 11px}",
    /* inspector line */
    ".cpn-empty{font-size:12.5px;color:var(--cpn-ink3);margin:0}",
    /* drawers */
    ".cpn-scrim{position:fixed;inset:0;background:rgb(20 20 40/.16);z-index:70;animation:cpnfade .15s}",
    "@keyframes cpnfade{from{opacity:0}}",
    ".cpn-drawer{position:fixed;top:0;right:0;bottom:0;width:min(460px,100%);background:#fff;z-index:71;box-shadow:-12px 0 40px rgb(0 0 0/.12);display:flex;flex-direction:column;animation:cpnin .2s var(--ease,cubic-bezier(.4,0,.2,1))}",
    "@keyframes cpnin{from{transform:translateX(24px);opacity:0}}",
    ".cpn-dh{display:flex;align-items:center;gap:10px;padding:16px 18px;border-bottom:1px solid var(--cpn-line)}",
    ".cpn-dh h3{margin:0;font-size:15.5px;font-weight:650}",
    ".cpn-dh button{margin-left:auto;width:30px;height:30px;border-radius:7px;display:grid;place-items:center;color:var(--cpn-ink3);background:none;border:0;cursor:pointer}",
    ".cpn-dh button:hover{background:var(--cpn-soft)}",
    ".cpn-db{flex:1;overflow:auto;padding:14px 18px 30px}",
    ".cpn-db h4{font-size:12.5px;font-weight:600;color:var(--cpn-ink3);margin:20px 0 8px}",
    ".cpn-db h4:first-child{margin-top:4px}",
    ".cpn-big{font-family:var(--serif,'Source Serif 4',Georgia,serif);font-size:30px;line-height:1.1;margin:2px 0 2px;font-variant-numeric:tabular-nums}",
    ".cpn-big small{font-family:var(--sans,Inter,system-ui,sans-serif);font-size:12.5px;color:var(--cpn-ink3);margin-left:6px;font-style:normal}",
    ".cpn-kv{display:flex;justify-content:space-between;gap:16px;padding:6px 0;border-bottom:1px solid var(--cpn-line);font-size:12.5px}",
    ".cpn-kv span:last-child{font-variant-numeric:tabular-nums;text-align:right}",
    ".cpn-note{font-size:12px;color:var(--cpn-ink3);margin:8px 0 0;line-height:1.5}",
    ".cpn-delta{font-size:13px;color:var(--cpn-ink);line-height:1.55;margin:0;background:var(--cpn-soft);border-radius:10px;padding:9px 11px}",
    ".cpn-f{display:grid;grid-template-columns:minmax(0,1fr) 156px;gap:2px 14px;align-items:center;padding:8px 0;border-bottom:1px solid var(--cpn-line)}",
    ".cpn-f label{font-size:12.5px;color:var(--cpn-ink);font-weight:500}",
    ".cpn-f .d{grid-column:1;font-size:11.5px;color:var(--cpn-ink3)}",
    ".cpn-f input,.cpn-f select{grid-row:1/3;grid-column:2;height:32px;width:100%;border:1px solid var(--i200,#d5d8e0);border-radius:9px;padding:0 9px;font:inherit;font-size:13px;background:#fff;outline:0;color:inherit;font-variant-numeric:tabular-nums}",
    ".cpn-f input:focus,.cpn-f select:focus{border-color:var(--blue7,#2b55d0);box-shadow:0 0 0 3px rgb(61 109 240/.14)}",
    ".cpn-f input.bad{border-color:#c2362b}",
    ".cpn-f.edited label::after{content:'edited';margin-left:8px;font-size:10.5px;font-weight:600;color:var(--blue7,#2b55d0)}",
    ".cpn-reset{margin-top:14px;height:32px;padding:0 12px;border-radius:9px;border:1px solid rgb(0 0 0/.12);background:#fff;font:inherit;font-size:12.5px;font-weight:500;cursor:pointer;color:var(--cpn-ink2)}",
    ".cpn-reset:hover{background:var(--cpn-soft)}",
    ".cpn-fact{padding:12px 0;border-bottom:1px solid var(--cpn-line)}",
    ".cpn-fact:last-child{border:0}",
    ".cpn-afrow{margin-top:10px}.cpn-afrow .t{font-size:13px}.cpn-af{overflow-wrap:anywhere}",
    ".cpn-fact .t{font-size:14px;font-weight:600;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}",
    ".cpn-fact .x{font-size:13px;color:var(--cpn-ink);margin:4px 0 0;line-height:1.5}",
    ".cpn-fact .s{font-size:12px;color:var(--cpn-ink3);margin:4px 0 0;line-height:1.5}",
    /* narrow mounts */
    "@container (max-width:620px){",
    ".cpn-row>summary{grid-template-columns:auto minmax(0,1fr) auto;grid-template-areas:'bl bl vd' 'pw pw pw' 'cl lf lf' 'wy wy wy';gap:2px 12px}",
    ".cpn-row>summary .cpn-bl{grid-area:bl}.cpn-row>summary .cpn-pw{grid-area:pw;padding-left:12px}.cpn-row>summary .cpn-cl{grid-area:cl;padding-left:12px}.cpn-row>summary .cpn-life{grid-area:lf}.cpn-vd{grid-area:vd}.cpn-why{grid-area:wy}",
    ".cpn-lines{margin-left:0}",
    ".cpn-pw small{display:inline;margin-left:6px}",
    ".cpn-part{grid-template-columns:1fr}",
    ".cpn-lede{font-size:16px}}",
    "@media (prefers-reduced-motion:reduce){.cpn-drawer,.cpn-scrim{animation:none}}",
  ].join("\n");

  function injectCss() {
    if (typeof document === "undefined" || document.getElementById("cpn-styles")) return;
    var s = document.createElement("style");
    s.id = "cpn-styles";
    s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }

  /* ------------------------------------------------------------ formatting */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmtInt(x) {
    return Math.round(x).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }
  function pct1(x) {
    return (x * 100).toFixed(1) + "%";
  }
  function sharePct(x) {
    var v = x * 100;
    return (v < 0.01 ? v.toPrecision(2) : v < 1 ? v.toFixed(3) : v.toFixed(1)) + "%";
  }
  function mW(uw) {
    return (uw / 1000).toPrecision(3) + " mW";
  }
  function uW(uw) {
    return uw >= 1000 ? mW(uw) : uw >= 10 ? Math.round(uw) + " µW" : uw.toPrecision(2) + " µW";
  }
  function life(days) {
    return days >= 2 ? fmtInt(days) + " days" : (days * 24).toFixed(1) + " h";
  }
  function hoursText(h) {
    return h >= 48 && h % 24 === 0 ? h / 24 + " days" : fmtInt(h) + " h";
  }
  function money(x) {
    return "$" + Math.abs(x).toFixed(2);
  }
  function est(txt, field) {
    return '<span class="est" title="' + esc(M().describeEstimate(field)) + '">' + txt + "</span>";
  }
  function estT(txt, tip) {
    return '<span class="est" title="' + esc(tip) + '">' + txt + "</span>";
  }
  // a short note's full sentence, shown on hover, focus or tap by ../i1-tip.js (a plain title without it)
  function tipA(full) {
    return window.ChipInTip ? window.ChipInTip.attr(full) : ' title="' + esc(full) + '"';
  }
  function plain(h) {
    return String(h).replace(/<[^>]+>/g, "").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");
  }
  var MK_SIM = '<span class="mk sim">simulated</span>';
  var MK_MEA = '<span class="mk mea">measured</span>';
  var MK_EST = '<span class="mk no">estimated</span>';
  var MK_ILL = '<span class="mk no">illustrative</span>'; // the battery-class minimum life only, never cost
  function srcMark(d) {
    return d && d.source === "measured" ? MK_MEA : MK_SIM;
  }
  function cellShort(name) {
    return name ? String(name).split(" ")[0] : "";
  }

  /* ---------------------------------------------------------- battery class */
  var CLASS_LOOK = {
    "primary coin cell": { label: "Coin cell", color: "--okt", hex: "#047857" },
    "rechargeable lithium": { label: "Rechargeable lithium", color: "--amb", hex: "#b45309" },
    "larger pack or mains": { label: "Larger pack or mains", color: "--badt", hex: "#b91c1c" },
  };
  function look(cls) {
    return CLASS_LOOK[cls] || { label: cls, color: "--i500", hex: "#5c6276" };
  }
  function unitWord(ctx) {
    var k = M().DEVICE_KINDS[ctx.caseKind];
    return k ? k.unit : "channels";
  }
  function budgetCount(ctx, b) {
    return ctx.caseKind === "incubator-radar-thermal" ? (b.sensors != null ? b.sensors : b.channels) : b.channels != null ? b.channels : b.sensors;
  }
  function chipGates(ctx) {
    var d = ctx.chosen || ctx.selected;
    return d && d.gates > 0 ? d.gates : 2500;
  }
  function dps(ctx) {
    return ctx.decisionsPerSecond > 0 ? ctx.decisionsPerSecond : 1;
  }
  function rowsFor(ctx) {
    var budgets = ctx.budgets || [];
    var rows = M().classBoundaries(ctx.caseKind, {
      budgets: budgets.map(function (b) {
        return budgetCount(ctx, b);
      }),
      gates: chipGates(ctx),
      decisionsPerSecond: dps(ctx),
    });
    return rows.map(function (r, i) {
      r.key = budgets[i].key;
      r.label = budgets[i].label;
      r.parts = M().deviceBudget({
        kind: ctx.caseKind,
        channels: budgetCount(ctx, budgets[i]),
        sensors: budgetCount(ctx, budgets[i]),
        gates: chipGates(ctx),
        decisionsPerSecond: dps(ctx),
      });
      r.verdict = verdict(ctx, r);
      return r;
    });
  }
  // judged against the user's wear-time target and the disposable or reusable answer
  function verdict(ctx, r) {
    var T = ctx.batteryTargetHours;
    if (ctx.reusable === false && r.class !== "primary coin cell")
      return { out: true, pill: '<span class="pf no">Not disposable</span>', why: (r.class === "rechargeable lithium" ? "A rechargeable cell means a reusable device; " : "A larger pack or mains supply is not a disposable patch; ") + "you asked for disposable." };
    if (T > 0) {
      if (r.class === "larger pack or mains")
        return { out: false, pill: '<span class="pf na">Depends on the pack</span>', why: "" };
      var meets = r.life_days * 24 >= T;
      return meets
        ? { out: false, pill: '<span class="pf ok">Meets ' + esc(hoursText(T)) + "</span>", why: "" }
        : { out: true, pill: '<span class="pf no">Misses ' + esc(hoursText(T)) + "</span>", why: "Lasts " + life(r.life_days) + (r.class === "rechargeable lithium" ? " per charge" : "") + ", under your " + hoursText(T) + "." };
    }
    return { out: false, pill: "", why: "" };
  }

  function batteryClassFor(ctx, budgetKey) {
    var rows = rowsFor(ctx);
    for (var i = 0; i < rows.length; i++)
      if (String(rows[i].key) === String(budgetKey)) {
        var l = look(rows[i].class);
        return { class: rows[i].class, label: l.label, color: l.color, hex: l.hex };
      }
    return null;
  }

  function consequencesHTML(cls) {
    var list = M().CONSEQUENCES[cls] || [];
    return '<ul class="cpn-cons">' + list.map(function (c) {
      var tag = c.kind === "sourced"
        ? '<span class="k">sourced: ' + (c.source_url ? '<a href="' + esc(c.source_url) + '" target="_blank" rel="noopener">' + esc(c.source_name) + "</a>" : esc(c.source_name)) + "</span>"
        : '<span class="k">general engineering knowledge</span>';
      return "<li>" + esc(c.text) + tag + "</li>";
    }).join("") + "</ul>";
  }

  // ChipInModels.channelStory(kind, opts) -> { text, estimate, tips } when the model has it
  function storyHTML(ctx) {
    var fn = M().channelStory;
    if (typeof fn !== "function") return "";
    var s;
    try {
      s = fn(ctx.caseKind, {
        budgets: (ctx.budgets || []).map(function (b) {
          return budgetCount(ctx, b);
        }),
        gates: chipGates(ctx),
        decisionsPerSecond: dps(ctx),
      });
    } catch (e) {
      return "";
    }
    if (!s || !s.text) return "";
    // the first sentence leads; the rest of the model's story sits one click away
    var parts = String(s.text).split(/(?<=\.)\s+(?=[A-Z])/);
    var wrap = function (t) {
      return s.estimate ? estT(esc(t), typeof s.estimate === "string" ? M().describeEstimate(s.estimate) : M().describeEstimate("device_power")) : esc(t);
    };
    return { lead: wrap(parts[0]), more: parts.length > 1 ? wrap(parts.slice(1).join(" ")) : "" };
  }

  function batteryHTML(ctx, openKeys) {
    var rows = rowsFor(ctx);
    var unit = unitWord(ctx);
    var d = ctx.chosen || ctx.selected;
    var gatesTxt = d && d.gates > 0 ? fmtInt(d.gates) + " gates " + (d.source === "measured" ? '<span class="mk mea">measured</span>' : '<span class="mk sim">simulated</span>') : "2,500 gates (the model's default; no chip chosen yet)";
    var maxShare = 0;
    rows.forEach(function (r) {
      if (r.chip_share > maxShare) maxShare = r.chip_share;
    });
    var story = storyHTML(ctx) || { lead: "", more: "" };
    var neck = rows.length && maxShare < 0.01
      ? "The chip is never your battery bottleneck: at most " + estT(sharePct(maxShare), M().describeEstimate("chip_power")) + " of device power in these budgets."
      : "";
    var lede = [story.lead, neck].filter(Boolean).join(" ");
    // shown short: the chip's share; the channel story (the rows below show its figures) is in the detail
    if (neck) lede = "<span" + tipA(plain(lede) + " Estimated: " + M().describeEstimate("device_power")) + ">The chip is never the bottleneck: at most " + estT(sharePct(maxShare), M().describeEstimate("chip_power")) + " of device power in these budgets.</span>";

    var dev = ctx.reusable === true ? "a <b>reusable</b> device" : ctx.reusable === false ? "a <b>disposable</b> device" : "";
    var ask = ctx.batteryTargetHours > 0
      ? "You asked for at least <b>" + esc(hoursText(ctx.batteryTargetHours)) + "</b> per cell or charge" + (dev ? ", " + dev : "") + "."
      : "No wear-time target set" + (dev ? "; " + dev : "") + ".";
    if (ctx.reusable == null) ask += " Disposable or reusable is not set.";
    // shown short when a target is set: the target and the device kind; the full sentence on hover
    if (ctx.batteryTargetHours > 0) {
      var kind = ctx.reusable === true ? "; <b>reusable</b>" : ctx.reusable === false ? "; <b>disposable</b>" : "; reusable or not unset";
      ask = "<span" + tipA(plain(ask)) + ">Target: at least <b>" + esc(hoursText(ctx.batteryTargetHours)) + "</b> per cell or charge" + kind + ".</span>";
    }

    var html = "";
    rows.forEach(function (r, i) {
      if (i > 0 && rows[i - 1].class !== r.class) {
        html += '<div class="cpn-tip" role="listitem" style="--cpn-tc:' + look(r.class).hex + '"><b>The device tips here: from ' + esc(r.label) + " it needs " + esc(r.class === "larger pack or mains" ? "a larger pack or mains" : "a " + r.class + " cell") + ".</b>" + consequencesHTML(r.class) + "</div>";
      }
      var l = look(r.class);
      var lifeTxt = r.class === "primary coin cell"
        ? est(life(r.life_days), "battery_life") + " on a " + esc(cellShort(r.cell))
        : r.class === "rechargeable lithium"
          ? est(life(r.life_days), "battery_life") + " per charge"
          : "the reference rechargeable lasts " + est(life(r.life_days), "battery_life");
      var lines = r.parts.lines.map(function (ln, j) {
        var isChip = j === r.parts.lines.length - 1;
        return '<div class="cpn-ln' + (isChip ? " chip" : "") + '"><span>' + esc(ln.name) +
          '<span class="src">' + (isChip ? "estimate from one run, " + esc(ln.source_name) : esc(ln.kind) + (ln.source_name ? ", " + (ln.source_url ? '<a href="' + esc(ln.source_url) + '" target="_blank" rel="noopener">' + esc(ln.source_name) + "</a>" : esc(ln.source_name)) : "")) + "</span></span>" +
          "<span>" + est(uW(ln.power_uw), isChip ? "chip_power" : "device_power") + "</span><span>" + est(sharePct(ln.share), "device_power") + "</span></div>";
      }).join("");
      html += '<details class="cpn-row' + (r.verdict.out ? " out" : "") + '" role="listitem" data-key="' + esc(r.key) + '"' + (openKeys[r.key] ? " open" : "") + ">" +
        "<summary>" +
        '<span class="cpn-bl">' + esc(r.label) + "</span>" +
        '<span class="cpn-pw">' + est(mW(r.total_uw), "device_power") + "<small>chip " + est(sharePct(r.chip_share), "chip_power") + "</small></span>" +
        '<span class="cpn-cl"><i class="cpn-dot" style="background:' + l.hex + '"></i>' + est(esc(l.label), "battery_class") + "</span>" +
        '<span class="cpn-life">' + lifeTxt + "</span>" +
        '<span class="cpn-vd">' + r.verdict.pill + "</span>" +
        (r.verdict.why ? '<p class="cpn-why">' + esc(r.verdict.why) + "</p>" : "") +
        "</summary>" +
        '<div class="cpn-lines">' + lines + "<p>" + esc(r.reason) + "</p></div>" +
        "</details>";
    });
    var classes = rows.map(function (r) {
      return r.class;
    }).filter(function (c, i, a) {
      return a.indexOf(c) === i;
    });
    var same = classes.length === 1
      ? '<details class="cpn-same"><summary>Every budget needs ' + esc(classes[0] === "larger pack or mains" ? "a larger pack or mains" : "a " + classes[0] + " cell") + ": what that means</summary>" + consequencesHTML(classes[0]) + "</details>"
      : "";
    var minH = M().ILLUSTRATIVE_MIN_LIFE_HOURS;
    return '<div class="cpn-pan">' +
      '<div class="cpn-h"><h2>What this means for the battery</h2><span class="cpn-sub">Chip of ' + gatesTxt + " at " + esc(dps(ctx)) + " decision" + (dps(ctx) === 1 ? "" : "s") + " a second " + estT('<span class="mk no">power estimated</span>', M().describeEstimate("chip_power")) + "</span></div>" +
      (lede ? '<p class="cpn-lede">' + lede + "</p>" : "") +
      (story.more ? '<details class="cpn-more"><summary>More from the power model</summary><p>' + story.more + "</p></details>" : "") +
      '<p class="cpn-ask">' + ask + "</p>" +
      '<div class="cpn-rows" role="list" aria-label="Battery by ' + esc(unit) + '">' + html + "</div>" + same +
      '<p class="cpn-foot"' + tipA("Device power is front end, Bluetooth radio and chip; the chip's power is an estimate from one layout run. A class needs at least an illustrative " + minH + " hours per cell or charge (not a clinical figure). Open a row for its parts and sources.") + ">Front end, radio and chip; chip power estimated. Class minimum: " + MK_ILL + "</p>" +
      "</div>";
  }

  function mountBattery(el, ctx) {
    injectCss();
    el.classList.add("cpn");
    var openKeys = {};
    el.addEventListener("toggle", function (e) {
      var t = e.target;
      if (t && t.classList && t.classList.contains("cpn-row")) openKeys[t.getAttribute("data-key")] = t.open;
    }, true);
    function render(c) {
      ctx = c;
      el.innerHTML = batteryHTML(c, openKeys);
    }
    render(ctx);
    return { update: render };
  }

  /* -------------------------------------------------------------- intervals */
  var FAMILY = {
    sensitivity: ["sensitivity_worst", "sensitivity_pooled", "sensitivity"],
    specificity: ["specificity_worst", "specificity", "specificity_pooled"],
  };
  function resolveField(design, metric) {
    var m = (design && design.metrics) || {};
    if (FAMILY[metric]) {
      for (var i = 0; i < FAMILY[metric].length; i++) if (m[FAMILY[metric][i]] != null) return FAMILY[metric][i];
      return null;
    }
    return m[metric] != null ? metric : null;
  }
  function familyOf(metric) {
    return /^sensitivity/.test(metric) ? "sensitivity" : /^specificity/.test(metric) ? "specificity" : metric;
  }
  var CLOSE = 0.0005;

  function intervalFor(design, metric) {
    if (!design || !metric) return null;
    var field = resolveField(design, metric);
    if (!field) return null;
    var fam = familyOf(field);
    if (fam !== "sensitivity" && fam !== "specificity") return null;
    if (/_window$/.test(field)) return null;
    var value = design.metrics[field];
    var sens = fam === "sensitivity";
    var k, n, patient = null, derived = false;
    if (/_worst$/.test(field)) {
      var pp = design.per_patient || [];
      var best = null;
      pp.forEach(function (p) {
        var pk = sens ? p.caught : p.neg_correct, pn = sens ? p.total : p.neg_total;
        if (!(pn > 0) || pk == null) return;
        var r = pk / pn;
        if (!best || r < best.r - 1e-12 || (Math.abs(r - best.r) <= 1e-12 && pn < best.n)) best = { r: r, k: pk, n: pn, id: p.id };
      });
      if (!best || Math.abs(best.r - value) > CLOSE) return null;
      k = best.k; n = best.n; patient = best.id;
    } else {
      var c = design.counts || {};
      k = sens ? c.events_caught : c.negatives_correct;
      n = sens ? c.events_total : c.negatives_total;
      if (!(n > 0)) return null;
      if (k == null) {
        if (value == null) return null;
        k = Math.round(value * n);
        if (Math.abs(k / n - value) > CLOSE) return null;
        derived = true;
      }
    }
    var iv = M().wilson(k, n);
    return { low: iv.low, high: iv.high, k: k, n: n, value: value, field: field, patient: patient, derived: derived };
  }

  /* ------------------------------------------------------------- confidence */
  var MET_NAME = { sensitivity: "Sensitivity", specificity: "Specificity" };
  function targetFor(ctx, metric) {
    var fam = familyOf(metric);
    var ts = ctx.targets || [];
    for (var i = 0; i < ts.length; i++) if (familyOf(ts[i].metric) === fam) return ts[i];
    return null;
  }
  function rangeRow(label, iv, cls) {
    return '<div class="cpn-rr ' + cls + '"><span>' + esc(label) + '</span><div class="cpn-trk">' +
      '<i class="cpn-iv" style="left:' + (iv.low * 100) + "%;width:" + ((iv.high - iv.low) * 100) + '%"></i>' +
      '<i class="cpn-pt" style="left:' + (iv.value * 100) + '%"></i></div></div>';
  }
  function whoOf(ctx) {
    return ctx.who || "patients";
  }
  function one(plural) {
    return /ies$/.test(plural) ? plural.replace(/ies$/, "y") : plural.replace(/s$/, "");
  }
  function scopeOf(ctx, iv) {
    var w = whoOf(ctx);
    if (iv.patient != null) return "worst unseen " + one(w) + " (" + (typeof iv.patient === "number" ? "no. " : "") + iv.patient + "), " + fmtInt(iv.k) + " of " + fmtInt(iv.n);
    return fmtInt(iv.k) + " of " + fmtInt(iv.n) + (iv.derived ? " (from the published rate and total)" : "") + ", all unseen " + w + " pooled";
  }

  function confidenceHTML(ctx) {
    var d = ctx.chosen || ctx.selected;
    var who = whoOf(ctx);
    if (!d) return '<div class="cpn-pan"><div class="cpn-h"><h2>How sure is this?</h2></div><p class="cpn-empty">No design chosen yet.</p></div>';
    var c = d.counts || {};
    var head = M().confidenceHeadline({
      positives: c.events_total || 0,
      negatives: c.negatives_total != null ? c.negatives_total : undefined,
      patients: ctx.patientsUnseen != null ? ctx.patientsUnseen : c.patients,
    });
    var prim = ctx.primary || "sensitivity";
    var iv = intervalFor(d, prim);
    var name = MET_NAME[familyOf(prim)] || prim;
    var t = targetFor(ctx, prim);
    var sim = d.source !== "measured" ? " " + MK_SIM : "";
    var clin;
    var apart = "";
    if (iv) {
      var sel = ctx.selected && ctx.chosen && ctx.selected.id !== ctx.chosen.id ? intervalFor(ctx.selected, prim) : null;
      clin = name + " <b>" + pct1(iv.value) + "</b>, 95% range <b>" + pct1(iv.low) + " to " + pct1(iv.high) + "</b>" + sim +
        '<div style="font-size:11.5px;color:var(--cpn-ink3)">' + esc(scopeOf(ctx, iv)) + "</div>" +
        '<div class="cpn-rng">' + rangeRow(ctx.chosen ? "Chosen" : "Selected", iv, "cho") + (sel ? rangeRow("Selected", sel, "sel") : "") +
        '<div class="cpn-ax"><span></span><div><span>0%</span><span>100%</span></div></div>' +
        (t && t.value >= 0 && t.value <= 1 ? '<p class="cpn-key"' + tipA("your target, " + (t.op === "<=" ? "at most " : "at least ") + pct1(t.value).replace(".0%", "%") + ". The bar is the 95% range, the dot the design's value.") + '><i></i>your target, ' + esc((t.op === "<=" ? "at most " : "at least ") + pct1(t.value).replace(".0%", "%")) + "; bar: 95% range</p>" : "") + "</div>";
      if (t && t.value >= 0 && t.value <= 1) {
        clin = clin.replace(/<div class="cpn-trk">/g, '<div class="cpn-trk"><i class="cpn-tg" style="left:' + (t.value * 100) + '%"></i>');
      }
      if (sel) {
        var ap = M().cannotTellApart({ low: iv.low, high: iv.high }, { low: sel.low, high: sel.high });
        apart = ap.overlap
          ? '<p class="cpn-apart"' + tipA("The chosen chip (" + pct1(iv.value) + ") and the selected design (" + pct1(sel.value) + ") cannot be told apart on this data: their ranges overlap.") + ">Chosen " + pct1(iv.value) + ", selected " + pct1(sel.value) + ": cannot be told apart.</p>"
          : '<p class="cpn-apart">' + esc(ap.text) + "</p>";
      }
    } else {
      clin = "No range for " + esc(name.toLowerCase()) + " on this design: its counts are not in the data.";
    }
    var n = ctx.patientsUnseen != null ? ctx.patientsUnseen : c.patients;
    var few = n != null && n < M().CONFIDENCE_THRESHOLDS.low_if_patients_below;
    var genFull = ctx.dataSource === "simulated" || d.source === "simulated"
      ? "Simulated data: these figures show how the search behaves, not how a real device performs on real " + who + "."
      : (n != null ? "Judged on " + (few ? "only " : "") + fmtInt(n) + " unseen " + who + (few ? ": one " + one(who) + " more or less can move the result. " : ", held out before training. ") : "") +
        "They come from the same source as the training data; there is no external validation yet.";
    var gen = ctx.dataSource === "simulated" || d.source === "simulated"
      ? MK_SIM + " <span" + tipA(genFull) + ">Shows the search, not a real device.</span>"
      : "<span" + tipA(genFull) + ">" + (n != null ? (few ? "Only " : "") + fmtInt(n) + " unseen " + esc(who) + "; " : "") + "no external validation yet.</span>";
    var eng = estT("Power, area and cost are estimates", "Power from one layout run, area from an assumed size per gate and cost from assumed inputs are estimates, not measurements. Gate counts come from synthesis. Power: " + M().describeEstimate("chip_power") + " Area: " + M().describeEstimate("area") + " Cost: " + M().describeEstimate("cost")) + "; gate counts come from synthesis.";
    return '<div class="cpn-pan">' +
      '<div class="cpn-h"><h2>How sure is this?</h2></div>' +
      '<div class="cpn-head"><span class="cpn-lvl ' + esc(head.level) + '" aria-hidden="true"><i></i><i></i><i></i></span><b>' + esc(head.text) + "</b></div>" +
      '<div class="cpn-parts">' +
      '<div class="cpn-part"><span>Clinical range</span><div>' + clin + apart + "</div></div>" +
      '<div class="cpn-part"><span>Generalisation</span><div>' + gen + "</div></div>" +
      '<div class="cpn-part"><span>Engineering estimates</span><div>' + eng + "</div></div>" +
      "</div></div>";
  }

  function mountConfidence(el, ctx) {
    injectCss();
    el.classList.add("cpn");
    function render(c) {
      ctx = c;
      el.innerHTML = confidenceHTML(c);
    }
    render(ctx);
    return { update: render };
  }

  /* ------------------------------------------------------------------- cost */
  function designFor(ctx, d) {
    return { gates: d.gates, channels: d.channels, sensors: d.sensors || d.channels, kind: ctx.caseKind, decisionsPerSecond: dps(ctx) };
  }
  function classOfDesign(ctx, d) {
    var b = M().deviceBudget({ kind: ctx.caseKind, channels: d.channels, sensors: d.sensors || d.channels, gates: d.gates, decisionsPerSecond: dps(ctx) });
    return M().batteryClass(b.total_uw).class;
  }
  function costFor(ctx, d, inputs) {
    var o = {};
    var k;
    for (k in inputs || {}) o[k] = inputs[k];
    o.gates = d.gates;
    if (!o.battery_class) o.battery_class = classOfDesign(ctx, d);
    return M().costModel(o);
  }
  function deltaText(ctx, inputs) {
    if (!ctx.chosen || !ctx.selected || ctx.chosen.id === ctx.selected.id) return "";
    var o = {};
    for (var k in inputs || {}) o[k] = inputs[k];
    o.kind = ctx.caseKind;
    var r = M().costDelta(designFor(ctx, ctx.chosen), designFor(ctx, ctx.selected), o);
    return r.text.replace("Going from design A to design B", "Going from the chosen chip to the selected design");
  }
  // one line for the inspector: the unit cost change against the chosen chip; the full sentence goes in its title
  function deltaShort(ctx, inputs) {
    if (!ctx.chosen || !ctx.selected || ctx.chosen.id === ctx.selected.id) return "";
    var o = {};
    for (var k in inputs || {}) o[k] = inputs[k];
    o.kind = ctx.caseKind;
    var dc = M().costDelta(designFor(ctx, ctx.chosen), designFor(ctx, ctx.selected), o).unit_cost_delta;
    return Math.abs(dc) < 0.005 ? "Same unit cost as the chosen chip" : (dc < 0 ? "-" : "+") + money(dc) + " a unit against the chosen chip";
  }
  function costLine(ctx) {
    var d = ctx.selected || ctx.chosen;
    if (!d) return { unit_cost_text: "", delta_text: "", tip: M().describeEstimate("cost") };
    var m = costFor(ctx, d, ctx.costInputs);
    return {
      unit_cost_text: money(m.unit_cost) + " per unit for chip, battery and assembly (estimated)",
      unit_cost_short: money(m.unit_cost) + " a unit (estimated)",
      delta_text: deltaText(ctx, ctx.costInputs),
      delta_short: deltaShort(ctx, ctx.costInputs),
      tip: M().describeEstimate("cost"),
    };
  }

  var COST_FIELDS = [
    { key: "annual_volume", label: "Annual volume", unit: "units a year" },
    { key: "process_node", label: "Process node", type: "text" },
    { key: "wafer_cost", label: "Wafer cost", unit: "$" },
    { key: "wafer_diameter_mm", label: "Wafer diameter", unit: "mm" },
    { key: "area_per_gate_um2", label: "Logic area per gate", unit: "µm²" },
    { key: "pad_limited_floor_mm2", label: "Pad-limited die floor", unit: "mm²" },
    { key: "die_area_mm2", label: "Die area override", unit: "mm²", nullable: true },
    { key: "yield", label: "Yield", unit: "fraction good" },
    { key: "package_cost", label: "Package", unit: "$" },
    { key: "test_cost", label: "Test", unit: "$" },
    { key: "nre_cost", label: "One-off design and masks", unit: "$ total" },
    { key: "battery_cost.primary coin cell", label: "Coin cell", unit: "$" },
    { key: "battery_cost.rechargeable lithium", label: "Rechargeable cell", unit: "$" },
    { key: "battery_cost.larger pack or mains", label: "Larger pack or mains", unit: "$" },
    { key: "battery_class", label: "Battery class for the cost", type: "class" },
    { key: "assembly_cost", label: "Assembly", unit: "$" },
  ];
  function getIn(o, key) {
    var p = key.split(".");
    return p.length === 2 ? (o[p[0]] || {})[p[1]] : o[key];
  }
  function setIn(o, key, v) {
    var p = key.split(".");
    if (p.length === 2) {
      o[p[0]] = Object.assign({}, o[p[0]] || {});
      if (v === undefined) delete o[p[0]][p[1]];
      else o[p[0]][p[1]] = v;
      if (!Object.keys(o[p[0]]).length) delete o[p[0]];
    } else if (v === undefined) delete o[key];
    else o[key] = v;
  }
  function defText(v) {
    return v === null ? "from gates" : typeof v === "number" ? (v >= 1000 ? fmtInt(v) : String(v)) : String(v);
  }

  var openDrawer = null;
  function closeOpen() {
    if (openDrawer) openDrawer.close();
  }
  function drawer(title, bodyHTML) {
    injectCss();
    closeOpen();
    var prev = document.activeElement;
    var scrim = document.createElement("div");
    scrim.className = "cpn cpn-scrim";
    var d = document.createElement("aside");
    d.className = "cpn cpn-drawer";
    d.setAttribute("role", "dialog");
    d.setAttribute("aria-modal", "true");
    d.setAttribute("aria-label", title);
    d.innerHTML = '<div class="cpn-dh"><h3>' + esc(title) + '</h3><button type="button" aria-label="Close"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg></button></div><div class="cpn-db">' + bodyHTML + "</div>";
    function onKey(e) {
      if (e.key === "Escape") api.close();
    }
    var api = {
      el: d,
      body: d.querySelector(".cpn-db"),
      close: function () {
        document.removeEventListener("keydown", onKey);
        scrim.remove();
        d.remove();
        if (openDrawer === api) openDrawer = null;
        if (prev && prev.focus) prev.focus();
      },
    };
    scrim.onclick = api.close;
    d.querySelector(".cpn-dh button").onclick = api.close;
    document.addEventListener("keydown", onKey);
    document.body.appendChild(scrim);
    document.body.appendChild(d);
    openDrawer = api;
    d.querySelector(".cpn-dh button").focus();
    return api;
  }

  function openCost(ctx, onChange) {
    var D = M().COST_DEFAULTS;
    var inputs = JSON.parse(JSON.stringify(ctx.costInputs || {}));
    var subject = ctx.chosen || ctx.selected;
    var fields = COST_FIELDS.map(function (f) {
      var dv = getIn(D, f.key);
      var cur = getIn(inputs, f.key);
      var id = "cpn-c-" + f.key.replace(/[^a-z0-9]+/gi, "-");
      var ctl;
      if (f.type === "class") {
        var auto = subject ? classOfDesign(ctx, subject) : null;
        ctl = '<select id="' + id + '" data-k="' + esc(f.key) + '"><option value="">Follow the design' + (auto ? " (" + esc(look(auto).label.toLowerCase()) + ")" : "") + "</option>" +
          Object.keys(CLASS_LOOK).map(function (c) {
            return '<option value="' + esc(c) + '"' + (cur === c ? " selected" : "") + ">" + esc(look(c).label) + "</option>";
          }).join("") + "</select>";
        return '<div class="cpn-f' + (cur ? " edited" : "") + '"><label for="' + id + '">' + esc(f.label) + '</label><span class="d"' + tipA("Assumption. Default: follows the design's battery class (ChipIn power model)") + ">Default: the design's battery class</span>" + ctl + "</div>";
      }
      var val = cur !== undefined ? cur : dv;
      ctl = '<input id="' + id + '" data-k="' + esc(f.key) + '" type="' + (f.type === "text" ? "text" : "number") + '" step="any"' + (f.nullable ? ' placeholder="from gates"' : "") + ' value="' + esc(val === null ? "" : val) + '">';
      return '<div class="cpn-f' + (cur !== undefined ? " edited" : "") + '"><label for="' + id + '">' + esc(f.label) + (f.unit ? ' <span style="font-weight:400;color:var(--cpn-ink3)">(' + esc(f.unit) + ")</span>" : "") + '</label><span class="d">Default ' + esc(defText(dv)) + "</span>" + ctl + "</div>";
    }).join("");
    var body = '<div data-out></div><h4>Inputs</h4><p class="cpn-note" style="margin:0 0 4px"' + tipA("Every input is an assumption with a default value, so the cost is estimated; enter your own quotes and the figures above recompute.") + ">Assumptions with default values; edit to recompute.</p>" + fields + '<button type="button" class="cpn-reset">Reset to the defaults</button>';
    var dr = drawer("Cost assumptions", body);
    var out = dr.body.querySelector("[data-out]");
    function renderOut() {
      if (!subject) {
        out.innerHTML = '<p class="cpn-empty">No design chosen yet, so there is no unit cost to show.</p>';
        return;
      }
      var m = costFor(ctx, subject, inputs);
      var dt = deltaText(ctx, inputs);
      out.innerHTML = "<h4>" + (ctx.chosen ? "The chosen chip" : "The selected design") + ", " + fmtInt(subject.gates) + " gates " + srcMark(subject) + "</h4>" +
        '<div class="cpn-big" data-unit>' + est(money(m.unit_cost), "cost") + "<small>per unit, " + MK_EST + "</small></div>" +
        m.lines.map(function (l) {
          return '<div class="cpn-kv"><span>' + esc(l.name) + "</span><span>" + est(money(l.cost), "cost") + "</span></div>";
        }).join("") +
        m.notes.map(function (n) {
          return '<p class="cpn-note">' + esc(n) + "</p>";
        }).join("") +
        (dt ? '<h4>Against the selected design</h4><p class="cpn-delta" data-delta>' + estT(esc(dt), M().describeEstimate("cost")) + "</p>" : "");
    }
    renderOut();
    dr.body.addEventListener("input", function (e) {
      var t = e.target;
      var key = t.getAttribute && t.getAttribute("data-k");
      if (!key) return;
      var f = COST_FIELDS.filter(function (x) {
        return x.key === key;
      })[0];
      var v;
      if (f.type === "class") v = t.value || undefined;
      else if (f.type === "text") v = t.value.trim() || undefined;
      else if (t.value.trim() === "") v = f.nullable ? null : undefined;
      else {
        v = Number(t.value);
        var bad = !isFinite(v) || v < 0 || (key === "yield" && (v <= 0 || v > 1)) || (key === "annual_volume" && v <= 0) || (key === "wafer_diameter_mm" && v <= 0) || ((key === "pad_limited_floor_mm2" || key === "die_area_mm2") && v <= 0);
        t.classList.toggle("bad", bad);
        if (bad) return;
      }
      t.classList.remove("bad");
      if (f.nullable && v === null) v = undefined;
      setIn(inputs, key, v);
      t.closest(".cpn-f").classList.toggle("edited", getIn(inputs, key) !== undefined);
      renderOut();
      if (onChange) onChange(JSON.parse(JSON.stringify(inputs)));
    });
    dr.body.querySelector(".cpn-reset").onclick = function () {
      inputs = {};
      dr.close();
      if (onChange) onChange({});
      ctx = Object.assign({}, ctx, { costInputs: null });
      openCost(ctx, onChange);
    };
    return { close: dr.close };
  }

  /* --------------------------------------------------------- measured so far */
  function defaultFacts() {
    return [
      {
        title: "One full agent run through the real chip-lab tools",
        text: "Three classifier designs and a front end were compiled, each bit-exact on 100,000 random vectors and formally proved, in 17 min 50 s.",
        scope: "Placeholder weights, so this run gives no detection figures.",
      },
      {
        title: "Weight memory traffic per decision: 0 bytes",
        text: "A software implementation reads 89 bytes of trained weights per decision. The compiled chip has 0 memory cells among its 2,367 cells, so it fetches 0 weight bytes.",
        scope: "Measured on one design, the first of that run.",
      },
    ];
  }
  /* Against a published AF chip: every figure and word comes from data/af-baseline.json, next to this file. */
  var baselineUrl = (function () {
    var cs = typeof document !== "undefined" ? document.currentScript : null;
    return cs && cs.src ? new URL("data/af-baseline.json", cs.src).href : null;
  })();
  var baselineData; // undefined = not fetched, null = unavailable
  // escapes text and turns each phrase named in links ([{ text, url }]) into a link, once per string, in one pass
  function linkPhrases(text, links) {
    var t = esc(text), L = (Array.isArray(links) ? links : []).filter(function (l) { return l && l.text && l.url; });
    if (!L.length) return t;
    var seen = {}, re = new RegExp(L.map(function (l) { return esc(l.text).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).sort(function (a, b) { return b.length - a.length; }).join("|"), "gi");
    return t.replace(re, function (m) {
      var k = m.toLowerCase(), l = L.filter(function (x) { return esc(x.text).toLowerCase() === k; })[0];
      if (!l || seen[k]) return m;
      seen[k] = true;
      return '<a href="' + esc(l.url) + '" target="_blank" rel="noopener">' + m + "</a>";
    });
  }
  function baselineHtml(b) {
    if (!b || !Array.isArray(b.rows)) return "";
    var mk = function (m) { return m === "published" ? '<span class="mk no">published</span>' : MK_MEA; };
    return '<div class="cpn-fact cpn-af"><div class="t">' + esc(b.heading) + "</div>" +
      '<p class="s">' + linkPhrases(b.sub, b.links) + "</p>" +
      b.rows.map(function (r) {
        return '<div class="cpn-afrow"><div class="t">' + esc(r.title) +
          (r.verdict ? ' <span class="mk no">' + esc(r.verdict) + "</span>" : "") + "</div>" +
          (r.lines || []).map(function (l) { return '<p class="x">' + mk(l.mark) + " " + esc(l.text) + "</p>"; }).join("") +
          (r.caveat ? '<p class="x">' + esc(r.caveat) + "</p>" : "") + "</div>";
      }).join("") +
      (b.footer ? '<p class="s">' + linkPhrases(b.footer, b.links) + "</p>" : "") + "</div>";
  }
  function openMeasured(facts) {
    facts = Array.isArray(facts) ? facts : [];
    var body = facts.length
      ? facts.map(function (f) {
        return '<div class="cpn-fact"><div class="t">' + esc(f.title) + MK_MEA + "</div>" +
          (f.text ? '<p class="x">' + esc(f.text) + "</p>" : "") +
          (f.scope ? '<p class="s">' + esc(f.scope) + "</p>" : "") +
          (f.source_name ? '<p class="s">' + (f.source_url ? '<a href="' + esc(f.source_url) + '" target="_blank" rel="noopener">' + esc(f.source_name) + "</a>" : esc(f.source_name)) + "</p>" : "") +
          (f.file_name ? '<p class="s">' + (f.file_url ? '<a href="' + esc(f.file_url) + '" target="_blank" rel="noopener">' + esc(f.file_name) + "</a>" : esc(f.file_name)) + "</p>" : "") +
          "</div>";
      }).join("")
      : '<p class="cpn-empty">No measured facts were handed to this drawer.</p>';
    var dr = drawer("Measured so far", '<p class="cpn-note" style="margin:0 0 6px"' + tipA("Only figures that were measured, each with what it covers.") + ">Measured figures only, with their scope.</p>" + body);
    if (baselineUrl) {
      var addBaseline = function () {
        if (baselineData && dr.body.isConnected) dr.body.insertAdjacentHTML("beforeend", baselineHtml(baselineData));
      };
      if (baselineData !== undefined) addBaseline();
      else {
        fetch(baselineUrl, { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
          .then(function (j) { baselineData = j; addBaseline(); });
      }
    }
    return { close: dr.close };
  }

  function footerCredit() {
    return "Built at the SoTA Scientific Parallelism Hackathon, London, November 2026. Supported by Callosum, Inherent Labs, ARIA and Fractile.";
  }

  var api = {
    version: 1,
    mountBattery: mountBattery,
    batteryClassFor: batteryClassFor,
    intervalFor: intervalFor,
    mountConfidence: mountConfidence,
    openCost: openCost,
    costLine: costLine,
    openMeasured: openMeasured,
    defaultFacts: defaultFacts,
    footerCredit: footerCredit,
  };
  if (root) root.ChipInPanels = api;
})(typeof window !== "undefined" ? window : typeof globalThis !== "undefined" ? globalThis : null);
