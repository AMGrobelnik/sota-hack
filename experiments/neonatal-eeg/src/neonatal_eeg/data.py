"""Read the Helsinki neonatal EEG recordings, build the bipolar montage, label seconds and compute
integer-friendly window features.

Everything here is fixed before any model is trained; the numbers are documented in README.md.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from scipy import signal

FS_IN = 256          # native rate of every EEG channel in the record
DECIM = 4            # 256 Hz -> 64 Hz after the 30 Hz low-pass
FS = FS_IN // DECIM
WIN_S = 8            # window length, seconds
HOP_S = 1            # hop, seconds
BG_TAU_S = 900       # time constant of the causal background average for the relative features

# Standard neonatal 18-channel bipolar "double banana" montage (the full montage).
DOUBLE_BANANA = [
    ("Fp2", "F4"), ("F4", "C4"), ("C4", "P4"), ("P4", "O2"),
    ("Fp1", "F3"), ("F3", "C3"), ("C3", "P3"), ("P3", "O1"),
    ("Fp2", "F8"), ("F8", "T4"), ("T4", "T6"), ("T6", "O2"),
    ("Fp1", "F7"), ("F7", "T3"), ("T3", "T5"), ("T5", "O1"),
    ("Fz", "Cz"), ("Cz", "Pz"),
]
# Reduced channel budgets, chosen from standard positions before any data was looked at.
BUDGETS: dict[int, list[tuple[str, str]]] = {
    1: [("C3", "C4")],                                   # cross-cerebral, as single-channel aEEG
    2: [("C3", "P3"), ("C4", "P4")],                     # two-channel aEEG derivations
    4: [("C3", "P3"), ("C4", "P4"), ("T3", "O1"), ("T4", "O2")],
    18: DOUBLE_BANANA,
}
ALL_DERIVS = sorted({d for ds in BUDGETS.values() for d in ds})
FEATURES = ["line_length", "zero_cross_low", "ll_rel_bg", "low_ll_rel_bg", "amp_rel_bg", "hf_rel_bg"]


def read_consensus(ann_dir: Path, baby: int, *, min_agree: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """Per-second labels for one baby (1-based column): (consensus 0/1, votes 0..3), trimmed to the recording."""
    votes = None
    for name in ("annotations_2017_A_fixed.csv", "annotations_2017_B.csv", "annotations_2017_C.csv"):
        with open(ann_dir / name, newline="") as f:
            rows = list(csv.reader(f))
        col = [r[baby - 1].strip() for r in rows[1:]]
        col = [c for c in col if c != ""]
        a = np.array([int(float(c)) for c in col], dtype=np.int64)
        votes = a if votes is None else votes[: len(a)] + a[: len(votes)]
    assert votes is not None
    return (votes >= min_agree).astype(np.int8), votes.astype(np.int8)


def read_edf(path: Path) -> tuple[list[str], list[float], list[np.ndarray]]:
    """Minimal EDF reader (header fields as in the EDF specification; 16-bit samples), in physical units.
    Used instead of pyedflib, which rejects some of this record's headers for label formatting."""
    with open(path, "rb") as f:
        head = f.read(256)
        n_rec = int(head[236:244].decode("ascii").strip())
        dur = float(head[244:252].decode("ascii").strip())
        ns = int(head[252:256].decode("ascii").strip())
        h = f.read(256 * ns)
        raw = np.frombuffer(f.read(), dtype="<i2")

    def field(off: int, width: int) -> list[str]:
        base = off * ns
        return [h[base + i * width: base + (i + 1) * width].decode("ascii", "replace").strip() for i in range(ns)]

    labels = field(0, 16)
    pmin = np.array(field(104, 8), float); pmax = np.array(field(112, 8), float)
    dmin = np.array(field(120, 8), float); dmax = np.array(field(128, 8), float)
    nsamp = np.array(field(216, 8), int)
    rec_len = int(nsamp.sum())
    if n_rec < 0 or raw.size < n_rec * rec_len:
        n_rec = raw.size // rec_len
    data = raw[: n_rec * rec_len].reshape(n_rec, rec_len)
    gain = (pmax - pmin) / (dmax - dmin)
    sigs, off = [], 0
    for i in range(ns):
        d = data[:, off: off + nsamp[i]].reshape(-1).astype(np.float64)
        sigs.append((d - dmin[i]) * gain[i] + pmin[i])
        off += nsamp[i]
    return labels, [nsamp[i] / dur for i in range(ns)], sigs


def read_bipolar(edf_path: Path) -> np.ndarray:
    """Return the derivations in ALL_DERIVS order, band-passed 0.5-30 Hz (causal 4th-order Butterworth),
    decimated to 64 Hz, in microvolts, shape [n_deriv, n_samples]."""
    raw_labels, fs, sigs = read_edf(edf_path)
    labels = [lab.upper().replace("EEG ", "").replace("-REF", "").strip() for lab in raw_labels]
    need = sorted({e for d in ALL_DERIVS for e in d})
    ref = {}
    for e in need:
        i = labels.index(e.upper())
        if int(fs[i]) != FS_IN:
            raise ValueError(f"{edf_path.name}: {e} at {fs[i]} Hz, expected {FS_IN}")
        ref[e] = sigs[i]
    sos = signal.butter(4, [0.5, 30.0], btype="bandpass", fs=FS_IN, output="sos")
    out = []
    for a, b in ALL_DERIVS:
        x = signal.sosfilt(sos, ref[a] - ref[b])
        out.append(x[::DECIM])
    return np.asarray(out, dtype=np.float64)


def window_features(x: np.ndarray) -> np.ndarray:
    """Float features [n_windows, n_deriv, 5] for 8 s windows every 1 s; window k covers seconds [k, k+8)."""
    n_sec = x.shape[1] // FS
    x = x[:, : n_sec * FS]
    dx = np.abs(np.diff(x, axis=1, prepend=x[:, :1]))
    ax = np.abs(x)
    box = signal.lfilter(np.ones(4) / 4.0, [1.0], x, axis=1)          # 4-sample moving average
    hf = np.abs(x - box)
    low = signal.lfilter(np.ones(16) / 16.0, [1.0], x, axis=1)        # 16-sample moving average: ~0.5-4 Hz
    dlow = np.abs(np.diff(low, axis=1, prepend=low[:, :1]))
    zc = (np.signbit(low[:, 1:]) != np.signbit(low[:, :-1])).astype(np.float64)
    zc = np.concatenate([np.zeros((x.shape[0], 1)), zc], axis=1)

    def per_sec(v):
        return v.reshape(v.shape[0], n_sec, FS).sum(axis=2)

    def per_win(s):
        c = np.cumsum(np.pad(s, ((0, 0), (1, 0))), axis=1)
        return (c[:, WIN_S:] - c[:, :-WIN_S]) / (WIN_S * FS)

    ll, am, z, h, lll = (per_win(per_sec(v)) for v in (dx, ax, zc, hf, dlow))
    # causal background: exponential average of earlier windows' values (the first window seeds it)
    def rel(v):
        alpha = 1.0 / BG_TAU_S
        bg = np.empty_like(v)
        bg[:, 0] = v[:, 0]
        for k in range(1, v.shape[1]):
            bg[:, k] = (1 - alpha) * bg[:, k - 1] + alpha * v[:, k - 1]
        return v / np.maximum(bg, 1e-6)

    feats = np.stack([ll, z * FS, rel(ll), rel(lll), rel(am), rel(h)], axis=2)   # [deriv, win, feat]
    return np.transpose(feats, (1, 0, 2))


def window_labels(cons: np.ndarray, n_win: int) -> np.ndarray:
    """Training label of window k: at least half of its seconds are consensus seizure."""
    c = np.cumsum(np.concatenate([[0], cons[: n_win + WIN_S - 1].astype(np.int64)]))
    frac = (c[WIN_S:WIN_S + n_win] - c[:n_win]) / WIN_S
    return (frac >= 0.5).astype(np.int8)


def baby_cache(edf_dir: Path, cache_dir: Path, baby: int) -> Path:
    """Compute and cache features and labels for one baby."""
    out = cache_dir / f"b{baby:02d}.npz"
    if out.exists():
        return out
    cons, votes = read_consensus(edf_dir, baby)
    x = read_bipolar(edf_dir / f"eeg{baby}.edf")
    feats = window_features(x)
    n_sec = min(len(cons), x.shape[1] // FS)
    n_win = n_sec - WIN_S + 1
    feats = feats[:n_win]
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = cache_dir / f"b{baby:02d}.tmp.npz"
    np.savez(tmp, feats=feats.astype(np.float32), cons=cons[:n_sec], votes=votes[:n_sec],
             ywin=window_labels(cons[:n_sec], n_win))
    tmp.rename(out)
    return out
