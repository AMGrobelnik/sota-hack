"""Bridge to a ChipIn run: when the working directory holds the ChipIn `./progress` helper, every lab tool reports
through it (status lines, metrics with fixed keys, artifacts copied into the workspace), so the dashboard shows the
lab's compile/verify work. The lab executes the helper itself, never writes progress.jsonl, so the helper's own
validation applies. Reporting can never fail a tool.

The dashboard keeps one value per metric key (last one wins) and has no chip id, so the lab never lets two chips'
figures share the panel:
- exploring (every call): only `gates` (the chip just synthesised, keeps the headline live), `candidates` (distinct
  chips in ./chips/) and the run's cumulative `vectors_checked` / `mismatches`. Every other number of a chip goes
  to ./chips/<design_id>/metrics.json and a status line.
- reporting (chip_report, or `report_metrics: true` on any call): the full figure set of that one chip
  (tools_hw.FIGURE_KEYS) in one burst. After that, `gates` from other chips stays in status lines until the next
  report, so the panel always shows one chip.

Controls (tool arguments, also accepted by every tool): progress = "auto" (default) | "off" | "<path to helper>";
progress_stages = true marks the mapped stage started/done around the call (off by default: the agent owns stages);
report_metrics = true sends the full figure set of the call's design. Config file key "progress": "off" disables it.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from chiplab import config

#: metric key -> unit (numbers only). The dashboard contract; see docs/CHIPIN_INTEGRATION.md.
METRIC_KEYS = {"gates": "gates", "depth": "levels", "transistors": "transistors", "luts_ice40": "LUT4", "luts_xc7": "LUT6",
               "area_um2": "um2", "ge": "GE", "tt_tiles": "tiles", "cost_eur": "EUR", "vectors_checked": "vectors",
               "mismatches": "vectors", "verification_level": "level", "timing_slack_ns": "ns", "fmax_mhz": "MHz",
               "energy_pj": "pJ", "leakage_uw": "uW", "power_uw_at_rate": "uW", "candidates": "designs"}

#: The only keys sent while exploring; every other key is one chip's figure and goes out only in a report burst.
RUN_KEYS = ("gates", "candidates", "vectors_checked", "mismatches")
CHECK_TOOLS = ("simulate", "rtl_simulate", "submit_verilog")
STATE_FILE = ".chiplab-progress.json"          # in ./chips/: the run's counters (hidden; not a chip)

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
    """Every figure this call measured, as (METRIC_KEYS key, number). after() decides which are sent."""
    m = res.get("metrics") or {}
    out = []

    def add(k, v):
        v = _num(v)
        if v is not None and math.isfinite(v):
            out.append((k, round(v, 6) if isinstance(v, float) else v))
    if tool == "synthesize":
        add("gates", m.get("gates")); add("depth", m.get("depth")); add("transistors", m.get("transistors_est"))
        if m.get("family") == "ice40": add("luts_ice40", m.get("luts"))
        if m.get("family") == "xc7": add("luts_xc7", m.get("luts"))
    elif tool == "count_luts":
        add("luts_ice40" if m.get("family") == "ice40" else "luts_xc7", m.get("luts"))
    elif tool == "map_to_process":
        add("area_um2", m.get("area_um2")); add("ge", m.get("gate_equivalents")); add("tt_tiles", m.get("tt_tiles_est"))
    elif tool in CHECK_TOOLS:
        n, mism = check_counts(tool, res)
        add("vectors_checked", n); add("mismatches", mism); add("verification_level", res.get("verification_level"))
    elif tool in ("prove_equivalence", "prove_sequential", "verification_level"):
        add("verification_level", res.get("verification_level"))
    elif tool in ("layout", "timing_power"):
        add("area_um2", res.get("area_um2")); add("timing_slack_ns", res.get("timing_ws_ns")); add("fmax_mhz", res.get("fmax_mhz"))
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
    elif tool == "chip_report":
        for k, v in (res.get("figures") or {}).items():
            add(k, v)
    return out


def check_counts(tool: str, res: dict) -> tuple[int | None, int | None]:
    """(vectors compared, vectors that mismatched) of one check. A simulate call runs several comparisons over the same
    vectors (circuit vs model per output, vs the scientist's expected values); the largest mismatch count is used."""
    if tool == "simulate":
        pairs = (res.get("pairs") or {}).values()
        return res.get("n"), max((p.get("mismatches", 0) for p in pairs), default=0)
    if tool == "submit_verilog":
        return res.get("vectors"), res.get("mismatches")
    return res.get("vectors"), res.get("mismatches")


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


@contextmanager
def _run_state(ws: Path):
    """The run's counters, under a lock (an agent may run several lab tools at once)."""
    d = ws / "chips"
    d.mkdir(exist_ok=True)
    f = d / STATE_FILE
    with open(d / (STATE_FILE + ".lock"), "a+") as lk:
        try:
            import fcntl
            fcntl.flock(lk, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        try:
            st = json.loads(f.read_text())
        except (OSError, ValueError):
            st = {}
        st.setdefault("vectors_checked", 0); st.setdefault("mismatches", 0); st.setdefault("checks", [])
        yield st
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(st))
        os.replace(tmp, f)


def _chip_count(ws: Path) -> int:
    d = ws / "chips"
    return sum(1 for p in d.iterdir() if p.is_dir() and not p.name.startswith(".")) if d.exists() else 0


def _check_key(tool: str, args: dict) -> str:
    a = {k: v for k, v in args.items() if k not in ("progress", "progress_stages", "report_metrics", "run_id", "session_id",
                                                    "round", "force")}
    return hashlib.sha256(json.dumps([tool, a], sort_keys=True, default=str).encode()).hexdigest()[:16]


def _save_chip_metrics(ws: Path, design_id: str, tool: str, found: list[tuple[str, float]]) -> Path | None:
    """Merge one call's figures into ./chips/<design_id>/metrics.json; returns the path if the file is new."""
    d = ws / "chips" / design_id
    d.mkdir(parents=True, exist_ok=True)
    f = d / "metrics.json"
    new = not f.exists()
    try:
        cur = json.loads(f.read_text()) if not new else {}
    except ValueError:
        cur = {}
    cur.setdefault("design_id", design_id)
    m = cur.setdefault("metrics", {})
    for k, v in found:
        m[k] = {"value": v, "unit": METRIC_KEYS.get(k, ""), "from": tool, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    f.write_text(json.dumps(cur, indent=1))
    return f if new else None


LABEL = {"gates": "{v:,} gates", "depth": "depth {v} levels", "transistors": "~{v:,} transistors", "luts_ice40": "{v:,} iCE40 LUT4s",
         "luts_xc7": "{v:,} LUT6s", "area_um2": "{v:,.0f} um2", "ge": "{v:,.0f} GE", "tt_tiles": "{v} Tiny Tapeout tile(s)",
         "cost_eur": "EUR {v:,.0f}", "verification_level": "verification level {v}", "timing_slack_ns": "slack {v:+.2f} ns",
         "fmax_mhz": "fmax {v:,.1f} MHz", "energy_pj": "{v:,.1f} pJ per decision", "leakage_uw": "leakage {v:.3f} uW",
         "power_uw_at_rate": "{v:.3f} uW at the decision rate", "vectors_checked": "{v:,} vectors", "mismatches": "{v:,} mismatching"}


def _summary(found: list[tuple[str, float]]) -> str:
    parts = []
    for k, v in found:
        try:
            parts.append(LABEL.get(k, k + " {v}").format(v=v))
        except (ValueError, TypeError):
            parts.append(f"{k} {v}")
    return ", ".join(parts)


CHIP_FLAG_ENV = "CHIPIN_PROGRESS_CHIP"   # "1" once the backend's helper and tailer accept `--chip <design_id>`


def _send_metric(h: Path, k: str, v, chip: str | None = None) -> None:
    """One metric line. A chip figure carries `--chip <design_id>` only when CHIPIN_PROGRESS_CHIP=1 (today's helper
    rejects a fourth argument, so it is off until the backend enables it); run counters never carry a chip."""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
        extra = ["--chip", chip] if chip and k not in ("candidates", "vectors_checked", "mismatches") \
            and os.environ.get(CHIP_FLAG_ENV) == "1" else []
        _call(h, "metric", k, v, METRIC_KEYS.get(k, ""), *extra)


def report_figures(design_id: str, decision_rate_hz=None) -> dict:
    from chiplab.tools_hw import chip_figures
    return chip_figures(design_id, decision_rate_hz)["figures"]


def after(tool: str, args: dict, res: dict, h: Path | None, stages: bool, report: bool = False) -> None:
    if not h:
        return
    try:
        ws = h.parent
        did = res.get("design_id") or args.get("design_id")
        ran = res.get("status") in ("ok", "fail")
        if did and ran:
            for rel, kind in _export(did, tool, res, ws):
                _call(h, "artifact", rel, kind)
        found = metrics_for(tool, res) if ran else []
        send, new_file = [], None
        with _run_state(ws) as st:
            if did and found:
                new_file = _save_chip_metrics(ws, did, tool, found)
            if tool in CHECK_TOOLS and ran:
                n, mism = check_counts(tool, res)
                key = _check_key(tool, args)
                if isinstance(n, int) and key not in st["checks"]:      # the same check repeated counts once
                    st["checks"].append(key)
                    st["vectors_checked"] += n; st["mismatches"] += int(mism or 0)
                    send += [("vectors_checked", st["vectors_checked"]), ("mismatches", st["mismatches"])]
            gates = dict(found).get("gates")
            if tool == "synthesize" and gates is not None and not report and st.get("reported") in (None, did):
                send.append(("gates", gates))
            n_chips = _chip_count(ws)
            if n_chips != st.get("candidates"):
                st["candidates"] = n_chips
                send.append(("candidates", n_chips))
            if report and did and res.get("status") == "ok":
                st["reported"] = did
        if new_file is not None:
            _call(h, "artifact", str(new_file.relative_to(ws)), "file")
        for k, v in send:
            _send_metric(h, k, v, did)
        if found and not report and did:
            verb = "checked" if tool in CHECK_TOOLS else "measured"
            _call(h, "status", f"ChipIn {verb} chip {did}: {_summary(found)}"[:200])
        if report and did and res.get("status") == "ok":
            figs = res.get("figures") if tool == "chip_report" else report_figures(did, args.get("decision_rate_hz"))
            figs = figs or {}
            if figs:
                nf = _save_chip_metrics(ws, did, "chip_report" if tool == "chip_report" else f"{tool}+report_metrics", list(figs.items()))
                if nf is not None:
                    _call(h, "artifact", str(nf.relative_to(ws)), "file")
                _call(h, "status", f"ChipIn is showing chip {did}: {_summary([(k, figs[k]) for k in ('gates', 'area_um2', 'verification_level') if k in figs])}"[:200])
                for k, v in figs.items():
                    _send_metric(h, k, v, did)
        if res.get("status") not in ("ok",) and tool in VERB:
            word = {"fail": "found a problem", "timeout": "ran out of time", "error": "hit an error"}.get(res.get("status"), "stopped")
            _call(h, "status", f"ChipIn {word} while {VERB[tool].format(d=did or '').strip()}")
        if stages and tool in STAGE_OF:
            _call(h, "stage", STAGE_OF[tool], "done", *([int(args["round"])] if isinstance(args.get("round"), int) else []))
    except Exception:  # reporting never breaks a tool
        pass
