"""Hardware and verification tools beyond the core set: formal proof, process mapping, timing/power, packaging,
cost. Registered into tools.TOOLS on import."""
from __future__ import annotations

import json

from chiplab import log
from chiplab.tools import _design_dir, _ensure_synth, tool


@tool("Verification level 2: prove the gate netlist equals the model for every possible input (ABC equivalence "
      "check against an independent golden model of the IR; falls back to proving synthesis if inconclusive).",
      {"design_id": "str", "timeout": "int seconds per proof attempt (600)"})
def prove_equivalence(design_id: str, timeout: int = 600) -> dict:
    from chiplab.verify.formal import prove
    d = _design_dir(design_id)
    syn = _ensure_synth(design_id)
    ir = json.loads((d / "ir.json").read_text()); info = json.loads((d / "port.json").read_text())
    r = prove(ir, info, __import__("pathlib").Path(syn["gate_verilog"]), d / "design.v", d / "formal", timeout)
    (d / "formal.json").write_text(json.dumps(r))
    log.event("check", design_id=design_id, formal=r["proved"], against=r["against"])
    return {"design_id": design_id, **r}


@tool("Map a design onto a real process's standard cells: area in µm², gate-equivalents (area / NAND2), cell "
      "counts and an estimate of Tiny Tapeout tiles.", {"design_id": "str", "pdk": "str — sky130|gf180|ihp"})
def map_to_process(design_id: str, pdk: str = "sky130") -> dict:
    from chiplab.hw.pdk import map_to_process as _map
    d = _design_dir(design_id)
    info = json.loads((d / "port.json").read_text())
    r = _map(d / "design.v", info["top"], d / f"pdk_{pdk}", pdk)
    (d / f"pdk_{pdk}.json").write_text(json.dumps(r))
    log.event("stage", stage="map_to_process", design_id=design_id, pdk=pdk, area_um2=r["area_um2"])
    return {"design_id": design_id, "hw_kind": "synthesized", "metrics": {k: r[k] for k in ("area_um2", "gate_equivalents",
            "std_cells", "tt_tiles_est")}, **{k: r[k] for k in ("pdk", "library", "note", "seconds")},
            "files": [r["mapped_netlist"]]}
