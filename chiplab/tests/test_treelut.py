"""XGBoost -> TreeLUT quantisation -> chipir/1 -> gates, bit-exact against TreeLUTClassifier.predict().
XGBoost runs in a worker process (chiplab.ingest.xgb_worker): loading it next to torch can crash on macOS."""
import importlib.util
import json

import numpy as np
import pytest

if importlib.util.find_spec("xgboost") is None:
    pytest.skip("xgboost not installed", allow_module_level=True)

from chiplab.emit.verilog import emit  # noqa: E402
from chiplab.hw.yosys import synth_generic  # noqa: E402
from chiplab.ingest.xgb_worker import run_worker  # noqa: E402
from chiplab.ir.interp import run  # noqa: E402
from chiplab.verify.bitexact import check  # noqa: E402


@pytest.mark.parametrize("ncls", [2, 3])
def test_treelut_chip_bit_exact(ncls, tmp_path):
    spec = tmp_path / "spec.json"; spec.write_text(json.dumps({"ncls": ncls, "seed": ncls}))
    try:
        out = run_worker(["train_convert", str(spec)])
    except RuntimeError as e:
        if "libomp" in str(e) or "XGBoostError" in str(e):
            pytest.skip(f"xgboost not loadable here: {e}")
        raise
    ir, Xt, ref = out["ir"], np.asarray(out["X"]), np.asarray(out["ref"])
    assert (run(ir, Xt)["y"][:, 0] == ref).all()
    text, info = emit(ir)
    (tmp_path / "d.v").write_text(text)
    syn = synth_generic(tmp_path / "d.v", info["top"], tmp_path / "syn")
    res = check(ir, syn["netlist_json"], info, Xt, reference=ref)
    assert res["bit_exact"], res["pairs"]


def test_xgboost_not_imported_in_this_process():
    import sys
    assert "xgboost" not in sys.modules
