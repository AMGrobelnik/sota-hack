"""End-to-end: split by baby, features, a family of tiny quantised detectors, thresholds on validation babies,
event scoring on held-out babies. Writes designs.json (no window-level data) into the output folder.

usage: python -I -m neonatal_eeg.pipeline --data DIR --out DIR --babies N [--stage 1|2] [--workers K]
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from loguru import logger

from neonatal_eeg import data as D
from neonatal_eeg import models as M
from neonatal_eeg import scoring as S

N_BABIES = 79
SPLIT_SEED = 20261122
FA_BUDGET = 1.0        # validation false alarms per hour allowed when choosing a design's threshold
MIN_EVENTS = 2         # held-out babies with fewer scored events are left out of the worst-baby figure

FAMILIES = {
    0: dict(channels=[1, 18], hidden=[0, 4], wmax=[1], seeds=[0]),          # smoke test only
    1: dict(channels=[1, 2, 4, 18], hidden=[0, 2, 4, 8, 16, 32], wmax=[1, 7], seeds=[0, 1, 2]),
    2: dict(channels=[1, 2, 4, 18], hidden=[0, 1, 2, 4, 8, 12, 16, 24, 32], wmax=[1, 3, 7], seeds=[0, 1, 2, 3]),
}


def make_split(ann_dir: Path) -> dict:
    """Stratified by whether a baby has any consensus seizure second; fixed seed; made before any modelling."""
    has = {b: int(D.read_consensus(ann_dir, b)[0].any()) for b in range(1, N_BABIES + 1)}
    rng = np.random.default_rng(SPLIT_SEED)
    parts: dict[str, list[int]] = {"train": [], "val": [], "test": []}
    for flag in (1, 0):
        group = [b for b in range(1, N_BABIES + 1) if has[b] == flag]
        group = [group[i] for i in rng.permutation(len(group))]
        n_test = round(0.3 * len(group))
        n_val = round(0.2 * len(group))
        parts["test"] += group[:n_test]
        parts["val"] += group[n_test:n_test + n_val]
        parts["train"] += group[n_test + n_val:]
    return {k: sorted(v) for k, v in parts.items()} | {"has_seizure": has}


def _cache_one(args: tuple[str, str, int]) -> int:
    D.baby_cache(Path(args[0]), Path(args[1]), args[2])
    return args[2]


def choose_threshold(scores: list[np.ndarray], cons: list[np.ndarray]) -> tuple[int, dict]:
    """Highest mean per-baby event sensitivity (validation babies with >= MIN_EVENTS events) with pooled
    validation false alarms per hour <= FA_BUDGET; if no threshold meets the budget, the fewest false alarms."""
    allv = np.concatenate(scores)
    cands = np.unique(np.quantile(allv, np.linspace(0.5, 1.0, 301), method="lower").astype(np.int64))
    best = None
    for t in cands:
        sc = [S.score_baby((s > t).astype(np.int8), c) for s, c in zip(scores, cons)]
        pb = S.pooled(sc)
        per = [x.caught / x.total for x in sc if x.total >= MIN_EVENTS]
        pb["sens_mean"] = float(np.mean(per)) if per else 0.0
        ok = pb["fah"] <= FA_BUDGET
        key = (ok, pb["sens_mean"] if ok else -pb["fah"], -pb["fah"] if ok else pb["sens_mean"], int(t))
        if best is None or key > best[0]:
            best = (key, int(t), pb)
    assert best is not None
    return best[1], best[2]


_G: dict = {}


def _init(prep: str) -> None:
    import torch
    torch.set_num_threads(1)
    z = np.load(prep, allow_pickle=False)
    _G.update({k: z[k] for k in z.files})


def _babies(part: str) -> list[tuple[np.ndarray, np.ndarray]]:
    out = []
    for i in range(int(_G[f"{part}_n"])):
        out.append((_G[f"{part}_x{i}"], _G[f"{part}_c{i}"]))
    return out


def _run_spec(spec: M.Spec) -> dict:
    t0 = time.time()
    didx = [D.ALL_DERIVS.index(d) for d in D.BUDGETS[spec.channels]]
    nf = len(D.FEATURES)
    p = M.train(spec, _G["train_x"][:, didx, :].astype(np.float32), _G["train_y"], _G["train_g"])
    flat = lambda x: x[:, didx, :].reshape(len(x), -1)
    ir0 = M.to_ir(spec, p, nf, 0, spec.id)
    sn = M.score_node(ir0)
    val = _babies("val")
    t, vstats = choose_threshold([M.eval_ir(ir0, flat(x), sn) for x, _ in val], [c for _, c in val])
    ir = M.to_ir(spec, p, nf, t, spec.id)
    per = [S.score_baby(M.eval_ir(ir, flat(x)).astype(np.int8), c) for x, c in _babies("test")]
    return {"id": spec.id, "spec": spec.__dict__, "t": t, "ir": ir, "val": vstats,
            "test": [s.__dict__ for s in per], "train_s": round(time.time() - t0, 1)}


def baseline() -> dict:
    """One channel's (C3-C4) quantised line length against a threshold chosen on validation babies."""
    d = D.ALL_DERIVS.index(D.BUDGETS[1][0])
    val = _babies("val")
    t, vstats = choose_threshold([x[:, d, 0] for x, _ in val], [c for _, c in val])
    per = [S.score_baby((x[:, d, 0] > t).astype(np.int8), c) for x, c in _babies("test")]
    return {"id": "baseline-ll-c3c4", "t": t, "val": vstats, "test": [s.__dict__ for s in per], "ir": baseline_ir(t)}


def baseline_ir(t: int) -> dict:
    """The baseline as a chip: one 6-bit line-length input compared with t."""
    return {"ir": "chipir/1", "name": "baseline-ll-c3c4",
            "inputs": [{"name": "x", "lanes": 1, "bits": M.IN_BITS, "signed": False}],
            "nodes": [{"id": "dec", "op": "cmp", "src": "x", "rel": "gt", "t": [int(t)]}],
            "outputs": [{"name": "y", "src": "dec"}], "meta": {"baseline": True}}


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--babies", type=int, required=True, help="use babies 1..N")
    ap.add_argument("--stage", type=int, default=1)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    out = a.out / f"stage{a.stage}"
    out.mkdir(parents=True, exist_ok=True)
    logger.add(out / "pipeline.log")
    split_path = a.out / "split.json"
    if split_path.exists():
        split = json.loads(split_path.read_text())
    else:
        split = make_split(a.data)
        split_path.write_text(json.dumps(split, indent=1))
    use = {k: [b for b in split[k] if b <= a.babies] for k in ("train", "val", "test")}
    logger.info(f"split in use: { {k: len(v) for k, v in use.items()} } {use}")

    cache = a.out / "cache"
    with Pool(min(a.workers, 6)) as pool:
        for b in pool.imap_unordered(_cache_one, [(str(a.data), str(cache), b) for b in sorted(sum(use.values(), []))]):
            logger.info(f"features ready: baby {b}")

    def load(b):
        z = np.load(cache / f"b{b:02d}.npz")
        return z["feats"], z["cons"], z["ywin"]

    tr = [load(b) for b in use["train"]]
    lo, hi = M.fit_quantiser(np.concatenate([f for f, _, _ in tr]))
    arrays = {"train_x": np.concatenate([M.quantise(f, lo, hi) for f, _, _ in tr]).astype(np.int16),
              "train_y": np.concatenate([y for _, _, y in tr]).astype(np.float32),
              "train_g": np.concatenate([np.full(len(y), i) for i, (_, _, y) in enumerate(tr)])}
    for part in ("val", "test"):
        arrays[f"{part}_n"] = np.array(len(use[part]))
        for i, b in enumerate(use[part]):
            f, c, _ = load(b)
            arrays[f"{part}_x{i}"] = M.quantise(f, lo, hi).astype(np.int16)
            arrays[f"{part}_c{i}"] = c
    prep = out / "prepared.npz"
    np.savez(prep, **arrays)
    logger.info(f"train windows {len(arrays['train_y'])}, positive share {arrays['train_y'].mean():.4f}")

    fam = FAMILIES[a.stage]
    specs = [M.Spec(c, h, w, s) for c, h, w, s in itertools.product(fam["channels"], fam["hidden"], fam["wmax"], fam["seeds"])]
    logger.info(f"training {len(specs)} designs")
    results = []
    with Pool(a.workers, initializer=_init, initargs=(str(prep),)) as pool:
        for r in pool.imap_unordered(_run_spec, specs):
            results.append(r)
            v = r["val"]
            logger.info(f"{len(results)}/{len(specs)} {r['id']} t={r['t']} validation mean per-baby sens "
                        f"{v['sens_mean']:.2f} pooled {v['caught']}/{v['total']} fa/h {v['fah']:.2f} ({r['train_s']}s)")
    _init(str(prep))
    base = baseline()
    # held-out test babies' events and hours, for the record
    test_events = [len(S.events_of(c)[0]) for _, c in _babies("test")]
    val_events = [len(S.events_of(c)[0]) for _, c in _babies("val")]
    train_events = [len(S.events_of(load(b)[1])[0]) for b in use["train"]]
    meta = {"stage": a.stage, "babies_used": a.babies, "split": use,
            "events": {"train": train_events, "val": val_events, "test": test_events},
            "quantiser": {"lo": lo.tolist(), "hi": hi.tolist(), "features": D.FEATURES},
            "rules": {"FA_BUDGET": FA_BUDGET, "MIN_EVENTS": MIN_EVENTS, "MERGE_GAP_S": S.MERGE_GAP_S,
                      "MIN_EVENT_S": S.MIN_EVENT_S, "MARGIN_S": S.MARGIN_S, "REFRACTORY_S": S.REFRACTORY_S,
                      "WIN_S": D.WIN_S, "HOP_S": D.HOP_S}}
    (out / "designs.json").write_text(json.dumps({"meta": meta, "baseline": base,
                                                  "designs": sorted(results, key=lambda r: r["id"])}))
    prep.unlink()
    logger.info(f"PIPELINE-DONE {len(results)} designs -> {out / 'designs.json'}")


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    sys.exit(main())
