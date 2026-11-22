"""Formal proof on the spike chip (2.2k gates): the real netlist is proved; a one-gate mutant is refuted."""
import json
import re
from pathlib import Path

import pytest

from chiplab import config
from chiplab.emit.verilog import emit
from chiplab.hw.yosys import synth_generic
from chiplab.verify.formal import prove

pytestmark = [pytest.mark.slow,
              pytest.mark.skipif(not (config.find_bin("yosys") and config.find_bin("yosys-abc")), reason="yosys not installed")]
FIX = Path(__file__).resolve().parent.parent / "fixtures" / "spike_best.json"


def spike_ir():
    m = json.loads(FIX.read_text()); c = m["cfg"]
    return {"ir": "chipir/1", "name": "spike", "inputs": [{"name": "x", "lanes": c["L"], "bits": c["bits"], "signed": c["feat"] == "drr"}],
            "nodes": [{"id": "h0", "op": "matvec", "src": "x", "W": m["W1"], "b": m["b1"]},
                      {"id": "h1", "op": "shift", "src": "h0", "k": m["shift"]},
                      {"id": "h2", "op": "clip", "src": "h1", "lo": 0, "hi": m["amax"]},
                      {"id": "s", "op": "matvec", "src": "h2", "W": [m["W2"]], "b": [m["b2"]]},
                      {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}],
            "outputs": [{"name": "y", "src": "y"}], "meta": {}}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("spike")
    ir = spike_ir(); text, info = emit(ir)
    (d / "d.v").write_text(text)
    syn = synth_generic(d / "d.v", info["top"], d / "syn")
    return d, ir, info, Path(syn["gate_verilog"])


def test_spike_proved(built):
    d, ir, info, gates = built
    r = prove(ir, info, gates, d / "d.v", d / "proof", timeout=120)
    assert r["proved"] is True and r["verification_level"] == 2


def test_small_chip_proved_against_golden(tmp_path):
    from test_fpga import tiny_ir
    ir = tiny_ir(); text, info = emit(ir)
    (tmp_path / "d.v").write_text(text)
    syn = synth_generic(tmp_path / "d.v", info["top"], tmp_path / "syn")
    r = prove(ir, info, Path(syn["gate_verilog"]), tmp_path / "d.v", tmp_path / "p", timeout=120, golden=True)
    assert r["proved"] is True and "golden" in r["against"] and all(n["proved"] for n in r["nodes"])


def test_mutant_refuted(built):
    d, ir, info, gates = built
    g = gates.read_text()
    m = re.search(r"assign (\S+) = (\S+) \^ (\S+);", g)
    bad = d / "bad.v"
    bad.write_text(g.replace(m.group(0), f"assign {m.group(1)} = ~({m.group(2)} ^ {m.group(3)});", 1))
    r = prove(ir, info, bad, d / "d.v", d / "proof_bad", timeout=120)
    assert r["proved"] is False and r["verification_level"] < 2
