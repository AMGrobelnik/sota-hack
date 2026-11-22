"""Reproduce the lab's own proofs on one design: B (gates == RTL, ABC cec) and A+B (golden, node by node).

usage: repro_lab.py <design_id> <timeout_s> <workdir>
Prints one JSON object with wall times. Uses chiplab.verify.formal unchanged.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from chiplab import config
from chiplab.verify.formal import prove


def main() -> None:
    did, timeout, wd = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
    d = config.HOME / "designs" / did
    ir = json.loads((d / "ir.json").read_text())
    info = json.loads((d / "port.json").read_text())
    syn = json.loads((d / "synth.json").read_text())
    gate = Path(syn["gate_verilog"]) if "gate_verilog" in syn else next((d / "synth").glob("*gate*.v"))
    out = {"design_id": did}
    t = time.time()
    b = prove(ir, info, gate, d / "design.v", wd / "b_only", timeout, golden=False)
    out["B_only"] = {"proved": b["proved"], "against": b["against"], "wall_s": round(time.time() - t, 2)}
    t = time.time()
    a = prove(ir, info, gate, d / "design.v", wd / "golden", timeout, golden=True)
    out["golden"] = {"proved": a["proved"], "against": a["against"], "wall_s": round(time.time() - t, 2),
                     "nodes": a.get("nodes") or (a.get("golden_attempt") or {}).get("nodes")}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
