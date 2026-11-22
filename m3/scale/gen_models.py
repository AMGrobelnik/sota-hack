"""Generate the scale sweep's models: random integer per-channel EEG-style networks at 1k, 5k, 10k and 30k weights.

One model per (size, style). Input: one EEG channel window, L raw samples of 6-bit signed data (the lab's
eeg_burst example uses the same input format). Hidden layers: h = clip((W h_prev + b) >> shift, 0, amax). One
output: decision = score > 0 (seizure-like burst yes / no).

Styles:
  ternary : every weight in {-1, 0, +1}, P(0) = 0.5, P(-1) = P(+1) = 0.25; activations 3-bit (amax 7).
  q4      : every weight a signed 4-bit integer in [-8, 7], a rounded normal (sigma 3) clipped to that range,
            which is how trained 4-bit weights are spread; activations 4-bit (amax 15).

Weights counted = all matrix entries (zeros included), biases not counted. Shifts are set from the layer's own
pre-activation spread on 4096 random inputs so activations use their range; biases are small (sigma = spread / 4);
the output bias centres the score so both decisions occur. A draw whose decision is nearly constant (under 5 % of
either class) is redrawn with the next seed; the seed used is written into each model. Deterministic.

Usage: python gen_models.py <out dir>   (writes <out dir>/<name>.json and <out dir>/index.json)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

IN_BITS = 6
# size label -> (input samples L, hidden widths); weights = L*H1 + H1*H2 + H_last*1
SIZES = {"1k": (24, [40]), "5k": (32, [96, 20]), "10k": (48, [160, 14]), "30k": (64, [384, 14])}
STYLES = {"ternary": 7, "q4": 15}  # style -> hidden activation amax
N_PROBE = 4096


def weights(rng: np.random.Generator, style: str, shape: tuple[int, ...]) -> np.ndarray:
    if style == "ternary":
        return rng.choice(np.array([-1, 0, 1]), size=shape, p=[0.25, 0.5, 0.25])
    return np.clip(np.rint(rng.normal(0.0, 3.0, size=shape)), -8, 7).astype(np.int64)


def make(size: str, style: str, seed: int) -> tuple[dict, dict]:
    lanes, hidden = SIZES[size]
    amax = STYLES[style]
    rng = np.random.default_rng(seed)
    lo, hi = -(1 << (IN_BITS - 1)), 1 << (IN_BITS - 1)
    h = rng.integers(lo, hi, size=(N_PROBE, lanes))
    layers, fan_in = [], lanes
    for width in hidden:
        W = weights(rng, style, (width, fan_in))
        pre = h @ W.T
        spread = float(pre.std()) or 1.0
        shift = max(0, int(round(np.log2(spread / (amax / 2)))))
        b = np.rint(rng.normal(0.0, spread / 4, size=width)).astype(np.int64)
        h = np.clip((pre + b) >> shift, 0, amax)
        layers.append({"W": W.tolist(), "b": b.tolist(), "shift": shift, "amax": amax})
        fan_in = width
    Wo = weights(rng, style, (1, fan_in))
    score = h @ Wo.T
    bo = [-int(np.median(score))]
    pos = float(((score[:, 0] + bo[0]) > 0).mean())
    model = {"layers": layers, "Wo": Wo.tolist(), "bo": bo, "out_dim": 1,
             "in_spec": {"lanes": lanes, "bits": IN_BITS, "signed": True}}
    n_w = sum(len(L["W"]) * len(L["W"][0]) for L in layers) + len(Wo[0])
    flat = np.concatenate([np.asarray(L["W"]).ravel() for L in layers] + [Wo.ravel()])
    info = {"name": f"{style}_{size}", "size": size, "style": style, "seed": seed, "inputs": lanes,
            "input_bits": IN_BITS, "hidden": hidden, "weights": int(n_w),
            "nonzero_weights": int((flat != 0).sum()), "zero_frac": round(float((flat == 0).mean()), 3),
            "biases": int(sum(hidden) + 1), "positive_rate_probe": round(pos, 3)}
    return model, info


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for style in STYLES:
        for k, size in enumerate(SIZES):
            seed = 1000 * (list(STYLES).index(style) + 1) + 10 * k
            while True:
                model, info = make(size, style, seed)
                if 0.05 <= info["positive_rate_probe"] <= 0.95:
                    break
                seed += 1
            (out / f"{info['name']}.json").write_text(json.dumps({"meta": info, "model": model}, separators=(",", ":")))
            index.append(info)
    (out / "index.json").write_text(json.dumps(index, indent=1))
    print(json.dumps([{k: i[k] for k in ("name", "weights", "nonzero_weights", "seed")} for i in index]))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
