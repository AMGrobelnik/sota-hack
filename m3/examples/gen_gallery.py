"""Build the chip lab's example model gallery from seeded synthetic data.

Run with the lab's venv python (it has torch, torchlogix, xgboost):
    chiplab/.venv/bin/python m3/examples/gen_gallery.py

Every example lands in m3/examples/<name>/ as
    model.json   the model in the format the lab ingests (XGBoost JSON, intnn params, torchlogix gate list,
                 or a list of heads plus fusion rules)
    model.pt     torchlogix only: the saved module (a pickle made here; ingest it only from this machine)
    chip.json    how run_gallery.py brings it in through the CLI
    vectors.npz  in_<port> inputs and out_<output> expected outputs, computed by the model's own framework
                 or by a plain numpy reading of its integer semantics, never by the lab
    README.md    one line on the generic sensor task, plus training details

All data is synthetic and seeded: no recordings, no downloads, no patient data.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# torch is imported inside the functions that train with it, so the spawned XGBoost process never loads it

OUT = Path(__file__).resolve().parent
N_VEC = 256


# ------------------------------------------------------------------------------------------------ helpers

def write_example(name: str, *, desc: str, model: dict, chip: dict, vectors: dict, notes: list[str],
                  extra: dict | None = None) -> None:
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "model.json").write_text(json.dumps(model) + "\n")
    for fn, doc in (extra or {}).items():
        (d / fn).write_text(json.dumps(doc) + "\n")
    (d / "chip.json").write_text(json.dumps(chip, indent=1) + "\n")
    np.savez_compressed(d / "vectors.npz", **{k: np.asarray(v, dtype=np.int64) for k, v in vectors.items()})
    ins = [k[3:] for k in vectors if k.startswith("in_")]
    outs = [k[4:] for k in vectors if k.startswith("out_")]
    lines = [f"# {name}", "", desc, "", f"- Chip flow: `{chip['kind']}` (see `chip.json`).",
             f"- Vectors: {len(next(iter(vectors.values())))} in `vectors.npz`; inputs {ins}, expected outputs {outs}.",
             *[f"- {n}" for n in notes], "",
             "Synthetic data, seeded; rebuilt by `m3/examples/gen_gallery.py`. Chip numbers: `../RESULTS.md`.", ""]
    (d / "README.md").write_text("\n".join(lines))


def split(X, y, n_test=N_VEC):
    return X[:-n_test], y[:-n_test], X[-n_test:], y[-n_test:]


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


def intnn_example(name, desc, X, y, *, bits, signed, hidden, wtype, n_cls, seed, spike_form=False):
    Xtr, ytr, Xte, yte = split(X, y)
    p, acc_tr = train_intnn(Xtr, ytr, hidden=hidden, wtype=wtype, n_cls=n_cls, seed=seed)
    dec, _ = intnn_forward(p, Xte)
    acc_te = float((dec[:, 0] == yte).mean())
    spec = {"lanes": X.shape[1], "bits": bits, "signed": signed}
    if spike_form:      # the feasibility-spike single-hidden-layer form (cfg/W1/b1/shift/W2/b2/amax)
        L = p["layers"][0]
        model = {"cfg": {"L": X.shape[1], "bits": bits, "H": len(L["W"]), "signed": signed, "wtype": wtype},
                 "W1": L["W"], "b1": L["b"], "shift": L["shift"], "W2": p["Wo"][0], "b2": p["bo"][0], "amax": L["amax"]}
    else:
        model = {**p, "in_spec": spec, "wtype": wtype}
    write_example(name, desc=desc, model=model,
                  chip={"kind": "ingest", "format": "intnn", "args": {"name": name}},
                  vectors={"in_x": Xte, "out_y": dec},
                  notes=[f"intnn, {wtype} hidden weights, layers {[X.shape[1], *hidden, len(p['Wo'])]}, input "
                         f"{X.shape[1]} lanes x {bits}-bit {'signed' if signed else 'unsigned'}"
                         + (", spike single-layer form" if spike_form else ", multi-layer form") + ".",
                         f"Accuracy of the integer model on synthetic data (numpy, this Mac): train {acc_tr:.3f}, "
                         f"held-out vectors {acc_te:.3f}.",
                         "Expected outputs: plain numpy of the intnn integer semantics (h = clip((W h + b) >> shift, "
                         "0, amax); score > 0 or argmax)."])
    return p, Xte, dec


# ------------------------------------------------------------------------------------------------ synthetic tasks

def task_vibration(rng, n, lanes=8, bits=4):
    """Band energies of a machine vibration spectrum (deviation from baseline); fault = energy in bands 5-7."""
    lim = (1 << (bits - 1)) - 1
    y = rng.integers(0, 2, n)
    X = rng.normal(0, 1.6, (n, lanes))
    X[:, 5:8] += np.where(y[:, None] == 1, 2.5, -0.5)
    return np.clip(np.round(X), -lim - 1, lim).astype(np.int64), y


def task_fall(rng, n, lanes=6, bits=5):
    """Accelerometer window features (peak, jerk, tilt change, ...); fall = high peak + tilt change + stillness."""
    lim = (1 << (bits - 1)) - 1
    y = rng.integers(0, 2, n)
    X = rng.normal(0, 3, (n, lanes))
    X[:, 0] += np.where(y == 1, 7, 0); X[:, 2] += np.where(y == 1, 6, -1); X[:, 4] -= np.where(y == 1, 5, 0)
    return np.clip(np.round(X), -lim - 1, lim).astype(np.int64), y


def task_hvac(rng, n):
    """Room temperature, setpoint gap, humidity, CO2, occupancy, outside temp (4-bit); idle / heat / cool."""
    y = rng.integers(0, 3, n)
    X = rng.normal(8, 2.2, (n, 6))
    X[:, 1] += np.select([y == 1, y == 2], [4.0, -4.0], 0.0)
    X[:, 0] += np.select([y == 1, y == 2], [-2.0, 2.0], 0.0)
    return np.clip(np.round(X), 0, 15).astype(np.int64), y


def task_gesture(rng, n):
    """16 capacitive touch pads (1 bit each, thresholded off-chip); swipe-left / swipe-right / tap."""
    y = rng.integers(0, 3, n)
    p = np.full((n, 16), 0.1)
    p[y == 0, :8] = 0.75; p[y == 1, 8:] = 0.75; p[y == 2, 5:11] = 0.85
    return (rng.random((n, 16)) < p).astype(np.int64), y


def task_leak(rng, n):
    """Water pipe: pressure drop, flow, night flow, acoustic level, temperature, valve state (4-bit); leak or not."""
    y = rng.integers(0, 2, n)
    X = rng.normal(6, 2.5, (n, 6))
    X[:, 0] += np.where(y == 1, 3.5, 0); X[:, 2] += np.where(y == 1, 3.0, 0); X[:, 3] += np.where(y == 1, 2.0, 0)
    return np.clip(np.round(X), 0, 15).astype(np.int64), y


def task_air(rng, n):
    """Air sensor: PM2.5, VOC, CO2, humidity, temperature (4-bit); good / moderate / poor."""
    y = rng.integers(0, 3, n)
    X = rng.normal(4, 2.0, (n, 5))
    X[:, 0] += 3.5 * y; X[:, 1] += 2.5 * y; X[:, 2] += 1.5 * y
    return np.clip(np.round(X), 0, 15).astype(np.int64), y


def task_temp(rng, n):
    """Bearing temperature trend: 4 samples (6-bit unsigned, 1 unit = 1 degree above ambient); overheating or not."""
    y = rng.integers(0, 2, n)
    base = rng.normal(20, 6, n) + np.where(y == 1, 18, 0)
    X = base[:, None] + rng.normal(0, 3, (n, 4)) + np.arange(4) * np.where(y == 1, 2, 0)[:, None]
    return np.clip(np.round(X), 0, 63).astype(np.int64), y


def task_gas(rng, n, lanes=4, bits=5, shift=0.0):
    """One gas sensor's features (baseline drift, rise rate, peak, recovery); gas present or not."""
    y = rng.integers(0, 2, n)
    X = rng.normal(shift, 3, (n, lanes))
    X[:, 1] += np.where(y == 1, 6, 0); X[:, 2] += np.where(y == 1, 5, 0)
    lim = (1 << (bits - 1)) - 1
    return np.clip(np.round(X), -lim - 1, lim).astype(np.int64), y


def task_strain(rng, n, lanes=24, bits=6):
    """24 consecutive strain-gauge samples (6-bit signed); impact event = a sharp spike then ringing."""
    y = rng.integers(0, 2, n)
    X = rng.normal(0, 4, (n, lanes))
    t = np.arange(lanes)
    pos = rng.integers(4, 12, n)
    ring = 20 * np.exp(-0.35 * np.clip(t[None, :] - pos[:, None], 0, None)) * np.cos(1.6 * (t[None, :] - pos[:, None]))
    X += np.where((y[:, None] == 1) & (t[None, :] >= pos[:, None]), ring, 0)
    lim = (1 << (bits - 1)) - 1
    return np.clip(np.round(X), -lim - 1, lim).astype(np.int64), y


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


def tree_example(name, desc, X, y, *, n_cls, seed, n_estimators, max_depth, w_feature=4, w_tree=3):
    Xtr, ytr, Xte, yte = split(X, y)
    mj, tl = train_xgb(Xtr, ytr, n_cls, seed, n_estimators, max_depth, w_feature, w_tree)
    dec, s = treelut_scores(tl, Xte)
    acc_tr = float((np.asarray(tl.predict(Xtr)).astype(int).reshape(-1) == ytr).mean())
    acc_te = float((dec[:, 0] == yte).mean())
    write_example(name, desc=desc, model=mj,
                  chip={"kind": "ingest", "format": "xgboost_json", "args": {"w_feature": w_feature, "w_tree": w_tree,
                                                                              "name": name},
                        "fallback": {"format": "chipir", "file": "chipir.json", "args": {"name": name}}},
                  extra={"chipir.json": treelut_chipir(tl, name)},
                  vectors={"in_x": Xte, "out_y": dec, "out_scores": s},
                  notes=[f"XGBoost {xgboost_version()}, {n_estimators} rounds x depth {max_depth}, "
                         f"{'binary' if n_cls == 2 else f'{n_cls} classes'}; TreeLUT w_feature={w_feature}, w_tree={w_tree}.",
                         f"Accuracy of TreeLUT's quantised model on synthetic data (this Mac): train {acc_tr:.3f}, "
                         f"held-out vectors {acc_te:.3f}.",
                         "Expected outputs: TreeLUT's own predict (vendored copy) and its per-class integer sums.",
                         "`chipir.json`: the same model after the lab's TreeLUT converter, ingested as format chipir "
                         "when the CLI's xgboost_json path fails (see ../RESULTS.md)."])
    return mj, tl, Xte, dec, s


def xgboost_version():
    import xgboost
    return xgboost.__version__


# ------------------------------------------------------------------------------------------------ torchlogix

def gesture_logic(seed=5):
    import torch
    from torchlogix.layers import GroupSum, LogicDense
    from torchlogix.utils import set_export_mode
    rng = np.random.default_rng(seed)
    X, y = task_gesture(rng, 3000)
    Xtr, ytr, Xte, yte = split(X, y)
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
    name = "gesture_logic_3class"
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
    write_example(name, desc="Gesture pad: 16 thresholded capacitive touch pads -> swipe-left / swipe-right / tap.",
                  model={"format": "torchlogix", "file": "model.pt", "layers": layers,
                         "note": "readable copy of the discrete network; the lab ingests model.pt"},
                  chip={"kind": "ingest", "format": "torchlogix", "args": {"path": "model.pt", "trusted": True,
                                                                            "name": name}},
                  vectors={"in_x": Xte, "out_y": dec, "out_scores": s},
                  notes=["torchlogix LogicDense(16,48) -> LogicDense(48,48) -> GroupSum(3, tau=4), 150 Adam steps; "
                         "model.pt is the saved module (pickle written on this machine).",
                         f"Accuracy of the discrete network on synthetic data (this Mac): train {acc_tr:.3f}, held-out "
                         f"vectors {float((dec[:, 0] == yte).mean()):.3f}.",
                         "Expected outputs: torchlogix's own export-mode forward (also checked against eval mode x tau)."])


# ------------------------------------------------------------------------------------------------ fusion

def fusion_example(name, desc, heads: dict, fusion: list, shared: bool, note: str):
    """heads: name -> (model, chip-ingest dict, X_test, {output: expected})."""
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
    write_example(name, desc=desc, model=model, chip={"kind": "compose", "shared_inputs": shared, "fusion": fusion},
                  vectors=vec, notes=[note, "Expected fusion outputs: numpy over the heads' expected decisions "
                                            "(and = all, or = any, kofn = at least k)."])


# ------------------------------------------------------------------------------------------------ gallery

def trees_phase():
    """All XGBoost training, in its own process: on macOS XGBoost's and torch's OpenMP runtimes crash or deadlock
    when both train in one process. Returns the gas_c head of the k-of-n example as plain lists."""
    X, y = task_leak(np.random.default_rng(6), 3000)
    tree_example("leak_treelut_binary", "Water pipe: 6 pressure/flow/acoustic features (4-bit) -> leak yes/no.",
                 X, y, n_cls=2, seed=6, n_estimators=8, max_depth=3)
    X, y = task_air(np.random.default_rng(7), 3000)
    tree_example("air_treelut_3class", "Indoor air: PM2.5, VOC, CO2, humidity, temperature (4-bit) -> good / "
                 "moderate / poor.", X, y, n_cls=3, seed=7, n_estimators=6, max_depth=3)
    # gas_c head of the k-of-n example: an XGBoost model on 4 features
    Xc, yc = task_leak(np.random.default_rng(13), 3000)
    Xc = Xc[:, :4]
    Xtr, ytr, Xte_c, _ = split(Xc, yc)
    mj_c, tl_c = train_xgb(Xtr, ytr, 2, 13, 6, 3, 4, 3)
    dec_c, s_c = treelut_scores(tl_c, Xte_c)
    return mj_c, treelut_chipir(tl_c, "gas_c"), Xte_c, dec_c, s_c


def main():
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(1, mp_context=mp.get_context("spawn")) as ex:
        mj_c, ir_c, Xte_c, dec_c, s_c = ex.submit(trees_phase).result()
    rng = np.random.default_rng(1)
    X, y = task_vibration(rng, 3000)
    vib = intnn_example("vibration_intnn_binary", "Machine vibration: 8 band-energy deviations (4-bit signed) -> "
                        "bearing fault yes/no.", X, y, bits=4, signed=True, hidden=[8], wtype="binary", n_cls=2,
                        seed=1, spike_form=True)
    X, y = task_fall(np.random.default_rng(2), 3000)
    intnn_example("fall_intnn_ternary", "Wearable accelerometer: 6 window features (5-bit signed) -> fall yes/no.",
                  X, y, bits=5, signed=True, hidden=[12], wtype="ternary", n_cls=2, seed=2)
    X, y = task_hvac(np.random.default_rng(3), 3000)
    intnn_example("hvac_intnn_4bit_3class", "Room climate: 6 sensor readings (4-bit) -> idle / heat / cool.",
                  X, y, bits=4, signed=False, hidden=[10, 8], wtype="4bit", n_cls=3, seed=3)
    gesture_logic()

    # fusion AND: vibration head (own port) + temperature head (own port) -> fault alarm only when both agree
    rt = np.random.default_rng(8)
    Xt, yt = task_temp(rt, 3000)
    Xtr, ytr, Xte_t, _ = split(Xt, yt)
    pt, _ = train_intnn(Xtr, ytr, hidden=[6], wtype="ternary", n_cls=2, seed=8)
    temp_head = ({**pt, "in_spec": {"lanes": 4, "bits": 6, "signed": False}}, {"format": "intnn", "args": {"name": "temp"}},
                 Xte_t, {"y": intnn_forward(pt, Xte_t)[0]})
    vib_p, vib_X, vib_dec = vib
    vib_head = ({**vib_p, "in_spec": {"lanes": 8, "bits": 4, "signed": True}}, {"format": "intnn", "args": {"name": "vib"}},
                vib_X, {"y": vib_dec})
    fusion_example("machine_fault_fusion_and", "Motor monitor, two sensors on two ports: vibration head AND bearing-"
                   "temperature head -> confirmed fault alarm.", {"vib": vib_head, "temp": temp_head},
                   [{"name": "fault", "op": "and", "inputs": ["vib_y", "temp_y"]}], False,
                   "Heads: vibration (intnn binary, same parameters as vibration_intnn_binary) and temperature "
                   "(intnn ternary 4 -> 6 -> 1), each on its own input port.")

    # fusion OR: two heads on one shared port (same vibration features) -> any alarm
    rv = np.random.default_rng(9)
    Xv, yv = task_vibration(rv, 3000)
    y_imb = (Xv[:, 0] + Xv[:, 1] > 3).astype(np.int64)      # second fault type: imbalance shows in bands 0-1
    Xtr, ytr, Xte_v, _ = split(Xv, yv)
    _, ytr2, _, _ = split(Xv, y_imb)
    pa, _ = train_intnn(Xtr, ytr, hidden=[8], wtype="ternary", n_cls=2, seed=9)
    pb, _ = train_intnn(Xtr, ytr2, hidden=[6], wtype="ternary", n_cls=2, seed=10)
    spec = {"lanes": 8, "bits": 4, "signed": True}
    fusion_example("vibration_any_alarm_fusion_or", "One vibration sensor, two fault heads on the shared port "
                   "(bearing wear, imbalance) -> OR: any-fault alarm.",
                   {"bearing": ({**pa, "in_spec": spec}, {"format": "intnn", "args": {"name": "bearing"}}, Xte_v,
                                {"y": intnn_forward(pa, Xte_v)[0]}),
                    "imbalance": ({**pb, "in_spec": spec}, {"format": "intnn", "args": {"name": "imbalance"}}, Xte_v,
                                  {"y": intnn_forward(pb, Xte_v)[0]})},
                   [{"name": "any_fault", "op": "or", "inputs": ["bearing_y", "imbalance_y"]}], True,
                   "Heads: two intnn ternary nets reading the same 8 x 4-bit signed input port (shared_inputs=true).")

    # fusion k-of-n: three redundant gas sensors, two intnn heads and one TreeLUT head -> 2-of-3 vote
    heads = {}
    for i, (h, sh) in enumerate((("gas_a", 0.0), ("gas_b", 1.0))):
        Xg, yg = task_gas(np.random.default_rng(11 + i), 3000, shift=sh)
        Xtr, ytr, Xte_g, _ = split(Xg, yg)
        pg, _ = train_intnn(Xtr, ytr, hidden=[6], wtype="ternary", n_cls=2, seed=11 + i)
        heads[h] = ({**pg, "in_spec": {"lanes": 4, "bits": 5, "signed": True}}, {"format": "intnn", "args": {"name": h}},
                    Xte_g, {"y": intnn_forward(pg, Xte_g)[0]})
    heads["gas_c"] = (mj_c, {"format": "xgboost_json", "args": {"w_feature": 4, "w_tree": 3, "name": "gas_c"},
                             "fallback": {"format": "chipir", "model": ir_c,
                                          "args": {"name": "gas_c"}}}, Xte_c,
                      {"y": dec_c, "scores": s_c})
    fusion_example("gas_vote_fusion_kofn", "Three redundant gas sensors on three ports, mixed model formats -> "
                   "2-of-3 vote alarm.", heads, [{"name": "gas_alarm", "op": "kofn", "k": 2,
                                                  "inputs": ["gas_a_y", "gas_b_y", "gas_c_y"]}], False,
                   "Heads: gas_a, gas_b (intnn ternary 4 -> 6 -> 1, 5-bit signed) and gas_c (XGBoost 6 x depth 3 "
                   "via TreeLUT, 4 x 4-bit), each on its own port.")

    # streaming: a wide frame (24 x 6-bit = 144 bits = 10 words of 15 bits) streamed in one word per strobe
    X, y = task_strain(np.random.default_rng(14), 3000)
    intnn_example("impact_stream_intnn_wide", "Structural monitor: 24 consecutive strain-gauge samples (6-bit signed) "
                  "streamed in one 15-bit word per strobe -> impact yes/no.", X, y, bits=6, signed=True, hidden=[8],
                  wtype="ternary", n_cls=2, seed=14)
    stream = json.loads((OUT / "impact_stream_intnn_wide" / "chip.json").read_text())
    stream["stream_generic_too"] = True
    (OUT / "impact_stream_intnn_wide" / "chip.json").write_text(json.dumps(stream, indent=1) + "\n")


if __name__ == "__main__":
    main()
