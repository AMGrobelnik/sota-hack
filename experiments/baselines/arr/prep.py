"""Beat extraction for MIT-BIH Arrhythmia, following the baseline's published code (flexwnn,
coin/arrhythmia/preprocess_mitdb.py and load_data.py) as closely as its release allows.

Per record: lead 0 (MLII), the Pan-Tompkins band-pass (original 200 Hz difference equations run
at 360 Hz, which the paper describes as a 9 to 21.6 Hz band), a 187-sample window centred on
every annotation i in [2, len-2] whose symbol maps to an AAMI class, per-window min-max
normalisation scaled to 16 bits. Also RR intervals from the beat annotations (for the extended
track and the DS1/DS2 track).

The baseline's own PTA_1 filter file is not in its repository; this file implements the
original PTA low-pass and high-pass and removes their 21-sample group delay (documented
difference).

Usage: python -I prep.py <mitdb dir> <out npz>
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import wfdb
from scipy.signal import lfilter

RECORDS = [
    100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 111, 112, 113, 114, 115, 116, 117, 118,
    119, 121, 122, 123, 124, 200, 201, 202, 203, 205, 207, 208, 209, 210, 212, 213, 214, 215,
    217, 219, 220, 221, 222, 223, 228, 230, 231, 232, 233, 234,
]
# Baseline label map (preprocess_mitdb.label_encoding), including its use of '+' as class 0.
LABEL = {
    **{s: 0 for s in "+NLRej"},
    **{s: 1 for s in "AaJS"},
    **{s: 2 for s in "V[!]E"},
    "F": 3,
    **{s: 4 for s in "/fQ"},
}
BEATS = set("NLRejAaJSVEF/fQ")  # true beat annotations, used for RR intervals
HALF_LO, HALF_HI = 93, 94
PTA_DELAY = 21  # 5 (low-pass) + 16 (high-pass) samples
N_AVG = 8  # causal running mean of the last 8 RR intervals


def pta_bandpass(x: np.ndarray) -> np.ndarray:
    """Original Pan-Tompkins integer low-pass then high-pass, delay removed."""
    b_lp = np.zeros(13)
    b_lp[[0, 6, 12]] = [1, -2, 1]
    y = lfilter(b_lp, [1, -2, 1], x)
    b_hp = np.zeros(33)
    b_hp[0], b_hp[16], b_hp[17], b_hp[32] = -1 / 32, 1, -1, 1 / 32
    y = lfilter(b_hp, [1, -1], y)
    out = np.empty_like(y)
    out[:-PTA_DELAY] = y[PTA_DELAY:]
    out[-PTA_DELAY:] = y[-1]
    return out


def rr_features(pos: np.ndarray, beat_pos: np.ndarray) -> np.ndarray:
    """pre RR, post RR and causal mean of the last N_AVG RR intervals, in samples."""
    k = np.clip(np.searchsorted(beat_pos, pos), 1, len(beat_pos) - 2)
    # snap to the nearest beat (rhythm '+' marks sit on or next to a beat)
    left_closer = np.abs(beat_pos[k - 1] - pos) < np.abs(beat_pos[k] - pos)
    k = np.where(left_closer, k - 1, k)
    k = np.clip(k, 1, len(beat_pos) - 2)
    rr = np.diff(beat_pos)
    pre = rr[k - 1]
    post = rr[k]
    csum = np.concatenate([[0], np.cumsum(rr)])
    lo = np.maximum(k - N_AVG, 0)
    avg = (csum[k] - csum[lo]) / np.maximum(k - lo, 1)
    return np.stack([pre, post, avg], axis=1)


def main(db: Path, out: Path) -> None:
    xs, ys, recs, poss, rrs, syms = [], [], [], [], [], []
    skipped = 0
    for r in RECORDS:
        sig, _ = wfdb.rdsamp(str(db / str(r)), channels=[0])
        ann = wfdb.rdann(str(db / str(r)), "atr")
        f = pta_bandpass(np.squeeze(sig).astype(np.float64))
        sym = ann.symbol
        smp = np.asarray(ann.sample)
        beat_pos = np.asarray([s for s, c in zip(smp, sym) if c in BEATS])
        keep_pos, keep_y, keep_s = [], [], []
        for i in range(2, len(sym) - 1):
            lab = LABEL.get(sym[i])
            if lab is None:
                continue
            p = int(smp[i])
            if p - HALF_LO < 0 or p + HALF_HI > len(f):
                skipped += 1
                continue
            keep_pos.append(p)
            keep_y.append(lab)
            keep_s.append(ord(sym[i]))
        pos = np.asarray(keep_pos)
        syms.append(np.asarray(keep_s, dtype=np.uint8))
        w = np.stack([f[p - HALF_LO : p + HALF_HI] for p in pos])
        w = w - w.min(axis=1, keepdims=True)
        w = w / w.max(axis=1, keepdims=True)
        xs.append((w * 65535).astype(np.int64).astype(np.uint16))
        ys.append(np.asarray(keep_y, dtype=np.int8))
        recs.append(np.full(len(pos), r, dtype=np.int16))
        poss.append(pos.astype(np.int32))
        rrs.append(rr_features(pos, beat_pos).astype(np.float32))
    np.savez_compressed(
        out,
        x16=np.concatenate(xs),
        y5=np.concatenate(ys),
        rec=np.concatenate(recs),
        pos=np.concatenate(poss),
        rr=np.concatenate(rrs),
        sym=np.concatenate(syms),
    )
    y = np.concatenate(ys)
    print("beats", len(y), "per class", np.bincount(y, minlength=5).tolist(), "skipped", skipped)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
