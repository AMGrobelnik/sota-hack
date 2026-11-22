"""Integer classifier families on the integer window features. Every model is a plain dict of integers that
both numpy (predict) and the chip IR builder (chip_ir.py) read, so the two compute the same thing.
All fitting (feature choice, weights, thresholds) uses training subjects only."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.tree import DecisionTreeClassifier

from afchip.features import int_feature_names



def count_feats() -> list[int]:
    """Indices of the count features of the active feature set (sums excluded)."""
    return [i for i, n in enumerate(int_feature_names()) if n not in ("sum_abs", "sum_rr")]

SEED = 0


def youden_threshold(s: np.ndarray, y: np.ndarray) -> int:
    """Integer t maximising sens + spec of (s >= t) on the given (training) data."""
    vals = np.unique(s)
    cand = np.concatenate([vals, [vals.max() + 1]])
    pos, neg = (y == 1).sum(), (y == 0).sum()
    order = np.argsort(s)
    ss, yy = s[order], y[order]
    # count of positives / negatives with s >= t
    idx = np.searchsorted(ss, cand, side="left")
    cpos = np.concatenate([[0], np.cumsum(yy == 1)])
    cneg = np.concatenate([[0], np.cumsum(yy == 0)])
    tp = pos - cpos[idx]
    tn = cneg[idx]
    j = tp / max(pos, 1) + tn / max(neg, 1)
    return int(cand[int(np.argmax(j))])


def _score_lin(F: np.ndarray, m: dict) -> np.ndarray:
    return F[:, m["feats"]] @ np.asarray(m["w"], dtype=np.int64)


def _hidden(F: np.ndarray, m: dict) -> np.ndarray:
    W1 = np.asarray(m["W1"], dtype=np.int64)
    return np.maximum(F[:, m["feats"]] @ W1.T + np.asarray(m["b1"], dtype=np.int64), 0)


def _tree_bits(F: np.ndarray, m: dict) -> np.ndarray:
    return np.stack([(F[:, f] > t).astype(np.int64) for f, t in zip(m["node_feat"], m["node_thr"])], axis=1)


def predict(F: np.ndarray, m: dict) -> np.ndarray:
    k = m["kind"]
    if k == "thr1":
        return (F[:, m["f"]] >= m["t"]).astype(np.int64)
    if k == "and2":
        return ((F[:, m["f1"]] >= m["t1"]) & (F[:, m["f2"]] >= m["t2"])).astype(np.int64)
    if k == "lin":
        return (_score_lin(F, m) >= m["t"]).astype(np.int64)
    if k == "mlp":
        return (_hidden(F, m) @ np.asarray(m["W2"], dtype=np.int64) >= m["t"]).astype(np.int64)
    if k == "tree":
        bits = _tree_bits(F, m)
        idx = (bits << np.arange(bits.shape[1])[None, :]).sum(axis=1)
        return np.asarray(m["table"], dtype=np.int64)[idx]
    raise ValueError(k)


def fit_thr1(F: np.ndarray, y: np.ndarray) -> dict:
    CF = count_feats()
    best = None
    for f in CF:
        t = youden_threshold(F[:, f], y)
        p = F[:, f] >= t
        j = p[y == 1].mean() + (~p[y == 0]).mean()
        if best is None or j > best[0]:
            best = (j, f, t)
    return {"kind": "thr1", "f": best[1], "t": best[2]}


def fit_and2(F: np.ndarray, y: np.ndarray) -> dict:
    """Best AND of two count-feature thresholds (Dash-style joint rule), exhaustive via 2-D cumulative counts."""
    CF = count_feats()
    best = None
    pos, neg = (y == 1).sum(), (y == 0).sum()
    for ii, f1 in enumerate(CF):
        for f2 in CF[ii + 1 :]:
            a, b = F[:, f1], F[:, f2]
            A, B = a.max() + 2, b.max() + 2
            hp = np.zeros((A, B)); hn = np.zeros((A, B))
            np.add.at(hp, (a[y == 1], b[y == 1]), 1)
            np.add.at(hn, (a[y == 0], b[y == 0]), 1)
            # counts with a >= t1 and b >= t2: reverse cumulative sums
            cp = hp[::-1, ::-1].cumsum(0).cumsum(1)[::-1, ::-1]
            cn = hn[::-1, ::-1].cumsum(0).cumsum(1)[::-1, ::-1]
            j = cp / max(pos, 1) + (neg - cn) / max(neg, 1)
            t1, t2 = np.unravel_index(int(np.argmax(j)), j.shape)
            if best is None or j[t1, t2] > best[0]:
                best = (j[t1, t2], f1, int(t1), f2, int(t2))
    return {"kind": "and2", "f1": best[1], "t1": best[2], "f2": best[3], "t2": best[4]}


def _quant(w: np.ndarray, q: int) -> np.ndarray:
    s = q / max(np.abs(w).max(), 1e-12)
    return np.rint(w * s).astype(np.int64)


def fit_lin(F: np.ndarray, y: np.ndarray, *, n: int, q: int = 7) -> dict:
    CF = count_feats()
    X = F[:, CF] / n
    lr = LogisticRegression(class_weight="balanced", max_iter=2000, C=1.0, random_state=SEED).fit(X, y)
    w = _quant(lr.coef_[0], q)
    keep = np.nonzero(w)[0]
    m = {"kind": "lin", "feats": [CF[i] for i in keep], "w": [int(v) for v in w[keep]]}
    m["t"] = youden_threshold(_score_lin(F, m), y)
    return m


def fit_mlp(F: np.ndarray, y: np.ndarray, *, n: int, h: int = 4, q1: int = 15, q2: int = 7) -> dict:
    CF = count_feats()
    X = F[:, CF] / n
    mlp = MLPClassifier(hidden_layer_sizes=(h,), alpha=1e-3, max_iter=300, random_state=SEED).fit(X, y)
    W1 = mlp.coefs_[0].T / n  # per count unit
    b1 = mlp.intercepts_[0]
    s1 = q1 / max(np.abs(W1).max(), 1e-12)
    W1q = np.rint(W1 * s1).astype(np.int64)
    b1q = np.rint(b1 * s1).astype(np.int64)
    W2q = _quant(mlp.coefs_[1][:, 0], q2)
    keep = np.nonzero(np.abs(W1q).sum(axis=0))[0]
    m = {"kind": "mlp", "feats": [CF[i] for i in keep], "W1": W1q[:, keep].tolist(), "b1": b1q.tolist(),
         "W2": W2q.tolist()}
    s = _hidden(F, m) @ W2q
    m["t"] = youden_threshold(s, y)
    return m


def fit_tree(F: np.ndarray, y: np.ndarray, *, depth: int = 3) -> dict:
    CF = count_feats()
    X = F[:, CF]
    dt = DecisionTreeClassifier(max_depth=depth, class_weight="balanced", random_state=SEED).fit(X, y)
    tr = dt.tree_
    internal = [i for i in range(tr.node_count) if tr.children_left[i] != -1]
    pos_of = {node: j for j, node in enumerate(internal)}
    node_feat = [CF[int(tr.feature[i])] for i in internal]
    node_thr = [int(np.floor(tr.threshold[i])) for i in internal]  # x <= thr.5  <=>  x <= floor
    k = len(internal)
    table = []
    for code in range(2**k):
        node = 0
        while tr.children_left[node] != -1:
            bit = (code >> pos_of[node]) & 1  # bit = feature > thr -> right child
            node = tr.children_right[node] if bit else tr.children_left[node]
        v = tr.value[node][0]
        table.append(int(v[1] > v[0]))
    if k == 0:  # degenerate: constant
        return {"kind": "thr1", "f": CF[0], "t": 0 if table and table[0] else 10**6}
    return {"kind": "tree", "node_feat": node_feat, "node_thr": node_thr, "table": table}


FAMILIES = {
    "thr1": lambda F, y, n: fit_thr1(F, y),
    "and2": lambda F, y, n: fit_and2(F, y),
    "tree3": lambda F, y, n: fit_tree(F, y, depth=3),
    "lin": lambda F, y, n: fit_lin(F, y, n=n),
    "mlp4": lambda F, y, n: fit_mlp(F, y, n=n),
}


def used_features(m: dict) -> list[int]:
    k = m["kind"]
    if k == "thr1":
        return [m["f"]]
    if k == "and2":
        return [m["f1"], m["f2"]]
    if k in ("lin", "mlp"):
        return list(m["feats"])
    if k == "tree":
        return sorted(set(m["node_feat"]))
    raise ValueError(k)
