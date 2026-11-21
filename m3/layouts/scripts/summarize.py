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


def lab(r: dict) -> str:
    return "gf180*" if r["pdk"] == "gf180" else r["pdk"]


CORNERS = ("nom_tt_025C_3v30", "nom_ss_125C_3v00", "nom_ff_n40C_3v60")


def patched_section(res: dict) -> list[str]:
    """gf180 re-runs with proposed/gf180-lib.patch applied to the lab file itself (raw/*_gf180_patched.json)."""
    recs = []
    for name in ("spike", "fusion"):
        f = OUT / "raw" / f"{name}_gf180_patched.json"
        if not f.exists():
            continue
        raw = tilde(json.loads(f.read_text()))
        f.write_text(json.dumps(raw, indent=1))
        r, m = raw["result"], raw["metrics_full"]
        recs.append({"design": name, "pdk": "gf180", "job_id": raw["job_id"], "note": raw["note"],
                     "ok": r.get("status") == "ok", "clock_period_ns": r.get("clock_period_ns"),
                     "area_um2": r.get("area_um2"), "die_area_um2": r.get("die_area_um2"),
                     "setup_ws_ns": r.get("timing_ws_ns"),
                     "setup_ws_by_corner": {c: m.get(f"timing__setup__ws__corner:{c}") for c in CORNERS},
                     "setup_violations": m.get("timing__setup_vio__count"),
                     "hold_violations": m.get("timing__hold_vio__count"),
                     "route_drc_errors": m.get("route__drc_errors"),
                     "power_total_uw": r.get("power_uw"), "leakage_uw": r.get("leakage_uw"),
                     "energy_per_decision_pj": r.get("energy_per_decision_pj"),
                     "flow_seconds": r.get("seconds"), "png": f"m3/layouts/{name}_gf180mcuD.png",
                     "gds_path_uncommitted": r.get("gds"), "error": r.get("error")})
    if not recs:
        return []
    res["gf180_patch_check"] = {"lab_commit": "021f68d", "patch": "m3/layouts/proposed/gf180-lib.patch",
                                "how": "git apply of the patch to chiplab/chiplab/hw/librelane.py in this "
                                       "worktree only (never committed); stock `chiplab workers` + "
                                       "`chiplab submit-batch` of tool layout on the docker lane, both "
                                       "designs at once, clock 40 ns, core_util 25; one run each; not "
                                       "served from cache (the cache key includes the lab code hash)",
                                "runs": recs}
    md = ["", "## gf180 check of proposed/gf180-lib.patch (lab 021f68d)", "",
          "Patch applied with `git apply` to the lab file in this worktree only",
          "(not committed). Both chips submitted together with `chiplab",
          "submit-batch` (tool layout, docker lane, `chiplab workers`), 40 ns",
          "clock, 25% utilisation, one run each, M3 Max, LibreLane 3.0.14.", "",
          "| Chip | Done | Cell µm² | Die µm² | µW | pJ | s |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in recs:
        if r["ok"]:
            md.append(f"| {r['design']} | yes | {r['area_um2']:.0f} | {r['die_area_um2']:.0f} | "
                      f"{r['power_total_uw']:.0f} | {r['energy_per_decision_pj']:.0f} | {r['flow_seconds']:.0f} |")
        else:
            md.append(f"| {r['design']} | no: {str(r['error'])[:40]} | | | | | |")
    md += ["", "Setup slack (ns) per corner at 40 ns:", "",
           "| Chip | tt 25C 3.3V | ss 125C 3.0V | ff -40C 3.6V | Vio |",
           "| --- | --- | --- | --- | --- |"]
    for r in recs:
        if r["ok"]:
            s = r["setup_ws_by_corner"]
            md.append(f"| {r['design']} | {s[CORNERS[0]]:.2f} | {s[CORNERS[1]]:.2f} | {s[CORNERS[2]]:.2f} | "
                      f"{r['setup_violations']} |")
    md += ["", "Result: the patch works. Synthesis now finds the 3.3 V liberty files and",
           "both layouts complete to GDS with 0 routing DRC errors and 0 hold",
           "violations; numbers are identical to the earlier runs through",
           "scripts/layout_cli.py (same settings in memory). Timing at 40 ns is met",
           "at the typical corner (+13.3 and +13.6 ns) but NOT at the slow corner",
           "(ss 125C 3.0V: -14.0 and -13.1 ns); the lab reports that worst corner",
           "as the slack. A 20 ns clock fails at the typical corner, so the flow",
           "stops there (LibreLane error: setup violations in nom_tt_025C_3v30).",
           "Power is OpenSTA vectorless at the nominal corner."]
    return md


def main() -> None:
    designs = tilde(json.loads((OUT / "designs.json").read_text()))
    rows = [row(n, p) for n, p in ORDER]
    res = {"tool": VERSION, "machine": MACHINE,
           "how_measured": {
               "layout": "LibreLane Classic flow in Docker (place, CTS off, route, STA, GDS), one run per row; "
                         "numbers read from the run's final/metrics.json by the lab's `layout` tool",
               "area_um2": "standard-cell area incl. tap and repair buffers, excluding filler",
               "gate_equivalents": "layout cell area / NAND2 area of the process (lab's NAND2_UM2)",
               "timing": "worst setup slack at the stated clock (virtual clock, combinational paths), worst of the "
                         "process's STA corners (gf180: tt, ss 125C 3.0V, ff; see gf180_patch_check per corner)",
               "gf180_rows": "gf180 rows ran with the gf180 liberty fix (proposed/gf180-lib.patch) applied locally, "
                             "not on the stock lab 021f68d, where gf180 synthesis fails",
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
            md.append(f"| {r['design']} | {lab(r)} | {r['area_um2']:.0f} | {r['die_area_um2']:.0f} | "
                      f"{r['cells_logic']} | {r['gate_equivalents']:.0f} |")
        else:
            md.append(f"| {r['design']} | {r['pdk']} | failed | | | |")
    md += ["", "## Timing, power, run time", "",
           "| Chip | Process | Clk ns | Slack ns | µW | Leak µW | pJ | s |",
           "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        if r["ok"]:
            md.append(f"| {r['design']} | {lab(r)} | {r['clock_period_ns']:g} | {r['setup_ws_ns']} | "
                      f"{r['power_total_uw']:.1f} | {r['leakage_uw']:.4f} | {r['energy_per_decision_pj']} | "
                      f"{r['flow_seconds']:.0f} |")
        else:
            md.append(f"| {r['design']} | {r['pdk']} | {r['clock_period_ns']:g} | failed | | | | |")
    md += ["", "Columns: Cells = placed standard cells without tap and filler cells; GE = cell area / NAND2 area;",
           "Slack = worst setup slack at the clock; µW and Leak µW = vectorless total and leakage power;",
           "pJ = energy per decision (dynamic power x clock period); s = layout flow time.",
           "gf180* = run with the gf180 liberty fix applied locally (proposed/gf180-lib.patch);",
           "on the stock lab (021f68d) gf180 synthesis fails. See the gf180 check below.", "",
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
            text = str(a.get("error"))
            err = [ln.strip() for ln in text.splitlines() if "ERROR:" in ln][:1]
            if not err and "Setup violations found" in text:
                err = ["LibreLane: setup violations at the typical corner (nom_tt_025C_3v30)"]
            retried.append(f"- {n} on {p}: clock {a['clock_period_ns']:g} ns, util {a['core_util']}%: "
                           f"{err[0] if err else 'failed (see raw json)'}")
    if retried:
        md += ["", "## Failed attempts before the result above", "", *retried, "",
               "The gf180 failures were a lab config bug, not the design: LibreLane 3 no longer reads",
               "LIB_SYNTH, so synthesis got no liberty file. The gf180 rows were re-run through",
               "scripts/layout_cli.py, which sets LIB per 3.3 V corner (proposed/gf180-lib.patch)."]
    md += patched_section(res)
    (OUT / "results.json").write_text(json.dumps(res, indent=1))
    fails = [r for r in rows if not r["ok"]]
    if fails:
        md += ["", "## Failures", ""]
        for r in fails:
            md += [f"{r['design']} on {r['pdk']} ({r['attempts']} attempts):", "", "```text",
                   *[ln[:100] for ln in r["error_tail"].splitlines()[-25:]], "```", ""]
    (OUT / "RESULTS.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
