"""Aim 1: the AF detector as a clocked circuit, one RR interval per clock enable.

Combinational next-state core (chipir/1, compiled and proved by the chip lab):
    inputs  x (new interval, 8 bit), h (last L intervals), c (one counter per feature), p (position in the
            segment) and, when a running-mean count is used, m (12-bit mean register)
    outputs af (decision, 1 on the last interval of a segment when the rule fires), done (last interval),
            h_next, c_next, p_next (and m_next)
A Verilog wrapper holds the state registers. Checks: lab simulate (core, real state trajectories), lab
prove-equivalence with the golden model (core), the lab's prove_sequential (wrapper, core black-boxed; and the
flattened design), and Icarus over every record, compared with an independent step model (seqfeat.GoldenStep)
and with the segment-level integer model (fit.predict on seqfeat.segment_features).

Usage: python -I -m afr2.seqchip --design NAME --model-json FILE[:key] --out DIR --data DATA_ROOT
       [--dbs afdb ltafdb] [--layout]
Env: CHIPLAB_BIN_DIR (chiplab bin dir), CHIPLAB_HOME, CHIPLAB_USER_DIR, CHIPLAB_CONFIG, CHIPLAB_OSS_BIN.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import numpy as np

from afchip.chip_run import call
from afchip.run_eval import load_db
from afr2.fit import predict, rule_from_counts, used
from afr2.seqfeat import GoldenStep, history_needed, lag_of, segment_features

PDKS = ("sky130", "gf180", "ihp")
MEAN_BITS = 12


def _bits(v: int) -> int:
    return max(int(v).bit_length(), 1)


def build_core_ir(model: dict, n: int, name: str) -> dict:
    feats = used(model)
    nf = len(feats)
    L = max(history_needed(feats), 1)
    cb = _bits(n - 1)
    dev = any(f.startswith("dev_") for f in feats)
    inputs = [{"name": "x", "lanes": 1, "bits": 8, "signed": False},
              {"name": "h", "lanes": L, "bits": 8, "signed": False},
              {"name": "c", "lanes": nf, "bits": cb, "signed": False},
              {"name": "p", "lanes": 1, "bits": cb, "signed": False}]
    if dev:
        inputs.append({"name": "m", "lanes": 1, "bits": MEAN_BITS, "signed": False})
    nodes: list[dict] = []
    have: set[str] = set()

    def add(node: dict) -> str:
        if node["id"] not in have:
            nodes.append(node)
            have.add(node["id"])
        return node["id"]

    def tap(lag: int) -> str:
        return add({"id": f"h{lag}", "op": "gather", "src": "h", "idx": [lag - 1]})

    def absdiff(lag: int) -> str:  # |x - r_(i-lag)|
        add({"id": f"e{lag}", "op": "sub", "a": "x", "b": tap(lag)})
        return add({"id": f"ae{lag}", "op": "abs", "src": f"e{lag}"})

    def x16() -> str:
        return add({"id": "x16", "op": "matvec", "src": "x", "W": [[16]]})

    bits = []
    for f in feats:
        if f.startswith("rel"):
            lag, k = (int(v) for v in f[3:].split("_"))
            add({"id": f"s{lag}_{k}", "op": "shift", "src": tap(lag), "k": k})
            bits.append(add({"id": f"b_{f}", "op": "cmp", "src": absdiff(lag), "rel": "gt", "other": f"s{lag}_{k}"}))
        elif f.startswith("abs_"):
            bits.append(add({"id": f"b_{f}", "op": "cmp", "src": absdiff(1), "rel": "gt", "t": int(f[4:])}))
        elif f == "tp":
            add({"id": "dp", "op": "sub", "a": tap(1), "b": tap(2)})
            add({"id": "dn", "op": "sub", "a": "x", "b": tap(1)})
            add({"id": "dp_pos", "op": "cmp", "src": "dp", "rel": "gt", "t": 0})
            add({"id": "dp_neg", "op": "cmp", "src": "dp", "rel": "lt", "t": 0})
            add({"id": "dn_pos", "op": "cmp", "src": "dn", "rel": "gt", "t": 0})
            add({"id": "dn_neg", "op": "cmp", "src": "dn", "rel": "lt", "t": 0})
            add({"id": "tp4", "op": "concat", "srcs": ["dp_pos", "dp_neg", "dn_pos", "dn_neg"]})
            table = [int(((c & 1) and (c >> 3) & 1) or ((c >> 1) & 1 and (c >> 2) & 1)) for c in range(16)]
            bits.append(add({"id": "b_tp", "op": "lut", "src": "tp4", "inputs": [[0, 1, 2, 3]], "tables": [table]}))
        elif f.startswith("run_"):
            k = int(f[4:])
            add({"id": f"sn{k}", "op": "shift", "src": tap(1), "k": k})
            add({"id": f"bn{k}", "op": "cmp", "src": absdiff(1), "rel": "gt", "other": f"sn{k}"})
            add({"id": "ep", "op": "sub", "a": tap(1), "b": tap(2)})
            add({"id": "aep", "op": "abs", "src": "ep"})
            add({"id": f"sp{k}", "op": "shift", "src": tap(2), "k": k})
            add({"id": f"bp{k}", "op": "cmp", "src": "aep", "rel": "gt", "other": f"sp{k}"})
            add({"id": f"bb{k}", "op": "concat", "srcs": [f"bp{k}", f"bn{k}"]})
            bits.append(add({"id": f"b_{f}", "op": "lut", "src": f"bb{k}", "inputs": [[0, 1]], "tables": [[0, 0, 0, 1]]}))
        elif f.startswith("dev_"):
            k = int(f[4:])
            add({"id": "dm", "op": "sub", "a": x16(), "b": "m"})
            add({"id": "adm", "op": "abs", "src": "dm"})
            add({"id": f"sm{k}", "op": "shift", "src": "m", "k": k})
            bits.append(add({"id": f"b_{f}", "op": "cmp", "src": "adm", "rel": "gt", "other": f"sm{k}"}))
        else:
            raise ValueError(f)
    add({"id": "B", "op": "concat", "srcs": bits})
    add({"id": "pF", "op": "gather", "src": "p", "idx": [0] * nf})
    add({"id": "V", "op": "cmp", "src": "pF", "rel": "ge", "t": [lag_of(f) for f in feats]})
    add({"id": "BV", "op": "concat", "srcs": ["B", "V"]})
    add({"id": "G", "op": "lut", "src": "BV", "inputs": [[j, nf + j] for j in range(nf)], "tables": [[0, 0, 0, 1]] * nf})
    add({"id": "cnt", "op": "add", "a": "c", "b": "G"})
    add({"id": "done", "op": "cmp", "src": "p", "rel": "eq", "t": n - 1})
    add({"id": "kdone", "op": "matvec", "src": "done", "W": [[1 << cb]]})
    add({"id": "cr", "op": "sub", "a": "cnt", "b": "kdone"})
    add({"id": "c_next", "op": "clip", "src": "cr", "lo": 0, "hi": n - 1})
    add({"id": "pd", "op": "concat", "srcs": ["p", "done"]})
    add({"id": "p1", "op": "matvec", "src": "pd", "W": [[1, -n]], "b": [1]})
    add({"id": "p_next", "op": "clip", "src": "p1", "lo": 0, "hi": n - 1})
    if L > 1:
        add({"id": "hs", "op": "gather", "src": "h", "idx": list(range(L - 1))})
        add({"id": "h_next", "op": "concat", "srcs": ["x", "hs"]})
    else:
        add({"id": "h_next", "op": "concat", "srcs": ["x"]})
    col = {f: j for j, f in enumerate(feats)}
    k = model["kind"]
    if k == "thr1":
        add({"id": "c0", "op": "gather", "src": "cnt", "idx": [col[model["feats"][0]]]})
        add({"id": "r", "op": "cmp", "src": "c0", "rel": "ge", "t": model["t"][0]})
    elif k in ("and2", "or2"):
        add({"id": "c01", "op": "gather", "src": "cnt", "idx": [col[f] for f in model["feats"]]})
        add({"id": "ge2", "op": "cmp", "src": "c01", "rel": "ge", "t": list(model["t"])})
        add({"id": "r", "op": "lut", "src": "ge2", "inputs": [[0, 1]],
             "tables": [[0, 0, 0, 1] if k == "and2" else [0, 1, 1, 1]]})
    elif k.startswith("lin"):
        add({"id": "score", "op": "matvec", "src": "cnt", "W": [[int(w) for w in model["w"]]]})
        add({"id": "r", "op": "cmp", "src": "score", "rel": "ge", "t": int(model["t"])})
    elif k.startswith("tree"):
        add({"id": "cs", "op": "gather", "src": "cnt", "idx": [col[f] for f in model["node_feat"]]})
        add({"id": "gt", "op": "cmp", "src": "cs", "rel": "gt", "t": list(model["node_thr"])})
        add({"id": "r", "op": "lut", "src": "gt", "inputs": [list(range(len(model["node_feat"])))],
             "tables": [list(model["table"])]})
    else:
        raise ValueError(k)
    add({"id": "rd", "op": "concat", "srcs": ["r", "done"]})
    add({"id": "af", "op": "lut", "src": "rd", "inputs": [[0, 1]], "tables": [[0, 0, 0, 1]]})
    outputs = [{"name": "af", "src": "af"}, {"name": "done", "src": "done"}, {"name": "h_next", "src": "h_next"},
               {"name": "c_next", "src": "c_next"}, {"name": "p_next", "src": "p_next"}]
    if dev:
        add({"id": "dm3", "op": "shift", "src": "dm", "k": 3})
        add({"id": "upd", "op": "add", "a": "m", "b": "dm3"})
        add({"id": "updc", "op": "clip", "src": "upd", "lo": 0, "hi": (1 << MEAN_BITS) - 1})
        add({"id": "st", "op": "cmp", "src": "p", "rel": "eq", "t": 0})
        add({"id": "nst", "op": "cmp", "src": "p", "rel": "ne", "t": 0})
        add({"id": "kst", "op": "matvec", "src": "st", "W": [[1 << (MEAN_BITS + 1)]]})
        add({"id": "knst", "op": "matvec", "src": "nst", "W": [[1 << (MEAN_BITS + 1)]]})
        add({"id": "ma0", "op": "sub", "a": "updc", "b": "kst"})
        add({"id": "ma", "op": "clip", "src": "ma0", "lo": 0, "hi": (1 << MEAN_BITS) - 1})
        add({"id": "mb0", "op": "sub", "a": "x16", "b": "knst"})
        add({"id": "mb", "op": "clip", "src": "mb0", "lo": 0, "hi": (1 << MEAN_BITS) - 1})
        add({"id": "m_next", "op": "add", "a": "ma", "b": "mb"})
        outputs.append({"name": "m_next", "src": "m_next"})
    return {"ir": "chipir/1", "name": name, "inputs": inputs, "nodes": nodes, "outputs": outputs,
            "meta": {"family": k, "window": n, "features": feats, "kind": "clocked next-state core"}}


def golden_record(model: dict, n: int, rr: np.ndarray, dev: bool) -> dict:
    """Step the independent model through one record. Returns per-step core inputs and af, and per-segment
    (af, counts before the last interval)."""
    feats = used(model)
    g = GoldenStep(names=feats, n=n, rule=lambda c: rule_from_counts(model, c))
    L = max(history_needed(feats), 1)
    xs, hs, cs, ps, ms, afs, seg_af, seg_c = [], [], [], [], [], [], [], []
    for x in rr.tolist():
        xs.append([x]); hs.append(list(g.h[:L])); cs.append(list(g.c)); ps.append([g.p]); ms.append([g.m])
        af, done, before = g.step(int(x))
        afs.append(af)
        if done:
            seg_af.append(af); seg_c.append(before)
    out = {"x": xs, "h": hs, "c": cs, "p": ps, "af": afs, "seg_af": seg_af, "seg_c": seg_c}
    if dev:
        out["m"] = ms
    return out


def wrapper_verilog(core_top: str, ports: dict, top: str) -> str:
    w = {p["name"]: p["lanes"] * p["bits"] for p in ports["inputs"]}
    o = {p["name"]: p["lanes"] * p["bits"] for p in ports["outputs"]}
    for s in ("h", "c", "p") + (("m",) if "m" in w else ()):
        if o[f"{s}_next"] != w[s]:
            raise ValueError(f"state {s}: next-state width {o[s + '_next']} != register width {w[s]}")
    st = ["h", "c", "p"] + (["m"] if "m" in w else [])
    regs = "\n".join(f"  reg [{w[s] - 1}:0] {s}_r;\n  wire [{w[s] - 1}:0] {s}_c;" for s in st)
    conn = ", ".join([".x(rr)"] + [f".{s}({s}_r)" for s in st] + [".af(af_c)", ".done(done_c)"]
                     + [f".{s}_next({s}_c)" for s in st])
    rst = " ".join(f"{s}_r <= {w[s]}'d0;" for s in st)
    upd = " ".join(f"{s}_r <= {s}_c;" for s in st)
    return f"""// Clocked AF detector: lab-generated next-state core {core_top} plus the state registers.
module {top} (
  input wire clk,
  input wire rst_n,
  input wire start,
  input wire valid,
  input wire [7:0] rr,
  output reg af,
  output reg done
);
{regs}
  wire [0:0] af_c;
  wire [0:0] done_c;
  {core_top} core ({conn});
  always @(posedge clk) begin
    if (!rst_n || start) begin
      {rst} af <= 1'b0; done <= 1'b0;
    end else if (valid) begin
      {upd} af <= af_c[0]; done <= done_c[0];
    end
  end
endmodule
"""


def testbench(top: str, cw: int) -> str:
    return f"""`timescale 1ns/1ps
module tb;
  reg clk = 0, rst_n = 0, start = 0, valid = 0;
  reg [7:0] rr = 0;
  reg [8:0] w;
  reg [{cw - 1}:0] csnap;
  wire af, done;
  integer fi, fo, r;
  {top} dut (.clk(clk), .rst_n(rst_n), .start(start), .valid(valid), .rr(rr), .af(af), .done(done));
  always #5 clk = ~clk;
  initial begin
    fi = $fopen("stim.hex", "r");
    fo = $fopen("trace.txt", "w");
    @(negedge clk); rst_n = 1;
    while (!$feof(fi)) begin
      r = $fscanf(fi, "%h\\n", w);
      if (r == 1) begin
        if (w[8]) begin start = 1; valid = 0; @(negedge clk); start = 0; end
        rr = w[7:0]; valid = 1; csnap = dut.c_r;
        @(negedge clk); valid = 0;
        if (done) $fdisplay(fo, "%0d %h", af, csnap);
      end
    end
    $fclose(fo);
    $finish;
  end
endmodule
"""


def _reap(pgid: int) -> None:
    """Kill anything left in a finished child's process group (solver children of a timed-out inner call)."""
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def labpy(code: str, wd: Path, timeout: int) -> dict:
    """Run code with the lab's own Python in its own process group; kill the whole group on timeout."""
    py = Path(os.environ["CHIPLAB_BIN_DIR"]) / "python"
    p = subprocess.Popen([str(py), "-I", "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         cwd=str(wd), start_new_session=True)
    try:
        so, se = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        return {"status": "timeout", "seconds": timeout}
    _reap(p.pid)
    try:
        return json.loads(so.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"status": "error", "stdout": so[-1500:], "stderr": se[-3000:]}


def run_proc(cmd: list[str], cwd: Path, timeout: int) -> tuple[int | None, str]:
    p = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         start_new_session=True)
    try:
        so, _ = p.communicate(timeout=timeout)
        _reap(p.pid)
        return p.returncode, so[-3000:]
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        return None, f"timeout after {timeout}s"


def icarus_db(name: str, recs: list, model: dict, n: int, dev: bool, sw: Path, top: str, srcs: list[str],
              cw: int, cb: int, nf: int, tag: str) -> dict:
    """One Icarus run over every record of a database; compare every segment with the step model and the
    segment-level integer model."""
    t0 = time.time()
    words, g_af, g_c, seg_pred = [], [], [], []
    feats = used(model)
    for r in recs:
        rr = r.rr.astype(np.int64)
        gr = golden_record(model, n, rr, dev)
        g_af += gr["seg_af"]; g_c += gr["seg_c"]
        mseg = len(rr) // n
        if mseg:
            Xs = rr[: mseg * n].reshape(mseg, n)
            seg_pred += predict(segment_features(Xs, feats), model, feats).tolist()
        for i, x in enumerate(rr.tolist()):
            words.append(f"{(int(i == 0) << 8) | int(x):x}")
    t_model = time.time() - t0
    rd = sw / f"icarus_{tag}_{name}"
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "stim.hex").write_text("\n".join(words) + "\n")
    (rd / "tb.v").write_text(testbench(top, cw))
    oss = Path(os.environ["CHIPLAB_OSS_BIN"])
    rc, log = run_proc([str(oss / "iverilog"), "-g2005", "-o", "sim.vvp", "tb.v"] + srcs, rd, 600)
    if rc != 0:
        return {"error": "iverilog: " + log}
    t1 = time.time()
    rc, log = run_proc([str(oss / "vvp"), "-n", "sim.vvp"], rd, 7200)
    if rc != 0:
        return {"error": "vvp: " + log}
    rows = (rd / "trace.txt").read_text().split()
    hw_af = [int(v) for v in rows[0::2]]
    hw_c = []
    for hx in rows[1::2]:
        v = int(hx, 16)
        hw_c.append([(v >> (j * cb)) & ((1 << cb) - 1) for j in range(nf)])
    (rd / "stim.hex").unlink()
    (rd / "trace.txt").unlink()
    ga, sp = np.asarray(g_af), np.asarray(seg_pred)
    res = {"records": len(recs), "intervals": len(words), "segments_hw": len(hw_af), "segments_model": len(g_af),
           "af_segments_hw": int(sum(hw_af)),
           "hw_vs_step_model_af_mismatches": int((np.asarray(hw_af) != ga).sum()) if len(hw_af) == len(ga) else None,
           "hw_vs_step_model_counter_mismatches": int((np.asarray(hw_c) != np.asarray(g_c)).any(axis=1).sum())
           if len(hw_c) == len(g_c) else None,
           "step_model_vs_segment_model_mismatches": int((ga != sp).sum()) if len(ga) == len(sp) else None,
           "model_seconds": round(t_model, 1), "sim_seconds": round(time.time() - t1, 1)}
    res["bit_exact"] = (res["segments_hw"] == res["segments_model"] == len(seg_pred)
                        and res["hw_vs_step_model_af_mismatches"] == 0 and res["hw_vs_step_model_counter_mismatches"] == 0
                        and res["step_model_vs_segment_model_mismatches"] == 0)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--model-json", required=True, help="file.json[:dotted.key] holding the model dict")
    ap.add_argument("--n", type=int, default=128)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--dbs", nargs="*", default=["afdb", "ltafdb"])
    ap.add_argument("--steps", nargs="*", default=["lab", "seq", "icarus"])
    ap.add_argument("--layout", action="store_true")
    a = ap.parse_args()
    f, _, key = a.model_json.partition(":")
    model = json.loads(Path(f).read_text())
    for part in [k for k in key.split(".") if k]:
        model = model[part]
    n, tag = a.n, a.design
    feats = used(model)
    dev = any(x.startswith("dev_") for x in feats)
    out = a.out / tag
    out.mkdir(parents=True, exist_ok=True)
    resf = out / "seqchip.json"
    res: dict = json.loads(resf.read_text()) if resf.exists() else {}
    res.update({"design": tag, "model": model, "features": feats, "n": n})
    ir = build_core_ir(model, n, f"afseq_{tag}")
    (out / "core_ir.json").write_text(json.dumps(ir, indent=1))
    bin_dir = Path(os.environ["CHIPLAB_BIN_DIR"])
    home = Path(os.environ["CHIPLAB_HOME"])
    c = call(bin_dir, "compile-ir", {"ir": ir}, out / "lab_compile.json", 600)
    did = c.get("design_id")
    if not did:
        res["error"] = c
        resf.write_text(json.dumps(res, indent=1, default=str))
        raise SystemExit(f"compile failed: {c}")
    res["core_design_id"] = did
    ddir = home / "designs" / did
    ports = json.loads((ddir / "port.json").read_text())
    res["core_ports"] = ports
    print(tag, "core", did, flush=True)
    data = {}
    for db in a.dbs:
        ext = "qrs" if db == "afdb" else "atr"
        data[db] = load_db(a.data / db, ext, set())
    if "lab" in a.steps:
        s = call(bin_dir, "synthesize", {"design_id": did}, out / "lab_synth.json", 1200)
        res["core_synth"] = {k: (s.get("metrics") or {}).get(k) for k in ("gates", "depth", "transistors_est")}
        res["core_map"] = {}
        for p in PDKS:
            mp = call(bin_dir, "map-to-process", {"design_id": did, "pdk": p}, out / f"lab_map_{p}.json", 1200)
            res["core_map"][p] = {k: (mp.get("metrics") or {}).get(k) for k in ("area_um2", "gate_equivalents", "std_cells")}
        # lab simulate of the core on its real state trajectory over every AF-database record
        if "afdb" in data:
            vec = {"x": [], "h": [], "c": [], "p": []} | ({"m": []} if dev else {})
            exp = []
            for r in data["afdb"]:
                gr = golden_record(model, n, r.rr.astype(np.int64), dev)
                for k2 in vec:
                    vec[k2] += gr[k2]
                exp += gr["af"]
            sim = call(bin_dir, "simulate", {"design_id": did, "inputs": "vectors", "vectors": vec, "expected": exp,
                                             "device": "numpy"}, out / "lab_simulate_afdb.json", 3600)
            res["core_simulate_afdb"] = {k2: sim.get(k2) for k2 in ("n", "pairs", "bit_exact", "status", "error")}
            print(tag, "simulate", sim.get("bit_exact"), sim.get("n"), flush=True)
        rnd = call(bin_dir, "simulate", {"design_id": did, "inputs": "random", "n": 200000, "device": "numpy"},
                   out / "lab_simulate_random.json", 3600)
        res["core_simulate_random"] = {k2: rnd.get(k2) for k2 in ("n", "pairs", "bit_exact")}
        pe = call(bin_dir, "prove-equivalence", {"design_id": did, "golden": True, "timeout": 900},
                  out / "lab_prove.json", 2400)
        res["core_prove_equivalence"] = {k2: v for k2, v in pe.items() if k2 not in ("cost", "log")}
        vl = call(bin_dir, "verification-level", {"design_id": did}, out / "lab_vlevel.json", 300)
        res["core_verification_level"] = vl
        print(tag, "prove", pe.get("status"), pe.get("proved"), flush=True)
        resf.write_text(json.dumps(res, indent=1, default=str))
    top = f"afseq_{tag}"
    sw = out / "seq"
    sw.mkdir(exist_ok=True)
    core_v = (ddir / "design.v").read_text()
    (sw / "core.v").write_text(core_v)
    (sw / "wrapper.v").write_text(wrapper_verilog(ports["top"], ports, top))
    (sw / "full.v").write_text(core_v + "\n" + (sw / "wrapper.v").read_text())
    if "seq" in a.steps:
        code = (
            "import json; from pathlib import Path\n"
            "from chiplab.hw.yosys import synth_generic\n"
            "from chiplab.hw.pdk import map_to_process\n"
            "from chiplab.verify.eqy import prove_sequential\n"
            f"w = Path({str(sw)!r}); out = {{}}\n"
            f"g = synth_generic(w / 'full.v', {top!r}, w / 'gen')\n"
            "out['generic'] = {k: g.get(k) for k in ('gates', 'depth', 'transistors_est', 'cells_by_type', 'netlist_v', 'gate_verilog')}\n"
            "for p in ('sky130', 'gf180', 'ihp'):\n"
            "    (w / p).mkdir(exist_ok=True)\n"
            f"    mp = map_to_process(w / 'full.v', {top!r}, w / p, pdk=p)\n"
            "    out[p] = {k: mp.get(k) for k in ('area_um2', 'gate_equivalents', 'std_cells', 'cells_by_type')}\n"
            f"ps = prove_sequential([w / 'core.v', w / 'wrapper.v'], {top!r}, w / 'eqy_bb', blackbox=[{ports['top']!r}], "
            "blackbox_sources=[w / 'core.v'], timeout=900)\n"
            "out['prove_sequential_compositional'] = {k: ps.get(k) for k in ('proved', 'method', 'scope', 'depth', 'seconds', 'error', 'blackboxed')}\n"
            "print(json.dumps(out, default=str))\n")
        r = labpy(code, sw, 3600)
        res["clocked"] = r
        for p in PDKS:
            cbt = ((r.get(p) or {}).get("cells_by_type")) or {}
            r.setdefault(p, {})["flip_flops"] = sum(v for k2, v in cbt.items() if "df" in k2.lower())
        cbt = ((r.get("generic") or {}).get("cells_by_type")) or {}
        res["clocked_generic_flip_flops"] = sum(v for k2, v in cbt.items() if "DFF" in k2.upper())
        print(tag, "clocked", {p: (r.get(p) or {}).get("gate_equivalents") for p in PDKS},
              (r.get("prove_sequential_compositional") or {}).get("proved"), flush=True)
        resf.write_text(json.dumps(res, indent=1, default=str))
        code2 = (
            "import json; from pathlib import Path\n"
            "from chiplab.verify.eqy import prove_sequential\n"
            f"w = Path({str(sw)!r})\n"
            f"pw = prove_sequential([w / 'full.v'], {top!r}, w / 'eqy_whole', timeout=1200)\n"
            "print(json.dumps({k: pw.get(k) for k in ('proved', 'method', 'scope', 'depth', 'seconds', 'error')}, default=str))\n")
        res["prove_sequential_whole"] = labpy(code2, sw, 1500)
        print(tag, "whole", res["prove_sequential_whole"], flush=True)
        resf.write_text(json.dumps(res, indent=1, default=str))
    if "icarus" in a.steps:
        cw = next(p["lanes"] * p["bits"] for p in ports["inputs"] if p["name"] == "c")
        cb = next(p["bits"] for p in ports["inputs"] if p["name"] == "c")
        res.setdefault("icarus", {})
        for db, recs in data.items():
            res["icarus"][db] = icarus_db(db, recs, model, n, dev, sw, top, [str(sw / "full.v")], cw, cb, len(feats), "rtl")
            print(tag, "icarus", db, res["icarus"][db], flush=True)
            resf.write_text(json.dumps(res, indent=1, default=str))
    if a.layout:
        code3 = (
            "import json; from pathlib import Path\n"
            "from chiplab.hw.librelane import timing_power_layout\n"
            f"w = Path({str(sw)!r})\n"
            f"r = timing_power_layout([w / 'full.v'], {top!r}, w / 'layout_sky130', pdk='sky130A', clock_period_ns=20.0, "
            "clock_port='clk', timeout=3600)\n"
            "print(json.dumps({k: v for k, v in r.items() if k not in ('log',)}, default=str))\n")
        res["layout_sky130"] = labpy(code3, sw, 4000)
        print(tag, "layout", {k: res["layout_sky130"].get(k) for k in ("area_um2", "die_area_um2", "timing_ws_ns", "error")}, flush=True)
        resf.write_text(json.dumps(res, indent=1, default=str))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
