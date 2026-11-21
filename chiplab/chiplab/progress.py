"""Bridge to a ChipIn run: when the working directory holds the ChipIn `./progress` helper, every lab tool reports
through it (status lines, metrics with fixed keys, artifacts copied into the workspace), so the dashboard shows the
lab's compile/verify work. The lab executes the helper itself, never writes progress.jsonl, so the helper's own
validation applies. Reporting can never fail a tool.

Controls (tool arguments, also accepted by every tool): progress = "auto" (default) | "off" | "<path to helper>";
progress_stages = true marks the mapped stage started/done around the call (off by default: the agent owns stages).
Config file key "progress": "off" disables it everywhere.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from chiplab import config

#: metric key -> unit (numbers only). The dashboard contract; see docs/CHIPIN_INTEGRATION.md.
METRIC_KEYS = {"gates": "gates", "depth": "gates", "transistors": "transistors", "luts_ice40": "LUT4", "luts_xc7": "LUT6",
               "area_um2": "um2", "ge": "GE", "tt_tiles": "tiles", "cost_eur": "EUR", "vectors_checked": "vectors",
               "mismatches": "vectors", "verification_level": "level", "timing_slack_ns": "ns", "fmax_mhz": "MHz",
               "energy_pj": "pJ", "leakage_uw": "uW", "power_uw_at_rate": "uW", "candidates": "designs",
               "best_gates": "gates"}

STAGE_OF = {**dict.fromkeys(("ingest_model", "compile_ir", "compile_verilog", "compose_chip", "submit_verilog", "synthesize",
                             "count_luts", "map_to_process", "compile_stream", "ingest_batch", "synthesize_batch"), "compile"),
            **dict.fromkeys(("simulate", "prove_equivalence", "prove_sequential", "rtl_simulate", "verification_level",
                             "simulate_batch"), "verify"),
            **dict.fromkeys(("chip_report", "layout", "timing_power", "tt_package", "tt_readiness", "tt_export", "bitstream",
                             "estimate_cost", "compare_hw_baseline", "gate_activity"), "report"),
            "estimate_batch": "propose"}

VERB = {"ingest_model": "bringing a model in", "compile_ir": "compiling a design", "compose_chip": "composing a multi-head chip",
        "submit_verilog": "checking submitted Verilog", "synthesize": "synthesising chip {d}", "count_luts": "counting LUTs for chip {d}",
        "map_to_process": "mapping chip {d} onto real cells", "simulate": "checking chip {d} bit for bit",
        "prove_equivalence": "proving chip {d} equals its model", "prove_sequential": "proving the clocked chip {d}",
        "rtl_simulate": "simulating the streaming chip {d}", "layout": "laying out chip {d}", "timing_power": "timing chip {d}",
        "bitstream": "building an FPGA bitstream for chip {d}", "tt_package": "packaging chip {d} for Tiny Tapeout",
        "chip_report": "writing the report for chip {d}", "estimate_batch": "ranking candidate chips",
        "synthesize_batch": "synthesising candidate chips", "gate_activity": "measuring gate activity of chip {d}"}


def helper(flag: str | None = "auto") -> Path | None:
    """The ChipIn helper to report through, or None."""
    if (flag or "auto") == "off" or str(getattr(config, "_CFG", {}).get("progress", "")).lower() == "off":
        return None
    if flag not in (None, "auto"):
        p = Path(flag)
        return p if p.is_file() and os.access(p, os.X_OK) else None
    p = Path.cwd() / "progress"
    try:
        if p.is_file() and os.access(p, os.X_OK) and "ChipIn progress helper" in p.read_text(errors="ignore")[:4000]:
            return p
    except OSError:
        pass
    return None


def _call(h: Path, *args) -> None:
    try:
        subprocess.run([str(h), *[str(a) for a in args]], cwd=h.parent, capture_output=True, text=True, timeout=30)
    except Exception:  # reporting never breaks a tool
        pass


def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def metrics_for(tool: str, res: dict) -> list[tuple[str, float]]:
    m = res.get("metrics") or {}
    out = []

    def add(k, v):
        v = _num(v)
        if v is not None:
            out.append((k, round(v, 6) if isinstance(v, float) else v))
    if tool == "synthesize":
        add("gates", m.get("gates")); add("depth", m.get("depth")); add("transistors", m.get("transistors_est"))
        if m.get("family") == "ice40": add("luts_ice40", m.get("luts"))
        if m.get("family") == "xc7": add("luts_xc7", m.get("luts"))
    elif tool == "count_luts":
        add("luts_ice40" if m.get("family") == "ice40" else "luts_xc7", m.get("luts"))
    elif tool == "map_to_process":
        add("area_um2", m.get("area_um2")); add("ge", m.get("gate_equivalents")); add("tt_tiles", m.get("tt_tiles_est"))
    elif tool in ("simulate", "rtl_simulate"):
        add("vectors_checked", res.get("n") if tool == "simulate" else res.get("vectors"))
        mism = sum(p.get("mismatches", 0) for p in (res.get("pairs") or {}).values()) if tool == "simulate" else res.get("mismatches")
        add("mismatches", mism); add("verification_level", res.get("verification_level"))
    elif tool in ("prove_equivalence", "prove_sequential", "verification_level"):
        add("verification_level", res.get("verification_level"))
    elif tool in ("layout", "timing_power"):
        add("area_um2", res.get("area_um2")); add("timing_slack_ns", res.get("timing_ws_ns"))
        add("energy_pj", res.get("energy_per_decision_pj")); add("leakage_uw", res.get("leakage_uw"))
        add("power_uw_at_rate", res.get("power_uw_at_rate"))
    elif tool == "bitstream":
        f = m.get("fmax_mhz")
        add("fmax_mhz", min(f.values()) if isinstance(f, dict) and f else f); add("luts_ice40", m.get("luts"))
    elif tool == "estimate_cost":
        tt = next((r for r in res.get("routes", []) if r.get("route") == "tt_sky130"), None)
        if tt: add("cost_eur", tt.get("cost")); add("tt_tiles", tt.get("tiles"))
    elif tool == "tt_package":
        t = res.get("tiles")
        if isinstance(t, str) and "x" in t:
            a, b = t.lower().split("x"); add("tt_tiles", int(a) * int(b))
    elif tool == "estimate_batch":
        g = [x for x in res.get("gates_est") or [] if x is not None]
        add("candidates", len(res.get("ids") or [])); add("best_gates", min(g) if g else None)
    elif tool in ("synthesize_batch", "simulate_batch", "submit_batch", "ingest_batch"):
        add("candidates", res.get("n"))
    return out


def _export(design_id: str, tool: str, res: dict, ws: Path) -> list[tuple[str, str]]:
    """Copy a design's artefacts into <workspace>/chips/<design_id>/; returns (workspace-relative path, kind)."""
    src = config.HOME / "designs" / design_id
    if not src.exists():
        return []
    dst = ws / "chips" / design_id
    picks: list[tuple[Path, str]] = []
    if tool in ("ingest_model", "compile_ir", "compile_verilog", "compose_chip", "submit_verilog"):
        picks += [(src / "design.v", "file"), (src / "ir.json", "file")]
    elif tool == "synthesize":
        picks += [(src / "synth" / "net.json", "file"), (src / "synth" / "gates.v", "file")]
    elif tool == "compile_stream":
        picks += [(src / "stream_tt.v", "file"), (src / "stream.v", "file")]
    elif tool == "chip_report":
        picks += [(src / "report.md", "report")]
    elif tool in ("layout", "timing_power"):
        picks += [(Path(res[k]), "chip") for k in ("png", "gds") if res.get(k)]
    elif tool == "bitstream" and res.get("bin"):
        picks += [(Path(res["bin"]), "chip")]
    elif tool == "gate_activity":
        picks += [(src / "gate_activity.json", "file"), (src / "ports.vcd", "file")]
    elif tool == "estimate_cost":
        picks += [(src / "cost.json", "file")]
    elif tool == "tt_package" and res.get("folder"):
        picks += [(Path(res["folder"]), "chip")]
    out = []
    for p, kind in picks:
        try:
            if not p.exists():
                continue
            target = dst / p.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if p.is_dir():
                shutil.rmtree(target, ignore_errors=True)
                shutil.copytree(p, target, ignore=shutil.ignore_patterns("tt", "runs", ".git", "sim_build", "__pycache__"))
            else:
                if p.stat().st_size > 200 * 2 ** 20:
                    continue
                shutil.copy2(p, target)
            out.append((str(target.relative_to(ws)), kind))
        except OSError:
            continue
    return out


def before(tool: str, args: dict, h: Path | None, stages: bool) -> None:
    if not h:
        return
    if stages and tool in STAGE_OF:
        _call(h, "stage", STAGE_OF[tool], "started", *([int(args["round"])] if isinstance(args.get("round"), int) else []))
    if tool in VERB:
        _call(h, "status", "ChipIn is " + VERB[tool].format(d=args.get("design_id") or "") .strip())


def after(tool: str, args: dict, res: dict, h: Path | None, stages: bool) -> None:
    if not h:
        return
    try:
        for k, v in metrics_for(tool, res):
            _call(h, "metric", k, v, METRIC_KEYS.get(k, ""))
        did = res.get("design_id") or args.get("design_id")
        if did and res.get("status") in ("ok", "fail"):
            for rel, kind in _export(did, tool, res, h.parent):
                _call(h, "artifact", rel, kind)
        if res.get("status") not in ("ok",) and tool in VERB:
            word = {"fail": "found a problem", "timeout": "ran out of time", "error": "hit an error"}.get(res.get("status"), "stopped")
            _call(h, "status", f"ChipIn {word} while {VERB[tool].format(d=did or '').strip()}")
        if stages and tool in STAGE_OF:
            _call(h, "stage", STAGE_OF[tool], "done", *([int(args["round"])] if isinstance(args.get("round"), int) else []))
    except Exception:  # reporting never breaks a tool
        pass
