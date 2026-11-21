"""Sequential equivalence (eqy) of a small streaming wrapper against its own gate netlist."""
import pytest

from chiplab import config
from chiplab.emit.verilog import emit
from chiplab.hw.tinytapeout import minimal_stream_wrapper
from chiplab.verify.eqy import prove_sequential

from test_fpga import tiny_ir

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not config.find_bin("eqy"), reason="eqy not installed")]


def test_stream_wrapper_equivalent(tmp_path):
    core, info = emit(tiny_ir())
    (tmp_path / "core.v").write_text(core)
    w, top = minimal_stream_wrapper(info["top"], 3, 4, 1)
    (tmp_path / "wrap.v").write_text(w)
    r = prove_sequential([tmp_path / "core.v", tmp_path / "wrap.v"], top, tmp_path / "run", timeout=300)
    assert r["proved"] is True
