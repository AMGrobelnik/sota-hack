"""intnn: predict() (torch, the training model) == the lowered integer math, for every candidate."""
import numpy as np
import pytest
import torch

from chiplab.plugins.base import BatchInputs
from chiplab.plugins.families.intnn import FAMILY, numpy_reference


def _data(N=3000, seed=0):
    r = np.random.default_rng(seed)
    a = r.integers(0, 16, size=(N, 12)); b = r.integers(-8, 8, size=(N, 8))
    y = ((a[:, :4].sum(1) - a[:, 4:8].sum(1) + b[:, 0] * 2) > 0).astype(int)
    return a, b, y


@pytest.mark.parametrize("dev", ["cuda" if torch.cuda.is_available() else "cpu"])
def test_predict_equals_lowered_integer_math(dev):
    a, b, y = _data()
    ins = {"u": {"lanes": 12, "bits": 4, "signed": False}, "s": {"lanes": 8, "bits": 4, "signed": True}}
    cfgs = [{"hidden": [8], "wtype": "ternary"}, {"hidden": [4], "wtype": "binary"},
            {"hidden": [16], "wtype": "kbit", "wbits": 3}, {"hidden": [8, 4], "wtype": "ternary", "abits": 3},
            {"hidden": [6], "wtype": "ternary"}, {"hidden": [5, 5], "wtype": "kbit", "wbits": 4},
            {"hidden": [3], "wtype": "binary", "abits": 2}, {"hidden": [12], "wtype": "ternary", "abits": 5}]
    cfgs = [{**c, "epochs": 2, "batch_size": 256} for c in cfgs]
    keys = ["u", "s", "u", "s", "u", "s", "u", "s"]
    t = {"u": torch.tensor(a, dtype=torch.float32, device=dev), "s": torch.tensor(b, dtype=torch.float32, device=dev)}
    bi = BatchInputs(keys=keys, tensors=t, in_specs=ins, y=torch.tensor(y, device=dev))
    st = FAMILY.train(cfgs, bi, dev, {"n_classes": 2})
    p = FAMILY.predict(st, BatchInputs(keys=keys, tensors=t, in_specs=ins), dev)
    for k in range(len(cfgs)):
        X = a if keys[k] == "u" else b
        ref = numpy_reference(FAMILY.int_params(st, k), X)
        assert (ref == p[k]).all(), f"candidate {k}: {(ref != p[k]).sum()} mismatches"
        ir = FAMILY.lower(st, k, ins[keys[k]])
        assert ir["ir"] == "chipir/1" and ir["outputs"][0]["name"] == "y"
        try:
            from chiplab.ir import interp
        except ImportError:
            continue
        if hasattr(interp, "run"):
            out = interp.run(ir, X)["y"]
            assert (np.asarray(out).reshape(-1) == p[k]).all(), f"candidate {k}: interp mismatch"


def test_multiclass_argmax():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    r = np.random.default_rng(1)
    X = r.integers(0, 8, size=(2000, 6)); y = (X[:, 0] // 3).clip(0, 2)
    ins = {"u": {"lanes": 6, "bits": 3, "signed": False}}
    t = {"u": torch.tensor(X, dtype=torch.float32, device=dev)}
    bi = BatchInputs(keys=["u", "u"], tensors=t, in_specs=ins, y=torch.tensor(y, device=dev))
    st = FAMILY.train([{"hidden": [8], "epochs": 3}, {"hidden": [4], "wtype": "kbit", "epochs": 3}], bi, dev, {"n_classes": 3})
    p = FAMILY.predict(st, BatchInputs(keys=["u", "u"], tensors=t, in_specs=ins), dev)
    for k in range(2):
        assert (numpy_reference(FAMILY.int_params(st, k), X) == p[k]).all()
