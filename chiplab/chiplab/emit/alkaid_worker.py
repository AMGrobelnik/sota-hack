"""Runs alkaid in its own process: its native CMVM solver and PyTorch each bring an OpenMP runtime, and on macOS a
process that loads both can abort ("Fatal Python error: Aborted"). emit.optimized.emit_optimized calls this, with a
timeout (alkaid's solver can hang on some constants). alkaid only solves the adder graphs; the Verilog for them is
written by chiplab (emit.optimized.graph_rtl), so the output holds no alkaid (LGPL-3.0) code.

    echo '{"ir": {...chipir/1...}, "top": null}' | python -m chiplab.emit.alkaid_worker   -> {"text", "info"} on stdout
"""
from __future__ import annotations

import json
import sys

if __name__ == "__main__":
    req = json.loads(sys.stdin.read())
    from chiplab.emit.optimized import emit_optimized_local
    text, info = emit_optimized_local(req["ir"], "alkaid", req.get("top"))
    sys.stdout.write(json.dumps({"text": text, "info": info}, default=str))
