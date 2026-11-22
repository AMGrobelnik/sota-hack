"""Runs XGBoost in its own process. XGBoost's OpenMP runtime and PyTorch's can crash one process on macOS when both
are loaded, so the lab never imports xgboost in the caller's process: it runs this worker instead.

    python -m chiplab.ingest.xgb_worker convert <model.json> <w_feature> <w_tree> <name>   -> chipir/1 JSON on stdout
    python -m chiplab.ingest.xgb_worker train_convert <spec.json>                          -> {ir, X, ref} (tests)
"""
from __future__ import annotations

import json
import subprocess
import sys


def convert_file(model_json: str, w_feature: int, w_tree: int, name: str = "treelut") -> dict:
    import xgboost as xgb
    from chiplab.ingest.treelut import from_xgboost
    m = xgb.XGBClassifier()
    m.load_model(model_json)
    return from_xgboost(m, w_feature, w_tree, name=name)


def run_worker(args: list[str], timeout: int = 600) -> dict:
    """Call this module in a fresh Python process and return its JSON answer."""
    p = subprocess.run([sys.executable, "-m", "chiplab.ingest.xgb_worker", *args], capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"xgboost worker failed (rc {p.returncode}): {(p.stderr or p.stdout)[-600:]}")
    return json.loads(p.stdout)


def _train_convert(spec: dict) -> dict:
    import numpy as np
    import xgboost as xgb
    from chiplab.ingest.treelut import from_treelut, treelut_classifier
    r = np.random.default_rng(spec["seed"])
    X = r.integers(0, 16, size=(2000, 6)); ncls = spec["ncls"]
    y = ((X[:, 0] + 2 * X[:, 1] - X[:, 2]) % (ncls * 7)) // 7
    kw = {"objective": "binary:logistic"} if ncls == 2 else {"objective": "multi:softmax", "num_class": ncls}
    m = xgb.XGBClassifier(n_estimators=8, max_depth=3, learning_rate=0.5, **kw).fit(X, y)
    tl = treelut_classifier(m, w_feature=4, w_tree=3)
    Xt = r.integers(0, 16, size=(2000, 6))
    return {"ir": from_treelut(tl), "X": Xt.tolist(), "ref": np.asarray(tl.predict(Xt)).astype(int).reshape(-1).tolist()}


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "convert":
        out = convert_file(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5] if len(sys.argv) > 5 else "treelut")
    elif cmd == "train_convert":
        out = _train_convert(json.loads(open(sys.argv[2]).read()))
    else:
        raise SystemExit(f"unknown command {cmd}")
    sys.stdout.write(json.dumps(out))
