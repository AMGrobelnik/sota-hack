"""Power at the decision rate: formula, and that changing the rate never re-runs LibreLane (no Docker needed)."""
import random

import chiplab.api as lab
import chiplab.hw.librelane as librelane
from chiplab.tools_hw import rate_power

TINY = {"ir": "chipir/1", "name": "ratepw", "inputs": [{"name": "x", "lanes": 3, "bits": 3, "signed": False}],
        "nodes": [{"id": "s", "op": "matvec", "src": "x", "W": [[1, 1, -1]], "b": [-1]},
                  {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}], "outputs": [{"name": "y", "src": "y"}], "meta": {}}


def test_formula():
    # 4.228 pJ per decision at 250 decisions/s = 1.057e-3 uW, plus 4.535 nW leakage
    assert rate_power(4.228, 0.004535, 250) == round(4.228 * 250 * 1e-6 + 0.004535, 6)
    assert rate_power(4.228, 0.004535, None) is None
    assert rate_power(None, 0.004535, 10) is None
    assert rate_power(2.0, None, 1e6) == 2.0     # 2 pJ x 1 MHz = 2 uW, no leakage given


def test_rate_change_reuses_librelane_run(monkeypatch):
    calls = []

    def fake(rtl_files, top, workdir, pdk="sky130A", clock_period_ns=10.0, **kw):
        calls.append(clock_period_ns)
        return {"area_um2": 100.0, "die_area_um2": 400.0, "timing_ws_ns": 5.0, "critical_path_ns": 1.0, "power_w": 1e-4,
                "leakage_w": 2e-9, "energy_per_decision_pj_vectorless": 2.0, "power_basis": "vectorless", "gds": None,
                "png": None, "netlist": None, "metrics": {}, "seconds": 0.01, "basis": "librelane-layout"}
    monkeypatch.setattr(librelane, "timing_power_layout", fake)
    d = lab.compile_ir(ir=TINY)["design_id"]
    clock = round(10 + random.random() * 50, 3)          # a fresh run key for this test run
    a = lab.layout(design_id=d, pdk="sky130", clock_period_ns=clock, decision_rate_hz=1.0)
    b = lab.timing_power(design_id=d, pdk="sky130", clock_period_ns=clock, decision_rate_hz=1000.0)
    c = lab.layout(design_id=d, pdk="sky130", clock_period_ns=clock)
    assert len(calls) == 1, calls                        # one LibreLane run served all three
    assert a["status"] == b["status"] == c["status"] == "ok"
    assert a["power_uw_at_rate"] == round(2.0 * 1.0 * 1e-6 + 0.002, 6)
    assert b["power_uw_at_rate"] == round(2.0 * 1000.0 * 1e-6 + 0.002, 6)
    assert "power_uw_at_rate" not in c and c["power_uw_at_clock"] == 100.0
    assert "decisions per second" in b["power_at_rate_basis"]
