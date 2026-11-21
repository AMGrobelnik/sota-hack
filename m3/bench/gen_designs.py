"""Generate the benchmark's candidate designs from the lab fixture (intnn feasibility-spike model).

Varies hidden width H, input bits and number of inputs L on a fixed grid, three accepted designs per grid point,
plus the fixture itself unchanged. Weights are ternary like the fixture, drawn with the fixture's own zero rate,
and biases are drawn from the fixture's own bias values, so every design is a plausible sibling of the fixture.

Screening: a random sibling can collapse to a constant output (0 gates after synthesis), which is not a
credible candidate design. Each draw is ingested and synthesised once with the lab's own tools in a throwaway
lab home (CHIPLAB_HOME, must be set and is never used by a timed run); draws with 0 gates are dropped and the
next weight seed is tried. The drop count is printed and written to the output. Draws are deterministic.

Output: designs.json, {"designs": [{"name", "H", "bits", "L", "seed", "model"}], "dropped_constant": [...]}.

Usage: CHIPLAB_HOME=<scratch home> python gen_designs.py <fixture spike_best.json> <out designs.json>
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HS = (4, 8, 12, 16, 24, 32)
BITS = (4, 6, 8)
LS = (4, 8, 12)
PER_POINT = 3


def sibling(fx: dict, *, h: int, bits: int, lanes: int, seed: int) -> dict:
    rng = random.Random(f"{h}-{bits}-{lanes}-{seed}")
    flat = [w for row in fx["W1"] for w in row]
    p_zero = flat.count(0) / len(flat)

    def tern() -> int:
        return 0 if rng.random() < p_zero else rng.choice((-1, 1))

    return {"cfg": {**fx["cfg"], "L": lanes, "bits": bits, "H": h},
            "W1": [[tern() for _ in range(lanes)] for _ in range(h)],
            "b1": [rng.choice(fx["b1"]) for _ in range(h)],
            "shift": fx["shift"],
            "W2": [tern() for _ in range(h)],
            "b2": fx["b2"],
            "amax": fx["amax"]}


def gates(tools: dict, model: dict, name: str) -> int:
    r = tools["ingest_model"]["fn"](format="intnn", model=model, name=name)
    if r.get("status") != "ok":
        raise RuntimeError(f"ingest {name}: {r.get('error')}")
    s = tools["synthesize"]["fn"](design_id=r["design_id"], target="generic")
    if s.get("status") != "ok":
        raise RuntimeError(f"synthesize {name}: {s.get('error')}")
    return int(s["metrics"]["gates"])


def main(fixture: Path, out: Path) -> None:
    from chiplab.cli import _tools
    tools = _tools()
    fx = json.loads(fixture.read_text())
    designs = [{"name": "fixture", "H": fx["cfg"]["H"], "bits": fx["cfg"]["bits"], "L": fx["cfg"]["L"],
                "seed": 0, "model": fx}]
    dropped = []
    for h in HS:
        for bits in BITS:
            for lanes in LS:
                seed, kept = 0, 0
                while kept < PER_POINT:
                    seed += 1
                    name = f"h{h}_b{bits}_l{lanes}_s{seed}"
                    m = sibling(fx, h=h, bits=bits, lanes=lanes, seed=seed)
                    if gates(tools, m, name) == 0:
                        dropped.append(name)
                        continue
                    kept += 1
                    designs.append({"name": name, "H": h, "bits": bits, "L": lanes, "fold": kept, "seed": seed,
                                    "model": m})
    designs[0]["fold"] = 0
    out.write_text(json.dumps({"designs": designs, "dropped_constant": dropped}))
    print(json.dumps({"designs": len(designs), "dropped_constant": len(dropped), "out": out.name}))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
