"""LibreLane place-and-route (docker): a tiny combinational chip gets area, timing, power, a GDS and a PNG."""
import shutil

import pytest

from chiplab.emit.verilog import emit
from chiplab.hw.librelane import timing_power_layout

from test_fpga import tiny_ir


@pytest.mark.docker
@pytest.mark.slow
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
def test_sky130_layout(tmp_path):
    core, info = emit(tiny_ir())
    (tmp_path / "core.v").write_text(core)
    r = timing_power_layout([tmp_path / "core.v"], info["top"], tmp_path / "ll", pdk="sky130A", clock_period_ns=20.0)
    assert r["area_um2"] and r["area_um2"] > 0
    assert r["timing_ws_ns"] is not None and r["power_w"] and r["power_w"] > 0
    assert r["gds"] and r["png"]


@pytest.mark.parametrize("pdk", ["sky130A", "gf180mcuD", "ihp-sg13g2"])
def test_pdk_and_config(pdk, tmp_path):
    """No flow run: the PDK resolves under PDK_ROOT and a LibreLane config is generated."""
    from chiplab.hw.librelane import check_pdk, write_config
    c = check_pdk(pdk)
    if not c["found"]:
        pytest.skip(f"{pdk} not installed under PDK_ROOT")
    assert c["ok"], c
    cfg = write_config(["core.v"], "chip_x", tmp_path, pdk)
    assert cfg["DESIGN_NAME"] == "chip_x" and (tmp_path / "config.json").exists()
    if pdk == "gf180mcuD":
        assert cfg["VDD_PIN_VOLTAGE"] == 3.3
