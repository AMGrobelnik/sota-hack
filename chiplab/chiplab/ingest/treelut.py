"""Gradient-boosted tree ensembles (XGBoost, quantised by TreeLUT) -> chipir/1.

TreeLUT (vendored, MIT) quantises an XGBoost model: integer input features in [0, 2^w_feature), integer
split thresholds, integer leaf values (w_tree bits) and per-class integer biases. We read that quantised
model and build:
  1. one `cmp` lane per unique (feature, threshold) split: bit = x[feature] < threshold  ("yes" branch);
  2. one `lut` lane per leaf: 1 when every split on the path to it agrees (path bits as LUT inputs);
  3. a `matvec` summing leaf values per class plus the class bias;
  4. binary: decision = sum >= threshold; multiclass: argmax.
This is exactly TreeLUTClassifier.predict(), checked bit for bit in tests/test_treelut.py.
"""
from __future__ import annotations

import json

from chiplab.ir.schema import validate


class _BoosterCompat:
    """XGBoost >= 2 writes base_score as '[5.0E-1]'; the vendored TreeLUT expects a plain float string."""

    def __init__(self, booster):
        self._b = booster

    def __getattr__(self, k):
        return getattr(self._b, k)

    def save_config(self):
        cfg = json.loads(self._b.save_config())
        lmp = cfg.get("learner", {}).get("learner_model_param", {})
        bs = lmp.get("base_score")
        if isinstance(bs, str) and bs.strip().startswith("["):
            lmp["base_score"] = bs.strip()[1:-1].split(",")[0].strip()
        return json.dumps(cfg)


class _XGBCompat:
    def __init__(self, model):
        self._m = model

    def __getattr__(self, k):
        return getattr(self._m, k)

    def get_booster(self):
        return _BoosterCompat(self._m.get_booster())


def treelut_classifier(xgb_model, w_feature: int, w_tree: int):
    """A converted TreeLUTClassifier for a trained XGBClassifier (works with XGBoost 3.x)."""
    from chiplab.ingest.vendor.treelut import TreeLUTClassifier
    tl = TreeLUTClassifier(_XGBCompat(xgb_model), w_feature=w_feature, w_tree=w_tree, pipeline=[0, 0, 0])
    tl.convert()
    return tl


def from_treelut(tl, name: str = "treelut") -> dict:
    """tl: a TreeLUTClassifier after .convert()."""
    if getattr(tl, "_status", None) != "quantized":
        tl.convert()
    trees = tl._treelut_model
    n_cls, n_feat, wf = tl._n_classes, tl._n_features, tl._w_feature
    # 1. unique splits
    splits = sorted({(d["feature"], d["threshold"]) for t in trees for d in t.values() if d["type"] == "split"})
    sidx = {s: i for i, s in enumerate(splits)}
    nodes = []
    if splits:
        nodes.append({"id": "feat", "op": "gather", "src": "x", "idx": [f for f, _ in splits]})
        nodes.append({"id": "split", "op": "cmp", "src": "feat", "rel": "lt", "t": [int(t) for _, t in splits]})
    # 2. leaves: path conditions
    sel, tabs, leaf_cls, leaf_val = [], [], [], []
    const_bias = [0] * n_cls
    for ti, t in enumerate(trees):
        c = ti % n_cls
        for nid, d in t.items():
            if d["type"] != "leaf":
                continue
            path, cur = [], nid
            while "parent_node" in t[cur]:
                p = t[cur]["parent_node"]; pd = t[p]
                path.append((sidx[(pd["feature"], pd["threshold"])], t[cur]["parent_yesno"] == "yes"))
                cur = p
            if not path:                       # single-leaf tree: constant contribution
                const_bias[c] += int(d["value"]); continue
            # merge repeated splits on one path (same lane twice): keep consistent constraints only
            req: dict[int, bool] = {}
            ok = True
            for lane, want in path:
                if lane in req and req[lane] != want:
                    ok = False
                req[lane] = want
            if not ok:
                continue                       # unreachable leaf
            lanes = sorted(req)
            target = sum((1 if req[l] else 0) << m for m, l in enumerate(lanes))
            sel.append(lanes); tabs.append([1 if v == target else 0 for v in range(2 ** len(lanes))])
            leaf_cls.append(c); leaf_val.append(int(d["value"]))
    bias = [int(tl._classes_bias[c]) + const_bias[c] for c in range(n_cls)]
    if sel:
        nodes.append({"id": "leaf", "op": "lut", "src": "split", "inputs": sel, "tables": tabs})
        W = [[leaf_val[j] if leaf_cls[j] == c else 0 for j in range(len(sel))] for c in range(n_cls)]
        nodes.append({"id": "sum", "op": "matvec", "src": "leaf", "W": W, "b": bias})
    else:
        nodes.append({"id": "sum", "op": "const", "values": bias})
    if n_cls == 1:
        nodes.append({"id": "dec", "op": "cmp", "src": "sum", "rel": "ge", "t": [int(tl._threshold)]})
    else:
        nodes.append({"id": "dec", "op": "argmax", "src": "sum"})
    ir = {"ir": "chipir/1", "name": name, "inputs": [{"name": "x", "lanes": int(n_feat), "bits": int(wf), "signed": False}],
          "nodes": nodes, "outputs": [{"name": "y", "src": "dec"}, {"name": "scores", "src": "sum"}],
          "meta": {"format": "treelut", "w_feature": wf, "w_tree": tl._w_tree, "trees": len(trees), "classes": max(n_cls, 2),
                   "unique_splits": len(splits), "leaves": len(sel)}}
    return validate(ir)


def from_xgboost(xgb_model, w_feature: int, w_tree: int, name: str = "treelut") -> dict:
    """Quantise a trained XGBClassifier (on integer features in [0, 2^w_feature)) with TreeLUT, then convert."""
    return from_treelut(treelut_classifier(xgb_model, w_feature, w_tree), name)
