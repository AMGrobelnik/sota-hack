"""Streaming wrapper: multi-word lanes (> 15 bits), several ports, single-transfer frames, and a negative control."""
import numpy as np

from chiplab.emit.stream import emit_stream, frame_words, transfers
from chiplab.ingest.intnn import to_ir
from chiplab.ir.schema import validate
from chiplab.verify.rtlsim import rtl_simulate


def wide_ir():
    return validate({"ir": "chipir/1", "name": "wide",
                     "inputs": [{"name": "a", "lanes": 3, "bits": 20, "signed": True},
                                {"name": "b", "lanes": 2, "bits": 3, "signed": False}],
                     "nodes": [{"id": "s", "op": "matvec", "src": "a", "W": [[1, -2, 1], [0, 1, 1]], "b": [5, -7]},
                               {"id": "c", "op": "cmp", "src": "s", "rel": "gt", "t": [0, 100]},
                               {"id": "m", "op": "max", "src": "b", "groups": [[0, 1]]},
                               {"id": "k", "op": "cmp", "src": "m", "rel": "ge", "t": [4]}],
                     "outputs": [{"name": "dec", "src": "c"}, {"name": "hi", "src": "k"}, {"name": "mx", "src": "m"}]})


def test_transfer_layout():
    _, info = emit_stream(wide_ir())
    tr = transfers(info["core"])
    assert len(tr) == 3 * 2 + 2 and info["transfers_per_frame"] == 8 and info["counter_bits"] == 3
    w = frame_words(info["core"], {"a": np.array([[-1, 1, 2 ** 18]]), "b": np.array([[5, 2]])})[0]
    assert w[0] == (2 ** 15 - 1) and w[1] == (2 ** 5 - 1) and w[2] == 1 and w[3] == 0 and w[6] == 5 and w[7] == 2


def test_wide_multiport_level3(tmp_path):
    for tt in (True, False):
        r = rtl_simulate(wide_ir(), tmp_path / str(tt), n=200, tt=tt, seed=1)
        assert r["passed"] and r["lint"]["ok"], r


def test_single_transfer_frame(tmp_path):
    ir = validate({"ir": "chipir/1", "name": "one", "inputs": [{"name": "x", "lanes": 1, "bits": 5, "signed": True}],
                   "nodes": [{"id": "a", "op": "abs", "src": "x"}], "outputs": [{"name": "y", "src": "a"}]})
    r = rtl_simulate(ir, tmp_path, n=100)
    assert r["passed"] and r["transfers_per_frame"] == 1, r


def test_negative_control_detects_wrong_model(tmp_path):
    import json
    spike = json.load(open("fixtures/spike_best.json"))
    good = to_ir(spike)
    bad = json.loads(json.dumps(good)); bad["nodes"][-2]["b"] = [bad["nodes"][-2]["b"][0] + 9]
    r = rtl_simulate(good, tmp_path, n=300, reference=bad)
    assert not r["passed"] and r["mismatches"] > 0
