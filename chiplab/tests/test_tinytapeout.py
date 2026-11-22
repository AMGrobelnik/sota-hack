"""Tiny Tapeout: project folder + RTL streaming test (cocotb + Icarus), and (docker, slow) harden + gate-level test."""
import numpy as np
import pytest

from chiplab import config
from chiplab.emit.verilog import emit
from chiplab.hw.tinytapeout import minimal_stream_wrapper, tt_package
from chiplab.ir.interp import run

from test_fpga import tiny_ir

needs_tools = pytest.mark.skipif(not (config.find_bin("iverilog") and config.find_bin("cocotb-config")),
                                 reason="iverilog/cocotb not installed")


def _project(tmp_path, harden):
    ir = tiny_ir(); core, info = emit(ir)
    (tmp_path / "core.v").write_text(core)
    wrap, top = minimal_stream_wrapper(info["top"], 3, 4, 1)
    (tmp_path / "wrap.v").write_text(wrap)
    X = np.random.default_rng(0).integers(-8, 8, size=(32, 3))
    y = run(ir, X)["y"][:, 0]
    vec = {"bits": 4, "out_bits": 1, "vectors": [{"lanes": [int(v) for v in X[i]], "expect": int(y[i])} for i in range(32)]}
    return tt_package([tmp_path / "core.v", tmp_path / "wrap.v"], top, tmp_path / "tt", {"title": "test"}, tiles="1x1",
                      harden=harden, vectors=vec)


@pytest.mark.slow
@needs_tools
def test_tt_folder_and_rtl_test(tmp_path):
    r = _project(tmp_path, harden=False)
    assert r["user_config_ok"], r.get("error")
    assert r["rtl_test_passed"] is True


@pytest.mark.slow
@pytest.mark.docker
@needs_tools
def test_tt_harden_and_gate_level(tmp_path):
    r = _project(tmp_path, harden=True)
    assert r["harden_ok"], r.get("error")
    assert r["gds"] and r["gl_test_passed"] is True
