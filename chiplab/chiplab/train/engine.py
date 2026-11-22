"""Population training of a batch of candidate designs, and the exact torch-side predictions used for checks.

Training and selection only ever see split parts 0 (train) and 1 (val). The sealed test part is reachable
only through predict_candidate(), which the tools layer calls via the referee and logs.
"""
from __future__ import annotations

import importlib
import json
import time
from pathlib import Path

import numpy as np
import torch

from chiplab.data.contract import View
from chiplab.data.encode import encode, encoding_key
from chiplab.data.splits import SealedTestError
from chiplab.plugins.base import BatchInputs, ModelFamily
from chiplab.referee import metrics as M


def get_family(name: str) -> ModelFamily:
    try:
        reg = importlib.import_module("chiplab.plugins.registry")
        if hasattr(reg, "get_family"):
            return reg.get_family(name)
    except ModuleNotFoundError:
        pass
    mod = importlib.import_module(f"chiplab.plugins.families.{name}")
    return mod.FAMILY


def _device(opts: dict) -> str:
    d = opts.get("device")
    if d:
        return d
    return "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")


def _encode_all(view_part: View, specs: list[dict], fit_part: View | None, fitted: dict | None = None):
    """-> keys per candidate, int arrays per key, in_specs per key, fitted spec per key."""
    keys, arrays, in_specs, fit_out = [], {}, {}, {}
    for spec in specs:
        key = encoding_key(spec)
        keys.append(key)
        if key in arrays:
            continue
        use = fitted[key] if fitted else spec
        Xi, ins, fs = encode(view_part.X, use, fit_X=None if fitted else (fit_part.X if fit_part is not None else None))
        arrays[key], in_specs[key], fit_out[key] = Xi, ins, (fitted[key] if fitted else fs)
    return keys, arrays, in_specs, fit_out


def _batch_inputs(keys, arrays, in_specs, dev, y=None) -> BatchInputs:
    t = {k: torch.as_tensor(v, dtype=torch.float32, device=dev) for k, v in arrays.items()}
    return BatchInputs(keys=keys, tensors=t, in_specs=in_specs,
                       y=None if y is None else torch.as_tensor(y, dtype=torch.long, device=dev))


def _row(k: int, cand: dict, s: dict, cost: dict) -> dict:
    r = {"k": k, "family": cand["family"], **{f"cfg.{a}": b for a, b in cand["cfg"].items() if a not in
                                              ("epochs", "lr", "batch_size", "class_weight", "seed")},
         **{f"enc.{a}": b for a, b in cand["encoding"].items()}}
    w = s["window"]
    r.update(val_win_f1=w.get("f1"), val_win_sens=w.get("sens"), val_win_spec=w.get("spec"),
             val_win_acc=w.get("acc"))
    if "record" in s:
        r.update(val_rec_f1=s["record"]["f1"], val_rec_sens=s["record"]["sens"], val_rec_spec=s["record"]["spec"],
                 val_worst_subject_sens=s["subject"]["worst_sens"], val_worst_subject_spec=s["subject"]["worst_spec"])
    r["est"] = cost
    return r


def run_batch(view: View, cands: list[dict], opts: dict, batch_dir: Path) -> dict:
    """Train all candidates at once on train, score on val. opts: device, epochs/lr/... overrides."""
    if any(p in (opts.get("train_parts") or [0]) for p in (2,)) or 2 in (opts.get("select_parts") or [1]):
        raise SealedTestError("the test part is sealed: training and selection use parts 0 and 1 only")
    batch_dir = Path(batch_dir); batch_dir.mkdir(parents=True, exist_ok=True)
    fams = {c["family"] for c in cands}
    if len(fams) != 1:
        raise ValueError(f"one family per batch (population training); got {sorted(fams)}")
    fam = get_family(fams.pop())
    over = {k: opts[k] for k in ("epochs", "lr", "batch_size", "class_weight", "seed") if k in opts}
    cfgs = [fam.validate_cfg({**c["cfg"], **over}) for c in cands]
    cands = [{**c, "cfg": cfg} for c, cfg in zip(cands, cfgs)]
    dev = _device(opts)
    vtr, vva = view.select(0), view.select(1)
    if len(vtr) == 0 or len(vva) == 0:
        raise ValueError("train and val parts must both have windows")
    specs = [c["encoding"] for c in cands]
    t_enc = time.time()
    keys, Atr, ins, fitted = _encode_all(vtr, specs, vtr)
    _, Ava, _, _ = _encode_all(vva, specs, None, fitted=fitted)
    t_enc = time.time() - t_enc
    bi_tr = _batch_inputs(keys, Atr, ins, dev, y=vtr.y)
    bi_va = _batch_inputs(keys, Ava, ins, dev)
    state = fam.train(cfgs, bi_tr, dev, {"n_classes": len(view.classes)})
    secs = float(state.get("train_seconds", 0.0))
    pv = fam.predict(state, bi_va, dev)
    rows = []
    for k, c in enumerate(cands):
        s = M.summary(vva, pv[k])
        rows.append(_row(k, c, s, fam.est_cost(c["cfg"], ins[keys[k]])))
    timing = {"device": dev, "K": len(cands), "train_seconds": round(secs, 3),
              "cand_per_min": round(len(cands) * 60 / max(secs, 1e-9), 1), "encode_seconds": round(t_enc, 3),
              "n_train_windows": int(len(vtr)), "n_val_windows": int(len(vva)),
              "populations": len(state.get("groups", [])) or 1}
    torch.save(state, batch_dir / "state.pt")
    (batch_dir / "cands.json").write_text(json.dumps(cands, indent=1))
    (batch_dir / "encodings.json").write_text(json.dumps({"keys": keys, "fitted": fitted, "in_specs": ins}, indent=1))
    (batch_dir / "val_scores.json").write_text(json.dumps(rows))
    (batch_dir / "batch.json").write_text(json.dumps({"timing": timing, "opts": {k: v for k, v in opts.items()
                                                                                 if isinstance(v, (int, float, str, bool, list, dict))},
                                                      "classes": view.classes}, indent=1))
    return {"batch_dir": str(batch_dir), "timing": timing, "rows": rows}


def load_batch(batch_dir: Path) -> dict:
    b = Path(batch_dir)
    enc = json.loads((b / "encodings.json").read_text())
    return {"dir": b, "state": torch.load(b / "state.pt", weights_only=False),
            "cands": json.loads((b / "cands.json").read_text()), "keys": enc["keys"], "fitted": enc["fitted"],
            "in_specs": enc["in_specs"], "rows": json.loads((b / "val_scores.json").read_text()),
            "batch": json.loads((b / "batch.json").read_text())}


def encoded_inputs(view: View, fitted_encoding: dict, part: int) -> np.ndarray:
    """Integer chip inputs for one split part (int64 [N, lanes])."""
    return encode(view.select(part).X, fitted_encoding)[0]


def lower_candidate(batch_dir: Path, k: int) -> dict:
    B = load_batch(batch_dir)
    c = B["cands"][k]
    fam = get_family(c["family"])
    key = B["keys"][k]
    ir = fam.lower(B["state"], k, B["in_specs"][key])
    ir.setdefault("meta", {}).update({"family": c["family"], "cfg": c["cfg"], "encoding": B["fitted"][key],
                                      "in_spec": B["in_specs"][key], "candidate": k, "batch_dir": str(batch_dir),
                                      "val": B["rows"][k]})
    return ir


def predict_candidate(batch_dir: Path, k: int, view: View, part: int, dev: str | None = None) -> np.ndarray:
    """The trained model's exact decisions on one part (torch path), for circuit = model = training checks."""
    B = load_batch(batch_dir)
    fam = get_family(B["cands"][k]["family"])
    vp = view.select(part)
    # only the candidate's own population needs inputs; encode the encodings its population reads
    state = B["state"]
    grp = next((g for g in state.get("groups", []) if k in g["members"]), None)
    members = grp["members"] if grp else list(range(len(B["cands"])))
    need = {B["keys"][m] for m in members}
    arrays = {key: encode(vp.X, B["fitted"][key])[0] for key in need}
    sub = dict(state); sub["groups"] = [grp] if grp else state["groups"]
    dev = dev or ("cuda" if torch.cuda.is_available() else "cpu")
    bi = _batch_inputs(B["keys"], arrays, B["in_specs"], dev)
    return fam.predict(sub, bi, dev)[k]


def best(rows: list[dict], metric: str = "val_win_f1", where=None) -> dict:
    """Best row by a val metric; ties -> fewer estimated weights (smaller chip)."""
    rs = [r for r in rows if (where is None or where(r)) and r.get(metric) is not None]
    if not rs:
        raise ValueError("no candidate matches")
    return max(rs, key=lambda r: (r[metric], -r["est"]["weights"]))
