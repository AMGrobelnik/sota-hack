"""Interval arithmetic over chipir/1: the exact value range of every lane, hence its bit width and signedness.

Widths are derived, never declared, so a generated circuit cannot overflow: every wire is wide enough for every
value its inputs can produce.
"""
from __future__ import annotations

from chiplab.ir.schema import IRError, lanes_of

INT64_SAFE = 2 ** 62


def width(lo: int, hi: int) -> tuple[int, bool]:
    """Minimal two's complement width and signedness covering [lo, hi]."""
    if lo >= 0:
        return max(1, hi.bit_length()), False
    return max((-lo - 1).bit_length(), hi.bit_length()) + 1, True


def _csd(w: int) -> list[tuple[int, int]]:
    """Canonical signed digits of w: [(sign, power)], fewest non-zero digits (used by the emitter and estimator)."""
    out, p, n = [], 0, w
    while n:
        if n & 1:
            d = 2 - (n & 3)          # +1 or -1
            out.append((d, p))
            n -= d
        n >>= 1
        p += 1
    return out


csd = _csd


def ranges(ir: dict) -> dict[str, list[tuple[int, int]]]:
    """{id: [(lo, hi) per lane]} for every input and node."""
    lanes_of(ir)  # validates
    R: dict[str, list[tuple[int, int]]] = {}
    for p in ir["inputs"]:
        b = p["bits"]
        r = (-(1 << (b - 1)), (1 << (b - 1)) - 1) if p["signed"] else (0, (1 << b) - 1)
        R[p["name"]] = [r] * p["lanes"]

    def bc(a, b):  # broadcast two lane lists
        if len(a) == len(b):
            return a, b
        return (a * len(b), b) if len(a) == 1 else (a, b * len(a))

    for nd in ir.get("nodes", []):
        op, i = nd["op"], nd["id"]
        if op == "const":
            out = [(v, v) for v in nd["values"]]
        elif op == "matvec":
            x = R[nd["src"]]; b = nd.get("b") or [0] * len(nd["W"])
            out = []
            for row, bias in zip(nd["W"], b):
                lo = hi = bias
                for w, (l, h) in zip(row, x):
                    if w > 0:
                        lo += w * l; hi += w * h
                    elif w < 0:
                        lo += w * h; hi += w * l
                out.append((lo, hi))
        elif op in ("add", "sub"):
            a, b = bc(R[nd["a"]], R[nd["b"]])
            if op == "add":
                out = [(la + lb, ha + hb) for (la, ha), (lb, hb) in zip(a, b)]
            else:
                out = [(la - hb, ha - lb) for (la, ha), (lb, hb) in zip(a, b)]
        elif op == "shift":
            k = nd["k"]
            out = [(l >> k, h >> k) for l, h in R[nd["src"]]]
        elif op == "clip":
            L, H = nd["lo"], nd["hi"]
            out = [(min(max(l, L), H), min(max(h, L), H)) for l, h in R[nd["src"]]]
        elif op == "abs":
            out = []
            for l, h in R[nd["src"]]:
                if l >= 0:
                    out.append((l, h))
                elif h <= 0:
                    out.append((-h, -l))
                else:
                    out.append((0, max(-l, h)))
        elif op == "max":
            x = R[nd["src"]]
            out = [(max(x[j][0] for j in g), max(x[j][1] for j in g)) for g in nd["groups"]]
        elif op == "cmp":
            out = [(0, 1)] * len(R[nd["src"]])
        elif op == "gather":
            x = R[nd["src"]]
            out = [x[j] for j in nd["idx"]]
        elif op == "concat":
            out = [r for s in nd["srcs"] for r in R[s]]
        elif op == "lut":
            x = R[nd["src"]]
            for sel in nd["inputs"]:
                for j in sel:
                    if not (0 <= x[j][0] and x[j][1] <= 1):
                        raise IRError(f"node {i}: lut input lane {j} has range {x[j]}, must be within [0, 1]")
            out = [(0, 1)] * len(nd["inputs"])
        elif op == "argmax":
            out = [(0, max(0, len(R[nd["src"]]) - 1))]
        else:  # pragma: no cover
            raise IRError(f"unknown op {op}")
        for l, h in out:
            if abs(l) >= INT64_SAFE or abs(h) >= INT64_SAFE:
                raise IRError(f"node {i}: range {(l, h)} exceeds the int64-safe limit")
        R[i] = out
    return R


def widths(ir: dict) -> dict[str, list[tuple[int, bool]]]:
    return {k: [width(l, h) for l, h in v] for k, v in ranges(ir).items()}
