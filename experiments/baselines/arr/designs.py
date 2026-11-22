"""Model families as integer chipir/1 documents.

Each `fit_*` trains on training beats only and returns a *probe* document whose node `score` is
an integer score and whose output `y` is `score > t`. The operating threshold t is fixed later
by the caller on non-test patients (`finalize`). Inputs are binary features: the baseline's 372
thermometer bits, optionally followed by RR-ratio indicator bits computed on chip from the rr
port (3 x 11-bit RR intervals).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.tree import DecisionTreeClassifier

from arrlib import N_SAMP, RATIO_LANES, RATIO_SCALE

N_BASE = 2 * N_SAMP  # the baseline's 372 thermometer bits (>=128, >=32768 of 65535)
N_LEVELS = 7  # finer thermometer: x >= k/8 of the beat's range, k = 1..7
N_BITS = N_BASE + N_LEVELS * N_SAMP  # all morphology bits; rr indicator bits follow
# RR-ratio indicator grid: bit = (num/den <= g), on chip 64*num - round(64 g)*den <= 0
RR_GRID: list[tuple[int, float]] = (
    [(0, g) for g in (0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.05, 1.15, 1.3, 1.6)]
    + [(1, g) for g in (0.7, 0.85, 0.95, 1.05, 1.15, 1.3, 1.6, 2.0)]
    + [(2, g) for g in (0.8, 0.95, 1.05, 1.15, 1.25, 1.4, 1.6, 2.0)]
)


def morph_bits(x16: np.ndarray) -> np.ndarray:
    """[baseline 2-bit code | 7-level thermometer] of the 186 normalised samples (0/1 ints)."""
    x = x16[:, :N_SAMP].astype(np.int64)
    blocks = [x >= 128, x >= 32768] + [x >= k * 8192 for k in range(1, N_LEVELS + 1)]
    return np.concatenate(blocks, axis=1).astype(np.int64)


def rr_bits(rr: np.ndarray) -> np.ndarray:
    """Exact integer indicator bits, same rule as the chip."""
    cols = []
    for ridx, g in RR_GRID:
        num, den = RATIO_LANES[ridx]
        cols.append(RATIO_SCALE * rr[:, num] - int(round(RATIO_SCALE * g)) * rr[:, den] <= 0)
    return np.stack(cols, axis=1).astype(np.int64)


@dataclass
class Data:
    X: np.ndarray  # binary features [n, 372 + len(RR_GRID)]
    y: np.ndarray  # 0/1
    w: np.ndarray  # sample weights


def balanced_weights(y: np.ndarray) -> np.ndarray:
    p = y.mean()
    return np.where(y == 1, 0.5 / p, 0.5 / (1 - p))


# ----------------------------------------------------------------------------- IR assembly


def _literal_block(feats: list[int]) -> tuple[list[dict], list[dict], dict, dict[int, int], str]:
    """Inputs and nodes exposing the used binary features as one lane vector."""
    morph = sorted(f for f in feats if f < N_BITS)
    rrf = sorted(f - N_BITS for f in feats if f >= N_BITS)
    ins, nodes, srcs = [], [], []
    if morph:
        ins.append({"name": "b", "lanes": len(morph), "bits": 1, "signed": False})
        srcs.append("b")
    if rrf:
        ins.append({"name": "rr", "lanes": 3, "bits": 11, "signed": False})
        W = []
        for j in rrf:
            ridx, g = RR_GRID[j]
            num, den = RATIO_LANES[ridx]
            row = [0, 0, 0]
            row[num] += RATIO_SCALE
            row[den] -= int(round(RATIO_SCALE * g))
            W.append(row)
        nodes.append({"id": "rrlin", "op": "matvec", "src": "rr", "W": W})
        nodes.append({"id": "rrbit", "op": "cmp", "src": "rrlin", "rel": "le", "t": 0})
        srcs.append("rrbit")
    if len(srcs) == 2:
        nodes.append({"id": "L", "op": "concat", "srcs": srcs})
        lsrc = "L"
    else:
        lsrc = srcs[0]
    lane = {f: i for i, f in enumerate(morph)}
    lane.update({N_BITS + j: len(morph) + i for i, j in enumerate(rrf)})
    meta = {"bit_features": morph, "rr_feature_idx": rrf, "rr_grid_used": [list(RR_GRID[j]) for j in rrf]}
    return ins, nodes, meta, lane, lsrc


def _doc(name: str, ins: list[dict], nodes: list[dict], meta: dict) -> dict:
    return {"ir": "chipir/1", "name": name, "inputs": ins, "nodes": nodes, "outputs": [{"name": "y", "src": "y"}], "meta": meta}


def _leaf_paths(tree) -> dict[int, list[tuple[int, int]]]:
    """leaf id -> [(feature, required bit)] along its path (binary features, split at 0.5)."""
    t = tree.tree_
    out: dict[int, list[tuple[int, int]]] = {}

    def walk(node: int, path: list[tuple[int, int]]) -> None:
        if t.children_left[node] == -1:
            out[node] = path
            return
        f = int(t.feature[node])
        walk(int(t.children_left[node]), path + [(f, 0)])
        walk(int(t.children_right[node]), path + [(f, 1)])

    walk(0, [])
    return out


def _path_lut(path: list[tuple[int, int]], lane: dict[int, int]) -> tuple[list[int], list[int]]:
    sel = [lane[f] for f, _ in path]
    want = [b for _, b in path]
    tab = [int(all(((i >> m) & 1) == want[m] for m in range(len(sel)))) for i in range(2 ** len(sel))]
    return sel, tab


def leaves_to_ir(name: str, paths: list[list[tuple[int, int]]], values: list[int], t: int, meta: dict) -> dict:
    """score = sum of integer values of the satisfied leaf paths; y = score > t."""
    feats = sorted({f for p in paths for f, _ in p})
    ins, nodes, m, lane, lsrc = _literal_block(feats)
    if not paths or any(len(p) == 0 for p in paths):
        raise ValueError("degenerate tree (a root leaf)")
    sels, tabs = zip(*(_path_lut(p, lane) for p in paths))
    nodes.append({"id": "leaf", "op": "lut", "src": lsrc, "inputs": list(sels), "tables": list(tabs)})
    nodes.append({"id": "score", "op": "matvec", "src": "leaf", "W": [list(values)]})
    nodes.append({"id": "y", "op": "cmp", "src": "score", "rel": "gt", "t": int(t)})
    return _doc(name, ins, nodes, {**m, **meta, "paths": [[list(x) for x in p] for p in paths], "values": list(values)})


def linear_to_ir(name: str, feats: list[int], w: list[int], t: int, meta: dict) -> dict:
    ins, nodes, m, lane, lsrc = _literal_block(feats)
    order = sorted(range(len(feats)), key=lambda i: lane[feats[i]])
    nodes.append({"id": "score", "op": "matvec", "src": lsrc, "W": [[int(w[i]) for i in order]]})
    nodes.append({"id": "y", "op": "cmp", "src": "score", "rel": "gt", "t": int(t)})
    return _doc(name, ins, nodes, {**m, **meta})


def finalize(probe: dict, t: int) -> dict:
    """Fix the threshold. A single tree becomes the OR of its leaves whose value exceeds t."""
    if probe["meta"].get("family", "").startswith("tree"):
        paths = [[tuple(x) for x in p] for p in probe["meta"]["paths"]]
        vals = probe["meta"]["values"]
        pos = [p for p, v in zip(paths, vals) if v > t]
        meta = {k: v for k, v in probe["meta"].items() if k not in ("paths", "values", "bit_features", "rr_feature_idx", "rr_grid_used")}
        if not pos:  # nothing passes: keep the top leaf with an unreachable threshold
            top = max(range(len(vals)), key=lambda i: vals[i])
            return leaves_to_ir(probe["name"], [paths[top]], [1], 1, {**meta, "threshold": int(t), "empty": True})
        return leaves_to_ir(probe["name"], pos, [1] * len(pos), 0, {**meta, "threshold": int(t)})
    ir = copy.deepcopy(probe)
    for nd in ir["nodes"]:
        if nd["id"] == "y":
            nd["t"] = int(t)
    ir["meta"]["threshold"] = int(t)
    return ir


# ----------------------------------------------------------------------------- families


def fit_width(tr: Data, name: str) -> dict:
    """Tiny: popcount of the >=50% bits in a centred window (a QRS-width proxy)."""
    best = None
    for k in (6, 10, 14, 20, 28, 40, 60, 93):
        cols = [N_SAMP + j for j in range(max(0, 93 - k), min(N_SAMP, 93 + k))]
        s = tr.X[:, cols].sum(1)
        auc = roc_auc_score(tr.y, s, sample_weight=tr.w)
        sign = 1 if auc >= 0.5 else -1
        auc = max(auc, 1 - auc)
        if best is None or auc > best[0]:
            best = (auc, cols, sign)
    _, cols, sign = best
    return linear_to_ir(name, cols, [sign] * len(cols), 0, {"family": "width", "window": len(cols), "train_auc": best[0]})


def fit_tree(tr: Data, name: str, depth: int, cols: np.ndarray) -> dict:
    clf = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=40, random_state=0)
    clf.fit(tr.X[:, cols], tr.y, sample_weight=tr.w)
    paths = _leaf_paths(clf)
    val = clf.tree_.value[:, 0, :]
    proba = val[:, 1] / val.sum(1)
    leaves = sorted(paths)
    uniq = np.unique(np.round(proba[leaves], 9))
    rank = [int(np.searchsorted(uniq, np.round(proba[lf], 9))) for lf in leaves]
    pl = [[(int(cols[f]), b) for f, b in paths[lf]] for lf in leaves]
    return leaves_to_ir(name, pl, rank, 0, {"family": f"tree_d{depth}"})


def fit_gbdt(tr: Data, name: str, n_trees: int, cols: np.ndarray, q: int = 7) -> dict:
    clf = GradientBoostingClassifier(n_estimators=n_trees, max_depth=2, learning_rate=0.3, random_state=0)
    clf.fit(tr.X[:, cols], tr.y, sample_weight=tr.w)
    paths_all, vals = [], []
    for est in clf.estimators_[:, 0]:
        for lf, path in _leaf_paths(est).items():
            if path:
                paths_all.append([(int(cols[f]), b) for f, b in path])
                vals.append(float(est.tree_.value[lf, 0, 0]))
    v = np.asarray(vals)
    ints = np.round(v * (q / np.abs(v).max())).astype(int)
    keep = [i for i in range(len(ints)) if ints[i] != 0]
    return leaves_to_ir(name, [paths_all[i] for i in keep], [int(ints[i]) for i in keep], 0, {"family": f"gbdt_d2_k{n_trees}", "leaf_bits": 4})


def fit_linear(tr: Data, name: str, target_nnz: int, cols: np.ndarray, q: int = 7) -> dict:
    best = None
    X = tr.X[:, cols].astype(np.float32)
    for C in (0.001, 0.003, 0.01, 0.03, 0.1):
        clf = LogisticRegression(l1_ratio=1.0, solver="liblinear", C=C, max_iter=100, tol=1e-3)
        clf.fit(X, tr.y, sample_weight=tr.w)
        nnz = int((clf.coef_ != 0).sum())
        if best is None or abs(nnz - target_nnz) < abs(best[0] - target_nnz):
            best = (nnz, clf)
        if nnz > 2 * target_nnz:
            break
    w = best[1].coef_[0]
    order = np.argsort(-np.abs(w))[:target_nnz]
    wi = np.round(w * (q / np.abs(w).max())).astype(int)
    idx = [int(i) for i in order if wi[i] != 0]
    return linear_to_ir(name, [int(cols[i]) for i in idx], [int(wi[i]) for i in idx], 0, {"family": f"linear_nnz{target_nnz}", "weight_bits": 4})


# ----------------------------------------------------------------------------- fast evaluation


def eval_ir(ir: dict, X: np.ndarray, node: str = "y") -> np.ndarray:
    """Integer evaluation from the full binary feature matrix (morph bits then rr bits)."""
    cols = list(ir["meta"]["bit_features"]) + [N_BITS + j for j in ir["meta"]["rr_feature_idx"]]
    L = X[:, cols].astype(np.int64)
    V: dict[str, np.ndarray] = {}
    n = X.shape[0]
    for nd in ir["nodes"]:
        if nd["op"] == "lut":
            out = []
            for sel, tab in zip(nd["inputs"], nd["tables"]):
                ix = np.zeros(n, dtype=np.int64)
                for m, j in enumerate(sel):
                    ix |= (L[:, j] & 1) << m
                out.append(np.asarray(tab)[ix])
            V[nd["id"]] = np.stack(out, 1)
        elif nd["op"] == "matvec" and nd["src"] != "rr":
            src = L if nd["src"] in ("b", "L", "rrbit") else V[nd["src"]]
            V[nd["id"]] = src @ np.asarray(nd["W"], dtype=np.int64).T
        elif nd["op"] == "cmp" and nd["id"] == "y":
            V["y"] = (V[nd["src"]] > nd["t"]).astype(np.int64)
    return V[node][:, 0]
