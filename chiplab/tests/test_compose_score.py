"""Score-level fusion in compose: the same per-channel model on several channel ports, max or sum over the
multi-bit head scores, then a threshold compare. Checked against the interpreter, bit-exact on the synthesised
netlist (level 1), and formally proved against the golden model (time cap on each proof)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from chiplab import config
from chiplab.emit.verilog import emit
from chiplab.ingest.compose import compose, io_spec
from chiplab.ingest.intnn import to_ir
from chiplab.ir.interp import run
from chiplab.ir.schema import IRError
from chiplab.verify.bitexact import check
from chiplab.verify.rtlsim import random_inputs

ROOT = Path(__file__).resolve().parent.parent
HAVE_YOSYS = bool(config.find_bin("yosys") and config.find_bin("yosys-abc"))
CHANNELS = ("c0", "c1", "c2")


def channel_model(seed=7, lanes=4, bits=4, signed=True):
    """A small per-channel model whose output is its multi-bit score (the final cmp dropped)."""
    r = np.random.default_rng(seed)
    p = {"layers": [{"W": r.integers(-2, 3, (3, lanes)).tolist(), "b": r.integers(-2, 3, 3).tolist(), "shift": 1,
                     "amax": 7}],
         "Wo": [r.integers(-2, 3, 3).tolist()], "bo": [int(r.integers(-3, 4))], "out_dim": 1}
    ir = to_ir(p, {"lanes": lanes, "bits": bits, "signed": signed}, name="chan")
    ir["nodes"] = [n for n in ir["nodes"] if n["id"] != "dec"]
    ir["outputs"] = [{"name": "s", "src": "score"}]
    return ir


FUSION = [{"name": "hit_max", "op": "max", "t": 3, "inputs": [f"{c}_s" for c in CHANNELS]},
          {"name": "hit_sum", "op": "sum", "t": 2, "rel": "gt", "score": True, "inputs": [f"{c}_s" for c in CHANNELS]}]


@pytest.fixture(scope="module")
def chip():
    m = channel_model()
    return compose({c: m for c in CHANNELS}, FUSION, shared_inputs=False, name="chanfuse")


def test_score_fusion_semantics(chip):
    assert [p["name"] for p in chip["inputs"]] == [f"{c}_x" for c in CHANNELS]
    assert [o["name"] for o in chip["outputs"]] == ["c0_s", "c1_s", "c2_s", "hit_max", "hit_sum", "hit_sum_score"]
    o = run(chip, random_inputs(chip, 4000, 0))
    S = np.stack([o[f"{c}_s"][:, 0] for c in CHANNELS], axis=1)
    assert S.min() < 0 < S.max()                       # signed multi-bit scores, not decisions
    assert (o["hit_max"][:, 0] == (S.max(axis=1) >= 3)).all()
    assert (o["hit_sum_score"][:, 0] == S.sum(axis=1)).all()
    assert (o["hit_sum"][:, 0] == (S.sum(axis=1) > 2)).all()
    spec = {x["name"]: x for x in io_spec(chip)["outputs"]}
    assert (spec["hit_max"]["lo"], spec["hit_max"]["hi"]) == (0, 1)
    assert (spec["hit_sum"]["lo"], spec["hit_sum"]["hi"]) == (0, 1)


def test_score_fusion_with_decision_ops():
    """Score ops and the existing decision ops sit side by side; the decision ops keep their behaviour."""
    m = channel_model()
    dec = to_ir({"layers": [{"W": [[1, -1, 0, 1]], "b": [0], "shift": 0, "amax": 7}], "Wo": [[1]], "bo": [-1],
                 "out_dim": 1}, {"lanes": 4, "bits": 4, "signed": True}, name="d")
    chip = compose({"a": m, "b": m, "d": dec},
                   [{"name": "big", "op": "max", "t": 0, "rel": "gt", "inputs": ["a_s", "b_s"]},
                    {"name": "any", "op": "or", "inputs": ["d_y"]}], shared_inputs=False)
    o = run(chip, random_inputs(chip, 2000, 4))
    assert (o["big"][:, 0] == (np.maximum(o["a_s"][:, 0], o["b_s"][:, 0]) > 0)).all()
    assert (o["any"][:, 0] == o["d_y"][:, 0]).all()


@pytest.mark.parametrize("bad", [
    {"name": "f", "op": "max", "inputs": ["c0_s"]},                              # no threshold
    {"name": "f", "op": "sum", "t": True, "inputs": ["c0_s"]},                   # bool is not a threshold
    {"name": "f", "op": "max", "t": 1, "rel": "approx", "inputs": ["c0_s"]},     # unknown relation
    {"name": "f", "op": "sum", "t": 1, "inputs": []},                            # no inputs
    {"name": "f", "op": "max", "t": 1, "inputs": ["zz_s"]},                      # unknown head output
    {"name": "f", "op": "and", "inputs": ["c0_s"]},                              # decision op on a score
])
def test_score_fusion_rejects_bad_spec(bad):
    with pytest.raises(IRError):
        compose({"c0": channel_model()}, [bad])


@pytest.mark.skipif(not HAVE_YOSYS, reason="yosys not installed")
def test_score_fusion_level1_netlist(chip, tmp_path):
    from chiplab.hw.yosys import synth_generic
    text, info = emit(chip)
    (tmp_path / "d.v").write_text(text)
    syn = synth_generic(tmp_path / "d.v", info["top"], tmp_path / "syn")
    res = check(chip, syn["netlist_json"], info, random_inputs(chip, 4000, 1))
    assert res["bit_exact"] and res["n"] == 4000, res["pairs"]


@pytest.mark.skipif(not HAVE_YOSYS, reason="yosys not installed")
@pytest.mark.parametrize("op", ["max", "sum"])
def test_score_fusion_proved_against_golden(tmp_path, op):
    """Two channels of a small model, fused by max or sum: gates == RTL == golden model, every input value."""
    from chiplab.hw.yosys import synth_generic
    from chiplab.verify.formal import prove
    m = channel_model(seed=3, lanes=3, bits=3)
    ir = compose({"c0": m, "c1": m}, [{"name": "hit", "op": op, "t": 1, "inputs": ["c0_s", "c1_s"]}],
                 shared_inputs=False, name=f"proof_{op}")
    text, info = emit(ir)
    (tmp_path / "d.v").write_text(text)
    syn = synth_generic(tmp_path / "d.v", info["top"], tmp_path / "syn")
    gates = Path(syn["gate_verilog"])
    r = prove(ir, info, gates, tmp_path / "d.v", tmp_path / "p", timeout=90, golden=True)
    assert r["proved"] is True and "golden" in r["against"], r
    # a one-gate mutant of the same netlist is refuted, so the proof above is not vacuous
    g = gates.read_text()
    m = re.search(r"assign (\S+) = (\S+) ([\^&|]) (\S+);", g)
    assert m, "no 2-input gate to mutate"
    bad = tmp_path / "bad.v"
    bad.write_text(g.replace(m.group(0), f"assign {m.group(1)} = ~({m.group(2)} {m.group(3)} {m.group(4)});", 1))
    r2 = prove(ir, info, bad, tmp_path / "d.v", tmp_path / "p_bad", timeout=90, golden=True)
    assert r2["proved"] is False, r2


def test_compose_chip_tool_score_fusion(tmp_path):
    """The compose-chip tool accepts score fusion over the CLI and reports the 1-bit decision in io_spec."""
    m = channel_model()
    args = {"heads": {c: m for c in CHANNELS}, "fusion": FUSION, "shared_inputs": False, "name": "chanfuse"}
    cli = str(Path(sys.executable).parent / "chiplab")
    p = subprocess.run([cli, "compose-chip", "--json", json.dumps(args)], cwd=ROOT,
                       env={**os.environ, "CHIPLAB_HOME": str(tmp_path)}, capture_output=True, text=True, timeout=300)
    res = json.loads(p.stdout)
    assert p.returncode == 0 and res["status"] == "ok", res
    outs = {o["name"]: o for o in res["io_spec"]["outputs"]}
    assert (outs["hit_max"]["lo"], outs["hit_max"]["hi"]) == (0, 1)
    assert "hit_sum_score" in outs
