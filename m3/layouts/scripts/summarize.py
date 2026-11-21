"""raw/*.json + designs.json -> results.json and RESULTS.md (home path written as ~ everywhere, raw files too).

Usage: python summarize.py <worktree root> <librelane version string> <machine string>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
VERSION, MACHINE = sys.argv[2], sys.argv[3]
OUT = ROOT / "m3" / "layouts"
HOME = str(Path.home())
ORDER = [("spike", "gf180"), ("spike", "ihp"), ("torchlogix", "sky130"), ("torchlogix", "gf180"),
         ("torchlogix", "ihp"), ("fusion", "sky130"), ("fusion", "gf180"), ("fusion", "ihp")]
SHORT = {"sky130A": "sky130", "gf180mcuD": "gf180", "ihp-sg13g2": "ihp"}


def tilde(o):
    return json.loads(json.dumps(o, default=str).replace(HOME, "~"))


def row(name: str, pdk: str) -> dict:
    f = OUT / "raw" / f"{name}_{pdk}.json"
    if not f.exists():
        return {"design": name, "pdk": pdk, "ok": False, "error": "not run"}
    raw = tilde(json.loads(f.read_text()))
    f.write_text(json.dumps(raw, indent=1))
    last = raw["attempts"][-1]
    rec = {"design": name, "pdk": pdk, "design_id": raw["design_id"], "ok": last["ok"],
           "attempts": len(raw.get("earlier_attempts", [])) + len(raw["attempts"]),
           "clock_period_ns": last["clock_period_ns"], "core_util_pct": last["core_util"]}
    if not last["ok"]:
        rec["error_tail"] = str(last.get("error"))[-1500:]
        return rec
    r, m = last["result"], last["metrics_full"]
    cells = m.get("design__instance__count__stdcell")
    taps = m.get("design__instance__count__class:tap_cell", 0)
    pw, lk = r.get("power_uw"), r.get("leakage_uw")
    rec.update({
        "pdk_full": r["pdk"], "area_um2": r["area_um2"], "die_area_um2": r["die_area_um2"],
        "cells_stdcell": cells, "cells_logic": cells - taps if cells is not None else None,
        "cells_fill": m.get("design__instance__count__class:fill_cell"),
        "gate_equivalents": r.get("gate_equivalents_layout"),
        "setup_ws_ns": round(r["timing_ws_ns"], 3) if r.get("timing_ws_ns") is not None else None,
        "critical_path_ns": r.get("critical_path_ns"),
        "setup_violations": m.get("timing__setup_vio__count"), "hold_violations": m.get("timing__hold_vio__count"),
        "power_total_uw": pw, "leakage_uw": lk, "power_basis": r.get("power_basis"),
        "energy_per_decision_pj": r.get("energy_per_decision_pj"),
        "route_drc_errors": m.get("route__drc_errors"),
        "flow_seconds": r.get("seconds"), "wall_seconds": last["wall_seconds"], "started": last["started"],
        "png": f"m3/layouts/{name}_{r['pdk']}.png", "gds_path_uncommitted": r.get("gds"),
    })
    return rec


def main() -> None:
    designs = tilde(json.loads((OUT / "designs.json").read_text()))
    rows = [row(n, p) for n, p in ORDER]
    res = {"tool": VERSION, "machine": MACHINE,
           "how_measured": {
               "layout": "LibreLane Classic flow in Docker (place, CTS off, route, STA, GDS), one run per row; "
                         "numbers read from the run's final/metrics.json by the lab's `layout` tool",
               "area_um2": "standard-cell area incl. tap and repair buffers, excluding filler",
               "gate_equivalents": "layout cell area / NAND2 area of the process (lab's NAND2_UM2)",
               "timing": "worst setup slack at the stated clock (virtual clock, combinational paths), default corner",
               "power": "OpenSTA vectorless (default toggle rates) at the stated clock, nominal corner",
               "energy_per_decision_pj": "(internal + switching power) x clock period: one decision per clock",
               "seconds": "flow_seconds: lab tool's own timer; wall_seconds: driver's timer around the CLI call",
               "synth": "Yosys + ABC generic gates (lab `synthesize`), this machine"},
           "designs": {k: {"design_id": v["design_id"], "synth": v["synth"]} for k, v in designs.items()},
           "runs": rows}
    (OUT / "results.json").write_text(json.dumps(res, indent=1))
    md = ["# P2 layouts: spike, torchlogix and fusion chips", "",
          f"Tool: {VERSION}. Machine: {MACHINE}.",
          "Every number below is from a real LibreLane layout run (basis: layout) unless marked.", "",
          "## Area and cells", "",
          "| Chip | Process | Cell µm² | Die µm² | Cells | GE |", "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        if r["ok"]:
            md.append(f"| {r['design']} | {r['pdk']} | {r['area_um2']:.0f} | {r['die_area_um2']:.0f} | "
                      f"{r['cells_logic']} | {r['gate_equivalents']:.0f} |")
        else:
            md.append(f"| {r['design']} | {r['pdk']} | failed | | | |")
    md += ["", "## Timing, power, run time", "",
           "| Chip | Process | Clk ns | Slack ns | µW | Leak µW | pJ | s |",
           "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        if r["ok"]:
            md.append(f"| {r['design']} | {r['pdk']} | {r['clock_period_ns']:g} | {r['setup_ws_ns']} | "
                      f"{r['power_total_uw']:.1f} | {r['leakage_uw']:.4f} | {r['energy_per_decision_pj']} | "
                      f"{r['flow_seconds']:.0f} |")
        else:
            md.append(f"| {r['design']} | {r['pdk']} | {r['clock_period_ns']:g} | failed | | | | |")
    md += ["", "Columns: Cells = placed standard cells without tap and filler cells; GE = cell area / NAND2 area;",
           "Slack = worst setup slack at the clock; µW and Leak µW = vectorless total and leakage power;",
           "pJ = energy per decision (dynamic power x clock period); s = layout flow time.", "",
           "## Synthesized (Yosys + ABC generic gates, no layout)", "",
           "| Chip | Design id | Gates | Depth | Synth s |", "| --- | --- | --- | --- | --- |"]
    for k, v in designs.items():
        s = v["synth"]
        md.append(f"| {k} | {v['design_id']} | {s['gates']} | {s['depth']} | {s['tool_seconds']} |")
    retried = []
    for n, p in ORDER:
        f = OUT / "raw" / f"{n}_{p}.json"
        raw = json.loads(f.read_text()) if f.exists() else {}
        for a in raw.get("earlier_attempts", []) + raw.get("attempts", [])[:-1]:
            err = [ln.strip() for ln in str(a.get("error")).splitlines() if "ERROR:" in ln][:1]
            retried.append(f"- {n} on {p}: clock {a['clock_period_ns']:g} ns, util {a['core_util']}%: "
                           f"{err[0] if err else 'failed (see raw json)'}")
    if retried:
        md += ["", "## Failed attempts before the result above", "", *retried, "",
               "The gf180 failures were a lab config bug, not the design: LibreLane 3 no longer reads",
               "LIB_SYNTH, so synthesis got no liberty file. The gf180 rows were re-run through",
               "scripts/layout_cli.py, which sets LIB per 3.3 V corner (proposed/gf180-lib.patch)."]
    fails = [r for r in rows if not r["ok"]]
    if fails:
        md += ["", "## Failures", ""]
        for r in fails:
            md += [f"{r['design']} on {r['pdk']} ({r['attempts']} attempts):", "", "```text",
                   *[ln[:100] for ln in r["error_tail"].splitlines()[-25:]], "```", ""]
    (OUT / "RESULTS.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
