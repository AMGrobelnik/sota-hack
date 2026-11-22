"""Build a chipir/1 document for the whole detector: input = a window of N quantised RR intervals (8 bit each),
on-chip = successive differences, absolute values, comparisons, turning points, popcounts and the classifier.
Only the features a model uses are emitted."""
from __future__ import annotations

from afchip.features import ABS_T, REL_K, int_feature_names



def _feature_nodes(n: int, feats: list[int]) -> tuple[list[dict], list[str]]:
    NAMES = int_feature_names()
    nodes: list[dict] = [
        {"id": "r_hi", "op": "gather", "src": "rr", "idx": list(range(1, n))},
        {"id": "r_lo", "op": "gather", "src": "rr", "idx": list(range(0, n - 1))},
        {"id": "d", "op": "sub", "a": "r_hi", "b": "r_lo"},
    ]
    need_abs = any(NAMES[f].startswith(("abs_", "rel_", "run2")) or NAMES[f] == "sum_abs" for f in feats)
    if need_abs:
        nodes.append({"id": "a", "op": "abs", "src": "d"})
    ones = [[1] * (n - 1)]
    out_ids = []
    for f in feats:
        name = NAMES[f]
        fid = f"f_{name}"
        if name.startswith("abs_gt"):
            t = int(name[len("abs_gt"):])
            assert t in ABS_T
            nodes += [{"id": f"b_{name}", "op": "cmp", "src": "a", "rel": "gt", "t": t},
                      {"id": fid, "op": "matvec", "src": f"b_{name}", "W": ones}]
        elif name.startswith("rel_k"):
            k = int(name[len("rel_k"):])
            assert k in REL_K
            nodes += [{"id": f"s_{name}", "op": "shift", "src": "r_lo", "k": k},
                      {"id": f"b_{name}", "op": "cmp", "src": "a", "rel": "gt", "other": f"s_{name}"},
                      {"id": fid, "op": "matvec", "src": f"b_{name}", "W": ones}]
        elif name == "tp":
            m = n - 1
            # bits: pos_i at lane i, neg_i at lane m+i; turning point at i: (pos_i & neg_i+1) | (neg_i & pos_i+1)
            table = [0] * 16
            for code in range(16):
                p0, n0, p1, n1 = code & 1, (code >> 1) & 1, (code >> 2) & 1, (code >> 3) & 1
                table[code] = int((p0 and n1) or (n0 and p1))
            nodes += [{"id": "pos", "op": "cmp", "src": "d", "rel": "gt", "t": 0},
                      {"id": "neg", "op": "cmp", "src": "d", "rel": "lt", "t": 0},
                      {"id": "pn", "op": "concat", "srcs": ["pos", "neg"]},
                      {"id": "tpb", "op": "lut", "src": "pn",
                       "inputs": [[i, m + i, i + 1, m + i + 1] for i in range(m - 1)], "tables": [table] * (m - 1)},
                      {"id": fid, "op": "matvec", "src": "tpb", "W": [[1] * (m - 1)]}]
        elif name.startswith("lag"):
            lag, k = (int(v) for v in name[len("lag"):].split("_k"))
            nodes += [{"id": f"hi_{name}", "op": "gather", "src": "rr", "idx": list(range(lag, n))},
                      {"id": f"lo_{name}", "op": "gather", "src": "rr", "idx": list(range(0, n - lag))},
                      {"id": f"e_{name}", "op": "sub", "a": f"hi_{name}", "b": f"lo_{name}"},
                      {"id": f"ea_{name}", "op": "abs", "src": f"e_{name}"},
                      {"id": f"s_{name}", "op": "shift", "src": f"lo_{name}", "k": k},
                      {"id": f"b_{name}", "op": "cmp", "src": f"ea_{name}", "rel": "gt", "other": f"s_{name}"},
                      {"id": fid, "op": "matvec", "src": f"b_{name}", "W": [[1] * (n - lag)]}]
        elif name == "run2_k3":
            m = n - 1
            nodes += [{"id": "s_run2", "op": "shift", "src": "r_lo", "k": 3},
                      {"id": "b_run2", "op": "cmp", "src": "a", "rel": "gt", "other": "s_run2"},
                      {"id": "rb_run2", "op": "lut", "src": "b_run2", "inputs": [[i, i + 1] for i in range(m - 1)],
                       "tables": [[0, 0, 0, 1]] * (m - 1)},
                      {"id": fid, "op": "matvec", "src": "rb_run2", "W": [[1] * (m - 1)]}]
        elif name == "sum_abs":
            nodes.append({"id": fid, "op": "matvec", "src": "a", "W": ones})
        elif name == "sum_rr":
            nodes.append({"id": fid, "op": "matvec", "src": "rr", "W": [[1] * n]})
        else:
            raise ValueError(name)
        out_ids.append(fid)
    return nodes, out_ids


def build_ir(model: dict, n: int, name: str) -> dict:
    NAMES = int_feature_names()
    k = model["kind"]
    if k == "thr1":
        feats = [model["f"]]
    elif k == "and2":
        feats = [model["f1"], model["f2"]]
    elif k in ("lin", "mlp"):
        feats = list(model["feats"])
    elif k == "tree":
        feats = sorted(set(model["node_feat"]))
    else:
        raise ValueError(k)
    nodes, fids = _feature_nodes(n, feats)
    col = {f: i for i, f in enumerate(feats)}
    nodes.append({"id": "F", "op": "concat", "srcs": fids})
    if k == "thr1":
        nodes.append({"id": "y", "op": "cmp", "src": "F", "rel": "ge", "t": model["t"]})
    elif k == "and2":
        nodes += [{"id": "c", "op": "cmp", "src": "F", "rel": "ge", "t": [model["t1"], model["t2"]]},
                  {"id": "y", "op": "lut", "src": "c", "inputs": [[0, 1]], "tables": [[0, 0, 0, 1]]}]
    elif k == "lin":
        nodes += [{"id": "s", "op": "matvec", "src": "F", "W": [model["w"]]},
                  {"id": "y", "op": "cmp", "src": "s", "rel": "ge", "t": model["t"]}]
    elif k == "mlp":
        nodes += [{"id": "h", "op": "matvec", "src": "F", "W": model["W1"], "b": model["b1"]},
                  {"id": "hr", "op": "clip", "src": "h", "lo": 0, "hi": 1 << 30},
                  {"id": "s", "op": "matvec", "src": "hr", "W": [model["W2"]]},
                  {"id": "y", "op": "cmp", "src": "s", "rel": "ge", "t": model["t"]}]
    elif k == "tree":
        sel = [col[f] for f in model["node_feat"]]
        nodes += [{"id": "Fs", "op": "gather", "src": "F", "idx": sel},
                  {"id": "c", "op": "cmp", "src": "Fs", "rel": "gt", "t": model["node_thr"]},
                  {"id": "y", "op": "lut", "src": "c", "inputs": [list(range(len(sel)))], "tables": [model["table"]]}]
    return {"ir": "chipir/1", "name": name,
            "inputs": [{"name": "rr", "lanes": n, "bits": 8, "signed": False}],
            "nodes": nodes, "outputs": [{"name": "af", "src": "y"}],
            "meta": {"family": k, "window": n, "rr_unit_ms": 8, "features": [NAMES[f] for f in feats]}}
