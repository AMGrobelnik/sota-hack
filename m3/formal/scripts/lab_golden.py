"""Run the lab's own chiplab.verify.formal.prove(golden=True) on one stored design and print the result with wall time.

usage: lab_golden.py <design_id> <workdir> [timeout_s]
With PYTHONPATH pointing at a patched copy of the chiplab package this measures proposed/formal.patch.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from chiplab import config
from chiplab.verify.formal import prove


def main() -> None:
    did, wd = sys.argv[1], Path(sys.argv[2])
    timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 600
    d = config.HOME / "designs" / did
    ir = json.loads((d / "ir.json").read_text())
    info = json.loads((d / "port.json").read_text())
    gate = Path(json.loads((d / "synth.json").read_text())["gate_verilog"])
    t = time.time()
    r = prove(ir, info, gate, d / "design.v", wd, timeout, golden=True)
    print(json.dumps({"design": did, "proved": r["proved"], "against": r["against"], "method": r.get("method"),
                      "nodes": r.get("nodes"), "wall_s": round(time.time() - t, 2)}))


if __name__ == "__main__":
    main()
