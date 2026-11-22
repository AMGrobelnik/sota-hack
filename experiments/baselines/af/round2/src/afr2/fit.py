"""Round-two model families, all fitted on training segments only, all at one fixed operating rule:

    threshold(s) = the ones with the highest training specificity among those with training sensitivity >= TARGET
    (ties: higher training sensitivity, then the first in a fixed scan order).

Families (models are plain dicts of feature names and integers, read by both `predict` and the chip builder):
    thr1   f >= t
    and2   f1 >= t1 AND f2 >= t2             (every pair, every threshold pair)
    or2    f1 >= t1 OR  f2 >= t2
    tree2  CART depth <= 2 on counts, leaf score >= tau
    tree3  CART depth <= 3 on counts, leaf score >= tau
    lin3   sum_j w_j f_j >= t over <= 3 counts, integer |w_j| <= 8
    lin6   the same over <= 6 counts
"""
from __future__ import annotations

import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from afr2.seqfeat import NAMES

TARGET = 0.96
FAMILIES = ("thr1", "and2", "or2", "tree2", "lin3", "tree3", "lin6")
FAMILY_ORDER = {f: i for i, f in enumerate(FAMILIES)}
L1_C = np.logspace(-3, 1, 17)
W_MAX = 8
SEED = 0


def _best_point(sens: np.ndarray, spec: np.ndarray) -> int:
    """Flat index of the highest spec with sens >= TARGET (ties: higher sens, then lowest index)."""
    ok = sens >= TARGET - 1e-12
    if not ok.any():  # cannot happen for a threshold scan that includes 'always positive'; guard anyway
        ok = sens >= sens.max()
    sp = np.where(ok, spec, -np.inf)
    top = sp >= sp.max() - 1e-12
    se = np.where(top, sens, -np.inf)
    return int(np.argmax(se))  # first index among the best spec, then best sens


def scan_threshold(s: np.ndarray, y: np.ndarray) -> int:
    """Integer t for the rule s >= t at the operating rule."""
    vals = np.unique(s)
    cand = np.concatenate([vals, [vals.max() + 1]])
    pos, neg = max(int((y == 1).sum()), 1), max(int((y == 0).sum()), 1)
    order = np.argsort(s, kind="stable")
    ss, yy = s[order], y[order]
    idx = np.searchsorted(ss, cand, side="left")
    cpos = np.concatenate([[0], np.cumsum(yy == 1)])
    cneg = np.concatenate([[0], np.cumsum(yy == 0)])
    sens = (cpos[-1] - cpos[idx]) / pos
    spec = cneg[idx] / neg
    return int(cand[_best_point(sens, spec)])


def fit_thr1(F: np.ndarray, y: np.ndarray, n: int) -> dict:
    best = None
    P, N = max(int((y == 1).sum()), 1), max(int((y == 0).sum()), 1)
    for f in range(F.shape[1]):
        t = scan_threshold(F[:, f], y)
        p = F[:, f] >= t
        se, sp = p[y == 1].sum() / P, (~p[y == 0]).sum() / N
        key = (sp, se)
        if best is None or key > best[0]:
            best = (key, f, t)
    return {"kind": "thr1", "feats": [NAMES[best[1]]], "t": [best[2]]}


def _pair_scan(F: np.ndarray, y: np.ndarray, n: int, mode: str) -> dict:
    V = n + 2  # count values 0..n, plus one spare so thresholds run 0..n+1
    P, N = max(int((y == 1).sum()), 1), max(int((y == 0).sum()), 1)
    best = None
    nf = F.shape[1]
    for f1 in range(nf):
        a = F[:, f1]
        for f2 in range(f1 + 1, nf):
            code = a * V + F[:, f2]
            hp = np.bincount(code[y == 1], minlength=V * V).reshape(V, V)
            hn = np.bincount(code[y == 0], minlength=V * V).reshape(V, V)
            if mode == "and":  # predicted positive: a >= t1 and b >= t2
                cp = hp[::-1, ::-1].cumsum(0).cumsum(1)[::-1, ::-1]
                cn = hn[::-1, ::-1].cumsum(0).cumsum(1)[::-1, ::-1]
                sens, spec = cp / P, 1.0 - cn / N
            else:  # predicted negative: a < t1 and b < t2
                zp = np.zeros((V + 1, V + 1)); zn = np.zeros((V + 1, V + 1))
                zp[1:, 1:] = hp.cumsum(0).cumsum(1); zn[1:, 1:] = hn.cumsum(0).cumsum(1)
                sens, spec = 1.0 - zp[:V, :V] / P, zn[:V, :V] / N
            i = _best_point(sens.ravel(), spec.ravel())
            t1, t2 = divmod(i, V)
            key = (spec.ravel()[i], sens.ravel()[i])
            if best is None or key > best[0]:
                best = (key, f1, int(t1), f2, int(t2))
    return {"kind": mode + "2", "feats": [NAMES[best[1]], NAMES[best[3]]], "t": [best[2], best[4]]}


def fit_tree(F: np.ndarray, y: np.ndarray, depth: int) -> dict:
    dt = DecisionTreeClassifier(max_depth=depth, class_weight="balanced", min_samples_leaf=10,
                                random_state=SEED).fit(F, y)
    tr = dt.tree_
    internal = [i for i in range(tr.node_count) if tr.children_left[i] != -1]
    if not internal:
        return {"kind": "thr1", "feats": [NAMES[0]], "t": [0 if y.mean() >= 0.5 else 10**3]}
    pos_of = {node: j for j, node in enumerate(internal)}
    node_feat = [NAMES[int(tr.feature[i])] for i in internal]
    node_thr = [int(np.floor(tr.threshold[i])) for i in internal]  # x <= thr.5  <=>  not (x > floor)
    leaf = dt.apply(F)
    val = tr.value[:, 0, :]
    score = val[:, 1] / np.maximum(val.sum(axis=1), 1e-300)
    s_leaf = score[leaf]
    taus = np.unique(s_leaf)
    P, N = max(int((y == 1).sum()), 1), max(int((y == 0).sum()), 1)
    sens = np.array([(s_leaf[y == 1] >= t).sum() / P for t in taus])
    spec = np.array([(s_leaf[y == 0] < t).sum() / N for t in taus])
    tau = taus[_best_point(sens, spec)]
    k = len(internal)
    table = []
    for code in range(2**k):
        node = 0
        while tr.children_left[node] != -1:
            node = tr.children_right[node] if (code >> pos_of[node]) & 1 else tr.children_left[node]
        table.append(int(score[node] >= tau))
    return {"kind": f"tree{depth}", "node_feat": node_feat, "node_thr": node_thr, "table": table}


def l1_path(F: np.ndarray, y: np.ndarray, n: int) -> list[np.ndarray]:
    """Nonzero feature sets along a fixed L1-logistic path (standardised counts, balanced classes)."""
    X = F / n
    mu, sd = X.mean(axis=0), X.std(axis=0)
    Z = (X - mu) / np.where(sd > 0, sd, 1.0)
    sets = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        for c in L1_C:
            lr = LogisticRegression(l1_ratio=1.0, solver="liblinear", C=float(c), class_weight="balanced",
                                    max_iter=500, random_state=SEED).fit(Z, y)
            sets.append(np.nonzero(lr.coef_[0])[0])
    return sets


def fit_lin(F: np.ndarray, y: np.ndarray, n: int, kmax: int, path: list[np.ndarray]) -> dict:
    sel = None
    for s in path:  # C increases along the path: keep the largest C whose model has 1..kmax counts
        if 1 <= len(s) <= kmax:
            sel = s
    if sel is None:
        sel = np.array([int(np.argmax(np.abs(np.corrcoef(F.T, y)[-1, :-1])))])
    X = F[:, sel] / n
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        lr = LogisticRegression(C=1.0, class_weight="balanced", max_iter=3000, random_state=SEED).fit((X - mu) / sd, y)
    w_raw = lr.coef_[0] / sd  # per count fraction
    scale = W_MAX / max(float(np.abs(w_raw).max()), 1e-12)
    w = np.rint(w_raw * scale).astype(np.int64)
    keep = np.nonzero(w)[0]
    feats = [NAMES[int(sel[i])] for i in keep]
    w = w[keep]
    s = F[:, sel[keep]] @ w
    t = scan_threshold(s, y)
    return {"kind": f"lin{kmax}", "feats": feats, "w": [int(v) for v in w], "t": int(t)}


def fit_all(F: np.ndarray, y: np.ndarray, n: int, families: tuple[str, ...] = FAMILIES) -> dict[str, dict]:
    out: dict[str, dict] = {}
    path = l1_path(F, y, n) if any(f.startswith("lin") for f in families) else []
    for fam in families:
        if fam == "thr1":
            out[fam] = fit_thr1(F, y, n)
        elif fam in ("and2", "or2"):
            out[fam] = _pair_scan(F, y, n, fam[:-1])
        elif fam.startswith("tree"):
            out[fam] = fit_tree(F, y, int(fam[4:]))
        elif fam.startswith("lin"):
            out[fam] = fit_lin(F, y, n, int(fam[3:]), path)
        else:
            raise ValueError(fam)
    return out


def used(m: dict) -> list[str]:
    if m["kind"].startswith("tree"):
        return sorted(set(m["node_feat"]), key=NAMES.index)
    return list(m["feats"])


def rule_from_counts(m: dict, cnt: dict[str, int]) -> int:
    """The same decision as `predict`, on one dict of counts (used by the step model)."""
    k = m["kind"]
    if k == "thr1":
        return int(cnt[m["feats"][0]] >= m["t"][0])
    if k == "and2":
        return int(cnt[m["feats"][0]] >= m["t"][0] and cnt[m["feats"][1]] >= m["t"][1])
    if k == "or2":
        return int(cnt[m["feats"][0]] >= m["t"][0] or cnt[m["feats"][1]] >= m["t"][1])
    if k.startswith("lin"):
        return int(sum(w * cnt[f] for f, w in zip(m["feats"], m["w"])) >= m["t"])
    if k.startswith("tree"):
        code = sum(int(cnt[f] > t) << j for j, (f, t) in enumerate(zip(m["node_feat"], m["node_thr"])))
        return int(m["table"][code])
    raise ValueError(k)


def predict(F: np.ndarray, m: dict, names: list[str] = NAMES) -> np.ndarray:
    col = {n: i for i, n in enumerate(names)}
    k = m["kind"]
    if k == "thr1":
        return (F[:, col[m["feats"][0]]] >= m["t"][0]).astype(np.int64)
    if k in ("and2", "or2"):
        a = F[:, col[m["feats"][0]]] >= m["t"][0]
        b = F[:, col[m["feats"][1]]] >= m["t"][1]
        return (a & b if k == "and2" else a | b).astype(np.int64)
    if k.startswith("lin"):
        s = F[:, [col[f] for f in m["feats"]]] @ np.asarray(m["w"], dtype=np.int64)
        return (s >= m["t"]).astype(np.int64)
    if k.startswith("tree"):
        bits = np.stack([(F[:, col[f]] > t) for f, t in zip(m["node_feat"], m["node_thr"])], axis=1).astype(np.int64)
        code = (bits << np.arange(bits.shape[1])[None, :]).sum(axis=1)
        return np.asarray(m["table"], dtype=np.int64)[code]
    raise ValueError(k)


def size_key(m: dict) -> tuple[int, int]:
    """Smaller design first: fewer distinct counters, then the fixed family order."""
    return (len(used(m)), FAMILY_ORDER[m["kind"]])
