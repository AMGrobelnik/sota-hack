"""official.json -> markdown section appended to RESULTS.md and the "official_gf180" key of results.json.

Usage: python official_md.py <worktree root> <lab commit> <batch wall seconds>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
COMMIT, BATCH_S = sys.argv[2], sys.argv[3]
OUT = ROOT / "m3" / "layouts"
rows = json.loads((OUT / "official.json").read_text())
order = {"spike": 0, "fusion": 1, "torchlogix": 2}
rows.sort(key=lambda r: order.get(r["design"], 9))

L = [f"## gf180 with the official fix (lab {COMMIT})", "",
     f"Lab merged into this branch at {COMMIT} (contains the lab's own gf180 liberty fix and the 40 ns default clock);",
     "no local patch applied (`git status` clean of lab files). Three chips submitted as one",
     "`chiplab submit-batch` of tool `layout` (pdk gf180, no clock given so the lab default applies,",
     "core utilisation 25%), docker lane with 2 workers, one run each, M3 Max,",
     f"LibreLane 3.0.14. Batch wall time {BATCH_S} s for all three (two at a time).", "",
     "| Chip | Done | Clk ns | Cell µm² | Die µm² | GE |", "| --- | --- | --- | --- | --- | --- |"]
for r in rows:
    if r["completed"]:
        L.append(f"| {r['design']} | yes | {r['clock_period_ns']:g} | {r['area_um2']:.0f} | {r['die_area_um2']:.0f} "
                 f"| {r['gate_equivalents']:.0f} |")
    else:
        L.append(f"| {r['design']} | NO ({r['state']}) | - | - | - | - |")
L += ["", "| Chip | tt ns | ss ns | ff ns | Setup vio | Hold vio | DRC |", "| --- | --- | --- | --- | --- | --- | --- |"]
for r in rows:
    if r["completed"]:
        c = r["setup_ws_ns_by_corner"]
        L.append(f"| {r['design']} | {c.get('tt')} | {c.get('ss')} | {c.get('ff')} | {r['setup_vio_count']} "
                 f"| {r['hold_vio_count']} | {r['route_drc_errors']} |")
L += ["", "| Chip | Power µW | Leak µW | pJ/decision | Run s |", "| --- | --- | --- | --- | --- |"]
for r in rows:
    if r["completed"]:
        L.append(f"| {r['design']} | {r['power_uw']:.0f} | {r['leakage_uw']:.3f} | {r['energy_per_decision_pj']:.0f} "
                 f"| {r['run_s']:.0f} |")
L += ["", "Slack = worst setup slack per STA corner (tt 25C 3.3V, ss 125C 3.0V, ff -40C 3.6V); the lab reports the",
      "worst of the three as the chip's slack. Power is OpenSTA vectorless at the nominal corner;",
      "pJ per decision = dynamic power x clock period. Run s = job run time in the lab queue (two jobs shared",
      "the docker engine with each other and with other agents' runs, so it is longer than a lone run)."]
sec = "\n".join(L) + "\n"
print(sec)
(OUT / "official_section.md").write_text(sec)
