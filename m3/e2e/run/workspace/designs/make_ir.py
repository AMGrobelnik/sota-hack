"""Build chipir/1 documents for the three candidate seizure classifiers and the line-length front-end.

No recordings are available in this run, so the weights are PLACEHOLDERS drawn from a seeded RNG at the
bit widths each design would be trained to. The circuits measure the size of each architecture; they do not
detect seizures. Plain Python only.

Also writes, per design, 256 random test vectors and the expected decision computed by an independent
pure-Python evaluator (eval_ir below), for the lab's `simulate` (inputs=vectors) check.

usage: python3 designs/make_ir.py            (writes designs/*.ir.json and designs/*.vectors.json)
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))


def ternary(rng, p_zero=1 / 3):
    return 0 if rng.random() < p_zero else rng.choice((-1, 1))


def kbit(rng, k=4):
    m = (1 << (k - 1)) - 1          # 4-bit signed, symmetric: -7..7
    return rng.randint(-m, m)


def mlp_ir(name, n_in, in_bits, hidden, wfn, shift, amax, rng, bias_range, out_wfn):
    W1 = [[wfn(rng) for _ in range(n_in)] for _ in range(hidden)]
    b1 = [rng.randint(-bias_range, bias_range) for _ in range(hidden)]
    Wo = [[out_wfn(rng) for _ in range(hidden)]]
    bo = [rng.randint(-8, 8)]
    nodes = [
        {"id": "l0_mv", "op": "matvec", "src": "x", "W": W1, "b": b1},
        {"id": "l0_sh", "op": "shift", "src": "l0_mv", "k": shift},
        {"id": "l0", "op": "clip", "src": "l0_sh", "lo": 0, "hi": amax},
        {"id": "score", "op": "matvec", "src": "l0", "W": Wo, "b": bo},
        {"id": "dec", "op": "cmp", "src": "score", "rel": "gt", "t": [0]},
    ]
    return {"ir": "chipir/1", "name": name,
            "inputs": [{"name": "x", "lanes": n_in, "bits": in_bits, "signed": False}],
            "nodes": nodes, "outputs": [{"name": "y", "src": "dec"}],
            "meta": {"placeholder_weights": True, "params": n_in * hidden + hidden + hidden + 1}}


def design_a(rng):
    """A: feature MLP. 8 features x 6 bit -> 8 hidden (4-bit weights) -> 1."""
    return mlp_ir("A_feat_mlp", 8, 6, 8, kbit, shift=6, amax=15, rng=rng, bias_range=200, out_wfn=kbit)


def design_c(rng):
    """C: wide ternary MLP. 10 band/line-length features x 4 bit -> 16 hidden (ternary) -> 1 (ternary)."""
    return mlp_ir("C_ternary_mlp", 10, 4, 16, ternary, shift=2, amax=15, rng=rng, bias_range=20, out_wfn=ternary)


def design_b(rng):
    """B: envelope CNN. 2 ch x 16 steps of 0.25 s line length (5 bit) -> conv1d 4 filters, k=4, stride 2,
    ternary, shared weights -> ReLU (clip) -> global max over 7 positions -> dense 4->1 (4-bit)."""
    C, T, F, K, S = 2, 16, 4, 4, 2
    P = (T - K) // S + 1                     # 7 positions
    w = [[[ternary(rng) for _ in range(K)] for _ in range(C)] for _ in range(F)]
    b = [rng.randint(-20, 20) for _ in range(F)]
    rows, bias = [], []
    for f in range(F):
        for p in range(P):
            row = [0] * (C * T)
            for c in range(C):
                for k in range(K):
                    row[c * T + p * S + k] = w[f][c][k]
            rows.append(row)
            bias.append(b[f])
    Wo = [[kbit(rng) for _ in range(F)]]
    nodes = [
        {"id": "conv", "op": "matvec", "src": "x", "W": rows, "b": bias},
        {"id": "conv_sh", "op": "shift", "src": "conv", "k": 4},
        {"id": "relu", "op": "clip", "src": "conv_sh", "lo": 0, "hi": 15},
        {"id": "pool", "op": "max", "src": "relu", "groups": [[f * P + p for p in range(P)] for f in range(F)]},
        {"id": "score", "op": "matvec", "src": "pool", "W": Wo, "b": [rng.randint(-8, 8)]},
        {"id": "dec", "op": "cmp", "src": "score", "rel": "gt", "t": [0]},
    ]
    return {"ir": "chipir/1", "name": "B_envelope_cnn",
            "inputs": [{"name": "x", "lanes": C * T, "bits": 5, "signed": False}],
            "nodes": nodes, "outputs": [{"name": "y", "src": "dec"}],
            "meta": {"placeholder_weights": True, "params": F * C * K + F + F + 1}}


def frontend_ll():
    """Line-length front-end datapath, one sample step for both channels:
    acc' = min(acc + |x - x_prev|, 2^21 - 1). Registers (x_prev, acc: 2 x 33 bits) are not in this count."""
    return {"ir": "chipir/1", "name": "F_linelength_step",
            "inputs": [{"name": "x", "lanes": 2, "bits": 12, "signed": True},
                       {"name": "xp", "lanes": 2, "bits": 12, "signed": True},
                       {"name": "acc", "lanes": 2, "bits": 21, "signed": False}],
            "nodes": [{"id": "d", "op": "sub", "a": "x", "b": "xp"},
                      {"id": "ad", "op": "abs", "src": "d"},
                      {"id": "s", "op": "add", "a": "acc", "b": "ad"},
                      {"id": "y", "op": "clip", "src": "s", "lo": 0, "hi": (1 << 21) - 1}],
            "outputs": [{"name": "y", "src": "y"}],
            "meta": {"placeholder_weights": False}}


# ---------- independent evaluator (semantics as documented for chipir/1) ----------

def eval_ir(ir, inputs):
    v = {k: list(x) for k, x in inputs.items()}
    for nd in ir["nodes"]:
        op = nd["op"]
        if op == "matvec":
            x = v[nd["src"]]
            b = nd.get("b") or [0] * len(nd["W"])
            out = [bj + sum(w * xi for w, xi in zip(row, x)) for row, bj in zip(nd["W"], b)]
        elif op in ("add", "sub"):
            a, bb = v[nd["a"]], v[nd["b"]]
            n = max(len(a), len(bb))
            ga = lambda j: a[j] if len(a) > 1 else a[0]
            gb = lambda j: bb[j] if len(bb) > 1 else bb[0]
            out = [ga(j) + gb(j) if op == "add" else ga(j) - gb(j) for j in range(n)]
        elif op == "shift":
            out = [x >> nd["k"] for x in v[nd["src"]]]          # arithmetic shift (floor), as >>>
        elif op == "clip":
            out = [min(max(x, nd["lo"]), nd["hi"]) for x in v[nd["src"]]]
        elif op == "abs":
            out = [abs(x) for x in v[nd["src"]]]
        elif op == "max":
            x = v[nd["src"]]
            out = [max(x[g] for g in grp) for grp in nd["groups"]]
        elif op == "cmp":
            t = nd["t"]
            out = [1 if x > (t[0] if len(t) == 1 else t[j]) else 0 for j, x in enumerate(v[nd["src"]])]
            assert nd["rel"] == "gt"
        else:
            raise ValueError(op)
        v[nd["id"]] = out
    return v[ir["outputs"][0]["src"]]


def random_vectors(ir, rng, n=256):
    vec = {}
    for p in ir["inputs"]:
        lo, hi = (-(1 << (p["bits"] - 1)), (1 << (p["bits"] - 1)) - 1) if p["signed"] else (0, (1 << p["bits"]) - 1)
        vec[p["name"]] = [[rng.randint(lo, hi) for _ in range(p["lanes"])] for _ in range(n)]
    return vec


def main():
    rng = random.Random(20261122)
    designs = {"A": design_a(rng), "B": design_b(rng), "C": design_c(rng), "F": frontend_ll()}
    for key, ir in designs.items():
        vec = random_vectors(ir, random.Random(1000 + ord(key)))
        n = len(next(iter(vec.values())))
        outs = [eval_ir(ir, {k: vec[k][i] for k in vec}) for i in range(n)]
        # one value per vector for a 1-lane output, the full lane list otherwise (the lab compares every lane)
        expected = [o[0] if len(o) == 1 else o for o in outs]
        with open(os.path.join(HERE, f"{key}.ir.json"), "w") as f:
            json.dump(ir, f)
        with open(os.path.join(HERE, f"{key}.vectors.json"), "w") as f:
            json.dump({"vectors": vec, "expected": expected}, f)
        pos = sum(expected) if key != "F" else None
        print(key, ir["name"], "params" , ir["meta"].get("params"), "vectors", n,
              "" if pos is None else f"positives {pos}")


if __name__ == "__main__":
    main()
