/*
 * i1-regulation.js: the Regulation panel of the ChipIn i1 dashboard, beside Why this size. Defines window.ChipInRegulation.
 *
 * Two short groups of entries, each from a cited public source: what starts to apply as the battery grows, and what
 * differs between a smaller and a larger chip. Each entry shows its title, its check status, the checked statement and a short
 * source link; the full rule, why it matters and every source open on expand. None carries a verdict.
 * Above them, the battery class for this chip and the bigger sizes Why this size shows (ChipInWhySize.biggerOf),
 * each from ChipInModels.deviceBudget and batteryClass, the same as Why this size.
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
    ".rg-e>div p.r{color:var(--i800)}",
    ".rg-e>div{padding:0 0 8px 12px;font-size:12px;color:var(--i700);line-height:1.45}",
    ".rg-e>div p{margin:0 0 3px}",
    ".rg-e>div p.w b{color:var(--i900);font-weight:600}",
    ".rg-e>div a{color:var(--blue7);font-weight:600}",
    ".rg-st{font-size:10.5px;font-weight:600;border-radius:99px;padding:1px 7px;white-space:nowrap;justify-self:end}",
    ".rg-st.chk{color:var(--i600);background:var(--i100)}",
    ".rg-st.ok{color:#047857;background:#ecfdf5}.rg-st.part{color:#b45309;background:#fffbeb}.rg-st.con{color:#b91c1c;background:#fef2f2}",
    ".rg-say{grid-column:1/-1;font-size:12px;color:var(--i700);line-height:1.4;padding-left:12px}",
    ".rg-say a{color:var(--blue7);font-weight:600;white-space:nowrap}",
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
  var SHORT = { "primary coin cell": "coin cell", "rechargeable lithium": "rechargeable", "larger pack or mains": "larger pack" };
  var DOT = { "primary coin cell": "#047857", "rechargeable lithium": "#b45309", "larger pack or mains": "#b91c1c" };

  /* The entries, as checked on 22 Nov 2026 against the linked sources. st: checked, partly checked, contested or to check.
   * say: the checked statement shown on the row; cite: the short source link on the row; rule and why open on expand. */
  var BATTERY = [
    { id: "air", st: "checked", title: "US air limits for lithium batteries",
      say: "Small-cell exceptions cap lithium-ion at 20 Wh per cell, 100 Wh per battery.", cite: "49 CFR 173.185",
      rule: "Small-cell exceptions cap lithium-ion at 20 Wh per cell and 100 Wh per battery; lithium-metal limits are by grams of lithium per cell and have changed between editions. The exceptions have conditions. Coin cells are lithium cells: they are not exempt from lithium rules. Checked in outline: read the current eCFR text before quoting thresholds.",
      why: "A larger battery is more likely to pass these limits. A coin cell does not avoid lithium transport rules.",
      src: [["49 CFR 173.185, eCFR (current text)", "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-I/subchapter-C/part-173/subpart-E/section-173.185"], ["49 CFR 173.185, Cornell LII copy", "https://www.law.cornell.edu/cfr/text/49/173.185"]] },
    { id: "iec62133", st: "checked", title: "Lithium cell safety standard",
      say: "Rechargeable lithium: IEC 62133-2. Primary lithium, such as a coin cell: IEC 60086-4.", cite: "IEC 62133 / IEC 60086-4",
      rule: "Devices to IEC 60601-1 with rechargeable lithium batteries are expected to meet IEC 62133(-2); non-rechargeable lithium batteries, IEC 60086-4. Checked against test-house and standards-body summaries, not the standard text.",
      why: "Moving from a coin cell to a rechargeable changes the cell standard and adds charging, reuse and reprocessing to the design.",
      src: [["Battery testing for medical devices, Intertek (test house)", "https://intertek.com/medical/electrical-testing/battery-testing"], ["UL 62133 family of standards, UL Solutions (test house)", "https://www.ul.com/news/ul-62133-family-standards-batteries"]] },
    { id: "skin", st: "checked", title: "Skin contact over 30 days",
      say: "Over 30 days on skin is long-term contact under ISO 10993-1.", cite: "ISO 10993-1, FDA",
      rule: "ISO 10993-1 durations: limited up to 24 h cumulative, prolonged over 24 h up to 30 days, long-term over 30 days. For intact skin FDA lists cytotoxicity, sensitisation and irritation. A revision changes how cumulative exposure is counted.",
      why: "A larger battery that allows longer wear could push a patch past 30 days of contact.",
      src: [["Biocompatibility endpoints by contact duration, FDA", "https://www.fda.gov/medical-devices/biocompatibility-assessment-resource-center/biocompatibility-evaluation-endpoints-contact-duration-periods"]] },
    { id: "emc", st: "partly checked", title: "EMC testing in each power mode",
      say: "The EMC test plan must cover charging if the device is used while charging (to confirm with the lab).", cite: "IEC 60601-1-2",
      rule: "IEC 60601-1-2 (4th ed.) requires an EMC risk assessment covering intended operating conditions; its Annex G lists what a test plan should cover. Test houses recommend testing charging modes. No normative wording that it must be tested while charging was found.",
      why: "A rechargeable design used while charging may add an EMC test setup.",
      src: [["IEC 60601 overview, UL (test house)", "https://ul.com/resources/iec-60601-international-product-safety-standards-medical-devices"], ["Medical device EMC testing beyond the standard, Intertek (test house)", "https://www.intertek.com/blog/2026/09-18-going-beyond-medical-device-emc-testing/"]] },
  ];
  var CHIP = [
    { id: "eu", st: "checked", title: "EU battery removability",
      say: "Not a wearable exemption: partial, listed derogations only (Battery Regulation 2023/1542 Art. 11, Delegated Regulation 2026/1770); check whether your device qualifies.", cite: "Delegated Reg. 2026/1770",
      rule: "From 18 February 2027 portable batteries must be removable and replaceable (Battery Regulation 2023/1542 Art. 11). Medical device derogations are partial and listed, not a general wearable exemption; Delegated Regulation 2026/1770 replaced Art. 11(2), allowing replacement by independent professionals for listed products. Check whether your device qualifies.",
      why: "A small sealed patch is not exempt for being a wearable; whether users must be able to replace its battery depends on the listed derogations.",
      src: [["Delegated Regulation (EU) 2026/1770, EUR-Lex", "https://eur-lex.europa.eu/eli/reg_del/2026/1770/oj"], ["Commission guidelines on Art. 11 removability, C/2025/214, EUR-Lex", "https://eur-lex.europa.eu/eli/C/2025/214/oj/eng"], ["Removability guidance summary, Cooley (law firm)", "https://products.cooley.com/2025/02/13/european-commission-publishes-guidance-on-eu-batteries-regulation-removability-requirements/"]] },
    { id: "cyber", st: "checked", title: "Cyber device definition, firmware versus logic",
      say: "A cyber device has sponsor software, can connect to the internet and could be vulnerable.", cite: "FD&C Act s.524B",
      rule: "FD&C Act s.524B: a cyber device (1) includes software validated, installed or authorised by the sponsor, (2) can connect to the internet, (3) could be vulnerable to cybersecurity threats. FDA reads it broadly; final guidance updates June 2025.",
      why: "A hard-wired detector with no sponsor software and no internet link may fall outside; any radio or app connection likely brings it back in.",
      src: [["Cybersecurity FAQs (s.524B), FDA", "https://www.fda.gov/medical-devices/digital-health-center-excellence/cybersecurity-medical-devices-frequently-asked-questions-faqs"], ["Cybersecurity guidance notice, Federal Register, 27 June 2025", "https://www.govinfo.gov/content/pkg/FR-2025-06-27/html/2025-11669.htm"]] },
    { id: "iec62304", st: "contested", title: "Medical device software life cycle",
      say: "Contested: Team-NB treats HDL as a tool, others say in scope; confirm with your notified body.", cite: "IEC 62304, Team-NB FAQ",
      rule: "Whether IEC 62304 covers hard-wired logic is contested: the Team-NB FAQ treats HDL used to produce an FPGA as a tool, not a software item; the Johner Institute (consultancy) argues FPGA programming is in scope.",
      why: "A chip with hard-wired logic may or may not fall under IEC 62304; confirm with your notified body.",
      src: [["EN 62304 FAQ, Team-NB", "https://www.team-nb.org//wp-content/uploads/2015/05/FAQ_62304_Final_130804.pdf"], ["FPGA under IEC 62304, Johner Institute (consultancy, in German)", "https://www.johner-institut.de/blog/iec-62304-medizinische-software/fpga/"]] },
  ];

  function final(run, v, P) {
    if (run.case === "af" && P.MEASURED && P.MEASURED.af) return P.afFinal(v);
    return !!(v.done || (P.isMea && P.isMea(run)));
  }
  function count(d) { return d.sensors || d.channels || 1; }
  // the estimator's battery class for one design, as Why this size computes it
  function battery(ctx, d) {
    var b = M().deviceBudget({ kind: ctx.caseKind, channels: d.channels, sensors: count(d), gates: d.gates, decisionsPerSecond: 1 });
    return M().batteryClass(b.total_uw).class;
  }
  // this chip and the bigger sizes Why this size shows, with its size wording
  function designs(run, v, P, d) {
    var W = window.ChipInWhySize, rows = W && W.biggerOf ? W.biggerOf(run, v, P, d) : [];
    return [{ d: d, me: true }].concat(rows);
  }
  function sizeText(P, r) {
    return r.estSize ? '<span class="est" title="' + esc(P.sizeTip ? P.sizeTip() : M().describeEstimate("area")) + '">about ' + esc(P.about(r.d.gates)) + "</span>" : esc(P.fmt(r.d.gates));
  }

  var ST = { "checked": ["ok", "Checked against the linked sources, 22 Nov 2026"], "partly checked": ["part", "Partly confirmed by the linked sources"],
    "contested": ["con", "Sources disagree"], "to check": ["chk", "Not yet checked: to check with a regulatory specialist"] };
  function link(x, txt) { return '<a href="' + esc(x[1]) + '" target="_blank" rel="noopener">' + esc(txt) + "</a>"; }
  function entryHTML(e) {
    var src = e.src.map(function (x) { return link(x, x[0]); }).join(" · "), st = ST[e.st] || ST["to check"];
    return '<details class="rg-e"><summary><b>' + esc(e.title) + '</b><span class="rg-st ' + st[0] + '" title="' + esc(st[1]) + '">' + esc(e.st) + "</span>" +
      '<span class="rg-say">' + esc(e.say) + " " + link(e.src[0], e.cite) + "</span>" +
      "</summary><div>" + '<p class="r">' + esc(e.rule) + "</p>" +
      '<p class="w"><b>Why it matters here:</b> ' + esc(e.why) + "</p>" +
      "<p>Source: " + src + "</p></div></details>";
  }
  function stripHTML(P, B) {
    // every size Why this size names, on a phone too: the chips wrap
    return '<div class="rg-bat">' + B.map(function (b) {
      return '<span class="b' + (b.me ? " me" : "") + '"><i style="background:' + DOT[b.cls] + '"></i><span>' + (b.me ? "this chip, " : "") + sizeText(P, b) + " gates: " +
        est(SHORT[b.cls], "battery_class") + "</span></span>";
    }).join("") + '<span class="mk no">estimated</span></div>';
  }
  function innerHTML(P, B) {
    var grp = function (name, c, list) { return '<div class="rg-grp" style="--rg-c:' + c + '"><h3>' + name + "</h3>" + list.map(entryHTML).join("") + "</div>"; };
    return '<div class="rg-h"><h2>Regulation</h2></div>' + (B ? stripHTML(P, B) : "") +
      '<div class="rg-g">' + grp("A larger battery", "#b45309", BATTERY) + grp("Smaller chip against larger chip", "#1d4ed8", CHIP) + "</div>" +
      '<p class="rg-f">Checked on 22 Nov 2026 against the linked sources. General information, not regulatory advice: check every point with a regulatory specialist.</p>';
  }

  function tick(el, run, v, P, ctx) {
    if (!el || !M() || !ctx) return;
    var d = ctx.chosen, on = !!(ctx.caseKind && d && d.gates > 0 && final(run, v, P));
    if (!on) { if (el.style.display !== "none") el.style.display = "none"; el._sig = ""; return; }
    css();
    el.style.display = "";
    var list = designs(run, v, P, d);
    var s = [run.id, list.map(function (x) { return x.d.id + ":" + x.d.gates + ":" + x.d.channels; }).join(","), ctx.caseKind].join("|");
    if (el._sig === s) return;
    el._sig = s;
    var B = null;
    try { B = list.map(function (x) { return { d: x.d, me: x.me, estSize: x.estSize, cls: battery(ctx, x.d) }; }); } catch (err) { B = null; }
    var open = {}; el.querySelectorAll(".rg-e[open]").forEach(function (x, i) { open[i] = 1; });
    el.innerHTML = '<section class="rg" aria-label="Regulation">' + innerHTML(P, B) + "</section>";
    el.querySelectorAll(".rg-e").forEach(function (x, i) { if (open[i]) x.open = true; });
  }
  // sources(): every entry with its cited sources, for the Sources tab (../i1-sources.js)
  window.ChipInRegulation = { tick: tick, sources: function () { return BATTERY.concat(CHIP); } };
})();
