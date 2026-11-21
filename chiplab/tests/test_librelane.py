"""LibreLane place-and-route (docker): a tiny combinational chip gets area, timing, power, a GDS and a PNG."""
import shutil

import pytest

from chiplab.emit.verilog import emit
from chiplab.hw.librelane import timing_power_layout

from test_fpga import tiny_ir

pytestmark = [pytest.mark.docker, pytest.mark.slow,
              pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")]


def test_sky130_layout(tmp_path):
    core, info = emit(tiny_ir())
    (tmp_path / "core.v").write_text(core)
    r = timing_power_layout([tmp_path / "core.v"], info["top"], tmp_path / "ll", pdk="sky130A", clock_period_ns=20.0)
    assert r["area_um2"] and r["area_um2"] > 0
    assert r["timing_ws_ns"] is not None and r["power_w"] and r["power_w"] > 0
    assert r["gds"] and r["png"]
