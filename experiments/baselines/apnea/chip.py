"""Build, check and measure the chosen designs with the team's chip lab (used as a tool, never edited).

For every design in designs/: the minute classifier and the night core (minute classifier + counter
next-state logic + AHI compare) go through compile, generic synthesis, bit-exact simulation on the test
records' actual inputs, formal equivalence (with the independent golden model) and standard-cell mapping on
the three open process kits. The night core is then wrapped with its two 10-bit state registers
(seq/night_wrapper.v) and that clocked design is synthesised and mapped with the lab's own library
functions, proved by the lab's sequential equivalence check, and simulated night by night with Icarus.

Lab location comes from the environment: CHIPLAB_BIN (the chiplab executable), CHIPLAB_PY (the lab's
Python), plus the lab's own CHIPLAB_USER_DIR, CHIPLAB_CONFIG and CHIPLAB_HOME.
Run with: python -I chip.py <features .npz> <designs dir> <work dir> <out json> [design tags...]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

import importlib.util

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("apnea_models", HERE / "models.py")
_models = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_models)
CNT_BITS, N_LEARN = _models.CNT_BITS, _models.N_LEARN
int_inputs, int_predict, load = _models.int_inputs, _models.int_predict, _models.load

PDKS = ("sky130", "gf180", "ihp")
CAP = 900  # seconds per lab call
WHOLE_PROOF_MAX_GATES = 300  # the lab documents the flattened sequential proof as practical for a few hundred gates


def lab(tool: str, args: dict, work: Path, cap: int = CAP) -> dict:
    f = work / f"req_{tool}_{abs(hash(json.dumps(args, sort_keys=True, default=str))) % 10**8}.json"
    f.write_text(json.dumps(args))
    try:
        p = subprocess.run([os.environ["CHIPLAB_BIN"], tool, "--json-file", str(f)], capture_output=True,
                           text=True, timeout=cap, start_new_session=True)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "tool": tool}
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "stdout": p.stdout[-800:], "stderr": p.stderr[-800:]}


def labpy(code: str, work: Path, cap: int = CAP) -> dict:
    try:
        p = subprocess.run([os.environ["CHIPLAB_PY"], "-I", "-c", code], capture_output=True, text=True,
                           timeout=cap, cwd=work, start_new_session=True)
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"status": "error", "stdout": p.stdout[-800:], "stderr": p.stderr[-1500:]}


def night_trace(m: dict, X: np.ndarray, rec: np.ndarray, recs: list[int]) -> dict:
    """Inputs and expected outputs of the night core for every test minute, in time order per night."""
    Q = int_inputs(m, X)
    y = int_predict(m, X)
    cmax = 2 ** CNT_BITS - 1
    xs, ns, ls, ys, n1s, l1s = [], [], [], [], [], []
    for r in recs:
        n = l_ = 0
        for i in np.where(rec == r)[0]:
            xs.append(Q[i].tolist()); ns.append([n]); ls.append([l_])
            n = min(n + int(y[i]), cmax); l_ = min(l_ + 1, cmax)
            ys.append(int(y[i])); n1s.append(n); l1s.append(l_)
    return {"x": xs, "n": ns, "l": ls, "y": ys, "n1": n1s, "l1": l1s}


def wrapper_verilog(core_top: str, x_bits: int) -> str:
    return f"""// Night accumulator: the lab-generated core {core_top} plus two {CNT_BITS}-bit state registers.
module apnea_night (
  input wire clk,
  input wire rst_n,
  input wire start,
  input wire valid,
  input wire [{x_bits - 1}:0] x,
  output reg y,
  output reg osa,
  output wire [{CNT_BITS - 1}:0] n_q,
  output wire [{CNT_BITS - 1}:0] l_q
);
  reg [{CNT_BITS - 1}:0] n_r;
  reg [{CNT_BITS - 1}:0] l_r;
  wire [0:0] y_c;
  wire [0:0] osa_c;
  wire [{CNT_BITS - 1}:0] n_c;
  wire [{CNT_BITS - 1}:0] l_c;
  {core_top} core (.x(x), .n(n_r), .l(l_r), .y(y_c), .n_next(n_c), .l_next(l_c), .osa(osa_c));
  always @(posedge clk) begin
    if (!rst_n || start) begin
      n_r <= {CNT_BITS}'d0; l_r <= {CNT_BITS}'d0; y <= 1'b0; osa <= 1'b0;
    end else if (valid) begin
      n_r <= n_c; l_r <= l_c; y <= y_c[0]; osa <= osa_c[0];
    end
  end
  assign n_q = n_r;
  assign l_q = l_r;
endmodule
"""


def testbench(x_bits: int, n_words: int) -> str:
    return f"""`timescale 1ns/1ps
module tb;
  reg clk = 0, rst_n = 0, start = 0, valid = 0;
  reg [{x_bits - 1}:0] x = 0;
  wire y, osa;
  wire [{CNT_BITS - 1}:0] n_q, l_q;
  reg [{x_bits + 1}:0] mem [0:{n_words - 1}];
  integer i, fd;
  apnea_night dut (.clk(clk), .rst_n(rst_n), .start(start), .valid(valid), .x(x), .y(y), .osa(osa), .n_q(n_q), .l_q(l_q));
  always #5 clk = ~clk;
  initial begin
    $readmemh("stim.hex", mem);
    fd = $fopen("trace.txt", "w");
    @(negedge clk); rst_n = 1;
    for (i = 0; i < {n_words}; i = i + 1) begin
      if (mem[i][{x_bits + 1}]) begin
        start = 1; valid = 0; @(negedge clk); start = 0;
      end
      x = mem[i][{x_bits - 1}:0]; valid = 1; @(negedge clk); valid = 0;
      $fdisplay(fd, "%0d %0d %0d %0d %0d", i, y, n_q, l_q, osa);
    end
    $fclose(fd);
    $finish;
  end
endmodule
"""


def main() -> None:
    npz, ddir, work, outp = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    work.mkdir(parents=True, exist_ok=True)
    res = json.loads((ddir / "designs.json").read_text())
    d = load(npz)
    X, rec = d["X"], d["rec"]
    test = list(range(N_LEARN, 2 * N_LEARN))
    sel = np.isin(rec, test)
    tags = sys.argv[5:] or [t for t in res["designs"] if t.startswith("D")]
    out = json.loads(outp.read_text()) if outp.exists() else {}
    for tag in tags:
        m = res["designs"][tag]["model"]
        k = res["designs"][tag]["night_k"]
        rep: dict = {"night_k": k}
        Qt = int_inputs(m, X[sel])
        yt = int_predict(m, X[sel])
        for part, irf in (("minute", ddir / f"{tag}.chipir.json"), ("night_core", ddir / f"{tag}_night.chipir.json")):
            ir = json.loads(irf.read_text())
            r: dict = {}
            c = lab("ingest-model", {"format": "chipir", "model": ir, "name": ir["name"]}, work)
            did = c.get("design_id")
            r["design_id"], r["lint_ok"] = did, (c.get("lint") or {}).get("ok")
            if not did:
                r["error"] = c
                rep[part] = r
                continue
            s = lab("synthesize", {"design_id": did}, work)
            r["synth"] = {"status": s.get("status"), **(s.get("metrics") or {}), "cells_by_type": s.get("cells_by_type"),
                          "tool": s.get("tool")}
            if part == "minute":
                vec = {"x": Qt.tolist()}
                exp = yt.tolist()
            else:
                tr = night_trace(m, X, rec, test)
                vec = {"x": tr["x"], "n": tr["n"], "l": tr["l"]}
                exp = tr["y"]
            sim = lab("simulate", {"design_id": did, "inputs": "vectors", "vectors": vec, "expected": exp,
                                   "device": "numpy"}, work)
            r["simulate_test_vectors"] = {k2: sim.get(k2) for k2 in sim if k2 not in ("cost",)}
            pe = lab("prove-equivalence", {"design_id": did, "golden": True, "timeout": 600}, work)
            r["prove_equivalence"] = {k2: pe.get(k2) for k2 in pe if k2 not in ("cost", "log")}
            r["map"] = {}
            for p in PDKS:
                mp = lab("map-to-process", {"design_id": did, "pdk": p}, work)
                mm = mp.get("metrics") or {}
                r["map"][p] = {"status": mp.get("status"), "library": mp.get("library"), "note": mp.get("note"),
                               **{k2: mm.get(k2) for k2 in ("area_um2", "gate_equivalents", "std_cells", "tt_tiles_est")}}
            vl = lab("verification-level", {"design_id": did}, work)
            r["verification_level"] = vl.get("level", vl.get("verification_level"))
            rep[part] = r
            print(tag, part, did, r["synth"].get("gates"), r["synth"].get("depth"), flush=True)
        # clocked night design
        nc = rep.get("night_core", {})
        if nc.get("design_id"):
            did = nc["design_id"]
            sw = work / f"seq_{tag}"
            sw.mkdir(exist_ok=True)
            core_v = Path(os.environ["CHIPLAB_HOME"]) / "designs" / did / "design.v"
            core_top = "chip_" + did
            x_bits = len(m["feats"]) * m["fbits"]
            (sw / "core.v").write_text(core_v.read_text())
            (sw / "wrapper.v").write_text(wrapper_verilog(core_top, x_bits))
            (sw / "night_full.v").write_text(core_v.read_text() + "\n" + wrapper_verilog(core_top, x_bits))
            code = (
                "import json; from pathlib import Path\n"
                "from chiplab.hw.yosys import synth_generic\n"
                "from chiplab.hw.pdk import map_to_process\n"
                "from chiplab.verify.eqy import prove_sequential\n"
                f"w = Path({str(sw)!r}); out = {{}}\n"
                "g = synth_generic(w / 'night_full.v', 'apnea_night', w / 'gen')\n"
                "out['generic'] = {k: g[k] for k in ('gates', 'depth', 'transistors_est', 'cells_by_type')}\n"
                "for p in ('sky130', 'gf180', 'ihp'):\n"
                "    (w / p).mkdir(exist_ok=True)\n"
                "    mp = map_to_process(w / 'night_full.v', 'apnea_night', w / p, pdk=p)\n"
                "    out[p] = {k: mp.get(k) for k in ('area_um2', 'gate_equivalents', 'std_cells', 'tt_tiles_est', 'cells_by_type')}\n"
                f"ps = prove_sequential([w / 'core.v', w / 'wrapper.v'], 'apnea_night', w / 'eqy_bb', blackbox=[{core_top!r}], blackbox_sources=[w / 'core.v'], timeout=600)\n"
                "out['prove_sequential_compositional'] = {k: ps.get(k) for k in ('proved', 'method', 'scope', 'depth', 'seconds', 'error')}\n"
                + ("pw = prove_sequential([w / 'night_full.v'], 'apnea_night', w / 'eqy_whole', timeout=600)\n"
                   "out['prove_sequential_whole'] = {k: pw.get(k) for k in ('proved', 'method', 'scope', 'depth', 'seconds', 'error')}\n"
                   if (nc.get("synth") or {}).get("gates", 10 ** 9) <= WHOLE_PROOF_MAX_GATES else
                   "out['prove_sequential_whole'] = {'proved': None, 'error': 'not run: core above the size where the whole-design proof is practical'}\n")
                + "print(json.dumps(out))\n")
            rep["night_clocked"] = labpy(code, sw, cap=2400)
            # Icarus simulation of the clocked design over every test night
            tr = night_trace(m, X, rec, test)
            words, starts, prev = [], [], None
            fb = m["fbits"]
            recs_t = rec[sel]
            for i, xv in enumerate(tr["x"]):
                word = 0
                for j, v in enumerate(xv):
                    word |= int(v) << (j * fb)
                st = int(recs_t[i] != prev)
                prev = recs_t[i]
                words.append(word | (st << (x_bits + 1)))
                starts.append(st)
            (sw / "stim.hex").write_text("\n".join(f"{w_:x}" for w_ in words) + "\n")
            (sw / "tb.v").write_text(testbench(x_bits, len(words)))
            oss = Path(os.environ["CHIPLAB_OSS_BIN"])
            try:
                subprocess.run([str(oss / "iverilog"), "-g2005", "-o", "sim.vvp", "tb.v", "night_full.v"], cwd=sw,
                               check=True, capture_output=True, timeout=300, start_new_session=True)
                subprocess.run([str(oss / "vvp"), "-n", "sim.vvp"], cwd=sw, check=True, capture_output=True,
                               timeout=1200, start_new_session=True)
                rows = np.loadtxt(sw / "trace.txt", dtype=np.int64)
                ok_y = bool((rows[:, 1] == np.array(tr["y"])).all())
                ok_n = bool((rows[:, 2] == np.array(tr["n1"])).all() and (rows[:, 3] == np.array(tr["l1"])).all())
                ends = [i - 1 for i in range(1, len(starts)) if starts[i]] + [len(starts) - 1]
                osa_hw = [int(rows[e, 4]) for e in ends]
                osa_model = [int(k * tr["n1"][e] >= tr["l1"][e]) for e in ends]
                rep["night_clocked_sim"] = {"tool": "Icarus Verilog (lab oss-cad-suite)", "minutes": len(words),
                                            "nights": len(ends), "minute_outputs_match": ok_y,
                                            "counters_match": ok_n, "night_decisions_match": osa_hw == osa_model,
                                            "osa_positive_nights_hw": int(sum(osa_hw))}
            except (subprocess.SubprocessError, OSError, ValueError) as e:
                rep["night_clocked_sim"] = {"error": str(e)[-500:]}
        out[tag] = rep
        outp.write_text(json.dumps(out, indent=1, default=str))
        print(tag, "done", flush=True)


if __name__ == "__main__":
    main()
