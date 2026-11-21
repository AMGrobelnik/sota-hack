"""Build the two benchmark designs through the lab's own API and print their ids as JSON.

spike : chiplab/fixtures/spike_best.json (intnn), as in the install check.
fuse3 : three spike-shaped heads (the fixture and two deterministic synthetic variants of it: input lanes
        rotated + output bias shifted; first layer negated + second-layer weights rotated) composed with the lab's compose_chip, one shared input,
        fusion = 2-of-3 vote. Synthetic, generated on this machine; no external data.

Run with the chiplab venv python and CHIPLAB_USER_DIR / CHIPLAB_CONFIG set.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import chiplab.api as lab


def main() -> None:
    fixture = Path(sys.argv[1])
    spike = json.loads(fixture.read_text())
    out = {}
    s = lab.ingest_model(format="intnn", model=spike, name="spike")
    out["spike"] = s["design_id"]
    v1 = copy.deepcopy(spike); v1["b2"] = spike["b2"] + 3
    v1["W1"] = [r[3:] + r[:3] for r in spike["W1"]]  # input lanes rotated: different first layer
    v2 = copy.deepcopy(spike); v2["W2"] = spike["W2"][5:] + spike["W2"][:5]
    v2["W1"] = [[-w for w in r] for r in spike["W1"]]  # first layer negated
    heads = {"h0": out["spike"]}
    for k, m in (("h1", v1), ("h2", v2)):
        heads[k] = lab.ingest_model(format="intnn", model=m, name=k)["design_id"]
    outs = [f"{h}_y" for h in heads]
    c = lab.compose_chip(heads=heads, fusion=[{"name": "vote", "op": "kofn", "k": 2, "inputs": outs}],
                         shared_inputs=True, name="fuse3")
    out["fuse3"] = c["design_id"]
    out["heads"] = heads
    for k in ("spike", "fuse3"):
        r = lab.synthesize(design_id=out[k])
        out[f"{k}_synth"] = {x: r.get(x) for x in ("metrics", "seconds") if x in r}
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
