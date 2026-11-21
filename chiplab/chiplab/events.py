"""Dashboard events, chip side. JSON lines per run, replayable, also streamed over SSE by the HTTP server.

Envelope on every event: {type, run_id, session_id, seq, t (seconds since the run's first event), round?}.
The lab emits: candidates_scored, chip_compiled, check_bitexact, hw_metrics, gate_activity, layout_ready,
tt_package_ready, bitstream_ready, report_ready, cost. The AI scientist emits its own events with the same
envelope (run_started, check_heldout, ...); the lab never invents clinical numbers.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from chiplab import config

_LOCK = threading.Lock()


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(str(config.home("events") / "seq.db"), timeout=30, isolation_level=None)
    con.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, seq INTEGER, t0 REAL)")
    return con


def path(run_id: str) -> Path:
    safe = "".join(c for c in run_id if c.isalnum() or c in "-_.")
    return config.home("events") / f"{safe}.jsonl"


def emit(type: str, run_id: str | None, session_id: str | None = None, round: int | None = None, **fields) -> dict | None:
    if not run_id:
        return None
    with _LOCK:
        con = _db()
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT seq, t0 FROM runs WHERE run_id=?", (run_id,)).fetchone()
        now = time.time()
        if row is None:
            seq, t0 = 0, now
            con.execute("INSERT INTO runs VALUES (?,?,?)", (run_id, 0, now))
        else:
            seq, t0 = row[0] + 1, row[1]
            con.execute("UPDATE runs SET seq=? WHERE run_id=?", (seq, run_id))
        con.execute("COMMIT")
        con.close()
        ev = {"type": type, "run_id": run_id, "session_id": session_id, "seq": seq, "t": round_(now - t0)}
        if round is not None:
            ev["round"] = round
        ev.update(fields)
        with open(path(run_id), "a") as f:
            f.write(json.dumps(ev, default=str) + "\n")
            f.flush(); os.fsync(f.fileno())
    return ev


def round_(x: float) -> float:
    return float(f"{x:.3f}")


def read(run_id: str, from_seq: int = 0) -> list[dict]:
    p = path(run_id)
    if not p.exists():
        return []
    return [e for e in (json.loads(l) for l in p.read_text().splitlines() if l.strip()) if e["seq"] >= from_seq]


# --- mapping from tool results to dashboard events ------------------------------------------------------------

def for_tool(tool: str, args: dict, res: dict) -> None:
    """Emit the dashboard event(s) that a successful tool result implies. No-op without run_id."""
    run_id, sid, rnd = args.get("run_id"), args.get("session_id"), args.get("round")
    if not run_id or res.get("status") != "ok":
        return
    m = res.get("metrics") or {}
    did = res.get("design_id")
    if tool == "synthesize" and args.get("target", "generic") == "generic":
        emit("chip_compiled", run_id, sid, rnd, designs=[{"id": did, "gates": m.get("gates"), "by_type": res.get("cells_by_type"),
             "depth": m.get("depth"), "transistors_est": m.get("transistors_est")}])
    elif tool in ("synthesize", "count_luts"):
        emit("chip_compiled", run_id, sid, rnd, designs=[{"id": did, "luts": {m.get("family"): m.get("luts")}}])
    elif tool == "simulate":
        tot = sum(p["identical"] + p["mismatches"] for p in res.get("pairs", {}).values()) // max(1, len(res.get("pairs", {})))
        mism = sum(p["mismatches"] for p in res.get("pairs", {}).values())
        emit("check_bitexact", run_id, sid, rnd, design_id=did, method="simulation", vectors_compared=res.get("n", tot),
             mismatches=mism, passed=res.get("bit_exact"), verification_level=res.get("verification_level"))
    elif tool == "prove_equivalence":
        emit("check_bitexact", run_id, sid, rnd, design_id=did, method="formal:" + str(res.get("method")), vectors_compared="all",
             mismatches=0 if res.get("proved") else None, passed=res.get("proved"), against=res.get("against"),
             verification_level=res.get("verification_level"))
    elif tool == "map_to_process":
        emit("hw_metrics", run_id, sid, rnd, design_id=did, pdk=res.get("pdk"), area_um2=m.get("area_um2"),
             ge=m.get("gate_equivalents"), basis="liberty-synth", note=res.get("note"))
    elif tool in ("timing_power", "layout"):
        emit("hw_metrics", run_id, sid, rnd, design_id=did, **{k: res.get(k) for k in (
            "pdk", "area_um2", "core_mm2", "die_mm2", "timing_ws_ns", "power_uw", "power_basis", "energy_per_decision_pj")},
             basis="librelane-layout")
        if res.get("png"):
            emit("layout_ready", run_id, sid, rnd, design_id=did, pdk=res.get("pdk"), png_url=res.get("png_url") or res.get("png"),
                 gds_url=res.get("gds_url") or res.get("gds"), metrics=m)
    elif tool == "bitstream":
        emit("bitstream_ready", run_id, sid, rnd, design_id=did, path=res.get("bin"), luts=m.get("luts"))
    elif tool == "tt_package":
        emit("tt_package_ready", run_id, sid, rnd, design_id=did, path=res.get("folder"), tiles=res.get("tiles"))
    elif tool == "chip_report":
        emit("report_ready", run_id, sid, rnd, design_id=did, **{k: res.get(k) for k in (
            "report_md", "verilog_url", "netlist_json_url", "schematic_svg_url", "layout_png_url", "digest")})
    elif tool == "gate_activity":
        emit("gate_activity", run_id, sid, rnd, design_id=did, wire_toggle=res.get("wire_toggle_top"), regions=res.get("regions"))
    elif tool in ("estimate_batch",):
        emit("candidates_scored", run_id, sid, rnd, ids=res.get("ids"), gates_est=res.get("gates_est"),
             est_basis=res.get("est_basis"), kept_ids=res.get("kept_ids"))
    if res.get("cost"):
        emit("cost", run_id, sid, rnd, design_id=did, tool=tool, **res["cost"])
