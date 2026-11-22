"""The gate estimator ships calibrated: on a fresh lab home it uses the packaged fit, and on designs it was not
fitted on its median error stays modest (finding 14: before, a fresh home gave r2 -4.94 and 2.7x too high)."""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

from chiplab import config
from chiplab.emit.verilog import emit
from chiplab.hw.yosys import synth_generic
from chiplab.ir import estimate as E

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from refit_estimator import fused_ir, multilayer_ir, torchlogix_ir  # noqa: E402


def test_fresh_home_uses_shipped_fit(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOME", tmp_path)              # no local estimator.json here
    c = E._coef()
    assert c["source"] == "shipped fit" and c["n"] >= 150 and c["r2_heldout"] > 0.9
    assert "shipped fit" in E.estimate(multilayer_ir(1))["basis"]


def test_local_refit_takes_precedence(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOME", tmp_path)
    (tmp_path / "estimator.json").write_text('{"coef": [1, 0, 0, 0], "basis": "estimate (local)", "n": 3}')  # legacy 4-feature file
    r = E.estimate(multilayer_ir(2))
    assert r["fit_source"] == "local refit" and r["gates_est"] == max(1, r["adder_bits"])


def test_error_on_unseen_designs(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOME", tmp_path)
    errs = []
    for seed in range(9000, 9010):                          # seeds outside the calibration set (0..69, 500..623)
        ir = multilayer_ir(seed)
        text, info = emit(ir)
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "d.v").write_text(text)
            g = synth_generic(Path(td) / "d.v", info["top"], Path(td) / "s")["gates"]
        if g > 0:
            errs.append(abs(E.estimate(ir)["gates_est"] - g) / g)
    assert len(errs) >= 8 and float(np.median(errs)) < 0.35, errs


def _synth_gates(ir) -> int:
    text, info = emit(ir)
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "d.v").write_text(text)
        return synth_generic(Path(td) / "d.v", info["top"], Path(td) / "s")["gates"]


def test_lut_gates_counts_logic_not_table_rows():
    assert E._lut_gates([0, 0, 0, 0], 2) == 0                  # constant
    assert E._lut_gates([0, 1, 0, 1], 2) == 0                  # pass-through of input a
    assert E._lut_gates([0, 0, 0, 1], 2) == 1                  # AND
    assert E._lut_gates([0, 1, 1, 0], 2) == 1                  # XOR
    assert E._lut_gates([1 if v == 5 else 0 for v in range(8)], 3) == 2   # TreeLUT leaf: a 3-input AND
    assert E._lut_gates([0, 0, 0, 1] * 2, 3) == 1              # input 2 ignored: a 2-input AND


def test_new_features_leave_old_ones_alone():
    f = E.features(multilayer_ir(5))
    assert set(E.FEATURES) <= set(f) and f["wide_adder_bits"] == f["adder_bits"] and f["sum1_bits"] == 0
    tl = E.features(torchlogix_ir(0))                          # popcount over 1-bit gates: a 1-bit sum
    assert tl["sum1_bits"] > 0 and tl["lut_gates"] > 0 and tl["wide_adder_bits"] == 0


def test_shipped_fit_prices_luts_and_bit_sums(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOME", tmp_path)
    c = E._coef()
    for fam in ("torchlogix", "treelut"):
        fc = (c.get("families") or {}).get(fam) or c
        w = dict(zip(fc["features"], fc["coef"]))
        assert w.get("lut_gates", 0) > 0 or w.get("sum1_bits", 0) > 0, (fam, w)
    assert set(c["per_family_heldout"]) >= {"intnn", "composed", "torchlogix", "treelut", "alkaid"}


def test_torchlogix_estimate_not_free(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOME", tmp_path)
    errs = []
    for seed in range(900, 904):                            # outside the calibration seeds (0..39)
        ir = torchlogix_ir(seed)
        g = _synth_gates(ir)
        errs.append(abs(E.estimate(ir)["gates_est"] - g) / g)
    assert float(np.median(errs)) < 0.35, errs


def test_treelut_estimate_not_free(monkeypatch, tmp_path):
    import importlib.util
    import json
    if importlib.util.find_spec("xgboost") is None:
        pytest.skip("xgboost not installed")
    from chiplab.ingest.xgb_worker import run_worker
    monkeypatch.setattr(config, "HOME", tmp_path)
    spec = tmp_path / "spec.json"; spec.write_text(json.dumps({"ncls": 3, "seed": 11}))
    try:
        ir = run_worker(["train_convert", str(spec)])["ir"]
    except RuntimeError as e:
        pytest.skip(f"xgboost not loadable here: {e}")
    g = _synth_gates(ir)
    e = E.estimate(ir)
    assert e["family"] == "treelut" and abs(e["gates_est"] - g) / g < 0.5, (e["gates_est"], g)


def test_estimate_batch_family_notes_and_alkaid(monkeypatch, tmp_path):
    import json
    from chiplab.tools_jobs import estimate_batch
    monkeypatch.setattr(config, "HOME", tmp_path)
    ml = multilayer_ir(3)
    d = tmp_path / "designs" / "x-alk"; d.mkdir(parents=True)
    (d / "ir.json").write_text(json.dumps(ml)); (d / "meta.json").write_text(json.dumps({"optimizer": {"name": "alkaid"}}))
    r = estimate_batch.__wrapped__(designs=[ml, torchlogix_ir(1), fused_ir(1), "x-alk"])
    assert [f["family"] for f in r["features"]] == ["intnn", "torchlogix", "composed", "alkaid"]
    assert set(r["est_error_notes"]) == {"intnn", "torchlogix", "composed", "alkaid"}
    assert all("median error" in n for n in r["est_error_notes"].values()), r["est_error_notes"]
    assert r["gates_est"] == [f["gates_est"] for f in r["features"]] and r["est_basis"]     # old fields kept
    assert E.estimate(ml, optimizer="alkaid")["family"] == "alkaid"


@pytest.mark.parametrize("tt", [True, False])
def test_wrapper_ffs_match_synthesis(tt):
    from chiplab.emit.stream import emit_stream
    for ir in (multilayer_ir(4), torchlogix_ir(2)):
        text, si = emit_stream(ir, tt=tt)
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "s.v").write_text(text)
            cells = synth_generic(Path(td) / "s.v", si["top"], Path(td) / "o")["cells_by_type"]
        assert E.stream_wrapper_ffs(ir, tt=tt) == sum(v for k, v in cells.items() if "DFF" in k.upper())


def test_wrapper_fields_reported_separately(monkeypatch, tmp_path):
    from chiplab.tools import TOOLS
    monkeypatch.setattr(config, "HOME", tmp_path)
    ir = multilayer_ir(4)
    e = E.estimate(ir)
    assert e["wrapper_ffs"] == E.stream_wrapper_ffs(ir) and e["wrapper_area_um2"] > 0
    did = TOOLS["compile_verilog"]["fn"].__wrapped__(ir=ir)["design_id"]
    s = TOOLS["compile_stream"]["fn"].__wrapped__(design_id=did)
    assert s["wrapper_ffs"] == e["wrapper_ffs"] and s["wrapper_area_um2"] == e["wrapper_area_um2"]
    assert {"transfers_per_frame", "counter_bits", "truncated", "uo_map"} <= set(s)


def test_dead_lanes_not_counted():
    ir = {"ir": "chipir/1", "name": "dead", "inputs": [{"name": "x", "lanes": 4, "bits": 6, "signed": False}],
          "nodes": [{"id": "h", "op": "matvec", "src": "x", "W": [[1, 1, 1, 1], [1, -1, 1, -1]], "b": [0, 0]},
                    {"id": "s", "op": "matvec", "src": "h", "W": [[1, 0]], "b": [-5]},        # hidden unit 1 unused
                    {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}], "outputs": [{"name": "y", "src": "y"}], "meta": {}}
    live = E.live_lanes(ir)
    assert live["h"] == {0} and live["x"] == {0, 1, 2, 3}
