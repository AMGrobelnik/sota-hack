"""Turn a design space into a batch of candidate designs (what the AI scientist proposes, or a sweep it asks for).

A candidate = {"family": name, "cfg": {...family settings}, "encoding": {...chip-boundary settings}}.
space: {key: [values] (varied) | value (fixed)}. Encoding keys go to "encoding", everything else to "cfg".
"""
from __future__ import annotations

import itertools

import numpy as np

from chiplab.plugins.base import ModelFamily

ENCODING_KEYS = ("L", "encoder", "bits", "lo", "hi", "features", "levels")


def _split(d: dict) -> tuple[dict, dict]:
    enc = {k: v for k, v in d.items() if k in ENCODING_KEYS}
    cfg = {k: v for k, v in d.items() if k not in ENCODING_KEYS}
    enc.setdefault("encoder", "uniform")
    return cfg, enc


def _py(v):
    return v.item() if isinstance(v, np.generic) else v


def propose(family: ModelFamily, sampler: str, n: int | None, seed: int, space: dict) -> list[dict]:
    """sampler: random (each varied key drawn uniformly, keys in the order given), grid (product, first n),
    explicit (space = {"candidates": [flat dicts]})."""
    if sampler == "explicit":
        flat = list(space["candidates"])
    else:
        varied = [k for k, v in space.items() if isinstance(v, list) and k not in ("hidden", "features")
                  or (k in ("hidden", "features") and isinstance(v, list) and v and isinstance(v[0], list))]
        fixed = {k: v for k, v in space.items() if k not in varied}
        if sampler == "random":
            if not n:
                raise ValueError("random sampler needs n")
            rng = np.random.default_rng(seed)
            flat = []
            for _ in range(int(n)):
                d = dict(fixed)
                for k in varied:
                    vals = space[k]
                    d[k] = vals[int(rng.integers(len(vals)))] if isinstance(vals[0], list) else _py(rng.choice(vals))
                flat.append(d)
        elif sampler == "grid":
            flat = []
            for combo in itertools.product(*[space[k] for k in varied]):
                d = dict(fixed); d.update(dict(zip(varied, combo)))
                flat.append(d)
                if n and len(flat) >= n:
                    break
        else:
            raise ValueError(f"unknown sampler {sampler!r}; use random | grid | explicit")
    out = []
    for d in flat:
        cfg, enc = _split(d)
        out.append({"family": family.name, "cfg": family.validate_cfg(cfg), "encoding": enc})
    return out
