"""Shared code: features, integer models as chipir/1 documents, an integer interpreter, metrics.

Every reported accuracy number is computed by `run_ir` on the integer model, the same document
the chip lab compiles, so the score of a design is the score of its chip.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

N_SAMP = 186  # the baseline keeps columns 0..185 of the 187-sample window
RR_MAX = 2047  # RR inputs are 11-bit unsigned (samples at 360 Hz, up to 5.7 s)
RATIO_SCALE = 64  # ratio splits r <= t become 64*a <= round(64 t)*b on chip


# ----------------------------------------------------------------------------- data


@dataclass
class Beats:
    x16: np.ndarray
    y5: np.ndarray
    rec: np.ndarray
    rr: np.ndarray  # int: pre, post, avg (samples)
    sym: np.ndarray

    @property
    def bits(self) -> np.ndarray:
        """Morphology bits: the baseline chip's 372-bit code first, then a 7-level thermometer."""
        x = self.x16[:, :N_SAMP].astype(np.int64)
        blocks = [x >= 128, x >= 32768] + [x >= k * 8192 for k in range(1, 8)]
        return np.concatenate(blocks, axis=1).astype(np.int64)

    def subset(self, mask: np.ndarray) -> "Beats":
        return Beats(self.x16[mask], self.y5[mask], self.rec[mask], self.rr[mask], self.sym[mask])


def load_beats(path: Path) -> Beats:
    d = np.load(path)
    rr = np.clip(np.floor(d["rr"]), 1, RR_MAX).astype(np.int64)
    return Beats(d["x16"], d["y5"].astype(np.int64), d["rec"].astype(np.int64), rr, d["sym"])


def ratio_feats(rr: np.ndarray) -> np.ndarray:
    """pre/avg, post/avg, post/pre as floats (for training only; chip uses integer compares)."""
    pre, post, avg = rr[:, 0].astype(float), rr[:, 1].astype(float), rr[:, 2].astype(float)
    return np.stack([pre / avg, post / avg, post / pre], axis=1)


# (numerator lane, denominator lane) in the rr input for each ratio feature
RATIO_LANES = [(0, 2), (1, 2), (1, 0)]


# ----------------------------------------------------------------------------- IR


@dataclass
class IRBuilder:
    """Builds a chipir/1 document with a 1-bit input port per used bit feature and an rr port."""

    name: str
    bit_feats: list[int] = field(default_factory=list)  # indices into the 372-bit vector
    use_rr: bool = False
    nodes: list[dict] = field(default_factory=list)
    _n: int = 0

    def nid(self, p: str) -> str:
        self._n += 1
        return f"{p}{self._n}"

    def bit_lane(self, f: int) -> int:
        if f not in self.bit_feats:
            self.bit_feats.append(f)
        return self.bit_feats.index(f)

    def inputs(self) -> list[dict]:
        ins = []
        if self.bit_feats:
            ins.append({"name": "b", "lanes": len(self.bit_feats), "bits": 1, "signed": False})
        if self.use_rr:
            ins.append({"name": "rr", "lanes": 3, "bits": 11, "signed": False})
        return ins

    def doc(self, outputs: list[dict], meta: dict) -> dict:
        return {
            "ir": "chipir/1",
            "name": self.name,
            "inputs": self.inputs(),
            "nodes": self.nodes,
            "outputs": outputs,
            "meta": {**meta, "bit_features": list(self.bit_feats)},
        }


def run_ir(ir: dict, bits: np.ndarray | None, rr: np.ndarray | None) -> dict[str, np.ndarray]:
    """Integer interpreter for the op subset used here (same semantics as chipir/1)."""
    V: dict[str, np.ndarray] = {}
    for p in ir["inputs"]:
        if p["name"] == "b":
            V["b"] = bits[:, ir["meta"]["bit_features"]].astype(np.int64)
        elif p["name"] == "rr":
            V["rr"] = rr.astype(np.int64)
    n = next(iter(V.values())).shape[0]
    rel = {"gt": np.greater, "ge": np.greater_equal, "lt": np.less, "le": np.less_equal}
    for nd in ir["nodes"]:
        op = nd["op"]
        if op == "matvec":
            y = V[nd["src"]] @ np.asarray(nd["W"], dtype=np.int64).T
            if nd.get("b") is not None:
                y = y + np.asarray(nd["b"], dtype=np.int64)[None, :]
        elif op == "cmp":
            t = nd["t"]
            y = rel[nd["rel"]](V[nd["src"]], np.asarray([t] if isinstance(t, int) else t)[None, :])
            y = y.astype(np.int64)
        elif op == "gather":
            y = V[nd["src"]][:, nd["idx"]]
        elif op == "concat":
            y = np.concatenate([V[s] for s in nd["srcs"]], axis=1)
        elif op == "lut":
            x = V[nd["src"]]
            cols = []
            for sel, tab in zip(nd["inputs"], nd["tables"]):
                idx = np.zeros(n, dtype=np.int64)
                for m, j in enumerate(sel):
                    idx |= (x[:, j] & 1) << m
                cols.append(np.asarray(tab, dtype=np.int64)[idx])
            y = np.stack(cols, axis=1)
        else:
            raise ValueError(op)
        V[nd["id"]] = y
    return {o["name"]: V[o["src"]] for o in ir["outputs"]}


def ratio_cmp_rows(splits: list[tuple[int, float]]) -> tuple[list[list[int]], list[int]]:
    """Rows for 64*num - round(64 t)*den, one per (ratio index, threshold): bit = row <= 0."""
    W = []
    for ridx, t in splits:
        num, den = RATIO_LANES[ridx]
        row = [0, 0, 0]
        row[num] += RATIO_SCALE
        row[den] -= int(round(RATIO_SCALE * t))
        W.append(row)
    return W, [0] * len(W)


# ----------------------------------------------------------------------------- metrics


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (float(c - h), float(c + h))


def threshold_for_spec(scores_neg: np.ndarray, spec: float) -> int:
    """Smallest integer t with mean(scores_neg > t) <= 1 - spec (predict positive if score > t)."""
    s = np.sort(scores_neg)[::-1]
    k = int(np.floor((1 - spec) * len(s)))  # allowed false positives
    if k >= len(s):
        return int(s[-1]) - 1
    t = int(s[k])  # the (k+1)-th largest: everything strictly above it is <= k beats
    return t
