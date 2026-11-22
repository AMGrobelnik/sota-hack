"""The published-hardware registry is well-formed, sourced and usable by compare_hw_baseline."""
import re

import pytest
import yaml

from chiplab import config

REQUIRED_STR = ("id", "ref", "source", "task", "input", "dataset", "protocol", "where", "kind")
KINDS = {"measured_asic", "post_layout_asic", "synthesis_asic", "fpga_measured", "fpga_synthesis", "simulated", "mcu_measured"}


def _registry():
    return yaml.safe_load((config.PKG_DIR / "hw" / "baselines.yaml").read_text())


def test_entries_have_required_fields():
    reg = _registry()
    assert len(reg) >= 15
    for e in reg:
        for k in REQUIRED_STR:
            assert isinstance(e.get(k), str) and e[k].strip(), (e.get("id"), k)
        assert e["kind"] in KINDS, (e["id"], e["kind"])
        assert re.match(r"^https?://", e["source"]), (e["id"], e["source"])
        assert isinstance(e.get("metrics"), dict) and e["metrics"], e["id"]
        assert all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in e["metrics"].values()), e["id"]
        assert isinstance(e.get("units"), dict) and any(k in e["units"] for k in e["metrics"]), e["id"]
        assert isinstance(e.get("comparable_if"), list) and e["comparable_if"], e["id"]
        v = e.get("verified")
        assert isinstance(v, dict) and v.get("by") and v.get("date"), e["id"]


def test_ids_unique_and_key_entries_present():
    ids = [e["id"] for e in _registry()]
    assert len(ids) == len(set(ids))
    reg = {e["id"]: e for e in _registry()}
    assert reg["andersson2015"]["metrics"]["gate_equivalents"] == 24038
    assert reg["einhaus2026_small"]["metrics"]["luts_xc7"] == 536
    assert reg["einhaus2026_big"]["metrics"]["luts_xc7"] == 2844


def test_accuracy_metrics_are_fractions():
    for e in _registry():
        for k, v in e["metrics"].items():
            if any(s in k for s in ("accuracy", "sensitivity", "specificity", "f1", "detected")):
                assert 0 <= v <= 1, (e["id"], k, v)


@pytest.mark.skipif(config.find_bin("yosys") is None, reason="yosys not installed")
def test_compare_hw_baseline_runs():
    import chiplab.api as lab
    ir = {"ir": "chipir/1", "name": "bl", "inputs": [{"name": "x", "lanes": 3, "bits": 3, "signed": False}],
          "nodes": [{"id": "s", "op": "matvec", "src": "x", "W": [[1, -1, 1]], "b": [-2]},
                    {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}],
          "outputs": [{"name": "y", "src": "y"}], "meta": {}}
    d = lab.compile_ir(ir=ir)["design_id"]
    r = lab.compare_hw_baseline(design_id=d, task="af_vs_normal", dataset="AFDB", protocol="segment-level")
    assert r["status"] == "ok", r
    assert len(r["baselines"]) == len(_registry())
    assert all("comparable" in b for b in r["baselines"])
