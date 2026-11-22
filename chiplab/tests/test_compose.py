"""A multi-input, multi-output chip with fusion logic passes levels 1 (netlist bit-exact on 4k vectors) and 3
(streaming wrapper in cocotb + Icarus, Tiny Tapeout and generic variants)."""
import json

import numpy as np
import pytest

from chiplab.emit.verilog import emit
from chiplab.hw.yosys import synth_generic
from chiplab.ingest.compose import compose, io_spec
from chiplab.ingest.intnn import to_ir
from chiplab.ir.interp import run
from chiplab.ir.schema import IRError
from chiplab.verify.bitexact import check
from chiplab.verify.rtlsim import random_inputs, rtl_simulate

SPIKE = json.load(open("fixtures/spike_best.json"))


def small_head(seed, lanes, bits, signed):
    r = np.random.default_rng(seed)
    p = {"layers": [{"W": r.integers(-1, 2, (4, lanes)).tolist(), "b": r.integers(-2, 3, 4).tolist(), "shift": 1, "amax": 7}],
         "Wo": [r.integers(-2, 3, 4).tolist()], "bo": [int(r.integers(-3, 4))], "out_dim": 1}
    return to_ir(p, {"lanes": lanes, "bits": bits, "signed": signed}, name=f"h{seed}")


@pytest.fixture(scope="module")
def chip():
    heads = {"s1": to_ir(SPIKE), "s2": small_head(1, 5, 4, False), "s3": small_head(2, 3, 9, True)}
    fusion = [{"name": "both", "op": "and", "inputs": ["s1_y", "s2_y"]},
              {"name": "vote", "op": "kofn", "k": 2, "inputs": ["s1_y", "s2_y", "s3_y"]},
              {"name": "any", "op": "or", "inputs": ["s1_y", "s2_y", "s3_y"]}]
    return compose(heads, fusion, shared_inputs=False, name="fused")


def test_compose_semantics(chip):
    assert [p["name"] for p in chip["inputs"]] == ["s1_x", "s2_x", "s3_x"]
    assert [o["name"] for o in chip["outputs"]] == ["s1_y", "s2_y", "s3_y", "both", "vote", "any"]
    X = random_inputs(chip, 4000, 0)
    o = run(chip, X)
    a, b, c = o["s1_y"][:, 0], o["s2_y"][:, 0], o["s3_y"][:, 0]
    assert (o["both"][:, 0] == (a & b)).all()
    assert (o["vote"][:, 0] == ((a + b + c) >= 2)).all()
    assert (o["any"][:, 0] == (a | b | c)).all()
    assert io_spec(chip, "streaming")["mode"] == "streaming"


def test_compose_level1_netlist(chip, tmp_path):
    text, info = emit(chip)
    (tmp_path / "d.v").write_text(text)
    syn = synth_generic(tmp_path / "d.v", info["top"], tmp_path / "syn")
    res = check(chip, syn["netlist_json"], info, random_inputs(chip, 4000, 1))
    assert res["bit_exact"] and res["n"] == 4000, res["pairs"]


@pytest.mark.parametrize("tt", [True, False])
def test_compose_level3_stream(chip, tmp_path, tt):
    r = rtl_simulate(chip, tmp_path, n=300, tt=tt, seed=3)
    assert r["passed"] and r["mismatches"] == 0 and r["vectors"] == 300, r
    assert r["lint"]["ok"], r["lint"]
    assert r["verification_level"] == 3


def test_compose_rejects_bad_fusion():
    with pytest.raises(IRError):
        compose({"a": to_ir(SPIKE)}, [{"name": "f", "op": "kofn", "k": 3, "inputs": ["a_y"]}])
    heads = {"a": to_ir(SPIKE), "b": small_head(1, 5, 4, False)}
    with pytest.raises(IRError):  # same port name 'x' with different specs cannot be shared
        compose(heads, shared_inputs=True)
