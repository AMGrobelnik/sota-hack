"""The gate estimator ships calibrated: on a fresh lab home it uses the packaged fit, and on designs it was not
fitted on its median error stays modest (finding 14: before, a fresh home gave r2 -4.94 and 2.7x too high)."""
import sys
import tempfile
from pathlib import Path

import numpy as np

from chiplab import config
from chiplab.emit.verilog import emit
from chiplab.hw.yosys import synth_generic
from chiplab.ir import estimate as E

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from refit_estimator import multilayer_ir  # noqa: E402


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


def test_dead_lanes_not_counted():
    ir = {"ir": "chipir/1", "name": "dead", "inputs": [{"name": "x", "lanes": 4, "bits": 6, "signed": False}],
          "nodes": [{"id": "h", "op": "matvec", "src": "x", "W": [[1, 1, 1, 1], [1, -1, 1, -1]], "b": [0, 0]},
                    {"id": "s", "op": "matvec", "src": "h", "W": [[1, 0]], "b": [-5]},        # hidden unit 1 unused
                    {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}], "outputs": [{"name": "y", "src": "y"}], "meta": {}}
    live = E.live_lanes(ir)
    assert live["h"] == {0} and live["x"] == {0, 1, 2, 3}
