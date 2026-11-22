"""Verification-level stamping: a chip's result counts only at the highest CONTIGUOUS level it has evidence for.

  1  bit-exact simulation: circuit == integer model (== training model) on every compared input
  2  formal proof: combinational miter/cec against the model, or eqy for sequential designs
  3  cocotb + Icarus simulation of the streaming RTL (real or scientist-supplied vectors) and a clean Verilator lint
  4  Tiny Tapeout gate-level test of the laid-out netlist
  5  running on real hardware (never set automatically; recorded by a person)
"""
from __future__ import annotations

import json
from pathlib import Path

LEVELS = {1: "bit-exact simulation", 2: "formal equivalence proof", 3: "streaming RTL testbench + lint",
          4: "gate-level test after layout", 5: "measured on real hardware"}


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def stamp(design_dir: Path) -> dict:
    d = Path(design_dir)
    ev: dict[int, list[dict]] = {k: [] for k in LEVELS}
    fails: list[dict] = []
    for f in sorted(d.glob("simulate_*.json")):
        r = _load(f)
        if r is None:
            continue
        (ev[1] if r.get("bit_exact") else fails).append({"level": 1, "file": f.name, "n": r.get("n"),
                                                        "inputs": r.get("inputs"), "bit_exact": r.get("bit_exact")})
    for name in ("formal.json", "eqy.json"):
        r = _load(d / name)
        if r is not None:
            item = {"level": 2, "file": name, "method": r.get("method"), "against": r.get("against"), "proved": r.get("proved")}
            (ev[2] if r.get("proved") else fails).append(item)
    r = _load(d / "rtlsim.json")
    if r is not None:
        lint = r.get("lint_ok", True)
        item = {"level": 3, "file": "rtlsim.json", "passed": r.get("passed"), "vectors": r.get("vectors"), "lint_ok": lint}
        (ev[3] if r.get("passed") and lint is not False else fails).append(item)
    for name in ("tt_package.json", "tt.json"):
        r = _load(d / name)
        if r is not None and r.get("gl_test_passed") is not None:
            item = {"level": 4, "file": name, "gl_test_passed": r.get("gl_test_passed")}
            (ev[4] if r.get("gl_test_passed") else fails).append(item)
    r = _load(d / "hardware.json")
    if r is not None and r.get("measured_on_board"):
        ev[5].append({"level": 5, "file": "hardware.json", **{k: r[k] for k in r if k != "measured_on_board"}})
    level = 0
    for k in sorted(LEVELS):
        if ev[k]:
            level = k
        else:
            break
    return {"verification_level": level, "meaning": LEVELS.get(level, "unverified"),
            "evidence": [e for k in sorted(ev) for e in ev[k]], "failed_checks": fails,
            "missing_next": LEVELS.get(level + 1)}
