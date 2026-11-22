"""Collect the three official-fix gf180 jobs into raw/<name>_gf180_official.json and print a summary.

Usage: python official_summary.py <worktree root> <lab commit> job_id [job_id ...]
Writes m3/layouts/official.json (home path as ~) and prints markdown rows.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
COMMIT = sys.argv[2]
JOBS = sys.argv[3:]
OUT = ROOT / "m3" / "layouts"
CLI = str(ROOT / "chiplab" / ".venv" / "bin" / "chiplab")
HOME = str(Path.home())
NAMES = {v["design_id"]: k for k, v in json.loads((OUT / "designs.json").read_text()).items()}
CORNERS = {"tt": "nom_tt_025C_3v30", "ss": "nom_ss_125C_3v00", "ff": "nom_ff_n40C_3v60"}


def cli(tool: str, args: dict) -> dict:
    p = subprocess.run([CLI, tool, "--json", json.dumps(args)], capture_output=True, text=True, timeout=60,
                       cwd=str(ROOT / "chiplab"))
    return json.loads(p.stdout)


rows = []
for job in JOBS:
    st = cli("job-status", {"job_id": job})
    res = cli("job-result", {"job_id": job}).get("result", {})
    did = res.get("design_id")
    name = NAMES.get(did, did)
    gds = res.get("gds")
    mj = Path(gds).parent.parent / "metrics.json" if gds else None
    m = json.loads(mj.read_text()) if mj and mj.exists() else {}
    rec = {"design": name, "design_id": did, "job_id": job, "lab_commit": COMMIT, "state": st.get("state"),
           "completed": bool(gds), "run_s": st.get("run_s"), "queued_s": st.get("queued_s")}
    if gds:
        rec.update({
            "clock_period_ns": res.get("clock_period_ns"), "area_um2": res["area_um2"],
            "die_area_um2": res["die_area_um2"], "gate_equivalents": res.get("gate_equivalents_layout"),
            "setup_ws_worst_ns": round(res["timing_ws_ns"], 3),
            "setup_ws_ns_by_corner": {k: round(m[f"timing__setup__ws__corner:{c}"], 3) for k, c in CORNERS.items()
                                      if f"timing__setup__ws__corner:{c}" in m},
            "setup_vio_count": m.get("timing__setup_vio__count"), "hold_vio_count": m.get("timing__hold_vio__count"),
            "route_drc_errors": m.get("route__drc_errors"),
            "power_uw": res["power_uw"], "leakage_uw": res["leakage_uw"], "power_basis": res.get("power_basis"),
            "energy_per_decision_pj": res["energy_per_decision_pj"], "flow_seconds": res.get("seconds"),
            "png": f"m3/layouts/{name}_gf180mcuD_official.png", "gds_path_uncommitted": gds,
        })
        if res.get("png"):
            Path(OUT / f"{name}_gf180mcuD_official.png").write_bytes(Path(res["png"]).read_bytes())
    else:
        rec["result"] = res
    rows.append(rec)
txt = json.dumps(rows, indent=1, default=str).replace(HOME, "~")
(OUT / "official.json").write_text(txt)
print(txt)
