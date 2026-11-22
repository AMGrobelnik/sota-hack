"""Model ingest: chipir JSON and intnn parameters -> chipir/1, checked against independent numpy math."""
import json

import numpy as np

from chiplab.ingest.chipir import load
from chiplab.ingest.intnn import to_ir
from chiplab.ir.interp import run

SPIKE = json.load(open("fixtures/spike_best.json"))


def test_spike_intnn_equals_formula():
    ir = to_ir(SPIKE)
    assert ir["inputs"][0] == {"name": "x", "lanes": 8, "bits": 6, "signed": True}
    X = np.random.default_rng(0).integers(-32, 32, size=(5000, 8))
    h = np.clip((X @ np.array(SPIKE["W1"]).T + np.array(SPIKE["b1"])) >> SPIKE["shift"], 0, SPIKE["amax"])
    ref = ((h @ np.array(SPIKE["W2"]) + SPIKE["b2"]) > 0).astype(int)
    assert (run(ir, X)["y"][:, 0] == ref).all()


def test_intnn_multilayer_multiclass():
    r = np.random.default_rng(1)
    p = {"layers": [{"W": r.integers(-1, 2, (6, 5)).tolist(), "b": r.integers(-3, 4, 6).tolist(), "shift": 1, "amax": 7},
                    {"W": r.integers(-3, 4, (4, 6)).tolist(), "b": [0, 1, 2, 3], "shift": 2, "amax": 15}],
         "Wo": r.integers(-2, 3, (3, 4)).tolist(), "bo": [0, -1, 1], "out_dim": 3}
    ir = to_ir(p, {"lanes": 5, "bits": 4, "signed": False})
    X = r.integers(0, 16, size=(3000, 5))
    h = X
    for L in p["layers"]:
        h = np.clip((h @ np.array(L["W"]).T + np.array(L["b"])) >> L["shift"], 0, L["amax"])
    ref = np.argmax(h @ np.array(p["Wo"]).T + np.array(p["bo"]), axis=1)
    assert (run(ir, X)["y"][:, 0] == ref).all()


def test_chipir_load_roundtrip(tmp_path):
    ir = to_ir(SPIKE)
    (tmp_path / "m.json").write_text(json.dumps(ir))
    assert load(tmp_path / "m.json")["nodes"] == ir["nodes"]
    assert load(json.dumps(ir))["outputs"] == ir["outputs"]
