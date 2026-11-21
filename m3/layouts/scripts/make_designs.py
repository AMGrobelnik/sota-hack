"""Build the three P2 chips with the lab's own tools and synthesize them (generic gates, Yosys + ABC).

spike     : chiplab/fixtures/spike_best.json via ingest-model (intnn)
torchlogix: torchlogix 16-48-48, 3 classes, trained here on synthetic random bits (same recipe as the lab's
            test_torchlogix.py, seed 0), saved with torch.save and ingested with ingest-model (torchlogix, trusted)
fusion    : 3 heads on separate input ports (spike + two small random intnn heads, as in the lab's
            test_compose.py) with AND / 2-of-3 / OR fusion, via compose-chip

Run with the worktree's venv python from anywhere; argument 1 is the worktree root. Writes designs.json next to
this script's parent folder. No real or patient data is used anywhere.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torchlogix.layers import GroupSum, LogicDense

import chiplab.api as lab
from chiplab.ingest.intnn import to_ir

ROOT = Path(sys.argv[1]).resolve()
OUT = ROOT / "m3" / "layouts"
WORK = OUT / "work"  # uncommitted (pickled model)
WORK.mkdir(parents=True, exist_ok=True)
SPIKE = json.loads((ROOT / "chiplab" / "fixtures" / "spike_best.json").read_text())


def small_head(seed: int, lanes: int, bits: int, signed: bool) -> dict:
    r = np.random.default_rng(seed)
    p = {"layers": [{"W": r.integers(-1, 2, (4, lanes)).tolist(), "b": r.integers(-2, 3, 4).tolist(), "shift": 1,
                     "amax": 7}], "Wo": [r.integers(-2, 3, 4).tolist()], "bo": [int(r.integers(-3, 4))], "out_dim": 1}
    return to_ir(p, {"lanes": lanes, "bits": bits, "signed": signed}, name=f"h{seed}")


def torchlogix_model() -> Path:
    torch.manual_seed(0)
    m = torch.nn.Sequential(LogicDense(16, 48), LogicDense(48, 48), GroupSum(k=3, tau=4.0))
    x = torch.randint(0, 2, (512, 16)).float()
    y = (x[:, :4].sum(1) % 3).long()
    opt = torch.optim.Adam(m.parameters(), 0.05)
    for _ in range(25):
        loss = torch.nn.functional.cross_entropy(m(x), y)
        opt.zero_grad()
        loss.backward()
        opt.step()
    path = WORK / "torchlogix_16_48_48.pt"
    torch.save(m, path)
    return path


def main() -> None:
    designs = {}
    d = lab.ingest_model(format="intnn", model=SPIKE, name="spike")
    designs["spike"] = d["design_id"]
    d = lab.ingest_model(format="torchlogix", path=str(torchlogix_model()), trusted=True, name="torchlogix")
    designs["torchlogix"] = d["design_id"]
    heads = {"s1": to_ir(SPIKE), "s2": small_head(1, 5, 4, False), "s3": small_head(2, 3, 9, True)}
    fusion = [{"name": "both", "op": "and", "inputs": ["s1_y", "s2_y"]},
              {"name": "vote", "op": "kofn", "k": 2, "inputs": ["s1_y", "s2_y", "s3_y"]},
              {"name": "any", "op": "or", "inputs": ["s1_y", "s2_y", "s3_y"]}]
    d = lab.compose_chip(heads=heads, fusion=fusion, shared_inputs=False, name="fusion3")
    designs["fusion"] = d["design_id"]
    out = {}
    for name, did in designs.items():
        t0 = time.time()
        s = lab.synthesize(design_id=did)
        out[name] = {"design_id": did, "synth": {**s.get("metrics", {}), "tool": s.get("tool"),
                     "tool_seconds": s.get("seconds"), "wall_seconds": round(time.time() - t0, 2)}}
        for pdk in ("sky130", "gf180", "ihp"):
            m = lab.map_to_process(design_id=did, pdk=pdk)
            out[name].setdefault("mapped", {})[pdk] = {k: v for k, v in m.items() if k not in ("files", "cached")}
    (OUT / "designs.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: v["design_id"] for k, v in out.items()}))


if __name__ == "__main__":
    main()
