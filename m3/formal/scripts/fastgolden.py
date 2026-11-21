"""Golden equivalence (gate netlist == independent golden model of the IR) for chiplab designs: experiment driver.

usage: fastgolden.py <design_id> <method> [<method> ...] --timeout S --out DIR [--jobs N]

Methods (each timed with a hard limit; results appended to DIR/results.jsonl):
  whole-*  : one miter, golden model of the WHOLE IR vs the synthesised gate netlist (gates.v). No range
             assumptions; proves exactly "gates == golden model for every input".
  node-*   : the lab's proof A shape (production RTL == golden per IR node, inputs clamped to derived ranges),
             chained with proof B (gates == production RTL, ABC cec). Sound only if ir/ranges.py is sound.

Uses chiplab (emitters, ranges, sub-IR builder) unchanged, plus one local fix: emit/golden.py rewrites every
"[63:0]" in its text, which also corrupts a port that is exactly 64 bits wide (see proposed/formal.patch).
"""
from __future__ import annotations

import argparse
import copy
import os
import json
import re
import subprocess
import time
from pathlib import Path

from chiplab import config
from chiplab.config import oss_bin
from chiplab.emit.golden import emit_golden
from chiplab.emit.verilog import emit
from chiplab.ir.ranges import ranges as ir_ranges
from chiplab.verify.formal import _node_subir

ABC_GATES = "AND,NAND,OR,NOR,XOR,XNOR,ANDNOT,ORNOT,MUX"


def golden_fixed(ir: dict, module: str, info: dict) -> str:
    """emit_golden, with port declarations restored to their true widths (works around the [63:0] rewrite)."""
    text = emit_golden(ir, module, info)
    ports = [("input", p["name"], p["lanes"] * p["bits"]) for p in ir["inputs"]]
    ports += [("output", o["name"], o["lanes"] * o["bits"]) for o in info["outputs"]]
    for kind, name, w in ports:
        text = re.sub(rf"(\n  {kind} wire )\[\d+:0\] {name}(,?\n)", rf"\g<1>[{w - 1}:0] {name}\g<2>", text, count=1)
    return text


def sh(cmd: list[str], cwd: Path, timeout: int, log: str) -> tuple[int | None, str, float]:
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        out, rc = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out = ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))
        out, rc = out + f"\n[fastgolden] TIMEOUT after {timeout}s", None
    (cwd / log).write_text(out)
    return rc, out, time.time() - t0


def yosys(script: str, cwd: Path, timeout: int, name: str) -> tuple[int | None, str, float]:
    (cwd / f"{name}.ys").write_text(script)
    return sh([oss_bin("yosys"), "-q", "-s", f"{name}.ys"], cwd, timeout, f"{name}.log")


# ------------------------------------------------------------------------------------------------ miter builders
def read_pair(gold: str, gate: str, gate_is_netlist: bool) -> str:
    # gates.v from the lab is plain `assign` logic, so the netlist reads like any Verilog (flag kept for clarity).
    del gate_is_netlist
    return f"read_verilog gold.v\nread_verilog {gate}\nproc\nopt_clean\n"


def miter_aig(cwd: Path, gtop: str, rtop: str, gate: str, netlist: bool, timeout: int, prep: str) -> tuple[bool, str]:
    """Single-output miter (1 = mismatch) as AIGER. prep: 'synth' (lab flow: alumacc/techmap) or 'techmap'."""
    body = "synth -flatten -noabc -top miter\n" if prep == "synth" else "techmap\nopt -fast\n"
    s = (read_pair("gold.v", gate, netlist) + f"miter -equiv -flatten {gtop} {rtop} miter\nhierarchy -top miter\n"
         f"flatten\n{body}aigmap\nopt_clean\nwrite_aiger -zinit miter.aig\n")
    rc, out, _ = yosys(s, cwd, timeout, f"miter_{prep}")
    return rc == 0, out[-800:]


def abc_verdict(out: str) -> bool | None:
    keys = ("networks are", "property", "counter-example", "was asserted", "unsat", "satisfiable")
    lines = [ln for ln in out.lower().splitlines() if any(k in ln for k in keys) and "undecided" not in ln]
    o = lines[-1] if lines else ""
    if "after structural hashing" in o:  # cec/dcec given ONE network compare it with itself: not a proof
        return None
    if o.startswith("unsatisfiable"):  # iprove on a miter
        return True
    if o.startswith("satisfiable"):
        return False
    if "networks are equivalent" in o or "property proved" in o or "is unsatisfiable" in o or "unsat" in o.split():
        return True
    if "not equivalent" in o or "are not equivalent" in o or "property fails" in o or "counter-example" in o:
        return False
    return None


# ------------------------------------------------------------------------------------------------ methods on one miter
def m_yosys_sat(cwd: Path, gtop: str, rtop: str, gate: str, netlist: bool, timeout: int) -> bool | None:
    s = (read_pair("gold.v", gate, netlist) + f"miter -equiv -flatten -make_assert {gtop} {rtop} miter\n"
         f"hierarchy -top miter\nflatten\nopt -fast\nsat -verify -prove-asserts -timeout {timeout} miter\n")
    rc, out, _ = yosys(s, cwd, timeout + 30, "yosys_sat")
    if rc == 0:
        return True
    return None if (rc is None or "timed out" in out or "TIMEOUT" in out) else False


def m_abc(cwd: Path, gtop: str, rtop: str, gate: str, netlist: bool, timeout: int, cmd: str, prep: str) -> bool | None:
    ok, err = miter_aig(cwd, gtop, rtop, gate, netlist, timeout, prep)
    if not ok:
        (cwd / "error.txt").write_text(err)
        return None
    rc, out, _ = sh([oss_bin("yosys-abc"), "-c", f"read_aiger miter.aig; {cmd}"], cwd, timeout,
                    f"abc_{re.sub(r'[^a-z0-9]+', '_', cmd)}_{prep}.log")
    return abc_verdict(out) if rc is not None else None


def m_sby(cwd: Path, gtop: str, rtop: str, gate: str, netlist: bool, timeout: int, engine: str) -> bool | None:
    """Combinational miter as an assertion; BMC depth 1 = every input assignment (no state), i.e. a full proof."""
    del netlist
    files = "gold.v\n" + gate
    (cwd / "eq.sby").write_text(f"""[options]
mode {"prove" if engine.startswith("abc") else "bmc"}
depth 1

[engines]
{engine}

[script]
read_verilog gold.v
read_verilog {Path(gate).name}
proc
opt_clean
miter -equiv -flatten -make_assert {gtop} {rtop} miter
hierarchy -top miter
flatten
opt -fast

[files]
{files}
""")
    name = re.sub(r"[^a-z0-9]+", "_", engine)
    rc, out, _ = sh([oss_bin("sby"), "-f", "-d", f"sby_{name}", "eq.sby"], cwd, timeout, f"sby_{name}.log")
    if rc is None:
        return None
    if "DONE (PASS" in out:
        return True
    if "DONE (FAIL" in out:
        return False
    return None


def m_eqy(cwd: Path, gtop: str, rtop: str, gate: str, netlist: bool, timeout: int, strategy: str) -> bool | None:
    """YosysHQ eqy: partitions by matched signal names, then proves each partition with `strategy`."""
    del netlist
    (cwd / "eq.eqy").write_text(f"""[gold]
read_verilog {(cwd / 'gold.v').resolve()}
prep -top {gtop}
rename {gtop} {rtop}
flatten

[gate]
read_verilog {(cwd / gate).resolve()}
prep -top {rtop}
flatten

[collect *]

{strategy}
""")
    rc, out, _ = sh([oss_bin("eqy"), "-f", "eq.eqy", "-d", "eqy_out", "-j", "4"], cwd, timeout, "eqy.log")
    if rc is None:
        return None
    if rc == 0 and "Successfully proved designs equivalent" in out:
        return True
    if "Failed to prove equivalence" in out:
        return False
    return None


METHODS = {
    "eqy-sat": lambda c, g, r, f, n, t: m_eqy(c, g, r, f, n, t, "[strategy sat]\nuse sat\ndepth 1"),
    "eqy-sby-bitwuzla": lambda c, g, r, f, n, t: m_eqy(c, g, r, f, n, t,
                                                       "[strategy sby]\nuse sby\ndepth 1\nengine smtbmc bitwuzla"),
    "yosys-sat": lambda c, g, r, f, n, t: m_yosys_sat(c, g, r, f, n, t),
    "abc-cec-synth": lambda c, g, r, f, n, t: m_abc(c, g, r, f, n, t, "cec -n", "synth"),
    "abc-&cec-synth": lambda c, g, r, f, n, t: m_abc(c, g, r, f, n, t, "&get; &cec -m", "synth"),
    "abc-&cec-techmap": lambda c, g, r, f, n, t: m_abc(c, g, r, f, n, t, "&get; &cec -m", "techmap"),
    "abc-dcec-synth": lambda c, g, r, f, n, t: m_abc(c, g, r, f, n, t, "dcec", "synth"),
    "abc-iprove-synth": lambda c, g, r, f, n, t: m_abc(c, g, r, f, n, t, "iprove", "synth"),
    "abc-iprove-techmap": lambda c, g, r, f, n, t: m_abc(c, g, r, f, n, t, "iprove", "techmap"),
    "abc-dsec-synth": lambda c, g, r, f, n, t: m_abc(c, g, r, f, n, t, "dsec", "synth"),
    "abc-pdr-synth": lambda c, g, r, f, n, t: m_abc(c, g, r, f, n, t, "pdr", "synth"),
    "sby-bitwuzla": lambda c, g, r, f, n, t: m_sby(c, g, r, f, n, t, "smtbmc bitwuzla"),
    "sby-yices": lambda c, g, r, f, n, t: m_sby(c, g, r, f, n, t, "smtbmc yices"),
    "sby-z3": lambda c, g, r, f, n, t: m_sby(c, g, r, f, n, t, "smtbmc z3"),
    "sby-boolector": lambda c, g, r, f, n, t: m_sby(c, g, r, f, n, t, "smtbmc boolector"),
    "sby-abc-pdr": lambda c, g, r, f, n, t: m_sby(c, g, r, f, n, t, "abc pdr"),
    "sby-btormc": lambda c, g, r, f, n, t: m_sby(c, g, r, f, n, t, "btor btormc"),
}


# ------------------------------------------------------------------------------------------------ design scopes
def design(did: str) -> tuple[dict, dict, Path, Path]:
    d = config.HOME / "designs" / did
    ir = json.loads((d / "ir.json").read_text())
    info = json.loads((d / "port.json").read_text())
    syn = json.loads((d / "synth.json").read_text())
    return ir, info, Path(syn["gate_verilog"]), d / "design.v"


def run_whole(did: str, method: str, timeout: int, out: Path, vs_rtl: bool = False) -> dict:
    ir, info, gate, rtl = design(did)
    gate = rtl if vs_rtl else gate
    cwd = out / did / f"{'wholertl' if vs_rtl else 'whole'}_{re.sub(r'[^a-z0-9]+', '_', method)}"
    if os.environ.get("FG_MUTANT"):  # soundness check: golden of a mutated IR (final threshold + 1) must FAIL
        ir = copy.deepcopy(ir)
        nd = [n for n in ir["nodes"] if n["op"] == "cmp" and "t" in n][-1]
        nd["t"] = nd["t"] + 1 if isinstance(nd["t"], int) else [t + 1 for t in nd["t"]]
    cwd.mkdir(parents=True, exist_ok=True)
    (cwd / "gold.v").write_text(golden_fixed(ir, "gold_top", info))
    (cwd / "gates.v").write_text(gate.read_text())
    t0 = time.time()
    v = METHODS[method](cwd, "gold_top", info["top"], "gates.v", True, timeout)
    return {"design": did, "scope": "wholertl" if vs_rtl else "whole", "method": method, "proved": v, "seconds": round(time.time() - t0, 2),
            "timeout": timeout, "mutant": bool(os.environ.get("FG_MUTANT"))}


def b_proof(did: str, timeout: int, cwd: Path) -> tuple[bool | None, float]:
    """Proof B exactly as the lab runs it (verify/formal.py)."""
    from chiplab.verify.formal import _blif, _cec
    ir, info, gate, rtl = design(did)
    t0 = time.time()
    r = _blif(rtl, info["top"], "rtl", cwd, timeout, synth=True)
    g = _blif(gate, info["top"], "gate", cwd, timeout, synth=False)
    ok, _ = _cec(r, g, cwd, timeout)
    return ok, time.time() - t0


def run_nodes(did: str, method: str, timeout: int, out: Path) -> dict:
    ir, _, _, _ = design(did)
    base = out / did / f"nodes_{re.sub(r'[^a-z0-9]+', '_', method)}"
    base.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    okb, tb = b_proof(did, timeout, base)
    R = ir_ranges(ir)
    rows = []
    for nd in ir.get("nodes", []):
        if nd["op"] == "const":
            continue
        left = int(timeout - (time.time() - t0))
        if left < 5:
            rows.append({"id": nd["id"], "proved": None, "note": "budget exhausted"}); break
        sub = _node_subir(ir, nd, R)
        text, sinfo = emit(sub, top=f"prod_{nd['id']}")
        cwd = base / f"node_{nd['id']}"
        cwd.mkdir(exist_ok=True)
        (cwd / "prod.v").write_text(text)
        (cwd / "gold.v").write_text(golden_fixed(sub, f"gold_{nd['id']}", sinfo))
        t1 = time.time()
        v = METHODS[method](cwd, f"gold_{nd['id']}", f"prod_{nd['id']}", "prod.v", False, left)
        rows.append({"id": nd["id"], "op": nd["op"], "proved": v, "seconds": round(time.time() - t1, 2)})
        if v is not True:
            break
    a_ok = all(r["proved"] is True for r in rows) and len(rows) == sum(1 for n in ir["nodes"] if n["op"] != "const")
    bad = any(r["proved"] is False for r in rows)
    proved = True if (a_ok and okb is True) else (False if (bad or okb is False) else None)
    return {"design": did, "scope": "nodes+B", "method": method, "proved": proved, "B_proved": okb,
            "B_seconds": round(tb, 2), "nodes": rows, "seconds": round(time.time() - t0, 2), "timeout": timeout}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("methods", nargs="+", help="whole:<m> or nodes:<m>, m in " + ",".join(METHODS))
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for spec in a.methods:
        scope, m = spec.split(":", 1)
        r = (run_whole(a.design, m, a.timeout, a.out, vs_rtl=scope == "wholertl") if scope.startswith("whole")
             else run_nodes(a.design, m, a.timeout, a.out))
        r["machine"] = "Apple M3 Max, 16 cores, 128 GB (this run)"
        line = json.dumps(r)
        print(line, flush=True)
        with (a.out / "results.jsonl").open("a") as f:
            f.write(line + "\n")


if __name__ == "__main__":
    main()
