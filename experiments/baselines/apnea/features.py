"""Per-minute RR-interval features for the PhysioNet Apnea-ECG database.

Reads only the database's machine beat annotations (.qrs, sqrs125, 100 Hz) and the per-minute apnoea
labels (.apn for the 35 learning records, the challenge's event-2-answers for the 35 test records, cross
checked against the x??.apn files). Writes one compressed array file of features and labels, kept next to
the data (outside the repository): no signal sample is read or stored.

Run with: python -I features.py <apnea-ecg dir> <challenge-2000 dir> <out .npz>
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import wfdb

FS = 100  # Hz, Apnea-ECG sampling rate
MIN = 60 * FS  # samples per minute
LEARN = [f"a{i:02d}" for i in range(1, 21)] + [f"b{i:02d}" for i in range(1, 6)] + [f"c{i:02d}" for i in range(1, 11)]
TEST = [f"x{i:02d}" for i in range(1, 36)]

FEATURE_NAMES = [
    "mean_rr_1",     # mean RR in the minute (ms)
    "sd_rr_1",       # SD of RR in the minute (ms)
    "rmssd_1",       # RMS of successive differences in the minute (ms)
    "pnn50_1",       # fraction of successive differences > 50 ms in the minute (x1000)
    "range_rr_1",    # max - min RR in the minute (ms)
    "sd_rr_5",       # SD of RR over the centred 5-minute window (ms)
    "sd_rr_3",       # SD of RR over the centred 3-minute window (ms)
    "sd_mean_5",     # SD of the five minute-means in the 5-minute window (ms)
    "cv_band_5",     # RR power in 0.01-0.05 Hz over the 5-minute window, 1 Hz resampled (ms, sqrt)
    "cv_frac_5",     # that power as a fraction of 0.01-0.5 Hz power (x1000)
    "hf_frac_5",     # 0.15-0.4 Hz power fraction over the 5-minute window (x1000)
    "rel_mean_1_5",  # mean RR of the minute minus mean RR of the 5-minute window (ms)
    "mad_rr_1",      # median absolute deviation from the minute median (ms)
    "n_beats_1",     # beats accepted in the minute
    "cv_band_3",     # as cv_band_5 over the centred 3-minute window
    "cv_band_9",     # as cv_band_5 over the centred 9-minute window
    "cv_frac_9",     # as cv_frac_5 over the centred 9-minute window
    "hf_frac_9",     # as hf_frac_5 over the centred 9-minute window
    "sd_mean_9",     # SD of the nine minute-means in the 9-minute window (ms)
    "lag1_corr_1",   # lag-1 serial correlation of RR in the minute (x1000, offset 1000)
]


def rr_series(rec_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Beat times (s) and RR intervals (ms) of accepted beats: RR in [300, 2000] ms and within 20 percent of
    the median of its 11 neighbours (the outlier rule in the spirit of apdet's filt 0.2)."""
    ann = wfdb.rdann(str(rec_path), "qrs")
    t = np.asarray(ann.sample, dtype=np.float64) / FS
    rr = np.diff(t) * 1000.0
    tt = t[1:]
    ok = (rr >= 300) & (rr <= 2000)
    tt, rr = tt[ok], rr[ok]
    if len(rr) > 11:
        pad = np.pad(rr, 5, mode="edge")
        med = np.median(np.lib.stride_tricks.sliding_window_view(pad, 11), axis=1)
        keep = np.abs(rr - med) <= 0.2 * med
        tt, rr = tt[keep], rr[keep]
    return tt, rr


def band_powers(t: np.ndarray, rr: np.ndarray, t0: float, t1: float) -> tuple[float, float, float]:
    """Resample RR at 1 Hz over [t0, t1), remove the mean, periodogram; return (0.01-0.05 power,
    0.01-0.5 power, 0.15-0.4 power) in ms^2."""
    m = (t >= t0) & (t < t1)
    if m.sum() < 20:
        return 0.0, 0.0, 0.0
    grid = np.arange(t0, t1, 1.0)
    x = np.interp(grid, t[m], rr[m])
    x = x - x.mean()
    x = x * np.hanning(len(x))
    p = np.abs(np.fft.rfft(x)) ** 2 / len(x)
    f = np.fft.rfftfreq(len(x), d=1.0)
    cv = float(p[(f >= 0.01) & (f < 0.05)].sum())
    tot = float(p[(f >= 0.01) & (f < 0.5)].sum())
    hf = float(p[(f >= 0.15) & (f < 0.4)].sum())
    return cv, tot, hf


def minute_features(t: np.ndarray, rr: np.ndarray, n_min: int) -> np.ndarray:
    F = np.zeros((n_min, len(FEATURE_NAMES)), dtype=np.float64)
    idx = np.floor(t / 60.0).astype(int)
    per_min = [rr[idx == i] for i in range(n_min)]
    means = np.array([x.mean() if len(x) else np.nan for x in per_min])
    gmean = np.nanmean(means)
    means = np.where(np.isnan(means), gmean, means)
    for i in range(n_min):
        x = per_min[i]
        if len(x) >= 2:
            d = np.diff(x)
            F[i, 0] = x.mean()
            F[i, 1] = x.std()
            F[i, 2] = np.sqrt(np.mean(d ** 2))
            F[i, 3] = 1000.0 * np.mean(np.abs(d) > 50)
            F[i, 4] = x.max() - x.min()
            F[i, 12] = np.median(np.abs(x - np.median(x)))
        else:
            F[i, 0] = means[i]
        lo5, hi5 = max(0, i - 2), min(n_min, i + 3)
        lo3, hi3 = max(0, i - 1), min(n_min, i + 2)
        w5 = rr[(idx >= lo5) & (idx < hi5)]
        w3 = rr[(idx >= lo3) & (idx < hi3)]
        F[i, 5] = w5.std() if len(w5) >= 2 else 0.0
        F[i, 6] = w3.std() if len(w3) >= 2 else 0.0
        F[i, 7] = means[lo5:hi5].std()
        cv, tot, hf = band_powers(t, rr, 60.0 * lo5, 60.0 * hi5)
        F[i, 8] = np.sqrt(cv)
        F[i, 9] = 1000.0 * cv / tot if tot > 0 else 0.0
        F[i, 10] = 1000.0 * hf / tot if tot > 0 else 0.0
        F[i, 11] = means[i] - means[lo5:hi5].mean()
        F[i, 13] = len(x)
        cv3, _, _ = band_powers(t, rr, 60.0 * lo3, 60.0 * hi3)
        F[i, 14] = np.sqrt(cv3)
        lo9, hi9 = max(0, i - 4), min(n_min, i + 5)
        cv9, tot9, hf9 = band_powers(t, rr, 60.0 * lo9, 60.0 * hi9)
        F[i, 15] = np.sqrt(cv9)
        F[i, 16] = 1000.0 * cv9 / tot9 if tot9 > 0 else 0.0
        F[i, 17] = 1000.0 * hf9 / tot9 if tot9 > 0 else 0.0
        F[i, 18] = means[lo9:hi9].std()
        if len(x) >= 4 and x[:-1].std() > 0 and x[1:].std() > 0:
            F[i, 19] = 1000.0 + 1000.0 * np.corrcoef(x[:-1], x[1:])[0, 1]
        else:
            F[i, 19] = 1000.0
    return F


def labels_learning(rec_path: Path) -> np.ndarray:
    ann = wfdb.rdann(str(rec_path), "apn")
    return np.array([1 if s == "A" else 0 for s in ann.symbol], dtype=np.int64)


def labels_test(answers: Path) -> dict[str, np.ndarray]:
    out: dict[str, list[int]] = {}
    cur = None
    for line in answers.read_text().splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("x") and len(s) == 3:
            cur = s
            out[cur] = []
            continue
        parts = s.split()
        if cur is not None and len(parts) == 2:
            out[cur].extend(1 if c == "A" else 0 for c in parts[1])
    return {k: np.array(v, dtype=np.int64) for k, v in out.items()}


def main() -> None:
    db, ch, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    test_lab = labels_test(ch / "event-2-answers")
    feats, labs, rec_ids, minute_ix = [], [], [], []
    names = LEARN + TEST
    mism = 0
    for r, name in enumerate(names):
        if name in test_lab:
            y = test_lab[name]
            apn = db / f"{name}.apn"
            if apn.exists():
                y2 = labels_learning(db / name)
                if len(y2) != len(y) or (y2 != y).any():
                    mism += 1
                    print(f"WARN {name}: x.apn differs from event-2-answers ({len(y2)} vs {len(y)})")
        else:
            y = labels_learning(db / name)
        t, rr = rr_series(db / name)
        F = minute_features(t, rr, len(y))
        feats.append(F)
        labs.append(y)
        rec_ids.append(np.full(len(y), r))
        minute_ix.append(np.arange(len(y)))
        print(name, len(y), int(y.sum()), len(rr))
    np.savez_compressed(out, X=np.vstack(feats), y=np.concatenate(labs), rec=np.concatenate(rec_ids),
                        minute=np.concatenate(minute_ix), names=np.array(names), feature_names=np.array(FEATURE_NAMES))
    print("test label files differing from event-2-answers:", mism)


if __name__ == "__main__":
    main()
