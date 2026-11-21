import numpy as np
import torch

from chiplab.data.encode import encode, encoding_key

LMAX = 25


def _spike_quantise(rr, L, bits, feat):
    """spike/src/common.py quantise, verbatim (float32 torch)."""
    step = 2048.0 / (2 ** bits)
    q = torch.clamp(torch.floor(torch.as_tensor(rr) / step), 0, 2 ** bits - 1)
    if feat == "rr":
        return q[:, LMAX - L:]
    d = q[:, 1:] - q[:, :-1]
    d = torch.clamp(d, -(2 ** (bits - 1)), 2 ** (bits - 1) - 1)
    return d[:, -L:]


def _rr(N=500, seed=0):
    r = np.random.default_rng(seed)
    return (r.normal(800, 250, size=(N, LMAX)).clip(150, 3000)).astype(np.float32)


def test_uniform_and_delta_match_spike():
    rr = _rr()
    X = rr.astype(np.float64)[:, :, None]
    for bits in (4, 5, 6, 8):
        for L in (8, 16, 24):
            u, ins, _ = encode(X, {"L": L, "encoder": "uniform", "bits": bits, "lo": 0, "hi": 2048})
            assert ins == {"lanes": L, "bits": bits, "signed": False}
            assert (u == _spike_quantise(rr, L, bits, "rr").numpy().astype(np.int64)).all()
            d, ins, _ = encode(X, {"L": L, "encoder": "delta", "bits": bits, "lo": 0, "hi": 2048})
            assert ins["signed"] and d.min() >= -(2 ** (bits - 1)) and d.max() <= 2 ** (bits - 1) - 1
            assert (d == _spike_quantise(rr, L, bits, "drr").numpy().astype(np.int64)).all()


def test_thermometer_fitted_on_train_only_and_reused():
    X = _rr().astype(np.float64)[:, :, None]
    t, ins, fitted = encode(X[:400], {"L": 4, "encoder": "thermometer", "levels": 4}, fit_X=X[:400])
    assert ins == {"lanes": 12, "bits": 1, "signed": False} and set(np.unique(t)) <= {0, 1}
    t2, _, _ = encode(X[400:], fitted)
    assert t2.shape == (100, 12)
    assert encoding_key(fitted) == encoding_key(dict(fitted))


def test_auto_range():
    X = _rr().astype(np.float64)[:, :, None]
    q, ins, f = encode(X, {"L": 8, "encoder": "uniform", "bits": 4, "lo": "auto", "hi": "auto"}, fit_X=X)
    assert "lo" in f["fitted"] and q.max() == 15 and q.min() == 0
