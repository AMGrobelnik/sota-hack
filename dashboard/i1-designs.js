/* ChipIn i1 designs: every design a run tried, drawn small in the Chip view ("Designs tried"), and the
 * selected one drawn larger with its key numbers and, where the run or data file holds them, its weights
 * as a heat map. Classic script, no dependencies; the Chip view of each kind of run calls one function:
 *
 *   ChipInDesigns.paintExample(anchor, ctx)  the example runs (variants/i1.html renderChipTab): the AF
 *                                            candidates, the neonatal EEG results file, simulated runs.
 *                                            The panel goes just after anchor (the 3D chip's stage) and its note.
 *   ChipInDesigns.paintRun(host, ctx)        recorded and live runs, from the shared fold (../i1-fold.js)
 *   ChipInDesigns.parseWeights(text)         weights written in a design's note or label, or null
 *
 * Honesty rules. A glyph is drawn from the design's recorded configuration only: inputs, hidden units and
 * output to scale, weight levels as the tone of the links, input bits as the width of the input bar, and a
 * size bar from its gate count (solid: measured; hollow: estimated; simulated runs say so on the panel).
 * Weights are drawn only where recorded: a compiled chip's chipir ir.json in a recorded run's files (shown
 * once the run has written it), w=[...] b=... or a weighted-sum rule in the design's own note or label,
 * and ../data/af-weights.json for the AF chosen design (public on the repo's main branch). Anywhere else
 * the panel draws the shape only and says the weights were not recorded. Selecting a glyph never changes
 * the circuit view: it stays on the chosen chip. */
(function () {
  "use strict";
  if (window.ChipInDesigns) return;

  /* ---------- helpers ---------- */
  const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const num = v => typeof v === "number" && isFinite(v) ? v : null;
  const fmt = n => Math.round(n).toLocaleString("en-GB");
  const pct = v => v == null ? "not reported" : (v * 100).toFixed(1) + "%";
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const RM = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const pl = (n, w) => fmt(n) + " " + w + (n === 1 ? "" : "s");

  /* ---------- styles ---------- */
  const STYLE = [
    ".dz-vis{padding-bottom:0}",
    ".dz{margin-top:14px;background:#fff;border:1px solid rgb(0 0 0/.07);border-radius:16px;box-shadow:var(--sh-hair);padding:14px 16px 12px;position:relative}",
    ".dz-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px}",
    ".dz-h h3{font-size:13.5px;font-weight:650;margin:0;color:var(--i900)}",
    ".dz-n{font-size:12px;color:var(--i600);font-variant-numeric:tabular-nums}",
    ".dz-lg{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:11.5px;color:var(--i600);margin:6px 0 0;align-items:center}",
    ".dz-lg span{display:inline-flex;align-items:center;gap:5px}",
    ".dz-lg svg{width:30px;height:14px;flex:none}",
    ".dz-b{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:14px;margin-top:10px;align-items:start}",
    "@media (max-width:900px){.dz-b{grid-template-columns:minmax(0,1fr)}}",
    ".dz-grid{min-width:0}",
    ".dz-g{margin:0 0 8px}",
    ".dz-g:last-child{margin-bottom:0}",
    ".dz-gh{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--i700);margin:0 0 3px;min-width:0}",
    ".dz-gh i{width:8px;height:8px;border-radius:2px;background:currentColor;flex:none}",
    ".dz-gh b{font-weight:600;color:var(--i900);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".dz-gh span{font-variant-numeric:tabular-nums;color:var(--i600)}",
    ".dz-cells{display:flex;flex-wrap:wrap;gap:2px;overflow:hidden;max-height:calc(var(--rows,4) * 30px - 2px)}",
    ".dz-g.open .dz-cells{max-height:none}",
    ".dz-more{border:0;background:none;padding:2px 0 0;font:inherit;font-size:11.5px;color:var(--blue7);cursor:pointer}",
    ".dz-more:hover{text-decoration:underline}",
    ".dz-c{--c:#6a7186;width:30px;height:28px;padding:1px 0 0;border:0;border-radius:6px;background:transparent;color:var(--c);cursor:pointer;flex:none;position:relative;transition:color .6s var(--ease,ease),background-color .2s,opacity .6s}",
    ".dz-c svg{width:30px;height:26px;display:block}",
    ".dz-grid.few .dz-c{width:54px;height:48px;border-radius:9px}.dz-grid.few .dz-c svg{width:54px;height:46px}.dz-grid.few .dz-cells{max-height:none}",
    ".dz-c:hover{background:var(--i100)}",
    ".dz-c:focus-visible{outline:2px solid var(--blue);outline-offset:0}",
    ".dz-c.on{background:#eef2fd;box-shadow:inset 0 0 0 1.5px var(--blue7)}",
    ".dz-c.ch{box-shadow:inset 0 0 0 1.5px var(--i900)}",
    ".dz-c.ch.on{box-shadow:inset 0 0 0 2px var(--i900);background:#eef2fd}",
    ".dz-c.nw{animation:dzIn .5s var(--ease,ease) both}",
    ".dz-c.lit::after{content:'';position:absolute;inset:-3px;border-radius:9px;border:2px solid var(--i900);animation:dzRing 1.4s var(--ease,ease) both;pointer-events:none}",
    "@keyframes dzIn{from{opacity:0;transform:scale(.55)}}",
    "@keyframes dzRing{from{opacity:.9;transform:scale(1.6)}to{opacity:0;transform:scale(1)}}",
    ".s-chosen{--c:#141a2e}.s-ver{--c:#0f7a55}.s-comp{--c:#2b55d0}.s-pass{--c:#2b55d0}.s-score{--c:#6a7186}.s-best{--c:#9a3412}.s-base{--c:#6b46c1}.s-drop{--c:#b2b6c2}",
    ".dz-gh.s-chosen,.dz-gh.s-ver,.dz-gh.s-comp,.dz-gh.s-pass,.dz-gh.s-score,.dz-gh.s-best,.dz-gh.s-base,.dz-gh.s-drop{color:var(--c)}",
    ".dz-gh.s-drop{--c:#9aa0ae}",
    ".dz-d{border-left:1px solid var(--hair);padding-left:14px;min-width:0}",
    "@media (max-width:900px){.dz-d{border-left:0;padding-left:0;border-top:1px solid var(--hair);padding-top:10px}}",
    ".dz-dh{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;margin:0}",
    ".dz-id{font-family:var(--mono);font-size:12px;color:var(--i900);word-break:break-all}",
    ".dz-lab{font-size:12px;color:var(--i600);margin:2px 0 0}",
    ".dz-big{display:block;width:100%;height:auto;margin:8px 0 2px}",
    ".dz-d .irow{padding:4px 0;font-size:12px}",
    ".dz-d .irow b{font-weight:600}",
    ".dz-wh{font-size:12px;font-weight:650;color:var(--i900);margin:10px 0 4px}",
    ".dz-wl{font-size:11px;color:var(--i600);margin:6px 0 2px}",
    ".dz-hm{display:block;max-width:100%;height:auto}",
    ".dz-key{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--i600);margin:6px 0 0;flex-wrap:wrap}",
    ".dz-key i{display:inline-block;width:12px;height:12px;border-radius:2px;vertical-align:-2px}",
    ".dz-src{font-size:11px;color:var(--i600);margin:6px 0 0;line-height:1.45;word-break:break-word}",
    ".dz-none{font-size:12px;color:var(--i600);margin:8px 0 0}",
    "@media (prefers-reduced-motion:reduce){.dz-c{transition:none}.dz-c.nw,.dz-c.lit::after{animation:none}}"
  ];
  function ensureCSS() {
    if (document.getElementById("dz-css")) return;
    const s = document.createElement("style"); s.id = "dz-css"; s.textContent = STYLE.join("\n"); document.head.appendChild(s);
  }

  /* ---------- weights written in a note or label ---------- */
  // "w=[-1, 5] b=-198", "3*bd1+1*zc1 >= 208", "-ll0+5*band1-99>0", "LOPO bd0,zc0 3,2 t233"
  function parseWeights(text) {
    const s = String(text || "");
    let m = s.match(/\bw\s*=\s*\[\s*(-?\d+(?:\s*,\s*-?\d+)*)\s*\]\s*,?\s*(?:b\s*=\s*(-?\d+))?/i);
    if (m) return { W: [m[1].split(",").map(x => +x)], b: m[2] != null ? [+m[2]] : null, names: null, how: "w and b" };
    m = s.match(/((?:[-+]?\s*(?:\d+\s*\*\s*)?[a-z][a-z_]*\d*\s*)(?:[-+]\s*(?:\d+\s*\*\s*)?[a-z][a-z_]*\d*\s*)*)([-+]\s*\d+\s*)?(>=|>)\s*(-?\d+)/i);
    if (m && /\d\s*\*|[a-z]\d/i.test(m[1])) {
      const names = [], W = [];
      m[1].replace(/([-+]?)\s*(?:(\d+)\s*\*\s*)?([a-z][a-z_]*\d*)/gi, (_, sg, k, n) => { names.push(n); W.push((sg === "-" ? -1 : 1) * (k ? +k : 1)); return ""; });
      if (names.length >= 1 && names.length <= 64) {
        const c = m[2] ? +m[2].replace(/\s+/g, "") : 0, t = +m[4];
        return { W: [W], b: [c - t], names, how: "rule" };
      }
    }
    m = s.match(/\b([a-z][a-z_]*\d+(?:,[a-z][a-z_]*\d+)+)\s+(-?\d+(?:,-?\d+)+)\s+t(-?\d+)\b/i);
    if (m) {
      const names = m[1].split(","), W = m[2].split(",").map(x => +x);
      if (names.length === W.length) return { W: [W], b: [-+m[3]], names, how: "rule" };
    }
    return null;
  }

  /* ---------- shape and weights from a chipir/1 file or an integer-network model ---------- */
  function fromIR(ir) {
    if (!ir || ir.ir !== "chipir/1" || !Array.isArray(ir.inputs) || !Array.isArray(ir.nodes)) return null;
    const ins = ir.inputs.reduce((a, x) => a + (num(x.lanes) || 1), 0), bits = num(ir.inputs[0] && ir.inputs[0].bits);
    const layers = [], W = [], ops = [];
    ir.nodes.forEach(n => {
      if (n.op === "matvec" && Array.isArray(n.W) && n.W.length) { layers.push(n.W.length); W.push({ name: n.id, W: n.W, b: Array.isArray(n.b) ? n.b : null }); }
      else if (n.op === "shift") { if (n.k) ops.push("shift " + n.k); }
      else if (n.op === "clip") ops.push("clip " + n.lo + " to " + n.hi);
      else if (n.op === "cmp") ops.push("compare " + (n.rel === "gt" ? ">" : n.rel === "ge" ? ">=" : n.rel || "") + " " + (Array.isArray(n.t) && n.t.every(x => x === n.t[0]) ? n.t[0] : "t"));
      else if (n.op) ops.push(String(n.op));
    });
    if (!layers.length) return null;
    return { ins, bits, layers, weights: W, ops: [...new Set(ops)] };
  }
  function fromIntnn(m) {
    if (!m || !Array.isArray(m.W1)) return null;
    const c = m.cfg || {}, W2 = Array.isArray(m.W2) ? (Array.isArray(m.W2[0]) ? m.W2 : [m.W2]) : null;
    const ins = m.W1[0] ? m.W1[0].length : num(c.L), H = m.W1.length;
    const W = [{ name: "hidden", W: m.W1, b: m.b1 || null }];
    if (W2) W.push({ name: "output", W: W2, b: m.b2 != null ? [].concat(m.b2) : null });
    const ops = []; if (num(m.shift)) ops.push("shift " + m.shift); if (num(m.amax)) ops.push("clip 0 to " + m.amax);
    return { ins, bits: num(c.bits), layers: W2 ? [H, W2.length] : [H], weights: W, ops };
  }
  // shape words in a label: "int MLP 2h 3f 4-bit w", "integer linear 2f", "band detector, 3 comparators"
  // bit widths: "4-bit w" and "4-bit weights" are the weights' width, never the inputs'; input bits come from
  // the label's other n-bit, else from the note ("6-bit features", "features ll0 and band1 (6-bit)")
  const WBIT = /(\d+)-bit\s*(?:w\b|weights?\b)/;
  function bitsOf(label, note) {
    const s = String(label || "").toLowerCase(), t = String(note || "").toLowerCase();
    const lb = s.replace(new RegExp(WBIT.source, "g"), " ").match(/(\d+)-bit/);
    const nb = t.match(/(\d+)-bit\s+(?:unsigned\s+)?(?:features?|inputs?|ints?|integers?)\b|features?\b[^.;\n]{0,40}?\((\d+)-bit\)|unsigned\s+(\d+)-bit/);
    const wb = s.match(WBIT) || t.match(WBIT);
    return { bits: lb ? +lb[1] : nb ? +(nb[1] || nb[2] || nb[3]) : null, wbits: wb ? +wb[1] : null };
  }
  function fromLabel(label, note) {
    const s = String(label || "").toLowerCase(); if (!s) return null;
    const f = s.match(/(\d+)\s*f\b|(\d+)-feature|(\d+) features?|(\d+) lanes?/), h = s.match(/(\d+)\s*h\b|(\d+) hidden|(\d+) comparators?/), b = bitsOf(label, note);
    const ins = f ? +(f[1] || f[2] || f[3] || f[4]) : /threshold/.test(s) ? 1 : null;
    const hid = h ? +(h[1] || h[2] || h[3]) : /linear|logistic|threshold/.test(s) ? 0 : null;
    if (ins == null && hid == null) return { ins: null, layers: null, bits: b.bits, wbits: b.wbits };
    return { ins, layers: hid ? [hid, 1] : hid === 0 ? [1] : null, bits: b.bits, wbits: b.wbits };
  }
  const levelsOf = W => { const s = new Set(); W.forEach(l => l.W.forEach(r => r.forEach(x => s.add(x)))); return s.size; };
  const maxAbsOf = W => W.reduce((a, l) => l.W.reduce((a2, r) => r.reduce((a3, x) => Math.max(a3, Math.abs(x)), a2), a), 0) || 1;

  /* ---------- the AF chosen design's published weights ---------- */
  const AFW = { p: null, map: {} };
  function loadAFWeights(onload) {
    if (AFW.p) return AFW.p;
    AFW.p = fetch("../data/af-weights.json", { cache: "no-store" }).then(r => r.ok ? r.json() : null).then(j => {
      (j && Array.isArray(j.designs) ? j.designs : []).forEach(d => { if (d && d.id && d.model) AFW.map[d.id] = d; });
      onload();
    }).catch(() => { /* no file: the AF designs show their shape only */ });
    return AFW.p;
  }

  /* ---------- glyphs ---------- */
  const linkOp = lev => lev == null ? 0.3 : lev <= 2 ? 0.2 : lev <= 3 ? 0.28 : lev <= 7 ? 0.38 : lev <= 15 ? 0.46 : 0.52;
  // the small drawing: columns of units to scale (sqrt of the run's largest column), links between them,
  // the size bar underneath on a log scale shared by the run
  function glyph(it, S) {
    const out = [], cy = 10;
    const cols = it.ins != null && it.layers ? [it.ins].concat(it.layers) : null;
    if (cols) {
      const n = cols.length, xs = cols.map((_, i) => n === 1 ? 15 : 4.5 + i * (21 / (n - 1)));
      const hs = cols.map(u => u <= 1 ? 0 : 2.6 + 13.4 * Math.sqrt((u - 1) / Math.max(1, S.maxU - 1)));
      const op = linkOp(it.lev);
      // a network shared by several channels: faint copies stacked behind it (1 for 2 channels, 2 for 4, 3 for more)
      const cp = it.shared > 1 ? (it.shared <= 2 ? 1 : it.shared <= 4 ? 2 : 3) : 0;
      for (let k = cp; k >= 1; k--) out.push(`<g transform="translate(${1.6 * k} ${-1.6 * k})" opacity="${(0.32 - 0.07 * k).toFixed(2)}">` + cols.map((u, i) => u <= 1 ? `<circle cx="${xs[i]}" cy="${cy}" r="1.5" fill="currentColor"/>` : `<rect x="${(xs[i] - 1).toFixed(2)}" y="${(cy - hs[i] / 2).toFixed(2)}" width="2" height="${hs[i].toFixed(2)}" rx="0.9" fill="currentColor"/>`).join("") + `</g>`);
      for (let i = 0; i < n - 1; i++) out.push(`<path d="M${xs[i]} ${cy - hs[i] / 2}L${xs[i + 1]} ${cy - hs[i + 1] / 2}V${cy + hs[i + 1] / 2}L${xs[i]} ${cy + hs[i] / 2}Z" fill="currentColor" fill-opacity="${op}"/>`);
      cols.forEach((u, i) => {
        const w = i === 0 ? 1.6 + clamp((it.bits || 4) - 4, 0, 4) * 0.32 : 2;
        out.push(u <= 1 ? `<circle cx="${xs[i]}" cy="${cy}" r="1.8" fill="currentColor"/>` : `<rect x="${(xs[i] - w / 2).toFixed(2)}" y="${(cy - hs[i] / 2).toFixed(2)}" width="${w.toFixed(2)}" height="${hs[i].toFixed(2)}" rx="0.9" fill="currentColor"/>`);
      });
    } else {
      // shape not recorded: a block whose side grows with the gate count, one input stub per channel
      const g = it.size ? it.size.g : 0, side = 5 + 9 * (g > 0 ? Math.log(g + 1) / Math.log(S.maxG + 1) : 0.2);
      const ch = clamp(it.chans || 1, 1, 4);
      for (let k = 0; k < ch; k++) { const y = cy - (ch - 1) * 1.6 + k * 3.2; out.push(`<path d="M4 ${y}H${15 - side / 2}" stroke="currentColor" stroke-width="1.1" opacity=".7"/>`); }
      out.push(`<rect x="${(15 - side / 2).toFixed(2)}" y="${(cy - side / 2).toFixed(2)}" width="${side.toFixed(2)}" height="${side.toFixed(2)}" rx="1.6" fill="currentColor" fill-opacity=".85"/><path d="M${(15 + side / 2).toFixed(2)} ${cy}H26" stroke="currentColor" stroke-width="1.1" opacity=".7"/>`);
    }
    // size bar
    out.push(`<rect x="3" y="21" width="24" height="3" rx="1.5" fill="#e7e9ee"/>`);
    if (it.size && it.size.g > 0) {
      const w = Math.max(1.5, 24 * Math.log(it.size.g + 1) / Math.log(S.maxG + 1));
      out.push(it.size.k === "e" ? `<rect x="3.4" y="21.4" width="${(w - 0.8).toFixed(2)}" height="2.2" rx="1.1" fill="#fff" stroke="currentColor" stroke-width=".8"/>` : `<rect x="3" y="21" width="${w.toFixed(2)}" height="3" rx="1.5" fill="currentColor"/>`);
    }
    // verified bit for bit, whatever its group: a small green dot in the corner
    if (it.vmark) out.push(`<circle cx="27.4" cy="2.6" r="2" fill="#0f7a55" stroke="#fff" stroke-width=".8"/>`);
    return `<svg viewBox="0 0 30 26" aria-hidden="true">${out.join("")}</svg>`;
  }

  // the larger drawing: one node per unit (a bar past 24), links coloured by the weight where recorded
  const POS = "#2b55d0", NEG = "#c2362b";
  function bigDrawing(it) {
    const W = 300, H = 132, top = 10, bot = 104, out = [];
    const cols = it.ins != null && it.layers ? [it.ins].concat(it.layers) : null;
    if (!cols) {
      out.push(`<rect x="110" y="28" width="80" height="64" rx="8" fill="currentColor" fill-opacity=".12" stroke="currentColor" stroke-opacity=".5"/><text x="150" y="64" text-anchor="middle" font-size="11" fill="#4a5062">${it.size ? esc(fmt(it.size.g)) + " gates" : "size not reported"}</text>`);
      const ch = clamp(it.chans || 1, 1, 8);
      for (let k = 0; k < ch; k++) { const y = 60 - (ch - 1) * 5 + k * 10; out.push(`<path d="M40 ${y}H110" stroke="#9aa0ae" stroke-width="1.2"/>`); }
      out.push(`<path d="M190 60H260" stroke="#9aa0ae" stroke-width="1.2"/><text x="40" y="${H - 12}" font-size="10.5" fill="#5c6276">${esc(it.chans ? pl(it.chans, "channel") : "inputs")}</text><text x="260" y="${H - 12}" font-size="10.5" fill="#5c6276" text-anchor="end">alarm</text>`);
      return `<svg class="dz-big" viewBox="0 0 ${W} ${H}" role="img" aria-label="Shape: ${esc(it.chans ? pl(it.chans, "channel") : "inputs")} into a block of ${it.size ? fmt(it.size.g) : "unknown"} gates">${out.join("")}</svg>`;
    }
    // a network shared by several channels leaves room on the right for the max over channels, then the alarm
    const sh = it.shared > 1, R = sh ? 74 : 0;
    const n = cols.length, xs = cols.map((_, i) => 34 + i * ((W - 68 - R) / Math.max(1, n - 1)));
    const pos = cols.map(u => { const k = Math.min(u, 24), span = Math.min(bot - top - (sh ? 10 : 0), (k - 1) * 18); return Array.from({ length: k }, (_, j) => (top + bot) / 2 + (sh ? 5 : 0) - span / 2 + (k > 1 ? j * span / (k - 1) : 0)); });
    if (sh) {
      const cp = Math.min(2, it.shared - 1), mx = xs[n - 1] + 30, my = (top + bot) / 2 + 5;
      for (let k = cp; k >= 1; k--) {
        out.push(`<g transform="translate(${5 * k} ${-5 * k})" opacity="${k === 1 ? 0.3 : 0.18}">` + cols.map((u, i) => pos[i].map(y => `<circle cx="${xs[i]}" cy="${y.toFixed(1)}" r="${u > 16 ? 2.2 : 3}" fill="none" stroke="currentColor" stroke-width="1"/>`).join("")).join("") + `</g>`);
        out.push(`<path d="M${xs[n - 1] + 5 * k} ${my - 5 * k}L${mx} ${my}" stroke="currentColor" stroke-opacity=".3" stroke-width="1"/>`);
      }
      out.push(`<path d="M${xs[n - 1]} ${my}H${mx}" stroke="currentColor" stroke-opacity=".6" stroke-width="1.1"/><rect x="${mx}" y="${my - 11}" width="28" height="22" rx="5" fill="#fff" stroke="currentColor" stroke-width="1.4"/><text x="${mx + 14}" y="${my + 3.5}" font-size="10" text-anchor="middle" fill="#4a5062">max</text><path d="M${mx + 28} ${my}H${W - 8}" stroke="currentColor" stroke-opacity=".6" stroke-width="1.1"/>`);
      out.push(`<text x="${W - 6}" y="${my - 20}" font-size="10.5" fill="#5c6276" text-anchor="end">× ${fmt(it.shared)} channels</text><text x="${W - 6}" y="${H - 12}" font-size="10.5" fill="#5c6276" text-anchor="end">alarm</text>`);
    }
    const wts = it.weights && it.weights.layers, m = wts ? maxAbsOf(wts) : 1;
    for (let i = 0; i < n - 1; i++) {
      const L = wts && wts[i] && wts[i].W.length === cols[i + 1] && wts[i].W.every(r => r.length === cols[i]) ? wts[i].W : null;
      const A = pos[i], B = pos[i + 1], many = A.length * B.length > 420;
      if (L && cols[i] <= 24 && cols[i + 1] <= 24) {
        L.forEach((row, b) => row.forEach((w, a) => { if (!w) return; out.push(`<path d="M${xs[i]} ${A[a].toFixed(1)}L${xs[i + 1]} ${B[b].toFixed(1)}" stroke="${w > 0 ? POS : NEG}" stroke-opacity="${(0.18 + 0.62 * Math.abs(w) / m).toFixed(2)}" stroke-width="${(0.7 + 1.1 * Math.abs(w) / m).toFixed(2)}"/>`); }));
      } else if (!many) {
        A.forEach(ya => B.forEach(yb => out.push(`<path d="M${xs[i]} ${ya.toFixed(1)}L${xs[i + 1]} ${yb.toFixed(1)}" stroke="currentColor" stroke-opacity=".14" stroke-width=".7"/>`)));
      } else {
        out.push(`<path d="M${xs[i]} ${A[0]}L${xs[i + 1]} ${B[0]}V${B[B.length - 1]}L${xs[i]} ${A[A.length - 1]}Z" fill="currentColor" fill-opacity=".1"/>`);
      }
    }
    cols.forEach((u, i) => {
      const P = pos[i];
      if (u > 24) out.push(`<rect x="${xs[i] - 3}" y="${P[0] - 3}" width="6" height="${P[P.length - 1] - P[0] + 6}" rx="3" fill="currentColor"/>`);
      else P.forEach(y => out.push(`<circle cx="${xs[i]}" cy="${y.toFixed(1)}" r="${u > 16 ? 2.6 : 3.4}" fill="#fff" stroke="currentColor" stroke-width="1.4"/>`));
      const lab = i === 0 ? `${fmt(u)} in` : i === n - 1 ? (u === 1 ? "out" : `${fmt(u)} out`) : `${fmt(u)} hidden`;
      const end = i === n - 1 && !sh;
      out.push(`<text x="${xs[i]}" y="${H - 12}" font-size="10.5" fill="#5c6276" text-anchor="${i === 0 ? "start" : end ? "end" : "middle"}" dx="${i === 0 ? -6 : end ? 6 : 0}">${lab}</text>`);
    });
    return `<svg class="dz-big" viewBox="0 0 ${W} ${H}" role="img" aria-label="Structure: ${cols.map(fmt).join(", then ")} units${sh ? `, one network shared by ${it.shared} channels, then the highest score over channels sets the alarm` : ""}${wts ? "; links coloured by weight" : ""}">${out.join("")}</svg>`;
  }

  // one weight matrix as a grid, one cell per weight, on a diverging scale shared by the design
  function mix(a, b, t) { const p = h => [1, 3, 5].map(k => parseInt(h.slice(k, k + 2), 16)), A = p(a), B = p(b); return "rgb(" + A.map((x, i) => Math.round(x + (B[i] - x) * t)).join(" ") + ")"; }
  const wColor = (w, m) => w === 0 ? "#eef0f3" : mix("#ffffff", w > 0 ? POS : NEG, 0.28 + 0.72 * Math.abs(w) / m);
  // a tall matrix (more units than inputs) is drawn turned, inputs down and units across, so the next
  // layer's row of weights lines up under the same units
  function heatmap(L, m, names, maxW) {
    const tr = L.W.length > L.W[0].length, G = tr ? L.W[0].map((_, c) => L.W.map(r => r[c])) : L.W;
    const R = G.length, C = G[0].length, cs = clamp(Math.floor(maxW / C), 7, C <= 6 ? 26 : 16), lab = !tr && names && names.length === C && cs >= 12;
    const w = C * cs, h = R * cs + (lab ? 14 : 0), out = [];
    G.forEach((row, r) => row.forEach((x, c) => { const u = tr ? c : r, i = tr ? r : c; out.push(`<rect x="${c * cs + 0.5}" y="${r * cs + 0.5}" width="${cs - 1}" height="${cs - 1}" rx="1.5" fill="${wColor(x, m)}"><title>${L.W.length > 1 ? `unit ${u + 1}, ` : ""}input ${names && names[i] ? esc(names[i]) : i + 1}: ${x}</title></rect>`); }));
    if (lab) names.forEach((nm, c) => out.push(`<text x="${c * cs + cs / 2}" y="${R * cs + 11}" font-size="9.5" text-anchor="middle" fill="#5c6276">${esc(nm.length > 6 ? nm.slice(0, 6) : nm)}</text>`));
    return `<svg class="dz-hm" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${R} by ${C} weights">${out.join("")}</svg>`;
  }
  function weightsHTML(it) {
    const Wt = it.weights;
    if (!Wt) return `<p class="dz-none">${esc(it.wnone || "Weights not recorded for this design.")}</p>`;
    const m = maxAbsOf(Wt.layers), ints = Wt.layers.every(l => l.W.every(r => r.every(x => Number.isInteger(x))));
    const parts = Wt.layers.map((L, i) => {
      const R = L.W.length, C = L.W[0] ? L.W[0].length : 0;
      if (!C) return "";
      const b = L.b && L.b.length ? (L.b.length <= 4 ? "bias " + L.b.join(", ") : "biases " + Math.min(...L.b) + " to " + Math.max(...L.b)) : "";
      const nm = (Wt.layers.length === 1 ? (R === 1 ? `${C} inputs to output` : `${C} inputs to ${R} units`) : i === 0 ? `${C} inputs to ${R} hidden` : i === Wt.layers.length - 1 ? `${C} hidden to output` : `Layer ${i + 1}`) + (R > C ? " (inputs down, units across)" : "");
      return `<p class="dz-wl">${esc(nm)}${b ? ", " + esc(b) : ""}</p>${heatmap(L, m, i === 0 ? Wt.names : null, 260)}`;
    }).join("");
    const keyVals = ints && m <= 4 ? Array.from({ length: 2 * m + 1 }, (_, k) => k - m) : null;
    const key = keyVals ? keyVals.map(v => `<span><i style="background:${wColor(v, m)}"></i>${v > 0 ? "+" + v : v}</span>`).join("") : `<span><i style="background:${wColor(-m, m)}"></i>${-m}</span><span><i style="background:${wColor(0, m)}"></i>0</span><span><i style="background:${wColor(m, m)}"></i>+${m}</span>`;
    return parts + `<div class="dz-key">${key}</div>` + (Wt.ops && Wt.ops.length ? `<p class="dz-src">Then: ${esc(Wt.ops.join(", "))}.</p>` : "") + `<p class="dz-src">From ${Wt.srcHTML || esc(Wt.src)}.</p>`;
  }

  /* ---------- the panel ---------- */
  function scaleOf(items) {
    let maxU = 2, maxG = 10;
    items.forEach(it => { if (it.ins != null && it.layers) maxU = Math.max(maxU, it.ins, ...it.layers); if (it.size && it.size.g > maxG) maxG = it.size.g; });
    return { maxU, maxG };
  }
  const LEGEND = (S, o) => {
    const ex = o.sim ? { chans: 2, size: { g: Math.sqrt(S.maxG), k: "s" } } : { ins: 6, layers: [4, 1], lev: 3, bits: 6, size: { g: Math.sqrt(S.maxG), k: "m" } };
    return `<span>${glyph(ex, { maxU: 8, maxG: S.maxG })}${o.sim ? "channels in, a block that grows with its gates" : "inputs, hidden, output, to scale"}</span>` +
      `<span><svg viewBox="0 0 30 14"><rect x="3" y="5" width="24" height="3" rx="1.5" fill="#e7e9ee"/><rect x="3" y="5" width="15" height="3" rx="1.5" fill="#4a5062"/></svg>gates, ${o.sim ? "simulated" : "measured"}</span>` +
      (o.est ? `<span><svg viewBox="0 0 30 14"><rect x="3" y="5" width="24" height="3" rx="1.5" fill="#e7e9ee"/><rect x="3.4" y="5.4" width="14.2" height="2.2" rx="1.1" fill="#fff" stroke="#4a5062" stroke-width=".8"/></svg>gates, estimated</span>` : "");
  };
  const VDOT = `<span><svg viewBox="0 0 30 14"><circle cx="15" cy="7" r="3" fill="#0f7a55"/></svg>verified bit for bit</span>`;
  function skeleton(host, title) {
    host.innerHTML = `<section class="dz" aria-label="${esc(title)}"><div class="dz-h"><h3>${esc(title)}</h3><span class="dz-n"></span><span class="dz-mk"></span></div><div class="dz-lg"></div>` +
      `<div class="dz-b"><div class="dz-grid" role="list"></div><aside class="dz-d" aria-live="polite"></aside></div></section>`;
    const S = host._dz;
    host.onclick = e => {
      const c = e.target.closest(".dz-c");
      if (c) { S.sel = c.dataset.id; S.dsig = ""; paintBody(host); return; }
      const mo = e.target.closest(".dz-more");
      if (mo) { const g = mo.closest(".dz-g"); S.open[g.dataset.g] = !S.open[g.dataset.g]; S.gsig = ""; paintBody(host); }
    };
  }
  // the grid: groups in order, one keyed button per design, so a design that changes state keeps its place
  // in the DOM and only its colour changes; new designs fade in, a moved one slides (FLIP), all off under reduced motion
  function paintGrid(host) {
    const S = host._dz, M = S.model, grid = host.querySelector(".dz-grid"), motion = !RM() && S.painted;
    grid.classList.toggle("few", M.items.length <= 40);
    const before = new Map();
    if (motion) S.cells.forEach((el, id) => { if (el.isConnected) before.set(id, el.getBoundingClientRect()); });
    const live = new Set(), rows = matchMedia("(max-width:600px)").matches ? 3 : 4;
    const groups = M.groups.map(g => ({ g, items: M.items.filter(it => it.grp === g.k) })).filter(x => x.items.length);
    const want = new Set(groups.map(x => x.g.k));
    [...grid.children].forEach(el => { if (!want.has(el.dataset.g)) el.remove(); });
    groups.forEach((x, gi) => {
      let ge = grid.querySelector(`.dz-g[data-g="${CSS.escape(x.g.k)}"]`);
      if (!ge) { ge = document.createElement("div"); ge.className = "dz-g"; ge.dataset.g = x.g.k; ge.setAttribute("role", "listitem"); ge.innerHTML = `<div class="dz-gh"><i></i><b></b><span></span></div><div class="dz-cells"></div><button type="button" class="dz-more" hidden></button>`; }
      if (grid.children[gi] !== ge) grid.insertBefore(ge, grid.children[gi] || null);
      ge.style.setProperty("--rows", rows);
      ge.classList.toggle("open", !!S.open[x.g.k]);
      const gh = ge.firstChild; gh.className = "dz-gh " + x.g.c; gh.children[1].textContent = x.g.t; gh.children[1].title = x.g.t; gh.children[2].textContent = fmt(x.items.length);
      const box = ge.children[1];
      x.items.forEach((it, i) => {
        live.add(it.id);
        let el = S.cells.get(it.id);
        if (!el) { el = document.createElement("button"); el.type = "button"; el.className = "dz-c"; el.dataset.id = it.id; if (S.painted && !RM()) { el.classList.add("nw"); el.addEventListener("animationend", () => el.classList.remove("nw"), { once: true }); } S.cells.set(it.id, el); }
        const gs = it.gsig;
        if (el._g !== gs) { el.innerHTML = glyph(it, M.S); el._g = gs; }
        const cls = "dz-c " + it.c + (it.id === S.selId ? " on" : "") + (it.chosen ? " ch" : "") + (el.classList.contains("nw") ? " nw" : "") + (el.classList.contains("lit") ? " lit" : "");
        if (el.className !== cls) el.className = cls;
        if (it.chosen && !el._ch && S.painted && !RM()) { el.classList.add("lit"); setTimeout(() => el.classList.remove("lit"), 1500); }
        el._ch = it.chosen;
        if (el.title !== it.tip) { el.title = it.tip; el.setAttribute("aria-label", it.tip); }
        if (box.children[i] !== el) box.insertBefore(el, box.children[i] || null);
      });
      while (box.children.length > x.items.length) box.lastChild.remove();
    });
    S.cells.forEach((el, id) => { if (!live.has(id)) { el.remove(); S.cells.delete(id); } });
    // a group longer than its rows folds behind "Show all"
    grid.querySelectorAll(".dz-g").forEach(ge => {
      const box = ge.children[1], mo = ge.children[2], open = ge.classList.contains("open"), over = open || box.scrollHeight > box.clientHeight + 2;
      mo.hidden = !over; if (over) mo.textContent = open ? "Show fewer" : `Show all ${fmt(box.children.length)}`;
    });
    if (motion && before.size) {
      S.cells.forEach((el, id) => {
        const a = before.get(id); if (!a || !el.isConnected) return;
        const b = el.getBoundingClientRect(), dx = a.left - b.left, dy = a.top - b.top;
        if ((dx || dy) && Math.abs(dx) + Math.abs(dy) < 1600 && b.height) el.animate([{ transform: `translate(${dx}px,${dy}px)` }, { transform: "none" }], { duration: 520, easing: "cubic-bezier(.4,0,.2,1)" });
      });
    }
    S.painted = true;
  }
  function paintDetail(host) {
    const S = host._dz, M = S.model, d = host.querySelector(".dz-d");
    const it = M.items.find(x => x.id === S.selId);
    const sig = it ? it.id + "|" + it.dsig : "none";
    if (S.dsig === sig) return;
    S.dsig = sig;
    if (!it) { d.innerHTML = `<p class="dz-none">${esc(M.empty || "No design yet.")}</p>`; return; }
    const pill = it.chosen ? `<span class="pf ok">${esc(it.pill || "Chosen")}</span>` : it.c === "s-drop" ? `<span class="pf no">${esc(it.why || "Dropped")}</span>` : it.c === "s-best" ? `<span class="pf no">${esc(it.why || "Misses the bar")}</span>` : `<span class="pf na">${esc(it.why || it.stText || "")}</span>`;
    // a design is named in words (its label, read by ../i1-fold.js humanLabel); the technical id stays small under it
    const hl = it.label ? ((window.ChipInFold && window.ChipInFold.humanLabel) ? window.ChipInFold.humanLabel(it.label) : it.label) : "";
    const nm = it.plain || hl, wk = it.plain && it.label && hl !== it.plain ? it.label : "";
    d.innerHTML = `<div class="dz-dh">${nm ? `<span class="dz-nm" style="font-weight:600;font-size:13px;color:var(--i900)">${esc(nm)}</span>` : `<span class="dz-id">${esc(it.id)}</span>`}${pill}</div>${nm ? `<p class="dz-lab">${wk ? `<span class="dz-wk" style="font-size:11px;color:var(--i550,#7a8194)" title="Working name in the design file">${esc(wk)}</span> ` : ""}<span class="dz-id" style="font-size:10.5px;color:var(--i550,#7a8194)" title="Technical id">${esc(it.id)}</span></p>` : ""}` +
      `<div style="color:var(--c)" class="${it.c}">${bigDrawing(it)}</div>` +
      it.facts.map(r => `<div class="irow"><span>${esc(r[0])}</span><b>${r[1]}</b></div>`).join("") +
      `<p class="dz-wh">Weights</p>${weightsHTML(it)}`;
  }
  function paintBody(host) {
    const S = host._dz, M = S.model;
    const ids = new Set(M.items.map(x => x.id));
    S.selId = S.sel && ids.has(S.sel) ? S.sel : M.defId && ids.has(M.defId) ? M.defId : null;
    const hd = host.querySelector(".dz-n"); if (hd.innerHTML !== M.count) hd.innerHTML = M.count;
    const mk = host.querySelector(".dz-mk"); if (mk.innerHTML !== M.mark) mk.innerHTML = M.mark;
    const lg = host.querySelector(".dz-lg"), lgs = M.legend; if (lg._s !== lgs) { lg.innerHTML = lgs; lg._s = lgs; }
    const gsig = M.sig + "|" + S.selId + "|" + JSON.stringify(S.open) + "|" + innerWidth;
    if (S.gsig !== gsig) { S.gsig = gsig; paintGrid(host); }
    paintDetail(host);
  }
  function paint(host, key, sig, build) {
    ensureCSS();
    let S = host._dz;
    if (!S || S.key !== key) { S = host._dz = { key, sel: null, open: {}, cells: new Map(), painted: false, sig: "", gsig: "", dsig: "" }; skeleton(host, "Designs tried"); }
    if (S.sig === sig && host.querySelector(".dz")) { paintBody(host); return; }
    S.sig = sig;
    S.model = build();
    S.model.sig = sig;
    paintBody(host);
  }

  /* ---------- example runs (variants/i1.html) ---------- */
  // ctx: { key, sig, kind: "af" | "file" | "sim", designs, total, ph, done, chosenId, nearIds, passIds (Set),
  //        fails(d) -> [short metric names], rows(d) -> [[label, html]], budget(ch) -> label, mark,
  //        af: { chosenId, bestId, size(d) -> { g, m }, sizeTip, built: { gates, depth, verified } } }
  function exampleHost(anchor) {
    if (!anchor || !anchor.parentNode) return null;
    let host = anchor.parentNode.querySelector(":scope > .dz-host");
    // below the chip and its note, so the 3D chip stays the first thing in view
    const after = anchor.nextElementSibling && anchor.nextElementSibling.classList.contains("vf") ? anchor.nextElementSibling : anchor;
    if (!host) { host = document.createElement("div"); host.className = "dz-host"; anchor.parentNode.insertBefore(host, after.nextSibling); }
    return host;
  }
  function paintExample(anchor, ctx) {
    const host = exampleHost(anchor); if (!host || !ctx) return;
    if (ctx.kind === "af") loadAFWeights(() => { /* the next tick repaints: the weights count is part of the signature */ });
    const wsig = ctx.kind === "af" ? Object.keys(AFW.map).length : 0;
    paint(host, ctx.key, ctx.sig + "|" + wsig, () => ctx.kind === "af" ? buildAF(ctx) : ctx.kind === "file" ? buildFile(ctx) : buildSim(ctx));
  }
  const tipOf = it => [it.id, it.chosen ? (it.pill || "chosen") : it.why || it.stText, it.size ? (it.size.g === 0 ? "0 gates" : (it.size.k === "e" ? "about " : "") + fmt(it.size.g) + " gates" + (it.size.k === "e" ? ", estimated" : it.size.k === "s" ? ", simulated" : "")) : ""].filter(Boolean).join(" · ");
  function finish(it) {
    it.tip = tipOf(it);
    it.gsig = [it.ins, it.layers && it.layers.join(","), it.lev, it.bits, it.chans, it.shared, it.vmark ? 1 : 0, it.size && it.size.g, it.size && it.size.k].join("|");
    it.dsig = [it.plain, it.label, it.c, it.why, it.pill, it.gsig, it.weights ? 1 : 0, it.facts.map(r => r[1]).join("|")].join("|");
    return it;
  }
  function sizeHTML(sz, tip) {
    if (!sz) return "not reported";
    if (sz.g === 0) return "0 gates (constant output)";
    if (sz.k === "e") return `<span class="est" title="${esc(tip || "Estimated, not measured by the chip lab")}">about ${fmt(sz.g)} gates, estimated</span>`;
    return `${fmt(sz.g)} gates, ${sz.k === "s" ? "simulated" : "measured"}`;
  }
  const FEAT = { rr: "beat intervals", drr: "beat-interval differences" };
  function buildAF(ctx) {
    const A = ctx.af, ph = ctx.ph || 0, items = [];
    ctx.designs.forEach(d => {
      const c = d.cfg || {}, sz = A.size(d), isCh = d.id === A.chosenId, isBest = d.id === A.bestId;
      const it = { id: d.id, ins: c.L, layers: [c.H, 1], bits: c.bits, lev: c.weights === "binary" ? 2 : c.weights === "ternary" ? 3 : null, size: { g: sz.g, k: sz.m ? "m" : "e" }, facts: [] };
      it.label = `L${c.L}, ${c.bits}-bit, H${c.H}, ${c.weights}, ${FEAT[c.feature] || c.feature}`;
      if (isCh && ph >= 3) { it.grp = "chosen"; it.c = "s-chosen"; it.chosen = true; it.pill = ph >= 5 ? "Chosen, built, checked" : ph >= 4 ? "Chosen, built" : "Chosen"; }
      else if (isBest && ph >= 2) { it.grp = "slow"; it.c = "s-drop"; it.why = "synthesis too slow"; }
      else if (ph >= 3 && !d.under) { it.grp = "cap"; it.c = "s-drop"; it.why = "over size cap"; }
      else if (ph >= 3) { it.grp = "under"; it.c = "s-score"; it.why = "under cap, not built"; }
      else { it.grp = "scored"; it.c = "s-score"; it.stText = "trained and scored"; }
      it.facts.push(["Shape", `${c.L} inputs, ${c.H} hidden, 1 output`]);
      it.facts.push(["Weights", c.weights === "ternary" ? "ternary (−1, 0, +1)" : c.weights === "binary" ? "binary (±1)" : esc(c.weights)]);
      it.facts.push(["Inputs", `${c.bits}-bit ${esc(FEAT[c.feature] || c.feature)}`]);
      it.facts.push(["Size", sizeHTML(it.size, A.sizeTip)]);
      if (isCh && ph >= 4 && A.built && A.built.depth != null) it.facts.push(["Logic depth", fmt(A.built.depth)]);
      const m = d.metrics || {};
      if (m.f1 != null) it.facts.push(["F1, validation, per window", pct(m.f1)]);
      if (m.sensitivity_window != null) it.facts.push(["Sensitivity, validation, per window", pct(m.sensitivity_window)]);
      if (m.specificity_window != null) it.facts.push(["Specificity, validation, per window", pct(m.specificity_window)]);
      if (isCh && ph >= 5 && A.built && A.built.verified) { const v = A.built.verified; it.facts.push(["Circuit against its model", `${fmt(v.identical != null ? v.identical : v.vectors - v.mismatches)} of ${fmt(v.vectors)} test windows identical`]); }
      const w = AFW.map[d.id];
      if (w) { const x = fromIntnn(w.model); if (x) it.weights = { layers: x.weights, ops: x.ops, src: w.source, srcHTML: w.source_url ? `<a href="${esc(w.source_url)}" target="_blank" rel="noopener">chiplab/fixtures/spike_best.json</a> on the main branch (the spike's saved weights)` : null }; }
      if (!it.weights) it.wnone = "Weights not recorded for this design: only the chosen design's weights were published.";
      items.push(finish(it));
    });
    const order = { chosen: 0, under: 1, scored: 1, slow: 2, cap: 3 };
    items.sort((a, b) => order[a.grp] - order[b.grp] || a.layers[0] - b.layers[0] || a.ins - b.ins || a.bits - b.bits || (a.lev || 0) - (b.lev || 0) || (a.id < b.id ? -1 : 1));
    const S = scaleOf(items);
    return {
      // the chosen design once named, else the one the newest step is about, else the newest arrival
      items, S, defId: A.chosenId && items.some(x => x.id === A.chosenId && x.chosen) ? A.chosenId : ph >= 2 && A.bestId && items.some(x => x.id === A.bestId) ? A.bestId : ctx.designs.length ? ctx.designs[ctx.designs.length - 1].id : null,
      groups: [{ k: "chosen", t: ph >= 4 ? "Chosen and built" : "Chosen", c: "s-chosen" }, { k: "under", t: "Under the size cap, not built", c: "s-score" }, { k: "scored", t: "Trained, validation scored", c: "s-score" }, { k: "slow", t: "Dropped: synthesis too slow", c: "s-drop" }, { k: "cap", t: "Dropped: over the size cap", c: "s-drop" }],
      count: `${fmt(ctx.designs.length)} of ${pl(ctx.total, "candidate")}`, mark: '<span class="mk mea">measured</span>',
      legend: LEGEND(S, { est: true }), empty: "The candidates appear as the search is replayed."
    };
  }
  function buildFile(ctx) {
    const items = [], near = new Set(ctx.nearIds || []), ver = d => d.verified && typeof d.verified === "object";
    ctx.designs.forEach(d => {
      const ch = num(d.channels) || 1, H = num(d.hidden_units), base = d.role === "baseline";
      const it = { id: d.id, chans: ch, size: num(d.gates) != null ? { g: d.gates, k: "m" } : null, facts: [], lev: num(d.weight_levels) };
      // one tiny network of 6 features, shared by the channels; the alarm takes the highest score over channels
      if (!base && H != null) { it.ins = 6; it.layers = H ? [H, 1] : [1]; it.bits = 6; it.shared = ch; }
      const caught = d.counts && num(d.counts.events_caught), tot = d.counts && num(d.counts.events_total);
      if (ver(d)) it.vmark = true;
      if (base) { it.grp = "base"; it.c = "s-base"; it.why = ver(d) ? "baseline, verified" : "baseline, not ours"; }
      else if (d.id === ctx.chosenId) { it.grp = "chosen"; it.c = "s-chosen"; it.chosen = true; if (ver(d)) it.pill = "Chosen, verified"; }
      else if (num(d.gates) === 0) { it.grp = "const"; it.c = "s-drop"; it.why = "constant output"; }
      else if (near.has(d.id)) { it.grp = "best"; it.c = "s-best"; it.why = ver(d) ? "verified, misses bar" : "best, misses bar"; }
      else if (ver(d)) { it.grp = "ver"; it.c = "s-ver"; it.stText = "verified"; }
      else if (caught === 0) { it.grp = "none"; it.c = "s-drop"; it.why = "caught nothing"; }
      else { it.grp = "comp"; it.c = "s-comp"; it.stText = "compiled"; }
      it.label = base ? "line length against a threshold" : `${ctx.budget ? ctx.budget(ch) : pl(ch, "channel")}, ${H ? H + " hidden units" : "one linear unit"}, ${it.lev || "?"}-level weights`;
      if (!base) it.facts.push(["Shape", `6 features, ${H ? H + " hidden" : "no hidden layer"}, 1 output; ${ch === 1 ? "one network on 1 channel" : `one network shared by the ${ch} channels, alarm on the highest score`}`]);
      if (it.lev) it.facts.push(["Weights", `${it.lev} levels`]);
      it.facts.push(["Size", sizeHTML(it.size) + " (classifier only)"]);
      if (num(d.depth) != null) it.facts.push(["Logic depth", fmt(d.depth)]);
      if (caught != null && tot) it.facts.push(["Held-out events caught", `${fmt(caught)} of ${fmt(tot)}, pooled`]);
      if (d.metrics && num(d.metrics.sensitivity_worst) != null) it.facts.push(["Worst held-out baby", pct(d.metrics.sensitivity_worst)]);
      if (d.metrics && num(d.metrics.false_alarms_per_hour) != null) it.facts.push(["False alarms per hour", String(+d.metrics.false_alarms_per_hour.toFixed(3))]);
      if (ver(d)) it.facts.push(["Circuit against its model", `${fmt(d.verified.vectors)} vectors, ${d.verified.mismatches} mismatches${d.verified.proved_equivalent ? ", proved equal" : ""}`]);
      it.wnone = "Weights not recorded in the results file; the shape comes from its configuration.";
      items.push(finish(it));
    });
    const order = { chosen: 0, best: 1, ver: 2, comp: 3, none: 4, const: 5, base: 6 };
    items.sort((a, b) => order[a.grp] - order[b.grp] || (a.chans - b.chans) || ((a.layers ? a.layers[0] : 0) - (b.layers ? b.layers[0] : 0)) || ((a.lev || 0) - (b.lev || 0)) || (a.id < b.id ? -1 : 1));
    const S = scaleOf(items);
    return {
      items, S, defId: ctx.chosenId || (ctx.nearIds || [])[0] || null,
      groups: [{ k: "chosen", t: "Chosen", c: "s-chosen" }, { k: "best", t: "Best so far, misses the bar", c: "s-best" }, { k: "ver", t: "Verified bit for bit", c: "s-ver" }, { k: "comp", t: "Compiled, catch some events", c: "s-comp" }, { k: "none", t: "Dropped: caught nothing", c: "s-drop" }, { k: "const", t: "Dropped: constant output", c: "s-drop" }, { k: "base", t: "Baseline, not ours", c: "s-base" }],
      count: pl(items.filter(x => x.grp !== "base").length, "design") + " compiled", mark: '<span class="mk mea">measured</span>', legend: LEGEND(S, {}) + `<span>${glyph({ ins: 6, layers: [4, 1], lev: 3, bits: 6, shared: 18 }, { maxU: 8, maxG: S.maxG })}stacked: one network shared by the channels</span>` + "<span>darker links: more weight levels</span>" + (items.some(x => x.vmark) ? VDOT : ""), empty: "No designs in the file."
    };
  }
  function buildSim(ctx) {
    const items = [], pass = ctx.passIds || new Set();
    ctx.designs.forEach(d => {
      const ch = num(d.channels) || 1, it = { id: d.id, chans: ch, size: num(d.gates) != null ? { g: d.gates, k: "s" } : null, facts: [] };
      if (d.id === ctx.chosenId) { it.grp = "chosen"; it.c = "s-chosen"; it.chosen = true; it.pill = ctx.done ? "Chosen" : "Smallest so far"; }
      else if (pass.has(d.id)) { it.grp = "pass"; it.c = "s-pass"; it.stText = "clears the bar"; }
      else { const f = ctx.fails ? ctx.fails(d) : []; it.grp = "miss:" + (f.length > 1 ? "2" : f[0] || "?"); it.c = "s-drop"; it.why = f.length > 1 ? "misses " + f.length + " targets" : f[0] ? "misses " + f[0] : "misses the bar"; }
      it.label = (ctx.budget ? ctx.budget(ch) : pl(ch, "channel")) + (d.round ? ", round " + d.round : "");
      it.facts.push(["Shape", `${pl(ch, "channel")} in; inner layout not modelled`]);
      it.facts.push(["Size", sizeHTML(it.size)]);
      if (num(d.depth) != null) it.facts.push(["Logic depth", fmt(d.depth) + ", simulated"]);
      (ctx.rows ? ctx.rows(d) : []).forEach(r => it.facts.push(r));
      it.wnone = "A simulated design: there are no trained weights to show.";
      items.push(finish(it));
    });
    const misses = [...new Set(items.filter(x => /^miss:/.test(x.grp)).map(x => x.grp))].sort((a, b) => (a === "miss:2") - (b === "miss:2") || (a < b ? -1 : 1));
    const order = g => g === "chosen" ? 0 : g === "pass" ? 1 : 2 + misses.indexOf(g);
    items.sort((a, b) => order(a.grp) - order(b.grp) || a.size.g - b.size.g || (a.id < b.id ? -1 : 1));
    const S = scaleOf(items);
    return {
      items, S, defId: ctx.chosenId || (items[0] && items[0].id) || null,
      groups: [{ k: "chosen", t: ctx.done ? "Chosen: smallest that clears every target" : "Smallest so far that clears every target", c: "s-chosen" }, { k: "pass", t: "Clear every target, larger", c: "s-pass" }].concat(misses.map(k => ({ k, t: k === "miss:2" ? "Dropped: misses several targets" : "Dropped: misses " + k.slice(5), c: "s-drop" }))),
      count: `${pl(ctx.designs.length, "design")}${ctx.done ? "" : " so far"}`, mark: '<span class="mk sim">simulated</span>',
      legend: LEGEND(S, { sim: true }) + "<span>inner layout not modelled</span>", empty: "The first designs appear when the first round is checked."
    };
  }

  /* ---------- recorded and live runs (../i1-playback.js, ../i1-live.js) ---------- */
  // ctx: { key, n, f (fold), chosen, ended, T (targets), spec, files: [{ path, text }] or null,
  //        arts: [artifact events reached so far] }
  function paintRun(host, ctx) {
    if (!host || !ctx || !ctx.f) return;
    const F = window.ChipInFold;
    paint(host, ctx.key, [ctx.n, ctx.chosen, ctx.ended ? 1 : 0, ctx.files ? ctx.files.length : 0, (ctx.arts || []).length].join("|"), () => buildRun(ctx, F));
  }
  const SHORT = { sensitivity: "sensitivity", specificity: "specificity", fa_per_hour: "false alarms", accuracy: "accuracy" };
  function buildRun(ctx, F) {
    const f = ctx.f, files = ctx.files || [], arts = ctx.arts || [], T = ctx.T || (F ? F.targetsOf(ctx.spec) : []);
    let recs = F ? F.designs(f) : [];
    // no design records: list the chips the lab measured, but only when there are some
    const chipRecs = recs.length ? [] : Object.keys(f.chips || {}).filter(id => num(f.chips[id].gates) != null).map(id => ({ id, label: "", metrics: {}, gates: null, gates_est: null, depth: num(f.chips[id].depth), verified: null, budget: {} }));
    const fromChips = chipRecs.length > 0;
    if (fromChips) recs = chipRecs;
    const reached = p => ctx.ended || arts.some(a => a && a.path === p);
    const irFile = id => files.find(x => x && typeof x.path === "string" && x.path.endsWith("/chips/" + id + "/ir.json"));
    const irArt = id => arts.find(a => a && typeof a.path === "string" && a.path.endsWith("/chips/" + id + "/ir.json"));
    const items = recs.map(r => {
      const id = r.id, cm = (f.chips && f.chips[id]) || {}, it = { id, facts: [], chans: r.budget && num(r.budget.ch) };
      const gm = num(r.gates) != null ? r.gates : num(cm.gates);
      it.size = gm != null ? { g: gm, k: "m" } : num(r.gates_est) != null ? { g: r.gates_est, k: "e" } : null;
      const ver = (r.verified && typeof r.verified === "object") || cm.verification_level != null || cm.verify_level != null || !!cm.formal_proved;
      // shape and weights: the chip's ir.json once written, else what the note or label says
      const fl = irFile(id); let ir = null;
      if (fl && fl.text && reached(fl.path)) { try { ir = fromIR(JSON.parse(fl.text)); } catch (e) { ir = null; } }
      if (ir) {
        it.ins = ir.ins; it.layers = ir.layers; it.bits = ir.bits; it.lev = levelsOf(ir.weights);
        it.weights = { layers: ir.weights, ops: ir.ops, src: fl.path.replace(/^workspace\//, "") + " in the run's files" };
        if (!r.label && fl.text) { try { const nm = JSON.parse(fl.text).name; it.label = nm && !/^(model|chip|design)$/i.test(nm) ? nm : ""; } catch (e) { /* no name */ } }
      }
      const pw = !ir && (parseWeights(r.note) || parseWeights(r.label));
      const ls = fromLabel(r.label, r.note), bw = bitsOf(r.label, r.note);
      if (!ir) {
        if (pw) { it.ins = pw.W[0].length; it.layers = [1]; it.lev = levelsOf([{ W: pw.W }]); it.weights = { layers: [{ name: "w", W: pw.W, b: pw.b }], names: pw.names, src: pw.how === "rule" && parseWeights(r.label) && !parseWeights(r.note) ? "the design's label (its weighted-sum rule)" : "the design's own note" }; }
        if (ls) { if (it.ins == null && ls.ins != null) it.ins = ls.ins; if (!it.layers && ls.layers) it.layers = ls.layers; }
        if (bw.bits) it.bits = bw.bits;
        it.wbits = bw.wbits;
        if (it.ins != null && !it.layers) it.layers = [1];
        if (it.layers && it.ins == null) it.layers = null;
        if (!it.weights) it.wnone = irArt(id) && !fl ? "Weights are in this chip's ir.json; open it under Files." : "Weights not recorded for this design; the shape comes from its label.";
        if (!it.weights && !it.layers) it.wnone = "Weights and shape not recorded for this design.";
      }
      if (!it.label) it.label = r.label || "";
      // the plain-language name first (ChipInFold.chipName, as the headline and Run summary read it); the working name stays small after it
      { const cn = F && F.chipName ? F.chipName(f, id, { files }) : null; it.plain = cn && (cn.from === "label" || cn.from === "ir") ? cn.name : ""; }
      // state
      const fails = T.filter(t => F && F.meets(t, num(r.metrics && r.metrics[t.metric])) === false).map(t => SHORT[t.metric] || (F ? F.metaOf(t.metric).n.toLowerCase() : t.metric));
      if (ver) it.vmark = true;
      if (id === ctx.chosen) { it.grp = "chosen"; it.c = "s-chosen"; it.chosen = true; it.pill = ver ? "Chosen, verified" : "Chosen"; }
      else if (fails.length) { it.grp = "miss:" + (fails.length > 1 ? "2" : fails[0]); it.c = "s-drop"; it.why = (ver ? "verified, " : "") + (fails.length > 1 ? "misses " + fails.length + " targets" : "misses " + fails[0]); }
      else if (ver) { it.grp = "ver"; it.c = "s-ver"; it.stText = "verified"; }
      else if (gm != null) { it.grp = "comp"; it.c = "s-comp"; it.stText = gm === 0 ? "compiled, 0 gates" : "compiled"; }
      else { it.grp = "score"; it.c = "s-score"; it.stText = "scored, not compiled"; }
      // key numbers
      if (it.ins != null && it.layers) it.facts.push(["Shape", `${pl(it.ins, "input")}${it.layers.length > 1 ? ", " + it.layers.slice(0, -1).join(" then ") + " hidden" : ""}, ${it.layers[it.layers.length - 1] === 1 ? "1 output" : it.layers[it.layers.length - 1] + " outputs"}`]);
      if (it.bits) it.facts.push(["Inputs", `${it.bits}-bit`]);
      if (it.wbits) it.facts.push(["Weights", `${it.wbits}-bit`]);
      if (r.budget && r.budget.name) it.facts.push(["Budget", esc(r.budget.name)]);
      it.facts.push(["Size", it.size ? (it.size.k === "e" ? sizeHTML(it.size, "Estimated by the agent; the chip lab has not measured it") : it.size.g === 0 ? "0 gates, measured by the lab" : `${fmt(it.size.g)} gates, measured by the lab`) : "not reported"]);
      const dep = num(r.depth) != null ? r.depth : num(cm.depth); if (dep != null) it.facts.push(["Logic depth", fmt(dep)]);
      const bn = r.basis === "validation" ? ", validation" : r.basis === "test" ? ", held-out" : "";
      // a one-off screening run with no false-alarm target shows no false-alarm rows (as the Chip view and chart)
      const noFA = F ? F.screenOnly(ctx.spec, T) : false;
      Object.keys(r.metrics || {}).filter(k => num(r.metrics[k]) != null && ["sensitivity", "specificity", "fa_per_hour"].indexOf(k) >= 0 && !(noFA && k === "fa_per_hour")).forEach(k => {
        const t = T.find(x => x.metric === k), v = r.metrics[k];
        it.facts.push([(F ? F.metaOf(k).n : k) + bn, esc(F ? F.fmtV(k, v, ctx.spec) : v) + (t ? (F.meets(t, v) ? ' <span class="pf ok">Pass</span>' : ' <span class="pf no">Fail</span>') : "")]);
      });
      if (r.verified && typeof r.verified === "object") it.facts.push(["Circuit against its model", `${num(r.verified.vectors) != null ? fmt(r.verified.vectors) + " vectors, " : ""}${num(r.verified.mismatches) != null ? r.verified.mismatches + " mismatches" : ""}${r.verified.proved ? ", proved" : ""}`]);
      if (r.data) it.facts.push(["Data", esc(r.data)]);
      return finish(it);
    });
    const misses = [...new Set(items.filter(x => /^miss:/.test(x.grp)).map(x => x.grp))].sort((a, b) => (a === "miss:2") - (b === "miss:2") || (a < b ? -1 : 1));
    const order = g => ({ chosen: 0, ver: 1, comp: 2, score: 3 }[g] != null ? { chosen: 0, ver: 1, comp: 2, score: 3 }[g] : 4 + misses.indexOf(g));
    const pos = {}; recs.forEach((r, i) => { pos[r.id] = i; });
    items.sort((a, b) => order(a.grp) - order(b.grp) || pos[a.id] - pos[b.id]);
    const S = scaleOf(items), last = recs.length ? recs[recs.length - 1].id : null;
    return {
      items, S, defId: ctx.chosen && items.some(x => x.id === ctx.chosen) ? ctx.chosen : last,
      groups: [{ k: "chosen", t: "Chosen", c: "s-chosen" }, { k: "ver", t: "Verified", c: "s-ver" }, { k: "comp", t: "Compiled by the lab", c: "s-comp" }, { k: "score", t: "Scored, size estimated", c: "s-score" }].concat(misses.map(k => ({ k, t: k === "miss:2" ? "Misses several targets" : "Misses " + k.slice(5), c: "s-drop" }))),
      count: !items.length ? (ctx.ended ? "No designs reported" : "No designs yet") : pl(items.length, fromChips ? "chip" : "design") + (ctx.ended ? "" : " so far") + (fromChips ? ", from the lab's figures" : ""), mark: '<span class="mk mea">recorded</span>',
      legend: LEGEND(S, { est: items.some(x => x.size && x.size.k === "e") }) + (items.some(x => x.vmark) ? VDOT.replace("verified bit for bit", "verified") : ""), empty: ctx.ended ? "This run reported no designs." : "Designs appear as the agent reports them."
    };
  }

  window.ChipInDesigns = { paintExample, paintRun, parseWeights, fromIR, fromIntnn };
})();
