"""The key test: random chipir/1 programs using every op -> Verilog -> Yosys gates -> netlist evaluation must equal
the reference interpreter on random inputs; and Icarus simulation of the RTL must equal it too."""
import json
import subprocess

import numpy as np
import pytest

from chiplab.config import oss_bin
from chiplab.emit.verilog import emit
from chiplab.hw.yosys import synth_generic
from chiplab.ir.interp import run as interp
from chiplab.ir.schema import validate
from chiplab.verify.bitexact import check
from chiplab.verify.netlist_eval import bits_to_lanes, lanes_to_bits


def random_ir(seed: int) -> dict:
    r = np.random.default_rng(seed)
    nl = int(r.integers(3, 7)); bits = int(r.integers(2, 6)); signed = bool(r.integers(0, 2))
    nodes, lanes = [], {"x": nl}

    def add(nd, n):
        nodes.append(nd); lanes[nd["id"]] = n

    def pick():
        return str(r.choice(list(lanes)))

    add({"id": "c0", "op": "const", "values": [int(v) for v in r.integers(-5, 6, size=3)]}, 3)
    ops = ["matvec", "add", "sub", "shift", "clip", "abs", "max", "cmp", "cmp2", "gather", "concat", "lut"]
    r.shuffle(ops)
    ops = ops + list(r.choice(ops, size=4))
    for k, op in enumerate(ops):
        i = f"n{k}"
        s = pick()
        if op == "matvec":
            m = int(r.integers(1, 5))
            W = r.integers(-5, 6, size=(m, lanes[s])).tolist()
            add({"id": i, "op": "matvec", "src": s, "W": W, "b": r.integers(-9, 10, size=m).tolist()}, m)
        elif op in ("add", "sub"):
            cands = [t for t in lanes if lanes[t] in (lanes[s], 1)] or [s]
            add({"id": i, "op": op, "a": s, "b": str(r.choice(cands))}, lanes[s])
        elif op == "shift":
            add({"id": i, "op": "shift", "src": s, "k": int(r.integers(0, 4))}, lanes[s])
        elif op == "clip":
            lo = int(r.integers(-8, 3)); add({"id": i, "op": "clip", "src": s, "lo": lo, "hi": lo + int(r.integers(0, 12))}, lanes[s])
        elif op == "abs":
            add({"id": i, "op": "abs", "src": s}, lanes[s])
        elif op == "max":
            g = [sorted(set(r.integers(0, lanes[s], size=int(r.integers(1, 4))).tolist())) for _ in range(int(r.integers(1, 3)))]
            add({"id": i, "op": "max", "src": s, "groups": g}, len(g))
        elif op == "cmp":
            add({"id": i, "op": "cmp", "src": s, "rel": str(r.choice(["gt", "ge", "lt", "le", "eq", "ne"])),
                 "t": r.integers(-6, 7, size=lanes[s]).tolist()}, lanes[s])
        elif op == "cmp2":
            cands = [t for t in lanes if lanes[t] in (lanes[s], 1)] or [s]
            add({"id": i, "op": "cmp", "src": s, "rel": str(r.choice(["gt", "le", "eq"])), "other": str(r.choice(cands))}, lanes[s])
        elif op == "gather":
            idx = r.integers(0, lanes[s], size=int(r.integers(1, 6))).tolist()
            add({"id": i, "op": "gather", "src": s, "idx": idx}, len(idx))
        elif op == "concat":
            t = pick(); add({"id": i, "op": "concat", "srcs": [s, t]}, lanes[s] + lanes[t])
        elif op == "lut":
            cid = f"{i}b"
            add({"id": cid, "op": "cmp", "src": s, "rel": "gt", "t": [0]}, lanes[s])
            sel = [r.integers(0, lanes[s], size=int(r.integers(1, 4))).tolist() for _ in range(int(r.integers(1, 4)))]
            add({"id": i, "op": "lut", "src": cid, "inputs": sel, "tables": [r.integers(0, 2, size=2 ** len(q)).tolist() for q in sel]}, len(sel))
    last = nodes[-1]["id"]
    add({"id": "am", "op": "argmax", "src": last}, 1)
    outs = [{"name": "y", "src": last}, {"name": "z", "src": "am"}, {"name": "w", "src": str(r.choice([n["id"] for n in nodes]))}]
    return validate({"ir": "chipir/1", "name": f"fuzz{seed}", "inputs": [{"name": "x", "lanes": nl, "bits": bits, "signed": signed}],
                     "nodes": nodes, "outputs": outs, "meta": {}})


def _inputs(ir, n, seed):
    p = ir["inputs"][0]; r = np.random.default_rng(seed)
    lo, hi = (-(1 << (p["bits"] - 1)), 1 << (p["bits"] - 1)) if p["signed"] else (0, 1 << p["bits"])
    return r.integers(lo, hi, size=(n, p["lanes"]))


@pytest.mark.parametrize("seed", range(12))
def test_netlist_equals_interp(seed, tmp_path):
    ir = random_ir(seed)
    text, info = emit(ir)
    (tmp_path / "d.v").write_text(text)
    syn = synth_generic(tmp_path / "d.v", info["top"], tmp_path / "syn", timeout=300)
    X = _inputs(ir, 4000, seed)
    res = check(ir, syn["netlist_json"], info, X)
    assert res["bit_exact"], (seed, res["pairs"])


@pytest.mark.parametrize("seed", range(6))
def test_icarus_rtl_equals_interp(seed, tmp_path):
    ir = random_ir(100 + seed)
    text, info = emit(ir)
    (tmp_path / "d.v").write_text(text)
    p = info["inputs"][0]; X = _inputs(ir, 512, seed)
    xb = lanes_to_bits(X, p["bits"])
    W = xb.shape[1]
    (tmp_path / "in.txt").write_text("\n".join("".join(str(b) for b in row[::-1]) for row in xb) + "\n")
    outs = info["outputs"]
    owid = [o["lanes"] * o["bits"] for o in outs]
    tb = [f"module tb; reg [{W - 1}:0] mem [0:{len(X) - 1}]; reg [{W - 1}:0] x;"]
    tb += [f"wire [{w - 1}:0] {o['name']};" for o, w in zip(outs, owid)]
    tb += [f"{info['top']} dut(.x(x), " + ", ".join(f".{o['name']}({o['name']})" for o in outs) + ");",
           "integer i; initial begin $readmemb(\"in.txt\", mem); for (i = 0; i < " + str(len(X)) + "; i = i + 1) begin x = mem[i]; #1; "
           "$display(\"%b " + " ".join("%b" for _ in outs[1:]) + "\", " + ", ".join(o["name"] for o in outs) + "); end $finish; end endmodule"]
    (tmp_path / "tb.v").write_text("\n".join(tb))
    subprocess.run([oss_bin("iverilog"), "-o", "sim", "tb.v", "d.v"], cwd=tmp_path, check=True, capture_output=True)
    raw = subprocess.run([oss_bin("vvp"), "-n", "sim"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout
    rows = [ln.split() for ln in raw.splitlines() if ln.split() and all(set(t) <= {"0", "1"} for t in ln.split())]
    ref = interp(ir, X)
    toks = np.array(rows).reshape(len(X), len(outs))
    for j, o in enumerate(outs):
        b = np.array([[int(c) for c in t[::-1]] for t in toks[:, j]], dtype=np.int64)
        got = bits_to_lanes(b, o["lanes"], o["bits"], o["signed"])
        assert (got == ref[o["name"]]).all(), (seed, o["name"])
