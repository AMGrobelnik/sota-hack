"""The chip boundary: float frame windows -> the integers the chip's input pins receive.

Computed in numpy float64 once per encoding, so training, the integer model, the RTL testbench and the
netlist all see identical integers.

spec = {"L": frames used (the LAST L of the window), "features": [frame feature idx] | absent (all),
        "encoder": "uniform" | "delta" | "thermometer", ...encoder params}
  (lo / hi may be "auto": fitted on train data, 0.1% / 99.9% quantiles)
  uniform     {bits, lo, hi}: q = clip(floor((v-lo)/step), 0, 2^bits-1), step = (hi-lo)/2^bits   unsigned
  delta       {bits, lo, hi}: q as uniform over L+1 frames, d = q[t]-q[t-1], clip to signed bits     signed
  thermometer {levels}: per feature, levels-1 thresholds = train quantiles; lane = (v > thr)          1-bit
Lane order: lane = t * F_used + f   (thermometer: (t * F_used + f) * (levels-1) + j)
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

ENCODERS = ("uniform", "delta", "thermometer")


def encoding_key(spec: dict) -> str:
    keep = {k: v for k, v in spec.items() if k != "fitted"}
    if "fitted" in spec:
        keep["fitted"] = spec["fitted"]
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:12]


def _feats(X: np.ndarray, spec: dict) -> list[int]:
    f = spec.get("features")
    F = X.shape[2]
    f = list(range(F)) if f is None else [int(i) for i in f]
    if not f or any(i < 0 or i >= F for i in f):
        raise ValueError(f"features {f} out of range for {F} frame features")
    return f


def _range(spec: dict, fit_X, f, fitted: dict):
    """lo/hi given, or "auto": fitted on train data (0.1% / 99.9% quantiles of the used features)."""
    lo, hi = spec.get("lo", "auto"), spec.get("hi", "auto")
    if lo == "auto" or hi == "auto":
        if "fitted" in spec and "lo" in spec["fitted"]:
            return spec["fitted"]["lo"], spec["fitted"]["hi"]
        if fit_X is None:
            raise ValueError("lo/hi 'auto' must be fitted on train data (pass fit_X)")
        src = np.asarray(fit_X, dtype=np.float64)[:, :, f]
        flo, fhi = float(np.quantile(src, 0.001)), float(np.quantile(src, 0.999))
        lo = flo if lo == "auto" else lo
        hi = fhi if hi == "auto" else hi
        if hi <= lo:
            hi = lo + 1.0
        fitted["fitted"] = {**fitted.get("fitted", {}), "lo": lo, "hi": hi}
    return float(lo), float(hi)


def _uniform(v: np.ndarray, bits: int, lo: float, hi: float) -> np.ndarray:
    step = (float(hi) - float(lo)) / (2 ** bits)
    if step <= 0:
        raise ValueError("hi must be > lo")
    return np.clip(np.floor((v.astype(np.float64) - float(lo)) / step), 0, 2 ** bits - 1).astype(np.int64)


def encode(X: np.ndarray, spec: dict, fit_X: np.ndarray | None = None):
    """X float [N, Lw, F] -> (int64 [N, lanes], in_spec {lanes, bits, signed}, fitted spec)."""
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 3:
        raise ValueError("X must be [N, window frames, features]")
    enc = spec.get("encoder", "uniform")
    if enc not in ENCODERS:
        raise ValueError(f"unknown encoder {enc!r}; known: {ENCODERS}")
    L = int(spec["L"])
    Lw = X.shape[1]
    f = _feats(X, spec)
    fitted = dict(spec)
    if enc == "uniform":
        if L > Lw:
            raise ValueError(f"L={L} > window frames {Lw}")
        bits = int(spec["bits"])
        lo, hi = _range(spec, fit_X, f, fitted)
        q = _uniform(X[:, Lw - L:, :][:, :, f], bits, lo, hi)
        out = q.reshape(len(X), -1)
        in_spec = {"lanes": out.shape[1], "bits": bits, "signed": False}
    elif enc == "delta":
        if L + 1 > Lw:
            raise ValueError(f"delta needs L+1={L + 1} frames, window has {Lw}")
        bits = int(spec["bits"])
        lo, hi = _range(spec, fit_X, f, fitted)
        q = _uniform(X[:, Lw - L - 1:, :][:, :, f], bits, lo, hi)
        d = np.clip(q[:, 1:, :] - q[:, :-1, :], -(2 ** (bits - 1)), 2 ** (bits - 1) - 1)
        out = d.reshape(len(X), -1)
        in_spec = {"lanes": out.shape[1], "bits": bits, "signed": True}
    else:  # thermometer
        if L > Lw:
            raise ValueError(f"L={L} > window frames {Lw}")
        levels = int(spec.get("levels", 4))
        if levels < 2:
            raise ValueError("thermometer needs levels >= 2")
        if "fitted" in spec:
            thr = np.asarray(spec["fitted"]["thresholds"], dtype=np.float64)
        else:
            if fit_X is None:
                raise ValueError("thermometer must be fitted on train data (pass fit_X)")
            src = np.asarray(fit_X, dtype=np.float64)[:, :, f].reshape(-1, len(f))
            qs = np.arange(1, levels) / levels
            thr = np.quantile(src, qs, axis=0).T            # [F_used, levels-1]
            fitted["fitted"] = {"thresholds": thr.tolist()}
        v = X[:, Lw - L:, :][:, :, f]                        # [N, L, F]
        out = (v[..., None] > thr[None, None, :, :]).astype(np.int64).reshape(len(X), -1)
        in_spec = {"lanes": out.shape[1], "bits": 1, "signed": False}
    return out, in_spec, fitted
