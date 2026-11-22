"""The ChipIn panel never mixes chips: replay of the M3 end-to-end run (20261122-001507-0ef5bb, lab 5b15d6c).

The dashboard keeps one value per metric key (last one wins) and has no chip id. In the M3 run the final panel
showed `gates` from chip C-alk and area, slack and power from the front-end F (BEFORE_M3 below, taken from
m3/e2e/run/events.jsonl). This test replays that run's call sequence through a stand-in `./progress` with the
real helper's command line, then checks:
- while exploring, the only chip figure on the panel is `gates`, plus run counters;
- after `chip-report` on the chosen chip, every chip figure on the panel is that chip's;
- timing-power reports once (it runs layout inside), depth is in levels, timing uses the 50 ns default and gives fmax.
LibreLane is replaced by the critical paths, area and power the M3 run measured for each chip, so no Docker.
"""
import json
import math
import os
import stat
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("alkaid")

import chiplab.api as lab  # noqa: E402
import chiplab.hw.librelane as librelane  # noqa: E402
from chiplab import cache, config  # noqa: E402
from chiplab.config import find_bin  # noqa: E402
from chiplab.ir.interp import run as interp  # noqa: E402
from chiplab.progress import METRIC_KEYS, RUN_KEYS  # noqa: E402

pytestmark = pytest.mark.skipif(not (find_bin("yosys") and find_bin("yosys-abc")), reason="yosys not installed")

FIX = Path(__file__).parent / "fixtures" / "m3_run"
IDS = {"A": "67301286c5e3", "B": "28fba9730991", "C": "94090842ebae", "F": "e05449cf23de"}

# Final panel of the M3 run (lab 5b15d6c): gates/depth/transistors from 94090842ebae-alk, the rest from e05449cf23de.
BEFORE_M3 = {"candidates": 3, "gates": 1279, "depth": 51, "transistors": 9854, "luts_ice40": 156, "area_um2": 5113.65,
             "ge": 643.3, "tt_tiles": 1, "vectors_checked": 256, "mismatches": 0, "verification_level": 2,
             "timing_slack_ns": 6.821885, "energy_pj": 7.898, "leakage_uw": 0.009027, "power_uw_at_rate": 0.011049}

# What LibreLane measured in the M3 run (sky130, 20 ns clock): critical path = 20 - slack.
M3_LAYOUT = {"67301286c5e3-alk": (22016.1, 20 + 1.353682, 456.106, 0.049404e-6),
             "28fba9730991-alk": (23147.2, 20 + 0.669919, 162.9, 0.048904e-6),
             "94090842ebae-alk": (11803.8, 20 + 0.84993, 368.121, 0.02649e-6),
             "e05449cf23de": (5113.65, 20 - 6.821885, 7.898, 0.009027e-6)}

HELPER = '''#!{py}
"""ChipIn progress helper (test stand-in: the real helper's command line and checks)."""
import json, math, os, sys, time
from pathlib import Path
cmd, rest = sys.argv[1], sys.argv[2:]
line = {{"ts": time.time(), "type": cmd, "argv": sys.argv[1:]}}
if cmd == "metric" and "--chip" in rest:
    if os.environ.get("STANDIN_ACCEPTS_CHIP") != "1":
        sys.exit(2)                                     # today's helper: "metric needs a key and a number"
    i = rest.index("--chip"); line["chip"] = rest[i + 1]; rest = rest[:i] + rest[i + 2:]
if cmd == "metric" and len(rest) not in (2, 3):
    sys.exit(2)
if cmd == "metric":
    v = float(rest[1])
    if not math.isfinite(v):
        sys.exit(2)
    line.update(key=rest[0], value=int(v) if v.is_integer() and "." not in rest[1] else v)
    if len(rest) == 3:
        line["unit"] = rest[2]
elif cmd == "status":
    line["text"] = rest[0]
elif cmd == "artifact":
    line.update(path=rest[0], kind=rest[1] if len(rest) > 1 else "file")
elif cmd == "stage":
    line.update(name=rest[0], state=rest[1])
else:
    sys.exit(2)
with Path(__file__).with_name("progress.jsonl").open("a") as f:
    f.write(json.dumps(line) + "\\n")
'''


def fake_librelane(rtl_files, top, workdir, pdk="sky130A", clock_period_ns=50.0, **kw):
    area, cp, e_pj, leak_w = M3_LAYOUT[Path(workdir).parent.name]
    return {"area_um2": area, "die_area_um2": area * 2, "timing_ws_ns": round(clock_period_ns - cp, 6),
            "critical_path_ns": round(cp, 6), "power_w": e_pj * 1e-12 / (clock_period_ns * 1e-9),
            "leakage_w": leak_w, "energy_per_decision_pj_vectorless": e_pj, "power_basis": "vectorless (M3 run values)",
            "gds": None, "png": None, "netlist": None, "metrics": {}, "seconds": 0.0, "basis": "librelane-layout"}


def panel(lines):
    """What the dashboard shows: st.metrics[key] = value, last one wins (amg/frontend dashboard/live.js)."""
    snap = {}
    for ln in lines:
        if ln["type"] == "metric":
            snap[ln["key"]] = ln["value"]
    return snap


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME", tmp_path / "labhome")          # own lab home and cache: stubbed layouts stay here
    monkeypatch.setattr(cache, "_CACHE", None)
    monkeypatch.setattr(librelane, "timing_power_layout", fake_librelane)
    w = tmp_path / "runs" / "r" / "workspace"
    w.mkdir(parents=True)
    h = w / "progress"
    h.write_text(HELPER.format(py=sys.executable))
    h.chmod(h.stat().st_mode | stat.S_IXUSR)
    monkeypatch.chdir(w)
    yield w
    cache._CACHE = None


def _lines(w):
    p = w / "progress.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def _vectors(ir, n=256, seed=1):
    rng = np.random.default_rng(seed)
    X = {}
    for p in ir["inputs"]:
        lo, hi = (-(1 << (p["bits"] - 1)), 1 << (p["bits"] - 1)) if p["signed"] else (0, 1 << p["bits"])
        X[p["name"]] = rng.integers(lo, hi, size=(n, p["lanes"]))
    out = interp(ir, X)[ir["outputs"][0]["name"]]
    return {k: v.tolist() for k, v in X.items()}, np.asarray(out).tolist()


def test_m3_run_replay_panel_shows_one_chip(ws):
    irs = {k: json.loads((FIX / f"{k}.json").read_text()) for k in "ABCF"}
    try:
        from chiplab.hw.pdk import liberty
        liberty("sky130"); have_pdk = True
    except Exception:
        have_pdk = False

    def ok(r, want="ok"):
        assert r["status"] == want, r
        return r
    # compile (the agent's order: A, B, C, the front-end F; then synthesize, count-luts, map-to-process each)
    for k in "ABCF":
        assert ok(lab.compile_ir(ir=irs[k]))["design_id"] == IDS[k]
    for k in "ABCF":
        ok(lab.synthesize(design_id=IDS[k]))
        ok(lab.count_luts(design_id=IDS[k], family="ice40"))
        if have_pdk:
            ok(lab.map_to_process(design_id=IDS[k], pdk="sky130"))
    alk = {}
    for k in "ABC":
        alk[k] = ok(lab.compile_ir(ir=irs[k], optimizer="alkaid"))["design_id"]
        assert alk[k] == IDS[k] + "-alk"
        ok(lab.synthesize(design_id=alk[k]))
    # verify: own vectors + expected, then random, then the proof; F's first vectors had wrong expected values
    for k in ["A", "B", "C", "F"]:
        X, exp = _vectors(irs[k])
        if k == "F":
            bad = (np.asarray(exp) + 1).tolist()
            ok(lab.simulate(design_id=IDS[k], inputs="vectors", vectors=X, expected=bad), "fail")
        else:
            ok(lab.simulate(design_id=IDS[k], inputs="vectors", vectors=X, expected=exp))
        ok(lab.simulate(design_id=IDS[k], inputs="random", n=20000))
        ok(lab.prove_equivalence(design_id=IDS[k]))
    for k in "ABC":
        X, exp = _vectors(irs[k])
        ok(lab.simulate(design_id=alk[k], inputs="vectors", vectors=X, expected=exp))
        ok(lab.simulate(design_id=alk[k], inputs="random", n=20000))
        ok(lab.prove_equivalence(design_id=alk[k]))
    X, exp = _vectors(irs["F"])
    ok(lab.simulate(design_id=IDS["F"], inputs="vectors", vectors=X, expected=exp))
    for d in [alk["A"], alk["B"], alk["C"], IDS["F"]]:
        ok(lab.verification_level(design_id=d))
    # report stage: timing and power of the three optimised chips and the front-end, at 1 decision per second
    tp = {d: ok(lab.timing_power(design_id=d, pdk="sky130", decision_rate_hz=1.0)) for d in [alk["A"], alk["B"], alk["C"], IDS["F"]]}

    lines = _lines(ws)
    before = panel(lines)
    for ln in lines:
        if ln["type"] == "metric":
            assert ln["key"] in METRIC_KEYS and ln.get("unit") == METRIC_KEYS[ln["key"]], ln
            assert isinstance(ln["value"], (int, float)) and math.isfinite(ln["value"]), ln
    assert all("--chip" not in ln["argv"] and len(ln["argv"]) <= 4 for ln in lines if ln["type"] == "metric")
    # exploring: only gates and run counters reach the panel
    assert set(before) <= set(RUN_KEYS), before
    c_alk = json.loads((ws / "chips" / alk["C"] / "metrics.json").read_text())["metrics"]
    assert before["gates"] == c_alk["gates"]["value"]                      # the last chip synthesised
    assert before["candidates"] == 7                                         # A, B, C, F and three -alk chips
    assert before["mismatches"] == 256                                       # F's one wrong-expected check
    assert before["vectors_checked"] == 7 * (256 + 20000) + 256            # F re-checked with corrected expected values
    # timing-power runs layout inside: one report, not two; the 50 ns default closes; fmax is always there
    status = [ln["text"] for ln in lines if ln["type"] == "status"]
    assert not any("laying out" in t for t in status), status
    for d, r in tp.items():
        assert r["clock_period_ns"] == 50.0 and r["timing_ws_ns"] > 0 and r["timing_met"] is True
        assert r["fmax_mhz"] == round(1000 / M3_LAYOUT[d][1], 2)
    assert any(t.startswith(f"ChipIn measured chip {IDS['F']}:") and "fmax" in t for t in status)
    assert all(len(t) <= 200 for t in status)

    # the agent picks C-alk and reports it: the panel becomes that chip's full, consistent figure set
    rep = ok(lab.chip_report(design_id=alk["C"], decision_rate_hz=1.0))
    lines = _lines(ws)
    after = panel(lines)
    figs = rep["figures"]
    chip_keys = {k: v for k, v in after.items() if k not in ("candidates", "vectors_checked", "mismatches")}
    assert chip_keys == figs, (chip_keys, figs)                              # every chip figure is C-alk's
    syn = json.loads((config.HOME / "designs" / alk["C"] / "synth.json").read_text())
    assert (after["gates"], after["depth"], after["transistors"]) == (syn["gates"], syn["depth"], syn["transistors_est"])
    assert figs["gates"] == c_alk["gates"]["value"] and figs["verification_level"] == 2
    assert figs["area_um2"] == M3_LAYOUT[alk["C"]][0] and figs["timing_slack_ns"] > 0
    assert figs["fmax_mhz"] == round(1000 / M3_LAYOUT[alk["C"]][1], 2)
    assert figs["power_uw_at_rate"] == round(368.121 * 1e-6 + 0.02649, 6)
    assert {"gates", "depth", "transistors", "tt_tiles", "cost_eur", "verification_level", "timing_slack_ns", "fmax_mhz",
            "energy_pj", "leakage_uw", "power_uw_at_rate"} <= set(figs)
    units = {ln["key"]: ln.get("unit") for ln in lines if ln["type"] == "metric"}
    assert units["depth"] == "levels"
    # a later synthesis of another chip stays out of the panel (status line only) until the next report
    ok(lab.synthesize(design_id=IDS["A"], force=True))
    assert panel(_lines(ws)) == after
    if os.environ.get("CHIPLAB_TEST_VERBOSE"):
        print("\nBEFORE (M3 run, 5b15d6c):", json.dumps(BEFORE_M3))
        print("AFTER, exploring:", json.dumps(before))
        print("AFTER, chip-report on", alk["C"] + ":", json.dumps(after))


def test_report_metrics_flag_sends_one_chips_figures(ws):
    ir = json.loads((FIX / "C.json").read_text())
    d = lab.compile_ir(ir=ir)["design_id"]
    r = lab.synthesize(design_id=d, report_metrics=True)
    assert r["status"] == "ok"
    snap = panel(_lines(ws))
    assert snap["gates"] == r["metrics"]["gates"] and snap["depth"] == r["metrics"]["depth"]
    assert "verification_level" in snap and "cost_eur" in snap


def test_nested_tool_reports_once(ws):
    d = lab.compile_ir(ir=json.loads((FIX / "F.json").read_text()))["design_id"]
    lab.timing_power(design_id=d, pdk="sky130", decision_rate_hz=1.0)
    lines = _lines(ws)
    assert sum(1 for ln in lines if ln["type"] == "status" and ln["text"].startswith("ChipIn is timing")) == 1
    assert not any(ln["type"] == "status" and "laying out" in ln["text"] for ln in lines)
    assert sum(1 for ln in lines if ln["type"] == "artifact" and ln["path"].endswith("metrics.json")) == 1


def test_chip_flag_only_when_backend_enables_it(ws, monkeypatch):
    ir = json.loads((FIX / "C.json").read_text())
    d = lab.compile_ir(ir=ir)["design_id"]
    lab.synthesize(design_id=d)                                              # off: today's form, no chip
    assert all("--chip" not in ln["argv"] for ln in _lines(ws) if ln["type"] == "metric")
    monkeypatch.setenv("CHIPIN_PROGRESS_CHIP", "1")
    monkeypatch.setenv("STANDIN_ACCEPTS_CHIP", "1")
    (ws / "progress.jsonl").unlink()
    lab.chip_report(design_id=d)
    ms = [ln for ln in _lines(ws) if ln["type"] == "metric"]
    chip = [m for m in ms if m["key"] not in ("candidates", "vectors_checked", "mismatches")]
    assert chip and all(m.get("chip") == d for m in chip)                    # every chip figure names its chip
    assert all("chip" not in m for m in ms if m["key"] in ("candidates", "vectors_checked", "mismatches"))
    assert {"gates", "depth", "transistors"} <= {m["key"] for m in chip}
