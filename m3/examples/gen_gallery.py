"""Build the chip lab's example gallery: medical-sensing detectors trained on seeded SYNTHETIC sensor windows.

Run with the lab's venv python (it has torch, torchlogix, xgboost):
    chiplab/.venv/bin/python m3/examples/gen_gallery.py

Every example lands in m3/examples/<name>/ as
    model.json   the model in the format the lab ingests (XGBoost JSON, intnn params, torchlogix gate list,
                 or a list of heads plus fusion rules)
    model.pt     torchlogix only: the saved module (a pickle made here; ingest it only from this machine)
    chip.json    how run_gallery.py brings it in through the CLI
    vectors.npz  in_<port> inputs and out_<output> expected outputs, computed by the model's own framework
                 or by a plain numpy reading of its integer semantics, never by the lab; label_<name> the
                 generator's ground truth for the same windows (ignored by the runner)
    meta.json    task, how the signal and the event are simulated, model kind and size, and the detection
                 figures of the model on the synthetic test windows
    README.md    the same in prose

All data is synthetic and seeded: simulated sensor windows, no recordings, no downloads, NOT patient data.
The examples show that a small detector of each kind goes to a chip bit-exactly; they make no clinical claim.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# torch is imported inside the functions that train with it, so the spawned XGBoost process never loads it

OUT = Path(__file__).resolve().parent
N_TRAIN = 3000
N_VEC = 256
DISCLAIMER = ("Synthetic data from a seeded generator, not patient data; the detection figures are on synthetic "
              "test windows and make no clinical claim.")


# ------------------------------------------------------------------------------------------------ helpers

def detection(pred, y, classes: list[str]) -> dict:
    """Detection figures of a decision against the generator's ground truth, on the synthetic test windows."""
    pred, y = np.asarray(pred).reshape(-1), np.asarray(y).reshape(-1)
    d = {"windows": int(len(y)), "accuracy": round(float((pred == y).mean()), 3)}
    if len(classes) == 2:
        tp, fn = int(((pred == 1) & (y == 1)).sum()), int(((pred == 0) & (y == 1)).sum())
        tn, fp = int(((pred == 0) & (y == 0)).sum()), int(((pred == 1) & (y == 0)).sum())
        d.update(events=tp + fn, sensitivity=round(tp / max(tp + fn, 1), 3),
                 specificity=round(tn / max(tn + fp, 1), 3), false_alarms=fp, missed=fn)
    else:
        d["recall"] = {c: round(float((pred[y == k] == k).mean()), 3) if (y == k).any() else None
                       for k, c in enumerate(classes)}
        d["windows_per_class"] = {c: int((y == k).sum()) for k, c in enumerate(classes)}
    return d


def fmt_det(d: dict) -> str:
    if "sensitivity" in d:
        return (f"sensitivity {d['sensitivity']:.3f} ({d['events']} events), specificity {d['specificity']:.3f}, "
                f"accuracy {d['accuracy']:.3f} on {d['windows']} synthetic test windows")
    rec = ", ".join(f"{c} {r:.3f}" for c, r in d["recall"].items())
    return f"accuracy {d['accuracy']:.3f}, recall per class: {rec}, on {d['windows']} synthetic test windows"


def write_example(name: str, *, title: str, task: str, signal: str, model_kind: str, model_size: str,
                  model: dict, chip: dict, vectors: dict, labels: dict, det: dict, notes: list[str],
                  extra: dict | None = None) -> None:
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "model.json").write_text(json.dumps(model) + "\n")
    for fn, doc in (extra or {}).items():
        (d / fn).write_text(json.dumps(doc) + "\n")
    (d / "chip.json").write_text(json.dumps(chip, indent=1) + "\n")
    np.savez_compressed(d / "vectors.npz", **{k: np.asarray(v, dtype=np.int64) for k, v in vectors.items()},
                        **{f"label_{k}": np.asarray(v, dtype=np.int64).reshape(-1) for k, v in labels.items()})
    meta = {"title": title, "task": task, "signal": signal, "model_kind": model_kind, "model_size": model_size,
            "detection": det, "data": DISCLAIMER}
    (d / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    ins = [k[3:] for k in vectors if k.startswith("in_")]
    outs = [k[4:] for k in vectors if k.startswith("out_")]
    lines = [f"# {name}: {title}", "", task, "",
             f"- Simulated signal and event: {signal}",
             f"- Model: {model_kind}, {model_size}.",
             f"- Chip flow: `{chip['kind']}` (see `chip.json`).",
             f"- Vectors: {N_VEC} test windows in `vectors.npz`; inputs {ins}, expected outputs {outs}, ground "
             f"truth {['label_' + k for k in labels]}.",
             *[f"- Detection ({k}, model on the synthetic test windows): {fmt_det(v)}." for k, v in det.items()],
             *[f"- {n}" for n in notes], "",
             f"{DISCLAIMER} Rebuilt by `m3/examples/gen_gallery.py`; chip numbers in `../RESULTS.md`.", ""]
    (d / "README.md").write_text("\n".join(lines))


def split(X, n_test=N_VEC):
    return X[:-n_test], X[-n_test:]


def qclip(X, bits, signed):
    lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
    return np.clip(np.round(X), lo, hi).astype(np.int64)


# ------------------------------------------------------------------------------------------------ intnn

def intnn_forward(p: dict, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Integer semantics from chiplab/ingest/intnn.py's docstring, in plain numpy: (decision [N,1], scores)."""
    h = X.astype(np.int64)
    for L in p["layers"]:
        W, b = np.asarray(L["W"], np.int64), np.asarray(L["b"], np.int64)
        h = np.clip((h @ W.T + b) >> L["shift"], 0, L["amax"])
    s = h @ np.asarray(p["Wo"], np.int64).T + np.asarray(p["bo"], np.int64)
    dec = (s[:, 0] > 0).astype(np.int64) if s.shape[1] == 1 else np.argmax(s, axis=1)
    return dec[:, None], s


def _qw(W: np.ndarray, wtype: str) -> tuple[np.ndarray, float]:
    a = np.abs(W)
    if wtype == "binary":
        return np.where(W >= 0, 1, -1), float(a.mean())
    if wtype == "ternary":
        q = np.where(a > 0.7 * a.mean(), np.sign(W), 0).astype(np.int64)
        return q, float(a[q != 0].mean()) if (q != 0).any() else 1.0
    bits = int(wtype.split("bit")[0])
    m = (1 << (bits - 1)) - 1
    s = float(a.max()) / m if a.max() > 0 else 1.0
    return np.clip(np.round(W / s), -m - 1, m).astype(np.int64), s


def train_intnn(X, y, *, hidden: list[int], wtype: str, n_cls: int, seed: int, amax: int = 15,
                out_bits: int = 5) -> tuple[dict, float]:
    """Float MLP on the integer inputs, then post-training quantisation with a grid search over shifts."""
    import torch
    torch.manual_seed(seed)
    Xt, yt = torch.tensor(X, dtype=torch.float32), torch.tensor(y)
    dims, mods = [X.shape[1], *hidden], []
    for a, b in zip(dims[:-1], dims[1:]):
        mods += [torch.nn.Linear(a, b), torch.nn.ReLU()]
    mods.append(torch.nn.Linear(dims[-1], 1 if n_cls == 2 else n_cls))
    net = torch.nn.Sequential(*mods)
    opt = torch.optim.Adam(net.parameters(), 0.01)
    for _ in range(400):
        out = net(Xt)
        loss = (torch.nn.functional.binary_cross_entropy_with_logits(out[:, 0], yt.float()) if n_cls == 2
                else torch.nn.functional.cross_entropy(out, yt))
        opt.zero_grad(); loss.backward(); opt.step()
    lin = [m for m in net if isinstance(m, torch.nn.Linear)]
    Ws = [m.weight.detach().numpy().astype(np.float64) for m in lin]
    bs = [m.bias.detach().numpy().astype(np.float64) for m in lin]
    best = None
    grid = np.array(np.meshgrid(*[range(0, 7)] * len(hidden))).reshape(len(hidden), -1).T
    for shifts in grid:
        layers, scale = [], 1.0
        for W, b, sh in zip(Ws[:-1], bs[:-1], shifts):
            q, s = _qw(W * scale, wtype)
            layers.append({"W": q.tolist(), "b": np.round(b / s).astype(int).tolist(), "shift": int(sh), "amax": amax})
            scale = s * (1 << int(sh))
        Wo = Ws[-1] * scale
        m = (1 << (out_bits - 1)) - 1
        so = float(np.abs(Wo).max()) / m
        p = {"layers": layers, "Wo": np.clip(np.round(Wo / so), -m - 1, m).astype(int).tolist(),
             "bo": np.round(bs[-1] / so).astype(int).tolist()}
        p["out_dim"] = len(p["Wo"])
        acc = float((intnn_forward(p, X)[0][:, 0] == y).mean())
        if best is None or acc > best[1]:
            best = (p, acc)
    return best


def intnn_size(p: dict, lanes: int, wtype: str) -> str:
    dims = [lanes, *[len(L["W"]) for L in p["layers"]], len(p["Wo"])]
    n_w = sum(len(L["W"]) * len(L["W"][0]) for L in p["layers"]) + len(p["Wo"]) * len(p["Wo"][0])
    return f"layers {dims}, {n_w} weights ({wtype} hidden, 5-bit output layer)"


def intnn_example(name, *, title, task, signal, X, y, classes, bits, signed, hidden, wtype, seed,
                  spike_form=False):
    (Xtr, Xte), (ytr, yte) = split(X), split(y)
    p, acc_tr = train_intnn(Xtr, ytr, hidden=hidden, wtype=wtype, n_cls=len(classes), seed=seed)
    dec, _ = intnn_forward(p, Xte)
    spec = {"lanes": X.shape[1], "bits": bits, "signed": signed}
    if spike_form:      # the feasibility-spike single-hidden-layer form (cfg/W1/b1/shift/W2/b2/amax)
        L = p["layers"][0]
        model = {"cfg": {"L": X.shape[1], "bits": bits, "H": len(L["W"]), "signed": signed, "wtype": wtype},
                 "W1": L["W"], "b1": L["b"], "shift": L["shift"], "W2": p["Wo"][0], "b2": p["bo"][0], "amax": L["amax"]}
    else:
        model = {**p, "in_spec": spec, "wtype": wtype}
    write_example(name, title=title, task=task, signal=signal,
                  model_kind=f"intnn {wtype}" + (" (spike single-layer form)" if spike_form else ""),
                  model_size=intnn_size(p, X.shape[1], wtype) + f"; input {X.shape[1]} lanes x {bits}-bit "
                  f"{'signed' if signed else 'unsigned'}",
                  model=model, chip={"kind": "ingest", "format": "intnn", "args": {"name": name}},
                  vectors={"in_x": Xte, "out_y": dec}, labels={"y": yte},
                  det={"y": detection(dec, yte, classes)},
                  notes=[f"Integer model accuracy on the synthetic training windows: {acc_tr:.3f}.",
                         "Expected outputs: plain numpy of the intnn integer semantics (h = clip((W h + b) >> shift, "
                         "0, amax); score > 0 or argmax)."])
    return p, Xte, dec, yte


# ------------------------------------------------------------------------------------------------ synthetic signals
# Every generator returns integer sensor windows as the chip sees them plus the ground truth it simulated.

def hr_windows(rng, n):
    """8 heart-rate samples, one per 2 s, 4-bit signed, 1 unit = 8 bpm from the wearer's resting rate.
    Event 1 = tachycardia-like rise, 2 = bradycardia-like fall; normal windows carry drift, noise and, in 15 %,
    a one-sample motion spike."""
    ev = rng.choice(3, n, p=[0.5, 0.3, 0.2])
    t = np.arange(8)
    bpm = rng.normal(0, 5, (n, 1)) + rng.normal(0, 4, (n, 8))
    onset = rng.integers(0, 5, n)
    frac = np.clip((t[None, :] - onset[:, None] + 1) / 3, 0, 1)
    mag = np.where(ev == 1, rng.uniform(25, 55, n), np.where(ev == 2, -rng.uniform(22, 40, n), 0.0))
    bpm += mag[:, None] * frac
    spike = (ev == 0) & (rng.random(n) < 0.15)
    bpm[spike, rng.integers(0, 8, spike.sum())] += rng.uniform(20, 32, spike.sum())
    return qclip(bpm / 8, 4, True), ev


HR_SIGNAL = ("8 heart-rate samples (one per 2 s, 4-bit signed, 8 bpm per unit from resting); the event is a "
             "sustained rise of 25-55 bpm or fall of 22-40 bpm ramping in from a random onset, against drift, "
             "noise and one-sample motion spikes.")


def spo2_windows(rng, n, lanes=6):
    """SpO2 readings, one per 5 s, 4-bit unsigned as 100 - SpO2 % (0 = 100 %, 15 = 85 % or lower).
    Event: a desaturation dip of 4-10 points with partial recovery; 20 % of normal windows have a one-sample
    motion artefact drop."""
    y = rng.integers(0, 2, n)
    t = np.arange(lanes)
    x = rng.uniform(1, 4, (n, 1)) + rng.normal(0, 0.7, (n, lanes))
    onset = rng.integers(0, lanes - 2, n)
    shape = np.clip((t[None, :] - onset[:, None] + 1) / 2, 0, 1) * (
        1 - 0.5 * np.clip((t[None, :] - onset[:, None] - 3) / 2, 0, 1))
    x += np.where(y[:, None] == 1, rng.uniform(4, 10, (n, 1)) * shape, 0)
    art = (y == 0) & (rng.random(n) < 0.2)
    x[art, rng.integers(0, lanes, art.sum())] += rng.uniform(5, 9, art.sum())
    return qclip(x, 4, False), y


SPO2_SIGNAL = ("6 SpO2 readings (one per 5 s, 4-bit as 100 minus SpO2 %); the event is a dip of 4-10 points with "
               "partial recovery from a random onset; 20 % of normal windows carry a one-sample motion-artefact "
               "drop.")


def fall_windows(rng, n):
    """6 wrist-accelerometer window features, 5-bit signed: peak magnitude, jerk, tilt change, pre-impact
    free-fall, post-impact stillness, step regularity. 25 % of non-falls are hard sit-downs (high peak only)."""
    y = rng.integers(0, 2, n)
    X = rng.normal(0, 3, (n, 6))
    X += np.where(y[:, None] == 1, np.array([7, 4, 6, 4, -5, -3]), 0)
    sit = (y == 0) & (rng.random(n) < 0.25)
    X[sit, 0] += 7; X[sit, 1] += 3
    return qclip(X, 5, True), y


def breath_windows(rng, n):
    """Chest-band breath amplitude in 6 sub-windows of 5 s, 4-bit unsigned. 0 normal, 1 shallow (2-4 consecutive
    sub-windows at 35-60 % amplitude), 2 pause (2-3 consecutive sub-windows near zero)."""
    y = rng.integers(0, 3, n)
    amp = rng.normal(10, 1.5, (n, 1)) + rng.normal(0, 1.2, (n, 6))
    for i in np.flatnonzero(y == 1):
        L = rng.integers(2, 5); s = rng.integers(0, 7 - L)
        amp[i, s:s + L] *= rng.uniform(0.35, 0.6)
    for i in np.flatnonzero(y == 2):
        L = rng.integers(2, 4); s = rng.integers(0, 7 - L)
        amp[i, s:s + L] = rng.normal(1, 0.8, L)
    return qclip(amp, 4, False), y


def rr_flags(rng, n):
    """16 beat-to-beat flags from 17 simulated RR intervals: flag = |RR_i - RR_(i-1)| > 12 % of the mean RR.
    0 regular (3 % jitter plus 4 % respiratory swing), 1 isolated premature beat (one or two short-long pairs),
    2 irregular rhythm (20 % random RR variation)."""
    y = rng.integers(0, 3, n)
    k = np.arange(17)
    rr = 0.8 * (1 + 0.04 * np.sin(2 * np.pi * k[None, :] / rng.uniform(4, 6, (n, 1))) + 0.03 * rng.normal(size=(n, 17)))
    for i in np.flatnonzero(y == 1):
        for p in rng.choice(np.arange(1, 15), rng.integers(1, 3), replace=False):
            rr[i, p] *= 0.65; rr[i, p + 1] *= 1.3
    irr = y == 2
    rr[irr] = rng.uniform(0.55, 0.95, (irr.sum(), 1)) * (1 + 0.2 * rng.normal(size=(irr.sum(), 17)))
    return (np.abs(np.diff(rr, axis=1)) > 0.12 * rr.mean(1, keepdims=True)).astype(np.int64), y


def fever_windows(rng, n):
    """6 skin-temperature samples, one per 30 min, 4-bit unsigned, 1 unit = 0.25 C above 36.0 C.
    0 normal (36.4-37.2 C, flat), 1 rising (from 36.5-37.0 C at 0.24-0.44 C per hour), 2 fever (38.0-39.5 C)."""
    y = rng.integers(0, 3, n)
    t = np.arange(6)
    start = np.select([y == 0, y == 1], [rng.uniform(36.4, 37.2, n), rng.uniform(36.5, 37.0, n)],
                      rng.uniform(38.0, 39.5, n))
    slope = np.where(y == 1, rng.uniform(0.12, 0.22, n), rng.normal(0, 0.04, n))
    temp = start[:, None] + slope[:, None] * t[None, :] + rng.normal(0, 0.12, (n, 6))
    return qclip((temp - 36.0) / 0.25, 4, False), y


def eeg_windows(rng, n):
    """24 samples of one band-passed EEG channel at 16 Hz (1.5 s), 6-bit signed, about 5 uV per unit.
    Background: AR(1) noise; 30 % of normal windows carry a slow blink-like bump; the event is a rhythmic
    spike-and-wave burst (period 5 samples, about 3 Hz) of 12-22 units from a random onset."""
    y = rng.integers(0, 2, n)
    x = np.zeros((n, 24)); e = rng.normal(0, 3, (n, 24))
    for t in range(24):
        x[:, t] = (0.7 * x[:, t - 1] if t else 0) + e[:, t]
    t = np.arange(24)
    blink = (y == 0) & (rng.random(n) < 0.3)
    c = rng.uniform(3, 21, n)
    x += np.where(blink[:, None], rng.uniform(12, 20, (n, 1)) * np.exp(-0.5 * ((t[None, :] - c[:, None]) / 2.5) ** 2), 0)
    pattern = np.array([1.0, -0.3, -0.5, -0.4, -0.2])
    onset = rng.integers(0, 12, n)
    burst = rng.uniform(12, 22, (n, 1)) * pattern[(t[None, :] - onset[:, None]) % 5]
    x += np.where((y[:, None] == 1) & (t[None, :] >= onset[:, None]), burst, 0)
    return qclip(x, 6, True), y


def deterioration_windows(seed: int, n: int = N_TRAIN) -> dict:
    """Multi-sensor fusion data. A hidden deterioration state (50 %) shows in each sensor with probability 0.85;
    each sensor also shows a spurious abnormality in 8 % of stable windows. Sensors, 4 samples each:
    heart rate (5-bit signed, 4 bpm per unit from resting; abnormal = +20-40 bpm), respiration rate (5-bit signed,
    1 breath/min per unit from 14/min; abnormal = +6-12), SpO2 (4-bit, 100 - SpO2 %; abnormal = 4-8 points down)."""
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 2, n)
    shows = {s: np.where(y == 1, rng.random(n) < 0.85, rng.random(n) < 0.08).astype(np.int64)
             for s in ("hr", "resp", "spo2")}
    hr = rng.normal(0, 6, (n, 1)) + rng.normal(0, 4, (n, 4)) + shows["hr"][:, None] * rng.uniform(20, 40, (n, 1))
    rr = rng.normal(0, 1.5, (n, 1)) + rng.normal(0, 1.2, (n, 4)) + shows["resp"][:, None] * rng.uniform(6, 12, (n, 1))
    sp = rng.uniform(1, 4, (n, 1)) + rng.normal(0, 0.7, (n, 4)) + shows["spo2"][:, None] * rng.uniform(4, 8, (n, 1))
    return {"y": y, "shows": shows, "hr": qclip(hr / 4, 5, True), "resp": qclip(rr, 5, True),
            "spo2": qclip(sp, 4, False)}


DET_SIGNAL = ("a hidden deterioration state (half the windows) shows in each of heart rate (+20-40 bpm), "
              "respiration rate (+6-12 /min) and SpO2 (4-8 points down) with probability 0.85; each sensor also "
              "shows a spurious abnormality in 8 % of stable windows; 4 samples per sensor.")


# ------------------------------------------------------------------------------------------------ trees

def train_xgb(X, y, n_cls, seed, n_estimators, max_depth, w_feature, w_tree):
    import tempfile

    import xgboost as xgb

    from chiplab.ingest.treelut import treelut_classifier
    # TreeLUT accepts only binary:logistic and multi:softmax (not XGBoost's default multi:softprob)
    kw = {} if n_cls == 2 else {"objective": "multi:softmax", "num_class": n_cls}
    m = xgb.XGBClassifier(n_estimators=n_estimators, max_depth=max_depth, learning_rate=0.5, random_state=seed,
                          n_jobs=1, **kw).fit(X, y)
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "m.json"
        m.save_model(f)
        model_json = json.loads(f.read_text())
        m2 = xgb.XGBClassifier(); m2.load_model(f)          # same path as the lab: reload from the JSON
    # a reloaded XGBClassifier has n_estimators=None, which TreeLUT needs (see proposed/xgboost-json-reload.patch)
    m2.set_params(n_estimators=m2.get_booster().num_boosted_rounds())
    tl = treelut_classifier(m2, w_feature=w_feature, w_tree=w_tree)
    return model_json, tl


def treelut_chipir(tl, name):
    """The lab's own TreeLUT -> chipir/1 converter, so the CLI can ingest the same model as format chipir."""
    from chiplab.ingest.treelut import from_treelut
    return from_treelut(tl, name)


def treelut_scores(tl, X):
    """TreeLUT's own quantised forward (vendored TreeLUTClassifier._single_tree_predict), keeping the class sums."""
    s = np.tile(np.asarray(tl._classes_bias, dtype=np.int64)[: tl._n_classes], (len(X), 1))
    for i, t in enumerate(tl._treelut_model):
        arr = np.zeros((len(t), 6), dtype=np.int64)
        for j in range(len(t)):
            d = t[j]
            if d["type"] == "leaf":
                arr[j, :2] = (j, 1); arr[j, 3] = d["value"]
            else:
                arr[j] = (j, 0, d["feature"], d["threshold"], d["yes"], d["no"])
        s[:, i % tl._n_classes] += np.asarray(tl._single_tree_predict(arr, X), dtype=np.int64)
    pred = np.asarray(tl.predict(X)).astype(np.int64).reshape(len(X), -1)
    dec = (s[:, :1] >= tl._threshold).astype(np.int64) if tl._n_classes == 1 else np.argmax(s, axis=1)[:, None]
    assert (dec == pred).all(), "TreeLUT predict disagrees with its own class sums"
    return dec, s


def tree_example(name, *, title, task, signal, X, y, classes, seed, n_estimators, max_depth, bits,
                 w_feature=4, w_tree=3):
    (Xtr, Xte), (ytr, yte) = split(X), split(y)
    n_cls = len(classes)
    mj, tl = train_xgb(Xtr, ytr, n_cls, seed, n_estimators, max_depth, w_feature, w_tree)
    dec, s = treelut_scores(tl, Xte)
    acc_tr = float((np.asarray(tl.predict(Xtr)).astype(int).reshape(-1) == ytr).mean())
    n_trees = n_estimators * (1 if n_cls == 2 else n_cls)
    write_example(name, title=title, task=task, signal=signal, model_kind="XGBoost via TreeLUT",
                  model_size=f"{n_estimators} rounds x depth {max_depth} ({n_trees} trees), "
                  f"{'binary' if n_cls == 2 else f'{n_cls} classes'}, TreeLUT w_feature={w_feature}, "
                  f"w_tree={w_tree}; input {X.shape[1]} x {bits}-bit",
                  model=mj, chip={"kind": "ingest", "format": "xgboost_json",
                                  "args": {"w_feature": w_feature, "w_tree": w_tree, "name": name},
                                  "fallback": {"format": "chipir", "file": "chipir.json", "args": {"name": name}}},
                  extra={"chipir.json": treelut_chipir(tl, name)},
                  vectors={"in_x": Xte, "out_y": dec, "out_scores": s}, labels={"y": yte},
                  det={"y": detection(dec, yte, classes)},
                  notes=[f"XGBoost {xgboost_version()}; TreeLUT quantised model accuracy on the synthetic training "
                         f"windows: {acc_tr:.3f}.",
                         "Expected outputs: TreeLUT's own predict (vendored copy) and its per-class integer sums.",
                         "`chipir.json`: the same model after the lab's TreeLUT converter, ingested as format chipir "
                         "when the CLI's xgboost_json path fails (see ../RESULTS.md)."])


def xgboost_version():
    import xgboost
    return xgboost.__version__


# ------------------------------------------------------------------------------------------------ torchlogix

def irregular_beat_logic(seed=5):
    import torch
    from torchlogix.layers import GroupSum, LogicDense
    from torchlogix.utils import set_export_mode
    X, y = rr_flags(np.random.default_rng(seed), N_TRAIN)
    (Xtr, Xte), (ytr, yte) = split(X), split(y)
    torch.manual_seed(seed)
    m = torch.nn.Sequential(LogicDense(16, 48), LogicDense(48, 48), GroupSum(k=3, tau=4.0))
    opt = torch.optim.Adam(m.parameters(), 0.05)
    xt, yt = torch.tensor(Xtr).float(), torch.tensor(ytr)
    for _ in range(150):
        loss = torch.nn.functional.cross_entropy(m(xt), yt); opt.zero_grad(); loss.backward(); opt.step()

    def discrete(Xn):          # torchlogix's own export-mode (boolean) forward
        set_export_mode(m, True)
        h = torch.as_tensor(Xn).bool()
        with torch.no_grad():
            for mod in m.children():
                if isinstance(mod, GroupSum):
                    s = h.reshape(h.shape[0], mod.k, -1).sum(-1).long(); break
                h = mod(h)
        set_export_mode(m, False)
        return s.numpy()

    s = discrete(Xte)
    m.eval()
    with torch.no_grad():
        ev = m(torch.tensor(Xte).float()).numpy()
    assert np.allclose(ev * 4.0, s), "torchlogix eval forward disagrees with export mode"
    dec = np.argmax(s, axis=1)[:, None]
    acc_tr = float((np.argmax(discrete(Xtr), 1) == ytr).mean())
    name = "irregular_beat_logic_3class"
    d = OUT / name; d.mkdir(parents=True, exist_ok=True)
    torch.save(m, d / "model.pt")
    layers = []
    for mod in m.children():
        if isinstance(mod, LogicDense):
            with torch.no_grad():
                _, ids = mod.get_luts_and_ids()
                conn = mod.connections
                idx = conn.resolve_connections() if hasattr(conn, "resolve_connections") else conn.indices
            layers.append({"type": "LogicDense", "in_dim": mod.in_dim, "out_dim": mod.out_dim,
                           "gate_ids": ids.long().tolist(), "a": idx[0].long().tolist(), "b": idx[1].long().tolist()})
        elif isinstance(mod, GroupSum):
            layers.append({"type": "GroupSum", "k": mod.k, "tau": float(mod.tau)})
    classes = ["regular", "premature beat", "irregular rhythm"]
    write_example(name, title="irregular beat",
                  task="Beat-to-beat flags from a heart-rate sensor -> regular / isolated premature beat / "
                       "irregular rhythm.",
                  signal="17 simulated RR intervals give 16 flags (beat-to-beat change above 12 % of the mean RR); "
                         "regular rhythm has 3 % jitter and a 4 % respiratory swing, a premature beat is one or two "
                         "short-long pairs, an irregular rhythm has 20 % random RR variation.",
                  model_kind="torchlogix logic network",
                  model_size="LogicDense(16,48) -> LogicDense(48,48) -> GroupSum(3, tau=4): 96 two-input logic "
                             "gates; input 16 x 1-bit",
                  model={"format": "torchlogix", "file": "model.pt", "layers": layers,
                         "note": "readable copy of the discrete network; the lab ingests model.pt"},
                  chip={"kind": "ingest", "format": "torchlogix", "args": {"path": "model.pt", "trusted": True,
                                                                            "name": name}},
                  vectors={"in_x": Xte, "out_y": dec, "out_scores": s}, labels={"y": yte},
                  det={"y": detection(dec, yte, classes)},
                  notes=[f"150 Adam steps; discrete network accuracy on the synthetic training windows: {acc_tr:.3f}. "
                         "model.pt is the saved module (pickle written on this machine).",
                         "Expected outputs: torchlogix's own export-mode forward (also checked against eval mode x tau)."])


# ------------------------------------------------------------------------------------------------ fusion

def fusion_example(name, *, title, task, signal, heads: dict, fusion: list, shared: bool, model_size: str,
                   labels: dict, classes2: list[str], note: str):
    """heads: name -> (model, chip-ingest dict, X_test, {output: expected}). labels: output name -> ground truth
    (fusion outputs and, where they have one, head outputs)."""
    model = {"heads": {h: {"format": c["format"], "args": c.get("args", {}), "model": m,
                           **({"fallback": c["fallback"]} if "fallback" in c else {})}
                       for h, (m, c, _, _) in heads.items()},
             "fusion": fusion, "shared_inputs": shared}
    vec, outs = {}, {}
    for h, (_, _, X, ex) in heads.items():
        vec[f"in_{'x' if shared else h + '_x'}"] = X
        for o, v in ex.items():
            outs[f"{h}_{o}"] = v
    for f in fusion:
        bits = np.concatenate([outs[i] for i in f["inputs"]], axis=1)
        k = {"and": bits.shape[1], "or": 1}.get(f["op"], f.get("k"))
        outs[f["name"]] = (bits.sum(1, keepdims=True) >= k).astype(np.int64)
    vec.update({f"out_{k}": v for k, v in outs.items()})
    det = {k: detection(outs[k], v, classes2) for k, v in labels.items()}
    write_example(name, title=title, task=task, signal=signal, model_kind="multi-head fusion (compose-chip, "
                  + " / ".join(sorted({f["op"] for f in fusion})) + ")", model_size=model_size, model=model,
                  chip={"kind": "compose", "shared_inputs": shared, "fusion": fusion}, vectors=vec, labels=labels,
                  det=det, notes=[note, "Expected fusion outputs: numpy over the heads' expected decisions "
                                        "(and = all, or = any, kofn = at least k)."])


# ------------------------------------------------------------------------------------------------ gallery

def trees_phase():
    """All XGBoost training, in its own process: on macOS XGBoost's and torch's OpenMP runtimes crash or deadlock
    when both train in one process. Returns the SpO2 head of the k-of-n example as plain values."""
    X, y = spo2_windows(np.random.default_rng(6), N_TRAIN)
    tree_example("spo2_drop_treelut_binary", title="SpO2 drop",
                 task="Pulse oximeter: 6 SpO2 readings over 30 s -> desaturation yes/no.", signal=SPO2_SIGNAL,
                 X=X, y=y, classes=["normal", "desaturation"], seed=6, n_estimators=8, max_depth=3, bits=4)
    X, y = fever_windows(np.random.default_rng(7), N_TRAIN)
    tree_example("fever_trend_treelut_3class", title="fever trend",
                 task="Skin-temperature patch: 6 readings over 3 h -> normal / rising trend / fever.",
                 signal="6 samples one per 30 min (4-bit, 0.25 C per unit above 36.0 C); normal is flat at "
                        "36.4-37.2 C, a rising trend climbs 0.24-0.44 C per hour from 36.5-37.0 C, fever sits at "
                        "38.0-39.5 C; 0.12 C noise.",
                 X=X, y=y, classes=["normal", "rising", "fever"], seed=7, n_estimators=6, max_depth=3, bits=4)
    D = deterioration_windows(21)
    (Xtr, Xte), (ytr, _) = split(D["spo2"]), split(D["shows"]["spo2"])
    mj, tl = train_xgb(Xtr, ytr, 2, 23, 6, 3, 4, 3)
    dec, s = treelut_scores(tl, Xte)
    return mj, treelut_chipir(tl, "spo2"), dec, s


def main():
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(1, mp_context=mp.get_context("spawn")) as ex:
        mj_s, ir_s, dec_s, s_s = ex.submit(trees_phase).result()
    bin2 = ["normal", "event"]

    # 1. heart-rate alarm: binary-weight intnn in the spike single-layer form
    X, ev = hr_windows(np.random.default_rng(1), N_TRAIN)
    hr = intnn_example("hr_alarm_intnn_binary", title="heart-rate alarm",
                       task="Wearable heart-rate sensor: 8 readings over 16 s -> abnormal rate alarm yes/no.",
                       signal=HR_SIGNAL, X=X, y=(ev > 0).astype(np.int64), classes=["normal", "abnormal rate"],
                       bits=4, signed=True, hidden=[8], wtype="binary", seed=1, spike_form=True)
    ev_te = split(ev)[1]

    # 2. fall detection: ternary intnn
    X, y = fall_windows(np.random.default_rng(2), N_TRAIN)
    intnn_example("fall_intnn_ternary", title="fall detection",
                  task="Wrist accelerometer: 6 features of a 4 s window -> fall yes/no.",
                  signal="6 accelerometer window features (5-bit signed: peak, jerk, tilt change, free-fall, "
                         "stillness, step regularity); a fall shifts all six together, 25 % of non-falls are hard "
                         "sit-downs with a high peak and jerk only; unit-variance noise x 3.",
                  X=X, y=y, classes=["no fall", "fall"], bits=5, signed=True, hidden=[12], wtype="ternary", seed=2)

    # 3. breathing pause: 4-bit intnn, 3 classes
    X, y = breath_windows(np.random.default_rng(3), N_TRAIN)
    intnn_example("breathing_pause_intnn_4bit_3class", title="breathing pause",
                  task="Chest respiration band: breath amplitude over 30 s -> normal / shallow / pause.",
                  signal="6 breath-amplitude sub-windows of 5 s (4-bit); shallow breathing scales 2-4 consecutive "
                         "sub-windows to 35-60 %, a pause holds 2-3 consecutive sub-windows near zero (10-15 s); "
                         "per-window and per-sample noise.",
                  X=X, y=y, classes=["normal", "shallow", "pause"], bits=4, signed=False, hidden=[10, 8],
                  wtype="4bit", seed=3)

    # 4. irregular beat: torchlogix
    irregular_beat_logic()

    # 5. seizure-like EEG burst: wide input streamed into the chip (24 x 6-bit = 144 bits)
    X, y = eeg_windows(np.random.default_rng(14), N_TRAIN)
    intnn_example("eeg_burst_stream_intnn_wide", title="seizure-like EEG burst",
                  task="One EEG channel: 24 raw samples (1.5 s) streamed in one 15-bit word per strobe -> "
                       "seizure-like burst yes/no.",
                  signal="24 samples at 16 Hz (6-bit signed, about 5 uV per unit) of AR(1) background noise; the "
                         "event is a 3 Hz spike-and-wave burst of 12-22 units from a random onset; 30 % of normal "
                         "windows carry a slow blink-like bump.",
                  X=X, y=y, classes=["background", "burst"], bits=6, signed=True, hidden=[8], wtype="ternary",
                  seed=14)
    stream = json.loads((OUT / "eeg_burst_stream_intnn_wide" / "chip.json").read_text())
    stream["stream_generic_too"] = True
    (OUT / "eeg_burst_stream_intnn_wide" / "chip.json").write_text(json.dumps(stream, indent=1) + "\n")

    # 6. fusion AND: heart-rate head (same parameters as example 1) AND an SpO2 head, each on its own port
    hr_p, hr_X, hr_dec, hr_y = hr
    Xs, ys = spo2_windows(np.random.default_rng(8), N_TRAIN)
    (Xs_tr, Xs_te), (ys_tr, ys_te) = split(Xs), split(ys)
    ps, _ = train_intnn(Xs_tr, ys_tr, hidden=[8], wtype="4bit", n_cls=2, seed=8)
    fusion_example("hr_spo2_fusion_and", title="heart rate AND SpO2 alarm",
                   task="Two sensors on two ports: abnormal heart rate AND desaturation -> confirmed alarm, which "
                        "suppresses single-sensor false alarms.",
                   signal="windows from the heart-rate and SpO2 generators above, paired by index; the ground truth "
                          "is both events present (independent draws, so about a quarter of the windows).",
                   heads={"hr": ({**hr_p, "in_spec": {"lanes": 8, "bits": 4, "signed": True}},
                                 {"format": "intnn", "args": {"name": "hr"}}, hr_X, {"y": hr_dec}),
                          "spo2": ({**ps, "in_spec": {"lanes": 6, "bits": 4, "signed": False}},
                                   {"format": "intnn", "args": {"name": "spo2"}}, Xs_te,
                                   {"y": intnn_forward(ps, Xs_te)[0]})},
                   fusion=[{"name": "alarm", "op": "and", "inputs": ["hr_y", "spo2_y"]}], shared=False,
                   model_size="heads: intnn binary 8 -> 8 -> 1 (heart rate) and intnn 4-bit 6 -> 8 -> 1 (SpO2)",
                   labels={"alarm": hr_y & ys_te, "hr_y": hr_y, "spo2_y": ys_te}, classes2=bin2,
                   note="Heads: heart rate (same parameters as hr_alarm_intnn_binary) and SpO2 (intnn 4-bit weights "
                        "6 -> 8 -> 1, 4-bit input), each on its own input port.")

    # 7. fusion OR: two heads on one shared heart-rate port -> any rate alarm
    Xh, evh = hr_windows(np.random.default_rng(9), N_TRAIN)
    (Xh_tr, Xh_te), (ev_tr, ev_te2) = split(Xh), split(evh)
    pa, _ = train_intnn(Xh_tr, (ev_tr == 1).astype(np.int64), hidden=[8], wtype="ternary", n_cls=2, seed=9)
    pb, _ = train_intnn(Xh_tr, (ev_tr == 2).astype(np.int64), hidden=[6], wtype="ternary", n_cls=2, seed=10)
    spec = {"lanes": 8, "bits": 4, "signed": True}
    fusion_example("hr_tachy_brady_fusion_or", title="fast OR slow heart rate",
                   task="One heart-rate sensor, two heads on the shared port (too fast, too slow) -> OR: any "
                        "rate alarm.",
                   signal=HR_SIGNAL,
                   heads={"tachy": ({**pa, "in_spec": spec}, {"format": "intnn", "args": {"name": "tachy"}}, Xh_te,
                                    {"y": intnn_forward(pa, Xh_te)[0]}),
                          "brady": ({**pb, "in_spec": spec}, {"format": "intnn", "args": {"name": "brady"}}, Xh_te,
                                    {"y": intnn_forward(pb, Xh_te)[0]})},
                   fusion=[{"name": "any_alarm", "op": "or", "inputs": ["tachy_y", "brady_y"]}], shared=True,
                   model_size="heads: intnn ternary 8 -> 8 -> 1 (fast) and 8 -> 6 -> 1 (slow) on one port",
                   labels={"any_alarm": (ev_te2 > 0).astype(np.int64), "tachy_y": (ev_te2 == 1).astype(np.int64),
                           "brady_y": (ev_te2 == 2).astype(np.int64)}, classes2=bin2,
                   note="Heads: two intnn ternary nets reading the same 8 x 4-bit signed port (shared_inputs=true).")

    # 8. multi-sensor fusion alarm: 2-of-3 vote over heart rate, respiration (intnn) and SpO2 (TreeLUT)
    D = deterioration_windows(21)
    heads = {}
    for h, seed in (("hr", 21), ("resp", 22)):
        (X_tr, X_te), (y_tr, _) = split(D[h]), split(D["shows"][h])
        p, _ = train_intnn(X_tr, y_tr, hidden=[6], wtype="ternary", n_cls=2, seed=seed)
        heads[h] = ({**p, "in_spec": {"lanes": 4, "bits": 5, "signed": True}}, {"format": "intnn", "args": {"name": h}},
                    X_te, {"y": intnn_forward(p, X_te)[0]})
    heads["spo2"] = (mj_s, {"format": "xgboost_json", "args": {"w_feature": 4, "w_tree": 3, "name": "spo2"},
                            "fallback": {"format": "chipir", "model": ir_s, "args": {"name": "spo2"}}},
                     split(D["spo2"])[1], {"y": dec_s, "scores": s_s})
    y_te = split(D["y"])[1]
    fusion_example("multi_sensor_fusion_kofn", title="multi-sensor fusion alarm",
                   task="Three vital-sign sensors on three ports, mixed model formats -> 2-of-3 vote "
                        "deterioration alarm.",
                   signal=DET_SIGNAL, heads=heads,
                   fusion=[{"name": "alarm", "op": "kofn", "k": 2, "inputs": ["hr_y", "resp_y", "spo2_y"]}],
                   shared=False,
                   model_size="heads: intnn ternary 4 -> 6 -> 1 (heart rate, respiration; 5-bit) and XGBoost "
                              "6 x depth 3 via TreeLUT (SpO2, 4-bit)",
                   labels={"alarm": y_te, "hr_y": y_te, "resp_y": y_te, "spo2_y": y_te}, classes2=bin2,
                   note="Heads: heart rate and respiration rate (intnn ternary 4 -> 6 -> 1, 5-bit signed) and SpO2 "
                        "(XGBoost 6 x depth 3 via TreeLUT, 4 x 4-bit), each on its own port; every head and the "
                        "vote are scored against the hidden deterioration state.")


if __name__ == "__main__":
    main()
