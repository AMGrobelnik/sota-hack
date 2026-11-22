"""Reference models and integer minute classifiers for Apnea-ECG, fitted on the 35 learning records only.

Every choice (features, weights, bit widths, minute threshold, night rule) is made from the learning records
with grouped cross-validation (c05 and c06 are one subject). The 35 test records are scored once, at the end,
for every design in the fixed list; nothing is selected on them.

Run with: python -I models.py <features .npz> <out dir>
Writes <out dir>/designs.json (integer models + training-CV and test metrics) and per-design chipir/1 files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

SEED = 0
N_LEARN = 35
NIGHT_K = (6, 8, 10, 12, 14, 16, 20, 24)  # night rule: OSA if K * positives >= minutes (K = 12 is AHI_est >= 5)
CNT_BITS = 10  # night counters saturate at 1023 minutes
CTX = (-2, -1, 1, 2)  # neighbouring minutes whose features join the current minute's
CV_FOLDS = 7  # grouped folds on the learning subjects


# ------------------------------------------------------------------ statistics
def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (float((c - h) / d), float((c + h) / d))


def subject_bootstrap(correct: np.ndarray, rec: np.ndarray, reps: int = 2000) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    ids = np.unique(rec)
    k = np.array([correct[rec == r].sum() for r in ids], dtype=np.float64)
    n = np.array([(rec == r).sum() for r in ids], dtype=np.float64)
    accs = []
    for _ in range(reps):
        s = rng.integers(0, len(ids), len(ids))
        accs.append(k[s].sum() / n[s].sum())
    lo, hi = np.percentile(accs, [2.5, 97.5])
    return float(lo), float(hi)


# ------------------------------------------------------------------ data
def load(path: Path) -> dict:
    z = np.load(path, allow_pickle=False)
    d = {k: z[k] for k in z.files}
    names = [str(s) for s in d["names"]]
    group = np.array([names.index("c06") if names[r] == "c05" else r for r in d["rec"]])
    d["group"] = group
    d["names"] = names
    d["train"] = d["rec"] < N_LEARN
    # context: the features of the two minutes before and after (edge minutes repeat the edge), as the
    # streaming front end would deliver them with a two-minute delay
    base = [str(f) for f in d["feature_names"]]
    X, rec = d["X"], d["rec"]
    cols, fn = [X], [f"{f}@0" for f in base]
    for sh in CTX:
        Xs = np.empty_like(X)
        for r in np.unique(rec):
            m = np.where(rec == r)[0]
            Xs[m] = X[m][np.clip(np.arange(len(m)) + sh, 0, len(m) - 1)]
        cols.append(Xs)
        fn += [f"{f}@{sh:+d}" for f in base]
    d["X"] = np.hstack(cols)
    d["feature_names"] = np.array(fn)
    return d


def night_truth(y: np.ndarray, rec: np.ndarray, recs: list[int]) -> np.ndarray:
    """Per-recording reference: estimated AHI from the reference minute labels, 60 * apnoea minutes / minutes
    >= 5, i.e. 12 * apnoea minutes >= minutes (the per-recording protocol of the Table 6 papers)."""
    return np.array([int(12 * y[rec == r].sum() >= (rec == r).sum()) for r in recs])


def night_decide(pred: np.ndarray, rec: np.ndarray, recs: list[int], k: int) -> np.ndarray:
    out = []
    for r in recs:
        n_pos = min(int(pred[rec == r].sum()), 2 ** CNT_BITS - 1)
        n_min = min(int((rec == r).sum()), 2 ** CNT_BITS - 1)
        out.append(int(k * n_pos >= n_min))
    return np.array(out)


# ------------------------------------------------------------------ quantisation and integer models
def quantiser(Xtr: np.ndarray, bits: int) -> tuple[np.ndarray, np.ndarray]:
    """Affine feature quantiser fixed on training data: q = clip(floor((f - lo) / step), 0, 2^bits - 1)."""
    lo = np.percentile(Xtr, 1, axis=0)
    hi = np.percentile(Xtr, 99, axis=0)
    step = np.maximum((hi - lo) / (2 ** bits - 1), 1e-9)
    return lo, step


def quantise(X: np.ndarray, lo: np.ndarray, step: np.ndarray, bits: int) -> np.ndarray:
    return np.clip(np.floor((X - lo) / step), 0, 2 ** bits - 1).astype(np.int64)


def best_threshold(s: np.ndarray, y: np.ndarray) -> int:
    """Integer t maximising accuracy of (s > t) on the given (training) scores."""
    order = np.unique(s)
    cands = np.concatenate([[order[0] - 1], order])
    best, bt = -1.0, int(cands[0])
    pos_total = y.sum()
    srt = np.argsort(s)
    ss, ys = s[srt], y[srt]
    # for t = ss[i]: predicted positive are s > t
    cum_pos = np.cumsum(ys)
    for t in cands:
        i = np.searchsorted(ss, t, side="right")
        neg_ok = i - (cum_pos[i - 1] if i > 0 else 0)
        pos_ok = pos_total - (cum_pos[i - 1] if i > 0 else 0)
        acc = (neg_ok + pos_ok) / len(y)
        if acc > best:
            best, bt = acc, int(t)
    return bt


def fit_linear(Xtr: np.ndarray, ytr: np.ndarray, feats: list[int], fbits: int, wbits: int) -> dict:
    lo, step = quantiser(Xtr[:, feats], fbits)
    Q = quantise(Xtr[:, feats], lo, step, fbits)
    sc = StandardScaler().fit(Q)
    lr = LogisticRegression(C=1.0, max_iter=2000).fit(sc.transform(Q), ytr)
    a = lr.coef_[0] / sc.scale_
    wmax = 2 ** (wbits - 1) - 1
    W = np.round(a / np.abs(a).max() * wmax).astype(np.int64)
    s = Q @ W
    t = best_threshold(s, ytr)
    return {"kind": "linear", "feats": feats, "fbits": fbits, "wbits": wbits, "lo": lo.tolist(),
            "step": step.tolist(), "W": [W.tolist()], "t": t}


def fit_mlp(Xtr: np.ndarray, ytr: np.ndarray, feats: list[int], fbits: int, wbits: int, hidden: int) -> dict:
    """One hidden ReLU layer, trained in float on the quantised features, then weights rounded to wbits."""
    from sklearn.neural_network import MLPClassifier
    lo, step = quantiser(Xtr[:, feats], fbits)
    Q = quantise(Xtr[:, feats], lo, step, fbits).astype(np.float64)
    mu, sd = Q.mean(0), Q.std(0) + 1e-6
    mlp = MLPClassifier(hidden_layer_sizes=(hidden,), activation="relu", alpha=1e-3, max_iter=400,
                        random_state=SEED).fit((Q - mu) / sd, ytr)
    # fold standardisation into layer 1: h = relu(W1 (q - mu)/sd + b1) = relu((W1/sd) q + b1 - W1 mu/sd)
    W1 = mlp.coefs_[0].T / sd[None, :]
    b1 = mlp.intercepts_[0] - W1 @ mu
    W2 = mlp.coefs_[1][:, 0]
    wmax = 2 ** (wbits - 1) - 1
    s1 = wmax / np.abs(W1).max()
    W1i = np.round(W1 * s1).astype(np.int64)
    b1i = np.round(b1 * s1).astype(np.int64)
    Qi = Q.astype(np.int64)
    H = np.maximum(Qi @ W1i.T + b1i, 0)
    hshift = max(0, int(np.ceil(np.log2(max(H.max(), 1)))) - fbits)  # keep hidden activations at about fbits
    H = H >> hshift
    s2 = wmax / np.abs(W2).max()
    W2i = np.round(W2 * s2).astype(np.int64)
    s = H @ W2i
    t = best_threshold(s, ytr)
    return {"kind": "mlp", "feats": feats, "fbits": fbits, "wbits": wbits, "hidden": hidden, "lo": lo.tolist(),
            "step": step.tolist(), "W1": W1i.tolist(), "b1": b1i.tolist(), "hshift": hshift, "W2": [W2i.tolist()],
            "t": t}


def int_inputs(m: dict, X: np.ndarray) -> np.ndarray:
    return quantise(X[:, m["feats"]], np.array(m["lo"]), np.array(m["step"]), m["fbits"])


def int_score(m: dict, Q: np.ndarray) -> np.ndarray:
    if m["kind"] == "linear":
        return Q @ np.array(m["W"][0])
    H = np.maximum(Q @ np.array(m["W1"]).T + np.array(m["b1"]), 0) >> m["hshift"]
    return H @ np.array(m["W2"][0])


def int_predict(m: dict, X: np.ndarray) -> np.ndarray:
    return (int_score(m, int_inputs(m, X)) > m["t"]).astype(np.int64)


def chipir(m: dict, name: str, night_k: int | None = None) -> dict:
    """chipir/1 document of the minute classifier; with night_k, the combinational core of the night counter
    too: inputs x (features), n (positive minutes so far), l (minutes so far); outputs y (minute decision),
    n1 = sat(n + y), l1 = sat(l + 1), osa = night_k * n1 >= l1."""
    n = len(m["feats"])
    inputs = [{"name": "x", "lanes": n, "bits": m["fbits"], "signed": False}]
    if m["kind"] == "linear":
        nodes = [{"id": "s", "op": "matvec", "src": "x", "W": m["W"]}]
    else:
        nodes = [{"id": "h0", "op": "matvec", "src": "x", "W": m["W1"], "b": m["b1"]},
                 {"id": "h1", "op": "clip", "src": "h0", "lo": 0, "hi": int(np.abs(np.array(m["W1"])).sum(1).max()
                                                                         * (2 ** m["fbits"] - 1) + max(m["b1"]))},
                 {"id": "h", "op": "shift", "src": "h1", "k": m["hshift"]},
                 {"id": "s", "op": "matvec", "src": "h", "W": m["W2"]}]
    nodes.append({"id": "yd", "op": "cmp", "src": "s", "rel": "gt", "t": int(m["t"])})
    outputs = [{"name": "y", "src": "yd"}]
    if night_k is not None:
        cmax = 2 ** CNT_BITS - 1
        inputs += [{"name": "n", "lanes": 1, "bits": CNT_BITS, "signed": False},
                   {"name": "l", "lanes": 1, "bits": CNT_BITS, "signed": False}]
        nodes += [{"id": "na", "op": "add", "a": "n", "b": "yd"},
                  {"id": "n1", "op": "clip", "src": "na", "lo": 0, "hi": cmax},
                  {"id": "one", "op": "const", "values": [1]},
                  {"id": "la", "op": "add", "a": "l", "b": "one"},
                  {"id": "l1", "op": "clip", "src": "la", "lo": 0, "hi": cmax},
                  {"id": "nl", "op": "concat", "srcs": ["n1", "l1"]},
                  {"id": "z", "op": "matvec", "src": "nl", "W": [[int(night_k), -1]]},
                  {"id": "od", "op": "cmp", "src": "z", "rel": "ge", "t": 0}]
        outputs += [{"name": "n_next", "src": "n1"}, {"name": "l_next", "src": "l1"}, {"name": "osa", "src": "od"}]
    return {"ir": "chipir/1", "name": name, "inputs": inputs, "nodes": nodes, "outputs": outputs,
            "meta": {"task": "apnea-ecg minute classifier" + (" + night counter core" if night_k else ""),
                     "features": m["feats"], "kind": m["kind"]}}


# ------------------------------------------------------------------ evaluation
def evaluate(pred: np.ndarray, y: np.ndarray, rec: np.ndarray, recs: list[int], names: list[str], k: int,
             e1: dict[str, str] | None = None) -> dict:
    sel = np.isin(rec, recs)
    p, t, r = pred[sel], y[sel], rec[sel]
    corr = (p == t)
    tp, tn = int(((p == 1) & (t == 1)).sum()), int(((p == 0) & (t == 0)).sum())
    P, N = int((t == 1).sum()), int((t == 0).sum())
    per_rec = {names[i]: float(corr[r == i].mean()) for i in recs}
    worst = min(per_rec, key=per_rec.get)
    truth = night_truth(y, rec, recs)
    dec = night_decide(pred, rec, recs, k)
    TPn, TNn = int(((dec == 1) & (truth == 1)).sum()), int(((dec == 0) & (truth == 0)).sum())
    out = {
        "minute": {"correct": int(corr.sum()), "n": int(len(corr)), "acc": float(corr.mean()),
                   "acc_wilson95": wilson(int(corr.sum()), len(corr)),
                   "acc_subject_bootstrap95": subject_bootstrap(corr, r),
                   "sens": [tp, P], "spec": [tn, N]},
        "worst_subject": {"record": worst, "minute_acc": per_rec[worst],
                          "minutes": int((r == names.index(worst)).sum())},
        "night_ahi5": {"k": k, "correct": TPn + TNn, "n": len(recs), "wilson95": wilson(TPn + TNn, len(recs)),
                       "sens": [TPn, int(truth.sum())], "spec": [TNn, int((truth == 0).sum())],
                       "errors": [names[recs[i]] for i in range(len(recs)) if dec[i] != truth[i]]},
    }
    if e1 is not None:
        ac = [i for i in recs if e1.get(names[i]) in ("A", "C")]
        dd = night_decide(pred, rec, ac, k)
        tt = np.array([int(e1[names[i]] == "A") for i in ac])
        c = int((dd == tt).sum())
        out["challenge_event1_A_vs_C"] = {"correct": c, "n": len(ac), "wilson95": wilson(c, len(ac)),
                                          "errors": [names[ac[i]] for i in range(len(ac)) if dd[i] != tt[i]]}
    return out


def cv_predict(fit, X: np.ndarray, y: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, list[dict]]:
    pred = np.zeros(len(y), dtype=np.int64)
    models = []
    for tr, va in GroupKFold(n_splits=CV_FOLDS).split(X, y, groups):
        m = fit(X[tr], y[tr])
        pred[va] = m["predict"](X[va]) if "predict" in m else int_predict(m, X[va])
        models.append(m)
    return pred, models


def choose_k(pred: np.ndarray, y: np.ndarray, rec: np.ndarray, recs: list[int]) -> int:
    truth = night_truth(y, rec, recs)
    scores = {k: int((night_decide(pred, rec, recs, k) == truth).sum()) for k in NIGHT_K}
    best = max(scores.values())
    return min((k for k in NIGHT_K if scores[k] == best), key=lambda k: abs(k - 12))


def l1_order(X: np.ndarray, y: np.ndarray, max_f: int) -> list[int]:
    """Order features by when they enter an L1 logistic-regression path on the (training) data."""
    Z = StandardScaler().fit_transform(X)
    order: list[int] = []
    for C in np.geomspace(1e-4, 1.0, 40):
        lr = LogisticRegression(penalty="l1", solver="liblinear", C=float(C), max_iter=2000).fit(Z, y)
        nz = np.flatnonzero(lr.coef_[0])
        for f in nz[np.argsort(-np.abs(lr.coef_[0][nz]))]:
            if f not in order:
                order.append(int(f))
        if len(order) >= max_f:
            break
    return order[:max_f]


def main() -> None:
    d = load(Path(sys.argv[1]))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    e1 = {}
    if len(sys.argv) > 3:
        for line in Path(sys.argv[3]).read_text().split("\n"):
            if line.strip():
                a, b = line.split()
                e1[a] = b
    X, y, rec, names = d["X"], d["y"], d["rec"], d["names"]
    tr = d["train"]
    Xtr, ytr, gtr, rtr = X[tr], y[tr], d["group"][tr], rec[tr]
    learn = list(range(N_LEARN))
    test = list(range(N_LEARN, 2 * N_LEARN))
    fnames = [str(s) for s in d["feature_names"]]
    res: dict = {"feature_names": fnames, "designs": {}}

    e1_learn = {nm: nm[0].upper() for nm in names[:N_LEARN]}  # a = class A, b = borderline, c = class C
    score_test = len(sys.argv) > 4 and sys.argv[4] == "test"
    res["test_scored"] = score_test

    def report(tag: str, cv_pred: np.ndarray, test_pred: np.ndarray, extra: dict) -> None:
        k = choose_k(cv_pred, ytr, rtr, learn)
        res["designs"][tag] = {**extra, "night_k": k,
                               "train_cv": evaluate(cv_pred, ytr, rtr, learn, names, k, e1_learn),
                               "train_cv_k12": evaluate(cv_pred, ytr, rtr, learn, names, 12)["night_ahi5"]}
        t = res["designs"][tag]
        msg = (f"{tag}: cv min {t['train_cv']['minute']['acc']:.4f} night {t['train_cv']['night_ahi5']['correct']}/35"
               f" k={k} (k12 {t['train_cv_k12']['correct']}/35) AvC {t['train_cv']['challenge_event1_A_vs_C']['correct']}/30"
               f" err {t['train_cv']['night_ahi5']['errors']}")
        if score_test:
            t["test"] = evaluate(test_pred, y, rec, test, names, k, e1)
            t["test_k12"] = evaluate(test_pred, y, rec, test, names, 12, e1)["night_ahi5"]
            msg += f" | test min {t['test']['minute']['acc']:.4f} night {t['test']['night_ahi5']['correct']}/35"
        print(msg, flush=True)

    # reference float models (all 14 features)
    def fit_lr(Xa, ya):
        sc = StandardScaler().fit(Xa)
        lr = LogisticRegression(max_iter=2000).fit(sc.transform(Xa), ya)
        return {"predict": lambda Z: lr.predict(sc.transform(Z)).astype(np.int64)}

    def fit_gb(Xa, ya):
        gb = HistGradientBoostingClassifier(random_state=SEED, max_iter=300, learning_rate=0.05).fit(Xa, ya)
        return {"predict": lambda Z: gb.predict(Z).astype(np.int64)}

    for tag, fit in (("ref_logreg_float_allctx", fit_lr), ("ref_gboost_float_allctx", fit_gb)):
        cvp, _ = cv_predict(fit, Xtr, ytr, gtr)
        full = fit(Xtr, ytr)
        report(tag, cvp, full["predict"](X), {"kind": "float reference", "feats": list(range(X.shape[1]))})

    # feature ranking on training data only
    order = l1_order(Xtr, ytr, 16)
    res["l1_order_train"] = [fnames[i] for i in order]
    print("order", res["l1_order_train"], flush=True)

    specs = [
        ("D1_1f_thr", "linear", order[:1], 8, 2, 0),
        ("D2_2f_lin_w4", "linear", order[:2], 6, 4, 0),
        ("D3_4f_lin_w6", "linear", order[:4], 8, 6, 0),
        ("D4_8f_lin_w8", "linear", order[:8], 8, 8, 0),
        ("D5_16f_lin_w8", "linear", order[:16], 8, 8, 0),
        ("D6_16f_mlp8_w6", "mlp", order[:16], 8, 6, 8),
    ]
    for tag, kind, feats, fb, wb, hid in specs:
        if kind == "linear":
            def fit(Xa, ya, feats=feats, fb=fb, wb=wb):
                return fit_linear(Xa, ya, feats, fb, wb)
        else:
            def fit(Xa, ya, feats=feats, fb=fb, wb=wb, hid=hid):
                return fit_mlp(Xa, ya, feats, fb, wb, hid)
        cvp, _ = cv_predict(fit, Xtr, ytr, gtr)
        m = fit(Xtr, ytr)
        report(tag, cvp, int_predict(m, X), {"model": m, "feat_names": [fnames[i] for i in feats]})
        k = res["designs"][tag]["night_k"]
        (out / f"{tag}.chipir.json").write_text(json.dumps(chipir(m, tag), indent=1))
        (out / f"{tag}_night.chipir.json").write_text(json.dumps(chipir(m, tag + "_night", k), indent=1))
    (out / "designs.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
