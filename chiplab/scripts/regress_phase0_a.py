"""Phase 0 regression, Track A: reproduce the feasibility spike through the generic pipeline on CUDA.

Gates: windows per part 16878/3688/3880; best val window F1 at H*L<=128 >= 0.68 (spike 0.7039);
batched candidates/min vs one at a time; predict() == integer math on all val windows of the best candidate.
usage: .venv/bin/python scripts/regress_phase0_a.py [--epochs 60] [--k 256] [--no-solo]
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np

from chiplab import config
from chiplab.data.splits import counts, make_split, split_hash
from chiplab.data.windows import build_view
from chiplab.plugins.datasets.cinc2017 import LOADER
from chiplab.plugins.families.intnn import FAMILY, numpy_reference
from chiplab.plugins.frontends.rr_intervals import STAGE
from chiplab.train import engine
from chiplab.train.propose import propose

ap = argparse.ArgumentParser()
ap.add_argument("--epochs", type=int, default=60)
ap.add_argument("--k", type=int, default=256)
ap.add_argument("--no-solo", action="store_true")
a = ap.parse_args()

t0 = time.time()
recs = [r for r in LOADER.recordings(config.DATA) if r.label in ("N", "A")]
classes = {"neg": ["N"], "pos": ["A"]}
frames, durs, fail = STAGE.frames_many(recs, {}, cache_key="cinc2017/1.0.0")
print("recordings", len(recs), "frontend failures", len(fail), f"{time.time() - t0:.1f}s", flush=True)
subjects = [r.subject_id for r in recs]
labels = [1 if r.label == "A" else 0 for r in recs]
assign = make_split(subjects, labels, (0.70, 0.15, 0.15), seed=0, algo="stratified-v1")
print("subjects per part", counts(assign), "split_hash", split_hash(assign, "cinc2017/1.0.0|rr_intervals"))
view = build_view(recs, STAGE, {}, {"L": 25, "stride": 4, "max_per_rec": 40}, classes, assign, frames=frames, durations=durs)
wpp = [int((view.part == p).sum()) for p in (0, 1, 2)]
pos = [int(view.y[view.part == p].sum()) for p in (0, 1, 2)]
recw = [len(np.unique(view.rec[view.part == p])) for p in (0, 1, 2)]
print("windows per part", wpp, "(spike 16878/3688/3880)", "positive windows", pos, "(spike 3341/736/864)")
print("recordings with a window per part", recw, "dropped (too short)", len(recs) - len(view.recs) + sum(
    1 for i in range(len(view.recs)) if i not in set(view.rec.tolist())))
view.save(config.home("cache") / "phase0_view.npz")

space = {"L": [8, 16, 24], "bits": [4, 5, 6, 8], "H": [4, 8, 16, 32], "encoder": ["uniform", "delta"],
         "wtype": ["ternary", "binary"], "lo": 0, "hi": 2048}
cands = propose(FAMILY, "random", 256, 1, space)[:a.k]
bdir = config.home("batches") / f"phase0_k{a.k}_e{a.epochs}"
res = engine.run_batch(view, cands, {"epochs": a.epochs}, bdir)
print("batched timing", json.dumps(res["timing"]), flush=True)


def hl(r):
    return r["cfg.hidden"][0] * r["enc.L"]


best_all = engine.best(res["rows"])
best_small = engine.best(res["rows"], where=lambda r: hl(r) <= 128)
print("best val window F1 (unconstrained)", best_all["val_win_f1"], {k: best_all[k] for k in ("k", "enc.L", "enc.bits", "cfg.hidden", "enc.encoder", "cfg.wtype")})
print("best val window F1 (H*L<=128)", best_small["val_win_f1"], "sens", best_small["val_win_sens"], "spec", best_small["val_win_spec"],
      {k: best_small[k] for k in ("k", "enc.L", "enc.bits", "cfg.hidden", "enc.encoder", "cfg.wtype")}, "(spike 0.7039, gate >= 0.68)")
f1s = sorted(r["val_win_f1"] for r in res["rows"])
print("val window F1 over candidates: min", f1s[0], "median", f1s[len(f1s) // 2], "max", f1s[-1])

# bit-exact: torch predict == independent numpy integer math, all val windows, best small candidate
k = best_small["k"]
B = engine.load_batch(bdir)
key = B["keys"][k]
Xv = engine.encoded_inputs(view, B["fitted"][key], 1)
pt = engine.predict_candidate(bdir, k, view, 1)
pn = numpy_reference(FAMILY.int_params(B["state"], k), Xv)
print(f"bit-exact predict vs numpy integer model on val: {int((pt == pn).sum())}/{len(pt)}")
try:
    from chiplab.ir import interp
    ir = engine.lower_candidate(bdir, k)
    pi = np.asarray(interp.run(ir, Xv)["y"]).reshape(-1)
    print(f"bit-exact predict vs ir.interp on val: {int((pt == pi).sum())}/{len(pt)}")
    (bdir / f"best_small_ir_k{k}.json").write_text(json.dumps(ir))
except Exception as e:  # interp is Track B's
    print("ir.interp check skipped:", e)

if not a.no_solo:
    solo = 0.0
    for i in range(16):
        r1 = engine.run_batch(view, [cands[i]], {"epochs": a.epochs}, config.home("batches") / f"phase0_solo_{i}")
        solo += r1["timing"]["train_seconds"]
    rate = 16 * 60 / solo
    print(f"one at a time: 16 candidates {solo:.1f}s = {rate:.1f}/min; batched {res['timing']['cand_per_min']}/min "
          f"= {res['timing']['cand_per_min'] / rate:.1f}x", flush=True)
print("batch dir", bdir, f"total {time.time() - t0:.0f}s")
