/* ChipIn i1 search steps: what a new run does between the brief and the run view (window.ChipInSearch).
 *
 * After Run on the guided spec, five short steps play before the run view opens:
 *   1. Reading your brief          the device, its signal and the targets, from the spec
 *   2. Searching public datasets   the sources checked and the sets on record for the device's signal
 *   3. Found                       the dataset the run uses: name, size and licence, read from the data
 *                                  files (../data/af-candidates.json, ../data/neonatal-eeg.json); nothing
 *                                  else is ever shown as found, and when no set fits, the step says so
 *   4. Checking fit                a warning where the data does not match the device
 *   5. Preparing N designs         N is the number of designs the run view then shows
 * The examples are static, so this is a replay of the steps, a few seconds each, and is marked as one.
 * A connected backend never comes here: its own stage events show at once (the LIVE HOOK in
 * startFromSpec returns first).
 *
 * Hook (dashboard/variants/i1.html, startFromSpec): ChipInSearch.play(run, spec, ctx) with
 *   ctx = { files: { af, eeg }, designs, sim, names: { metric: name }, dropped: [target names left out], to: open the run view,
 *           fresh: start the run's clock when the steps end, save: saveRuns }
 */
(function () {
  "use strict";
  var STEP_MS = 2300, END_MS = 700;
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var fmt = function (n) { return Number(n).toLocaleString("en-GB"); };
  var link = function (url, text) { return url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(text) + "</a>" : esc(text); };
  var SHORT_LIC = { "Open Data Commons Attribution License v1.0": "ODC-By 1.0" };

  // sets on record per signal, from dashboard/data and experiments/baselines on main (names only)
  var ON_RECORD = {
    ecg: { where: "PhysioNet", sets: ["CinC 2017", "MIT-BIH AF", "Long-Term AF", "MIT-BIH Arrhythmia", "Apnea-ECG"] },
    eeg: { where: "Zenodo", sets: ["Helsinki neonatal EEG"] }
  };
  var sigKind = function (t) { t = String(t || "").toLowerCase(); return /\beeg\b|electroenceph/.test(t) ? "eeg" : /\becg\b|\bekg\b|electrocardio/.test(t) ? "ecg" : ""; };

  // the dataset a run uses, from the data files only
  function foundSet(run, spec, files) {
    var k = run.case === "af" ? "af" : run.case === "neonatal-eeg" ? "eeg" : spec.data === "public" ? ({ cinc17: "af", helsinki: "eeg" })[spec.ds] : null;
    if (k === "af" && files.af && files.af.dataset) {
      var a = files.af.dataset;
      return { sig: "ecg", group: "", name: "PhysioNet/CinC Challenge 2017", url: a.url, size: a.recordings ? fmt(a.recordings) + " recordings" : "", lic: SHORT_LIC[a.licence] || a.licence, licUrl: a.licence_url, labels: "rhythm" };
    }
    if (k === "eeg" && files.eeg && files.eeg.datasets && files.eeg.datasets[0]) {
      var e = files.eeg.datasets[0];
      return { sig: "eeg", group: "newborns", name: "Helsinki neonatal EEG", url: e.url, size: e.subjects ? fmt(e.subjects) + " babies" : "", lic: e.licence, licUrl: e.licence_url, labels: "seizure" };
    }
    return null;
  }

  // the fit check: warnings where the set does not match the device, else one caution
  function fitCheck(run, spec, ds, ctx) {
    var sig = sigKind(run.signal + " " + run.brief), warn = [];
    if (!ds) return { warn: ["Nothing to check against: every number in this run is simulated."], ok: "" };
    if (ds.sig !== sig) warn.push((ds.sig === "eeg" ? "EEG" : "ECG") + " recordings, but your device senses " + (run.signal || "something else") + ": this data does not fit it.");
    if (ds.group === "newborns" && spec.group && spec.group !== "newborns") warn.push("Recordings of newborns, but your device is for " + spec.group + ": results would not carry over.");
    if (ctx.dropped && ctx.dropped.length) warn.push("This set has " + ds.labels + " labels only: " + ctx.dropped.join(" and ").toLowerCase() + " cannot be judged on it and is left out.");
    else if (ds.labels === "seizure" && /grad/.test(run.task || "")) warn.push("This set has seizure labels only: the grading target cannot be judged on it.");
    if (ctx.sim) warn.push("No measured results for your device here, so this run is simulated.");
    var ok = warn.length ? "" : "Fits: " + (ds.sig === "ecg" ? "single-lead ECG" : "EEG") + ". Recorded on other devices, so results are approximate.";
    return { warn: warn, ok: ok };
  }

  function steps(run, spec, ctx) {
    var sig = sigKind(run.signal + " " + run.brief), rec = ON_RECORD[sig], ds = foundSet(run, spec, ctx.files || {});
    var nT = (run.targets || []).length, fit = fitCheck(run, spec, ds, ctx);
    var nD = (ctx.designs || []).filter(function (d) { return d.role !== "baseline"; }).length;
    var device = run.device || "Your device", tg = (run.targets || []).map(function (t) { return (ctx.names && ctx.names[t.metric]) || t.metric; });
    return [
      { t: "Reading your brief", w: "Device, signal and targets", d: esc(device) + " \u00b7 " + (nT ? esc((nT === 1 ? "Target: " : "Targets: ") + tg.join(", ").toLowerCase()) : "no target set") },
      { t: "Searching public datasets", w: "Checking PhysioNet and Zenodo", d: rec ? esc((sig === "ecg" ? "ECG" : "EEG") + " sets on record: " + rec.sets.join(", ")) : "PhysioNet and Zenodo: nothing on record for " + esc((run.signal || "this signal").toLowerCase()) },
      spec.data === "own" ? { p: "Picking a dataset", t: "Your recordings: " + (spec.files || []).length + " file" + ((spec.files || []).length === 1 ? "" : "s"), w: "Reading them in this browser", d: "This demo does not design on them yet, so the run is simulated", warn: true }
        : ds ? { p: "Picking a dataset", t: "Found: " + ds.name, tHTML: "Found: " + link(ds.url, ds.name), w: "Reading its size and licence", d: [ds.size && esc(ds.size), ds.lic && link(ds.licUrl, ds.lic)].filter(Boolean).join(" · ") }
        : { p: "Picking a dataset", t: "No open data found", w: "Looking for a set that fits", d: "Synthetic data instead, from a small stated model", warn: true },
      { t: "Checking fit with your device", w: "Signal, patients and labels", d: fit.warn.length ? fit.warn.map(esc).join(" ") : esc(fit.ok), warn: fit.warn.length > 0 },
      { p: "Preparing candidate designs", t: "Preparing " + fmt(nD) + " candidate design" + (nD === 1 ? "" : "s"), w: "Lining them up for the chart", d: ctx.sim ? "Simulated designs, judged on your targets" : "From the real search, judged on your targets" }
    ];
  }

  var CSS = ".sx .gfc{max-width:620px}.sx-top{display:flex;align-items:center;gap:8px;margin:0 0 6px}" +
    ".sx ol{list-style:none;margin:30px 0 0;padding:0;display:flex;flex-direction:column}" +
    ".sx li{display:grid;grid-template-columns:22px minmax(0,1fr);gap:12px;padding:13px 0;border-top:1px solid var(--hair)}" +
    ".sx li:first-child{border-top:0}.sx .ic{width:22px;height:22px;display:grid;place-items:center;margin-top:1px}" +
    ".sx .ic i{width:9px;height:9px;border-radius:50%;border:1.6px solid var(--i200)}.sx .ic .spin{width:14px;height:14px}" +
    ".sx .ic svg{width:16px;height:16px;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}" +
    ".sx .st{font-size:14.5px;font-weight:600;color:var(--i900);line-height:1.35;overflow-wrap:anywhere}.sx .st a{color:inherit}" +
    ".sx .sl{font-size:12.5px;color:var(--i600);margin-top:2px;line-height:1.5;overflow-wrap:anywhere}.sx .sl a{color:var(--blue7)}" +
    ".sx li.pend .st{color:var(--i300)}.sx li.warn .sl{color:#8a5a0c}" +
    ".sx-foot{display:flex;justify-content:flex-end;margin-top:22px}";
  var ICON = {
    ok: '<svg viewBox="0 0 24 24" stroke="var(--okt)"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    warn: '<svg viewBox="0 0 24 24" stroke="#b45309"><circle cx="12" cy="12" r="8.5" stroke-width="1.8"/><path d="M12 8v4.5M12 16h.01"/></svg>'
  };

  function play(run, spec, ctx) {
    var main = document.getElementById("main");
    if (!main) { ctx.to(); return; }
    if (!document.getElementById("sx-css")) { var st = document.createElement("style"); st.id = "sx-css"; st.textContent = CSS; document.head.appendChild(st); }
    var S = steps(run, spec, ctx), hash = location.hash, timers = [], over = false;
    var badge = ctx.sim ? '<span class="mk sim">simulated</span>' : '<span class="mk mea">measured</span>';
    main.innerHTML = '<div class="gf sx" id="sx"><div class="gfc"><header class="gfh"><p class="gfn sx-top"><span>Replay of the search steps</span>' + badge + '</p><h1 tabindex="-1" id="sxH">Finding data for your device</h1></header>' +
      '<ol id="sxL" aria-live="polite"></ol><div class="sx-foot"><button type="button" class="btn s" id="sxSkip">Skip to the run</button></div></div></div>';
    var root = document.getElementById("sx"), list = document.getElementById("sxL");
    var draw = function (now) {
      list.innerHTML = S.map(function (s, i) {
        var state = i < now ? (s.warn ? "warn" : "done") : i === now ? "now" : "pend";
        var ic = state === "done" ? ICON.ok : state === "warn" ? ICON.warn : state === "now" ? '<span class="spin"></span>' : "<i></i>";
        var line = i < now ? s.d : i === now ? esc(s.w) + "…" : "";
        return '<li class="' + state + '"><span class="ic" aria-hidden="true">' + ic + '</span><div><div class="st">' + (i < now ? (s.tHTML || esc(s.t)) : esc(s.p || s.t)) + "</div>" + (line ? '<div class="sl">' + line + "</div>" : "") + "</div></li>";
      }).join("");
    };
    var finish = function (open) {
      if (over) return; over = true;
      timers.forEach(clearTimeout);
      if (ctx.fresh) { run.clock = { base: 0, anchor: Date.now(), playing: true }; if (ctx.save) ctx.save(); }
      if (open) ctx.to();
    };
    // the screen is gone: open the run unless the user went somewhere else
    var alive = function () { if (root.isConnected) return true; finish(location.hash === hash); return false; };
    document.getElementById("sxSkip").onclick = function () { finish(true); };
    draw(0);
    for (var i = 1; i <= S.length; i++) (function (k) { timers.push(setTimeout(function () { if (alive()) draw(k); }, k * STEP_MS)); })(i);
    timers.push(setTimeout(function () { if (alive()) finish(true); }, S.length * STEP_MS + END_MS));
    document.getElementById("sxH").focus({ preventScroll: true });
  }

  window.ChipInSearch = { play: play, steps: steps };
})();
