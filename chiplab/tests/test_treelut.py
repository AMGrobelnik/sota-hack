"""XGBoost -> TreeLUT quantisation -> chipir/1 -> gates, bit-exact against TreeLUTClassifier.predict()."""
import numpy as np
import pytest

xgb = pytest.importorskip("xgboost")

from chiplab.emit.verilog import emit  # noqa: E402
from chiplab.hw.yosys import synth_generic  # noqa: E402
from chiplab.ingest.treelut import from_treelut, treelut_classifier  # noqa: E402
from chiplab.ir.interp import run  # noqa: E402
from chiplab.verify.bitexact import check  # noqa: E402


@pytest.mark.parametrize("ncls", [2, 3])
def test_treelut_chip_bit_exact(ncls, tmp_path):
    r = np.random.default_rng(ncls)
    X = r.integers(0, 16, size=(2000, 6)); y = ((X[:, 0] + 2 * X[:, 1] - X[:, 2]) % (ncls * 7)) // 7
    kw = {"objective": "binary:logistic"} if ncls == 2 else {"objective": "multi:softmax", "num_class": ncls}
    m = xgb.XGBClassifier(n_estimators=8, max_depth=3, learning_rate=0.5, **kw).fit(X, y)
    tl = treelut_classifier(m, w_feature=4, w_tree=3)
    ir = from_treelut(tl)
    Xt = r.integers(0, 16, size=(2000, 6))
    ref = np.asarray(tl.predict(Xt)).astype(int).reshape(-1)
    assert (run(ir, Xt)["y"][:, 0] == ref).all()
    text, info = emit(ir)
    (tmp_path / "d.v").write_text(text)
    syn = synth_generic(tmp_path / "d.v", info["top"], tmp_path / "syn")
    res = check(ir, syn["netlist_json"], info, Xt, reference=ref)
    assert res["bit_exact"], res["pairs"]
