/*
 * i1-sources.js: the Sources tab of the ChipIn i1 dashboard. Defines window.ChipInSources.
 *
 * One plain list of every source a run's result rests on, each a link that opens in a new tab, under
 * small headings: Data, Papers, Standards and rules, Parts and batteries, Tools. Nothing else.
 *   html(o)        the example runs' list. o = { run, title, bare, ctx, af, eeg, ds } from the page (bare: no heading): af and eeg are
 *                  the run's own data files (or null), ds the page's dataset entries for a run without a file,
 *                  ctx the panels' context (caseKind, budgets, chosen) for the battery and regulation sources.
 *   count(o)       how many sources html(o) lists.
 *   liveHTML(M)    a live or finished backend run's list, from what its record names (the spec's data).
 * A paper is listed only when the run's data names its DOI; its authors, title and venue come from REF,
 * checked against Crossref. Datasheets and rules come from ChipInModels and ChipInRegulation, the same
 * entries the Overview's battery and Regulation panels show.
 */
(function () {
  "use strict";
  var CSS = [
    ".sxp h4{font-size:12px;font-weight:650;color:var(--i600);text-transform:uppercase;letter-spacing:.04em;margin:22px 0 2px}",
    ".sxp h4:first-of-type{margin-top:18px}",
    ".sxp>ul.sxl{list-style:none;margin:0;padding:0}",
    ".sxl li{padding:9px 0;border-bottom:1px solid var(--hair);font-size:12.5px;line-height:1.5;color:var(--i700)}",
    ".sxl li:last-child{border-bottom:0}",
    ".sxl .t{font-size:14px;font-weight:600;color:var(--i900)}",
    ".sxl a{color:var(--blue7)}",
    ".sxl .m{color:var(--i600)}",
    ".sxl p{margin:2px 0 0}",
    ".sxp .none{font-size:13px;color:var(--i700);margin:6px 0 0}",
    ".src-mv{margin:12px 0 0;border-top:1px solid var(--hair);padding-top:6px}",
    ".src-mv details{padding:4px 0}",
    ".src-mv summary{cursor:pointer;color:var(--blue7);font-size:12.5px;font-weight:600;width:fit-content}",
    ".src-mv ul,.src-mv ol{margin:6px 0 4px;padding-left:18px;font-size:12.5px;line-height:1.5;color:var(--i800)}",
    ".src-mv li+li{margin-top:3px}.src-mv p{margin:4px 0;font-size:12.5px;line-height:1.5}",
  ].join("\n");
  function css() {
    if (document.getElementById("sx-styles")) return;
    var s = document.createElement("style"); s.id = "sx-styles"; s.textContent = CSS; document.head.appendChild(s);
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function a(url, text) { return url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + text + "</a>" : text; }
  var LIC = { "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/", "Open Data Commons Attribution License v1.0": "https://opendatacommons.org/licenses/by/1-0/" };
  var SHORT_LIC = { "Open Data Commons Attribution License v1.0": "ODC-By 1.0" };
  var doiOf = function (u) { var m = String(u || "").match(/doi\.org\/(10\.[^\s]+)/i); return m ? m[1].toLowerCase() : null; };

  /* Papers and datasets the run's data files name by DOI. Authors, title, venue and year as Crossref and
     the dataset's own page give them; the run's data decides which appear. */
  var REF = {
    "10.22489/cinc.2017.065-469": { authors: "Clifford GD, Liu C, Moody B, Lehman LH, Silva I, Li Q, Johnson AE, Mark RG", title: "AF classification from a short single lead ECG recording: the PhysioNet/Computing in Cardiology Challenge 2017", venue: "Computing in Cardiology 44", year: 2017 },
    "10.1038/sdata.2019.39": { authors: "Stevenson NJ, Tapani K, Lauronen L, Vanhatalo S", title: "A dataset of neonatal EEG recordings with seizure annotations", venue: "Scientific Data 6, 190039", year: 2019 },
    "10.1109/tbcas.2014.2354054": { authors: "Andersson O, Chon KH, Sörnmo L, Rodrigues JN", title: "A 290 mV sub-V<sub>T</sub> ASIC for real-time atrial fibrillation detection", venue: "IEEE Transactions on Biomedical Circuits and Systems 9(3), 377-386", year: 2015 },
  };
  // the comparison databases of data/af-baseline.json: the citation each one's PhysioNet page asks for
  var BASE_DS = {
    "10.13026/c2mw2d": { name: "MIT-BIH Atrial Fibrillation Database (PhysioNet)", what: "Long-term ECG with AF annotations; used to check the AF design against the published AF chip, subjects held out.", cite: "Moody GB, Mark RG. A new method for detecting atrial fibrillation using R-R intervals. Computers in Cardiology 10:227-230 (1983)." },
    "10.13026/c2f305": { name: "MIT-BIH Arrhythmia Database (PhysioNet)", what: "ECG with beat and rhythm annotations; run once as a second database in the same comparison.", cite: "Moody GB, Mark RG. The impact of the MIT-BIH Arrhythmia Database. IEEE Engineering in Medicine and Biology 20(3):45-50 (2001)." },
  };

  // data/af-baseline.json, next to this file: fetched once; the list redraws when it arrives
  var base, baseUrl = (function () { var cs = document.currentScript; return cs && cs.src ? new URL("data/af-baseline.json", cs.src).href : null; })();
  var redraw = null;
  if (baseUrl) fetch(baseUrl, { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
    .then(function (j) { base = j; if (redraw) redraw(); });

  function dataItem(name, url, lic, licUrl, what, cite, citeUrl) {
    return '<li><div class="t">' + a(url, esc(name)) + "</div>" +
      (lic ? '<p class="m">Licence: ' + a(licUrl || LIC[lic], esc(lic)) + "</p>" : "") +
      (what ? "<p>" + esc(what) + "</p>" : "") +
      (cite ? '<p class="m">Cite: ' + esc(cite) + (citeUrl ? " " + a(citeUrl, esc(citeUrl.replace(/^https:\/\//, ""))) : "") + "</p>" : "") + "</li>";
  }
  function paperItem(doi, used) {
    var p = REF[doi]; if (!p) return "";
    return '<li><div class="t">' + a("https://doi.org/" + doi, p.title) + '</div><p class="m">' + esc(p.authors) + ". " + esc(p.venue) + ", " + p.year + ".</p><p>" + esc(used) + "</p></li>";
  }
  function plainItem(name, url, line) { return '<li><div class="t">' + a(url, esc(name)) + "</div>" + (line ? "<p>" + esc(line) + "</p>" : "") + "</li>"; }

  /* every source of an example run, grouped; each group a list of <li> strings */
  function collect(o) {
    var run = o.run, G = { data: [], papers: [], rules: [], parts: [], tools: [] }, seen = {};
    var once = function (k) { if (!k || seen[k]) return false; seen[k] = 1; return true; };
    var F = o.af, E = o.eeg;
    if (F && F.dataset) {
      var d = F.dataset;
      once(d.url);
      G.data.push(dataItem(d.name, d.url, d.licence, d.licence_url,
        "Single-lead ECG; " + (d.recordings ? d.recordings.toLocaleString("en-GB") + " normal and AF recordings " : "the recordings ") + "trained, selected and tested the AF design, split by recording" + (d.test_recordings ? ", " + d.test_recordings.toLocaleString("en-GB") + " held out for testing" : "") + ".",
        d.credit && REF[doiOf(d.credit_url)] ? "Clifford et al., Computing in Cardiology 2017." : d.credit, d.credit_url));
      var cd = doiOf(d.credit_url);
      if (cd && once(cd)) G.papers.push(paperItem(cd, "The dataset paper for the recordings this run trained and tested on."));
    } else if (E && Array.isArray(E.datasets)) {
      E.datasets.forEach(function (x) {
        if (!once(x.url)) return;
        var dois = (String(x.credit || "").match(/https:\/\/doi\.org\/[^\s,;]+[^\s,;.)]/g) || []).map(doiOf);
        var paper = dois.filter(function (k) { return REF[k]; })[0];
        G.data.push(dataItem(x.name, x.url, x.licence, x.licence_url,
          "EEG of " + (typeof x.subjects === "number" ? x.subjects + " newborns" : "newborns") + " with seizures marked by three experts; trained, set thresholds for and tested every design, split by baby" + (E.split && /(\d+) held out/.test(E.split) ? ", " + E.split.match(/(\d+) held out/)[1] + " held out for testing" : "") + ".",
          paper ? "Stevenson et al., Scientific Data 2019." : x.credit, paper ? "https://doi.org/" + paper : null));
        if (paper && once(paper)) G.papers.push(paperItem(paper, "The dataset paper for the recordings this run trained and tested on."));
      });
    } else if ((o.ds || []).length) {
      o.ds.forEach(function (x) { if (once(x.url)) G.data.push(dataItem(x.name, x.url, x.licence, x.licence_url, x.credit, "", null)); });
    }
    // the AF run's comparison against a published chip (the Measured so far drawer)
    if (run.case === "af" && base && Array.isArray(base.links)) {
      base.links.forEach(function (l) {
        var k = doiOf(l.url);
        if (k && BASE_DS[k] && once(k)) G.data.push(dataItem(BASE_DS[k].name, l.url, "Open Data Commons Attribution License v1.0", null, BASE_DS[k].what, BASE_DS[k].cite, null));
      });
      base.links.forEach(function (l) { var k = doiOf(l.url); if (k && REF[k] && once(k)) G.papers.push(paperItem(k, "The published AF chip this run's design is compared against for accuracy and size.")); });
    }
    if (F && (F.notes || []).some(function (n) { return /\bYosys\b/.test(n); }))
      G.tools.push(plainItem("Yosys Open SYnthesis Suite", "https://yosyshq.net/yosys/", "Synthesised the AF circuit that was compiled; its cell count and longest path are the measured gate count and logic depth."));
    // battery figures: the parts and cells behind the Overview's battery panel, and its sourced notes
    var M = window.ChipInModels, ctx = o.ctx;
    if (M && ctx && ctx.caseKind) {
      var gates = ctx.chosen && ctx.chosen.gates > 0 ? ctx.chosen.gates : 2500, parts = {}, order = [], classes = [];
      var add = function (name, url, what) { if (!url) return; if (!parts[url]) { parts[url] = { name: name, what: [] }; order.push(url); } if (parts[url].what.indexOf(what) < 0) parts[url].what.push(what); };
      (ctx.budgets || []).forEach(function (b) {
        var n = ctx.caseKind === "incubator-radar-thermal" ? (b.sensors != null ? b.sensors : b.channels) : (b.channels != null ? b.channels : b.sensors);
        var bd; try { bd = M.deviceBudget({ kind: ctx.caseKind, channels: n, sensors: n, gates: gates, decisionsPerSecond: 1 }); } catch (e) { return; }
        bd.lines.forEach(function (ln) { add(ln.source_name, ln.source_url, String(ln.name).replace(/^\d+ x /, "").replace(/, \d+ of \d+ channels enabled.*$/, "")); });
        var c = M.batteryClass(bd.total_uw); classes.push(c.class);
        if (!c.cell || c.class !== "primary coin cell") { var r = M.batteryClass(1e9); /* the reference rechargeable, named in the panel */ if (r && r.cell) add(r.cell.source_name, r.cell.source_url, r.cell.name); }
        if (c.cell) add(c.cell.source_name, c.cell.source_url, c.cell.name);
      });
      var p0 = M.batteryClass(1).cell; if (p0) add(p0.source_name, p0.source_url, p0.name);
      order.forEach(function (u) { if (once(u)) G.parts.push(plainItem(parts[u].name, u, "Power or capacity figure for the battery estimate: " + parts[u].what.join("; ") + ".")); });
      // the regulation panel's sources, then the battery panel's sourced notes at each change of battery class
      var R = window.ChipInRegulation && window.ChipInRegulation.sources ? window.ChipInRegulation.sources() : [];
      R.forEach(function (e) { e.src.forEach(function (s) { if (once(s[1])) G.rules.push(plainItem(s[0], s[1], "Regulation panel: " + e.title + ".")); }); });
      classes.forEach(function (cl, i) {
        if (i === 0 || classes[i - 1] === cl) return;
        (M.CONSEQUENCES[cl] || []).forEach(function (c) { if (c.kind === "sourced" && once(c.source_url)) G.rules.push(plainItem(c.source_name, c.source_url, "Battery panel: " + c.text)); });
      });
    }
    G.sim = !G.data.length;
    return G;
  }
  var GROUPS = [["data", "Data"], ["papers", "Papers"], ["rules", "Standards and rules"], ["parts", "Parts and batteries"], ["tools", "Tools"]];
  function total(G) { return GROUPS.reduce(function (s, g) { return s + G[g[0]].length; }, 0); }
  function listHTML(G) {
    return '<div class="srcp sxp">' + GROUPS.map(function (g) {
      if (g[0] === "data" && G.sim) return "<h4>Data</h4><p class=\"none\">Synthetic data, simulated from a small stated model; no external dataset.</p>";
      return G[g[0]].length ? "<h4>" + g[1] + '</h4><ul class="sxl">' + G[g[0]].join("") + "</ul>" : "";
    }).join("") + "</div>";
  }
  function head(n, title) { return '<div class="vh"><h2>' + (title || "Sources") + '</h2><p class="vs">' + n + (n === 1 ? " source" : " sources") + "</p></div>"; }

  function html(o, onRedraw) {
    css();
    redraw = onRedraw || null;
    var G = collect(o);
    return (o.bare ? "" : head(total(G), o.title)) + listHTML(G);
  }
  function count(o) { return total(collect(o)); }

  /* a live or finished backend run: what its record names */
  function liveHTML(M) {
    css();
    var dt = (M && M.spec && M.spec.data) || {}, G = { data: [], papers: [], rules: [], parts: [], tools: [] };
    if (dt.mode === "public" && dt.dataset) G.data.push(dataItem(String(dt.dataset), null, "", null, "Named by the run's spec as its public dataset; the record gives no link, licence or credit.", "", null));
    else if (dt.mode === "own") G.data.push(plainItem("Own recordings", null, "Named by the run's spec; not available in this build."));
    G.sim = !G.data.length;
    return '<div class="srcp srcpage">' + head(total(G)) + listHTML(G) + "</div>";
  }

  /* the notes the Sources tab used to carry, as collapsed sections of the Assumptions and limits dialog:
     sec = [[summary, innerHTML], ...] from the page */
  function movedHTML(sec) {
    css();
    var s = (sec || []).filter(function (x) { return x && x[1]; });
    return s.length ? '<div class="src-mv">' + s.map(function (x) { return "<details><summary>" + esc(x[0]) + "</summary>" + x[1] + "</details>"; }).join("") + "</div>" : "";
  }

  window.ChipInSources = { html: html, count: count, liveHTML: liveHTML, movedHTML: movedHTML };
})();
