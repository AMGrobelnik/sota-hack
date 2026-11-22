/*
 * i1-regulation.js: the Regulation panel of the ChipIn i1 dashboard, beside Why this size. Defines window.ChipInRegulation.
 *
 * Two short groups of entries, each from a cited public source: what starts to apply as the battery grows, and what
 * differs between a smaller and a larger chip. Each entry shows its title and rule; why it matters and the source
 * open on expand. Where the page's estimator (ChipInModels.deviceBudget and batteryClass) has a battery for the
 * chosen design and the larger candidates, an entry carries an estimated status; otherwise it is a checklist item.
 * tick(el, run, v, P, ctx): the same arguments as ChipInWhySize.tick, without the cost drawer.
 */
(function () {
  "use strict";
  var M = function () { return window.ChipInModels; };
  var CSS = [
    ".rg{background:#fff;border:1px solid rgb(0 0 0/.07);border-radius:16px;box-shadow:var(--sh-hair);padding:14px 18px 10px}",
    ".rg-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 0 4px}",
    ".rg-h h2{font-size:15px;font-weight:650;margin:0;color:var(--i900)}",
    ".rg-bat{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 10px;font-size:12px}",
    ".rg-bat span.b{display:inline-flex;align-items:center;gap:6px;padding:3px 9px;border-radius:99px;background:var(--i100);color:var(--i800)}",
    ".rg-bat span.b.me{background:#e8efff;color:#1e3a8a;font-weight:600}",
    ".rg-bat i{width:7px;height:7px;border-radius:50%;flex:none}",
    ".rg-g{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0 22px}",
    ".rg-grp{min-width:0;border-top:3px solid var(--rg-c);padding-top:6px}",
    ".rg-grp h3{font-size:12.5px;font-weight:650;color:var(--rg-c);margin:0 0 2px;text-transform:none}",
    ".rg-e{border-bottom:1px solid var(--hair)}",
    ".rg-e:last-child{border-bottom:0}",
    ".rg-e>summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:1px 10px;padding:6px 0;align-items:baseline}",
    ".rg-e>summary::-webkit-details-marker{display:none}",
    ".rg-e>summary b{font-size:12.5px;font-weight:600;color:var(--i900)}",
    ".rg-e>summary b::before{content:'+';display:inline-block;width:12px;color:var(--rg-c);font-weight:700}",
    ".rg-e[open]>summary b::before{content:'-'}",
    ".rg-e>summary .r{grid-column:1/-1;font-size:12px;color:var(--i700);line-height:1.4;padding-left:12px}",
    ".rg-e>div{padding:0 0 8px 12px;font-size:12px;color:var(--i700);line-height:1.45}",
    ".rg-e>div p{margin:0 0 3px}",
    ".rg-e>div p.w b{color:var(--i900);font-weight:600}",
    ".rg-e>div a{color:var(--blue7);font-weight:600}",
    ".rg-st{font-size:10.5px;font-weight:600;border-radius:99px;padding:1px 7px;white-space:nowrap;justify-self:end}",
    ".rg-st.past{color:#991b1b;background:#fdecec}",
    ".rg-st.near{color:#92400e;background:#fff3e0}",
    ".rg-st.under{color:#0b5a3f;background:#e6f5ed}",
    ".rg-st.chk{color:var(--i600);background:var(--i100)}",
    ".rg-f{font-size:11.5px;color:var(--i600);margin:8px 0 0;border-top:1px solid var(--hair);padding-top:6px}",
    "@media (max-width:900px){.rg-g{grid-template-columns:1fr}.rg-grp+.rg-grp{margin-top:10px}}",
    "@media (max-width:767px){.ov #regPanel{order:8}.rg{padding:12px 14px 8px}}",
  ].join("\n");
  function css() {
    if (document.getElementById("rg-styles")) return;
    var s = document.createElement("style"); s.id = "rg-styles"; s.textContent = CSS; document.head.appendChild(s);
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function est(txt, field) { return '<span class="est" title="' + esc(M().describeEstimate(field)) + '">' + esc(txt) + "</span>"; }
  function fmtInt(x) { return Math.round(x).toLocaleString("en-GB"); }
  function life(days) { return days >= 2 ? fmtInt(days) + " days" : (days * 24).toFixed(1) + " h"; }
  var SHORT = { "primary coin cell": "coin cell", "rechargeable lithium": "rechargeable", "larger pack or mains": "larger pack" };
  var DOT = { "primary coin cell": "#047857", "rechargeable lithium": "#b45309", "larger pack or mains": "#b91c1c" };
  var ST = { past: "past", near: "near", under: "clear", chk: "to check" };

  /* The entries: wording and thresholds as in the cited sources. */
  var BATTERY = [
    { id: "air", title: "US air limits for lithium batteries",
      rule: "Lighter shipping rules up to 20 Wh per lithium-ion cell (100 Wh per battery) or 1 g lithium per lithium-metal cell (2 g per battery); above that, full dangerous-goods rules. Every cell or battery type needs UN 38.3 testing.",
      why: "A larger battery is more likely to pass the Wh or lithium limit, bringing stricter shipping and handling; a new or larger cell is a new type and needs its own UN 38.3 evidence.",
      src: [["49 CFR 173.185, US DOT PHMSA (Cornell LII copy)", "https://www.law.cornell.edu/cfr/text/49/173.185"]] },
    { id: "iec62133", title: "Rechargeable lithium cell safety standard",
      rule: "IEC 62133-2 sets safety requirements and tests for portable sealed rechargeable lithium cells and batteries, with no size threshold.",
      why: "A design that moves to a larger rechargeable lithium cell would likely need that cell to show it meets this standard.",
      src: [["IEC 62133-2:2017 with Amendment 1 (2021), IEC", "https://webstore.iec.ch/en/publication/32662"]] },
    { id: "skin", title: "Skin contact over 30 days",
      rule: "For devices on intact skin, naming the colour additive is enough for up to 30 days of contact; longer contact counts as long-term and needs more information, including a toxicological risk assessment.",
      why: "A larger battery that allows longer wear could push a patch past 30 days of contact, which brings more biocompatibility information.",
      src: [["FDA CDRH webinar transcript on the ISO 10993-1 final guidance, 12 Oct 2023", "https://www.fda.gov/media/173290/download"]] },
    { id: "emc", title: "EMC testing in each power mode",
      rule: "FDA recommends testing a device that runs on battery and on mains in both modes; user-handled smart batteries are removed and tested separately for ESD immunity.",
      why: "A larger-battery design with a smart cell or extra power modes may add EMC test setups.",
      src: [["Electromagnetic Compatibility (EMC) of Medical Devices, FDA guidance, 6 June 2022", "https://www.fda.gov/media/94758/download"]] },
  ];
  var CHIP = [
    { id: "eu", title: "EU battery removability, wearable exemption",
      rule: "Portable batteries must be user-replaceable; some wearables too small to swap safely, or relying on a compact sealed enclosure, may allow removal by independent professionals only. Applies from 18 February 2027.",
      why: "A small sealed patch may qualify for this exemption, while a larger patch with an easy-to-reach cell may have to let users replace the battery.",
      src: [["Delegated Regulation amending Regulation (EU) 2023/1542, Council document ST 12056/2026", "https://data.consilium.europa.eu/doc/document/ST-12056-2026-INIT/en/pdf"], ["Dates as reported by UL", "https://www.ul.com/news/eu-expands-portable-battery-removability-derogations"]] },
    { id: "change", title: "When a battery change needs review",
      rule: "A new 510(k) is usually required for an energy type change, such as AC to battery; a voltage or battery-type change is treated as a performance specification or design change.",
      why: "Moving a cleared design to a larger chip with a different battery would likely need a documented design-change assessment, and might need a new submission.",
      src: [["Deciding When to Submit a 510(k) for a Change to an Existing Device, FDA guidance, 25 Oct 2017", "https://www.fda.gov/media/99812/download"]] },
    { id: "cyber", title: "Cyber device definition, firmware versus logic",
      rule: "A cyber device has sponsor-authorised software, can connect to the internet and could be vulnerable to cybersecurity threats; FDA counts firmware and programmable logic as software.",
      why: "A chip with fixed logic and no internet link may face fewer cybersecurity duties than one with updatable firmware, but the guidance does not exempt it.",
      src: [["21 USC 360n-2 (FD&C Act section 524B), Cornell LII", "https://www.law.cornell.edu/uscode/text/21/360n-2"], ["Cybersecurity in Medical Devices, FDA guidance, 3 Feb 2026", "https://www.fda.gov/media/119933/download"]] },
    { id: "iec62304", title: "Medical device software life cycle",
      rule: "IEC 62304 applies to developing and maintaining medical device software, whether it is the device or embedded in it.",
      why: "A design that runs embedded or updatable firmware is in scope; neither source says a design with no software is out of scope.",
      src: [["IEC 62304:2006 plus Amendment 1 (2015), IEC", "https://webstore.iec.ch/publication/6792"]] },
  ];

  function final(run, v, P) {
    if (run.case === "af" && P.MEASURED && P.MEASURED.af) return P.afFinal(v);
    return !!(v.done || (P.isMea && P.isMea(run)));
  }
  function count(d) { return d.sensors || d.channels || 1; }
  // the estimator's battery for one design: class, cell, life and the cell's energy from its datasheet figures
  function battery(ctx, d) {
    var b = M().deviceBudget({ kind: ctx.caseKind, channels: d.channels, sensors: count(d), gates: d.gates, decisionsPerSecond: 1 });
    var c = M().batteryClass(b.total_uw);
    return { d: d, cls: c.class, cell: c.cell, life: c.life_days, wh: c.cell ? c.cell.capacity_mah * c.cell.voltage_v / 1000 : null };
  }
  // the chosen design, the next larger candidate and the largest one
  function designs(v, d) {
    var up = (v.vis || []).filter(function (x) { return x.gates > d.gates && x.role !== "baseline"; }).sort(function (a, b) { return a.gates - b.gates; });
    var out = [{ d: d, tag: "this chip" }];
    if (up.length) out.push({ d: up[0], tag: "next larger" });
    if (up.length > 1) out.push({ d: up[up.length - 1], tag: "largest" });
    return out;
  }

  // estimated status per entry, only where the estimator's numbers decide it; null leaves it a checklist item
  function status(id, B) {
    var me = B[0], all = B, has = function (c) { return all.some(function (b) { return b.cls === c; }); };
    var big = all[all.length - 1];
    if (id === "air") {
      if (!me.cell) return { k: "chk", t: "The estimator sizes no cell for this design; check the pack against both limits." };
      if (me.cell.type === "primary") return { k: "chk", t: "This design: " + SHORT[me.cls] + " (estimated), a lithium-metal cell. Its lithium content is not in the page's data; check it against 1 g on the cell datasheet." };
      var k = me.wh > 20 ? "past" : me.wh >= 10 ? "near" : "under";
      return { k: k, t: "This design: " + esc(me.cell.name) + ", " + est("about " + me.wh.toFixed(2) + " Wh", "battery_life") + " against the 20 Wh cell limit." };
    }
    if (id === "iec62133") {
      if (me.cls === "rechargeable lithium") return { k: "past", t: "This design already needs a rechargeable lithium cell (" + est(SHORT[me.cls], "battery_class") + ")." };
      if (has("rechargeable lithium")) return { k: "near", t: "This design: " + est(SHORT[me.cls], "battery_class") + "; the " + big.tag + " candidate at " + fmtInt(big.d.gates) + " gates moves to a rechargeable (estimated)." };
      if (me.cls === "primary coin cell") return { k: "under", t: "All candidates shown run on a " + est("coin cell", "battery_class") + ", not a rechargeable." };
      return null;
    }
    if (id === "skin") {
      if (me.cls !== "primary coin cell") return null;
      var k2 = me.life >= 20 ? "near" : "under";
      return { k: k2, t: "This design's cell lasts " + est("about " + life(me.life), "battery_life") + "; " + (me.life > 30 ? "the battery alone does not stop wear past 30 days." : "a single cell keeps wear under 30 days.") };
    }
    if (id === "emc") {
      if (has("larger pack or mains")) return { k: "near", t: "A candidate here needs a " + est("larger pack or mains", "battery_class") + "; mains would add a second power mode." };
      return { k: "under", t: "All candidates shown run on a battery only (" + est(SHORT[me.cls], "battery_class") + " for this design)." };
    }
    if (id === "change") {
      var diff = all.filter(function (b) { return b.cls !== me.cls; })[0];
      if (diff) return { k: "near", t: "Going from this chip to " + fmtInt(diff.d.gates) + " gates changes the battery from " + est(SHORT[me.cls], "battery_class") + " to " + est(SHORT[diff.cls], "battery_class") + "." };
      if (all.length > 1) return { k: "under", t: "The larger candidates shown keep the same battery type (" + est(SHORT[me.cls], "battery_class") + ")." };
      return null;
    }
    return null;
  }

  function entryHTML(e, B) {
    var s = B ? status(e.id, B) : null, k = s ? s.k : "chk";
    var src = e.src.map(function (x) { return '<a href="' + esc(x[1]) + '" target="_blank" rel="noopener">' + esc(x[0]) + "</a>"; }).join(" · ");
    return '<details class="rg-e"><summary><b>' + esc(e.title) + '</b><span class="rg-st ' + k + '"' + (s ? ' title="Estimated from the page\'s battery model"' : "") + ">" + ST[k] + "</span>" +
      '<span class="r">' + esc(e.rule) + "</span></summary><div>" +
      '<p class="w"><b>Why it matters here:</b> ' + esc(e.why) + "</p>" +
      (s ? '<p><span class="mk no">estimated</span> ' + s.t + "</p>" : "") +
      "<p>Source: " + src + "</p></div></details>";
  }
  function stripHTML(B) {
    return '<div class="rg-bat">' + B.map(function (b, i) {
      var lt = b.cls === "primary coin cell" ? life(b.life) : b.cls === "rechargeable lithium" ? life(b.life) + "/charge" : "";
      return '<span class="b' + (i === 0 ? " me" : "") + '"><i style="background:' + DOT[b.cls] + '"></i><span>' + esc(b.tag) + ", " + fmtInt(b.d.gates) + " gates: " +
        est(SHORT[b.cls], "battery_class") + (lt ? ", " + est(lt, "battery_life") : "") + "</span></span>";
    }).join("") + '<span class="mk no">estimated</span></div>';
  }
  function innerHTML(B) {
    var grp = function (name, c, list) { return '<div class="rg-grp" style="--rg-c:' + c + '"><h3>' + name + "</h3>" + list.map(function (e) { return entryHTML(e, B); }).join("") + "</div>"; };
    return '<div class="rg-h"><h2>Regulation</h2></div>' + (B ? stripHTML(B) : "") +
      '<div class="rg-g">' + grp("A larger battery", "#b45309", BATTERY) + grp("Smaller chip against larger chip", "#1d4ed8", CHIP) + "</div>" +
      '<p class="rg-f">General information from the cited sources, not regulatory advice.</p>';
  }

  function tick(el, run, v, P, ctx) {
    if (!el || !M() || !ctx) return;
    var d = ctx.chosen, on = !!(ctx.caseKind && d && d.gates > 0 && final(run, v, P));
    if (!on) { if (el.style.display !== "none") el.style.display = "none"; el._sig = ""; return; }
    css();
    el.style.display = "";
    var list = designs(v, d);
    var s = [run.id, list.map(function (x) { return x.d.id + ":" + x.d.gates + ":" + x.d.channels; }).join(","), ctx.caseKind].join("|");
    if (el._sig === s) return;
    el._sig = s;
    var B = null;
    try { B = list.map(function (x) { var b = battery(ctx, x.d); b.tag = x.tag; return b; }); } catch (err) { B = null; }
    var open = {}; el.querySelectorAll(".rg-e[open]").forEach(function (x, i) { open[i] = 1; });
    el.innerHTML = '<section class="rg" aria-label="Regulation">' + innerHTML(B) + "</section>";
    el.querySelectorAll(".rg-e").forEach(function (x, i) { if (open[i]) x.open = true; });
  }
  // sources(): every entry with its cited sources, for the Sources tab (../i1-sources.js)
  window.ChipInRegulation = { tick: tick, sources: function () { return BATTERY.concat(CHIP); } };
})();
