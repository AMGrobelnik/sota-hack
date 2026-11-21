"""Shared: windows, record-level split, input quantisation, metrics."""
import numpy as np
import torch

LMAX = 25      # RR intervals per window (drr needs L+1 RR for L diffs, L<=24)
STRIDE = 4
MAX_WIN_PER_REC = 40
SEED = 0


def load_split(npz_path):
    d = np.load(npz_path, allow_pickle=False)
    labels, lens, flat = d["labels"], d["lens"], d["flat"]
    offs = np.concatenate([[0], np.cumsum(lens)])
    rng = np.random.default_rng(SEED)
    split = np.zeros(len(labels), dtype=int)  # 0 train 1 val 2 test
    for c in (0, 1):
        idx = np.where(labels == c)[0]
        rng.shuffle(idx)
        n = len(idx)
        split[idx[int(0.70 * n):int(0.85 * n)]] = 1
        split[idx[int(0.85 * n):]] = 2
    out = {s: {"rr": [], "y": [], "rec": []} for s in (0, 1, 2)}
    dropped = 0
    for i in range(len(labels)):
        rr = flat[offs[i]:offs[i + 1]]
        starts = list(range(0, len(rr) - LMAX + 1, STRIDE))[:MAX_WIN_PER_REC]
        if not starts:
            dropped += 1
            continue
        for st in starts:
            out[split[i]]["rr"].append(rr[st:st + LMAX])
            out[split[i]]["y"].append(labels[i])
            out[split[i]]["rec"].append(i)
    for s in out:
        out[s] = {k: np.array(v) for k, v in out[s].items()}
        out[s]["rr"] = out[s]["rr"].astype(np.float32)
    info = dict(records=len(labels), dropped_short=dropped,
                rec_per_split=[int((split == s).sum()) for s in (0, 1, 2)],
                af_rec_per_split=[int(((split == s) & (labels == 1)).sum()) for s in (0, 1, 2)],
                windows=[len(out[s]["y"]) for s in (0, 1, 2)],
                af_windows=[int(out[s]["y"].sum()) for s in (0, 1, 2)])
    return out, info


def quantise(rr, L, bits, feat):
    """rr: float32 tensor/array [N,LMAX] in ms -> integer-valued float [N,L].
    rr  : q = clip(floor(rr/step),0,2^bits-1), step = 2048/2^bits ms, last L RR
    drr : successive differences of q (last L+1 RR), clipped to signed bits range"""
    step = 2048.0 / (2 ** bits)
    q = torch.clamp(torch.floor(torch.as_tensor(rr) / step), 0, 2 ** bits - 1)
    if feat == "rr":
        return q[:, LMAX - L:]
    d = q[:, 1:] - q[:, :-1]
    d = torch.clamp(d, -(2 ** (bits - 1)), 2 ** (bits - 1) - 1)
    return d[:, -L:]


def metrics(y, p):
    y = np.asarray(y); p = np.asarray(p)
    tp = int(((y == 1) & (p == 1)).sum()); fn = int(((y == 1) & (p == 0)).sum())
    tn = int(((y == 0) & (p == 0)).sum()); fp = int(((y == 0) & (p == 1)).sum())
    sens = tp / max(tp + fn, 1); spec = tn / max(tn + fp, 1)
    f1 = 2 * tp / max(2 * tp + fp + fn, 1)
    return dict(sens=round(sens, 4), spec=round(spec, 4), f1=round(f1, 4),
                tp=tp, fn=fn, tn=tn, fp=fp)


def record_level(rec, y, p):
    """majority vote of window decisions per recording"""
    ids = np.unique(rec)
    ry = np.array([y[rec == i][0] for i in ids])
    rp = np.array([int(p[rec == i].mean() >= 0.5) for i in ids])
    return ry, rp
