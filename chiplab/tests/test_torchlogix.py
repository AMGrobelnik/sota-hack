"""torchlogix logic-gate network -> chipir/1 -> Verilog -> gates, bit-exact against torchlogix itself."""
import numpy as np
import pytest
import torch

pytest.importorskip("torchlogix")
from torchlogix.layers import GroupSum, LogicDense  # noqa: E402

from chiplab.emit.verilog import emit  # noqa: E402
from chiplab.hw.yosys import synth_generic  # noqa: E402
from chiplab.ingest.torchlogix import reference, to_ir  # noqa: E402
from chiplab.ir.interp import run  # noqa: E402
from chiplab.verify.bitexact import check  # noqa: E402


@pytest.fixture(scope="module")
def model():
    torch.manual_seed(0)
    m = torch.nn.Sequential(LogicDense(16, 48), LogicDense(48, 48), GroupSum(k=3, tau=4.0))
    X = torch.randint(0, 2, (512, 16)).float(); y = (X[:, :4].sum(1) % 3).long()
    opt = torch.optim.Adam(m.parameters(), 0.05)
    for _ in range(25):
        loss = torch.nn.functional.cross_entropy(m(X), y); opt.zero_grad(); loss.backward(); opt.step()
    return m


def test_ir_equals_torchlogix(model):
    ir = to_ir(model)
    X = np.random.default_rng(1).integers(0, 2, size=(2000, 16))
    ref, got = reference(model, X), run(ir, X)
    assert (got["y"] == ref["y"]).all() and (got["scores"] == ref["scores"]).all()
    model.eval()
    with torch.no_grad():
        ev = model(torch.tensor(X).float())
    assert torch.allclose(ev * 4.0, torch.tensor(ref["scores"]).float())


def test_torchlogix_chip_bit_exact(model, tmp_path):
    ir = to_ir(model)
    text, info = emit(ir)
    (tmp_path / "d.v").write_text(text)
    syn = synth_generic(tmp_path / "d.v", info["top"], tmp_path / "syn")
    X = np.random.default_rng(2).integers(0, 2, size=(2000, 16))
    res = check(ir, syn["netlist_json"], info, X, reference=reference(model, X)["y"])
    assert res["bit_exact"], res["pairs"]
    assert syn["gates"] > 0
