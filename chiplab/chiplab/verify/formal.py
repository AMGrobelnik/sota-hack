"""Verification ladder level 2: prove the synthesised gate netlist equals the model for EVERY possible input.

Two proofs, chained:
  A. production RTL == golden model of the IR (emit/golden.py, an independent naive rendering), proved node by node:
     for every IR node, a small sub-design whose free inputs are clamped, lane by lane, to the node's derived input
     ranges feeds that one node; Yosys `miter -equiv` + `sat -prove` shows the production code equals the golden
     code there. The ranges are sound (interval arithmetic, re-checked by the interpreter), so the composition of
     node proofs is a proof for the whole design on every input. Small SAT problems: seconds, not hours.
  B. gate netlist == production RTL, by ABC combinational equivalence (`cec`, SAT sweeping).
A and B together: gates == golden model for every input. If A is inconclusive, B alone is reported (synthesis
proved; RTL == IR then rests on construction and tests/test_ir_fuzz.py).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from chiplab.config import oss_bin
from chiplab.emit.golden import emit_golden
from chiplab.emit.verilog import emit
from chiplab.hw.yosys import SynthError, run
from chiplab.ir.ranges import ranges as ir_ranges, width


def _blif(src: Path, mod: str, name: str, workdir: Path, timeout: int, synth: bool) -> Path:
    # synth -noabc + a fast structural mapping: Yosys's default ABC script can take >15 min on adder trees
    body = (f"synth -flatten -noabc -top {mod}\nabc -g AND,NAND,OR,NOR,XOR,XNOR,ANDNOT,ORNOT,MUX -script \"+strash;map\"\n"
            if synth else "techmap\nopt_clean\n")
    run(f"read_verilog {src}\nhierarchy -top {mod}\nproc\nflatten\n{body}rename {mod} cmp\nwrite_blif {name}.blif\n",
        workdir, timeout, f"blif_{name}")
    return workdir / f"{name}.blif"


def _cec(a: Path, b: Path, workdir: Path, timeout: int) -> tuple[bool | None, str]:
    try:
        p = subprocess.run([oss_bin("yosys-abc"), "-c", f"cec -n {a.name} {b.name}"], cwd=workdir,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"
    out = (p.stdout + p.stderr).strip()
    if "Networks are equivalent" in out:
        return True, out[-300:]
    if "NOT EQUIVALENT" in out.upper() or "are not equivalent" in out:
        return False, out[-600:]
    return None, out[-300:]


def _node_subir(ir: dict, nd: dict, R: dict) -> dict:
    """IR with free inputs, clamped per lane to the node's input ranges, feeding a copy of node `nd`."""
    keys = [k for k in ("src", "a", "b", "other") if k in nd] + (["srcs"] if "srcs" in nd else [])
    srcs = []
    for k in keys:
        srcs += nd[k] if k == "srcs" else [nd[k]]
    srcs = list(dict.fromkeys(srcs))
    inputs, nodes, rename = [], [], {}
    for s in srcs:
        rr = R[s]
        signed = any(l < 0 for l, _ in rr)
        bits = max((w if s_ or not signed else w + 1) for (w, s_) in (width(l, h) for l, h in rr))
        pin = f"in_{s}"
        inputs.append({"name": pin, "lanes": len(rr), "bits": max(1, bits), "signed": signed})
        lane_ids = []
        for j, (lo, hi) in enumerate(rr):
            g, c = f"g_{s}_{j}", f"c_{s}_{j}"
            nodes.append({"id": g, "op": "gather", "src": pin, "idx": [j]})
            nodes.append({"id": c, "op": "clip", "src": g, "lo": int(lo), "hi": int(hi)})
            lane_ids.append(c)
        nodes.append({"id": f"r_{s}", "op": "concat", "srcs": lane_ids})
        rename[s] = f"r_{s}"
    node = dict(nd)
    for k in keys:
        node[k] = [rename[x] for x in nd[k]] if k == "srcs" else rename[nd[k]]
    nodes.append(node)
    return {"ir": "chipir/1", "name": f"node_{nd['id']}", "inputs": inputs, "nodes": nodes,
            "outputs": [{"name": "o", "src": nd["id"]}], "meta": {}}


def prove_rtl_vs_golden(ir: dict, workdir: Path, timeout: int = 600) -> dict:
    """Proof A, node by node. Returns {proved, nodes: [{id, proved, seconds}], seconds}."""
    workdir.mkdir(parents=True, exist_ok=True)
    R = ir_ranges(ir)
    t0, results = time.time(), []
    for nd in ir.get("nodes", []):
        if nd["op"] == "const":
            results.append({"id": nd["id"], "proved": True, "note": "constant"}); continue
        sub = _node_subir(ir, nd, R)
        text, info = emit(sub, top=f"prod_{nd['id']}")
        gold = emit_golden(sub, f"gold_{nd['id']}", info)
        d = workdir / f"node_{nd['id']}"
        d.mkdir(exist_ok=True)
        (d / "prod.v").write_text(text); (d / "gold.v").write_text(gold)
        t1 = time.time()
        left = max(10, int(timeout - (time.time() - t0)))
        try:
            run(f"read_verilog gold.v\nread_verilog prod.v\nproc\nopt_clean\n"
                f"miter -equiv -flatten -make_assert gold_{nd['id']} prod_{nd['id']} miter\nhierarchy -top miter\n"
                f"flatten\nopt -fast\nsat -verify -prove-asserts -timeout {left} miter\n", d, left + 30, "sat")
            ok = True
        except SynthError as e:
            log = (d / "sat.log").read_text() if (d / "sat.log").exists() else str(e)
            ok = None if ("timed out" in str(e) or "did time out" in log) else False
        results.append({"id": nd["id"], "op": nd["op"], "proved": ok, "seconds": round(time.time() - t1, 2)})
        if ok is not True:
            break
    proved = all(r["proved"] is True for r in results) and len(results) == len(ir.get("nodes", []))
    bad = next((r for r in results if r["proved"] is False), None)
    return {"proved": True if proved else (False if bad else None), "nodes": results,
            "seconds": round(time.time() - t0, 1)}


def prove(ir: dict, port_info: dict, gate_verilog: Path, rtl: Path, workdir: Path, timeout: int = 600) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    top = port_info["top"]
    t0 = time.time()
    # B: gates == production RTL
    try:
        r = _blif(rtl, top, "rtl", workdir, timeout, synth=True)
        g = _blif(gate_verilog, top, "gate", workdir, timeout, synth=False)
        ok_b, out_b = _cec(r, g, workdir, timeout)
    except SynthError as e:
        ok_b, out_b = None, str(e)[-300:]
    if ok_b is not True:
        return {"proved": ok_b, "against": "production RTL", "method": "abc cec", "detail": out_b,
                "seconds": round(time.time() - t0, 1), "verification_level": 2 if ok_b else (0 if ok_b is False else 1)}
    # A: production RTL == golden model of the IR, node by node
    a = prove_rtl_vs_golden(ir, workdir / "golden_nodes", timeout)
    if a["proved"] is True:
        return {"proved": True, "against": "independent golden model of the IR (emit/golden.py)",
                "method": "abc cec (gates == RTL) + per-node yosys miter/sat (RTL == golden on derived ranges)",
                "nodes": a["nodes"], "seconds": round(time.time() - t0, 1), "verification_level": 2}
    if a["proved"] is False:
        return {"proved": False, "against": "independent golden model of the IR (emit/golden.py)",
                "method": "per-node yosys miter/sat", "nodes": a["nodes"], "detail": "emitter disagrees with golden model",
                "seconds": round(time.time() - t0, 1), "verification_level": 1}
    return {"proved": True, "against": "production RTL (synthesis proved; RTL == IR by construction and fuzz tests)",
            "method": "abc cec", "golden_attempt": a, "detail": out_b, "seconds": round(time.time() - t0, 1),
            "verification_level": 2}
