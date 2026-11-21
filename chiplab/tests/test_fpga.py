"""iCE40 bitstream for a small registered design (streaming wrapper around a tiny chip)."""
import pytest

from chiplab import config
from chiplab.emit.verilog import emit
from chiplab.hw.fpga import board_top_for_tt, ice40_bitstream
from chiplab.hw.tinytapeout import minimal_stream_wrapper

pytestmark = pytest.mark.skipif(not (config.find_bin("nextpnr-ice40") and config.find_bin("icepack")),
                                reason="nextpnr-ice40/icepack not installed")


def tiny_ir():
    return {"ir": "chipir/1", "name": "tiny", "inputs": [{"name": "x", "lanes": 3, "bits": 4, "signed": True}],
            "nodes": [{"id": "h", "op": "matvec", "src": "x", "W": [[1, -2, 3], [2, 1, -1]], "b": [1, -2]},
                      {"id": "c", "op": "clip", "src": "h", "lo": 0, "hi": 7},
                      {"id": "s", "op": "matvec", "src": "c", "W": [[1, -1]], "b": [0]},
                      {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}],
            "outputs": [{"name": "y", "src": "y"}], "meta": {}}


def test_ice40_bitstream(tmp_path):
    ir = tiny_ir()
    core, info = emit(ir)
    (tmp_path / "core.v").write_text(core)
    wrap, top = minimal_stream_wrapper(info["top"], 3, 4, 1)
    (tmp_path / "wrap.v").write_text(wrap)
    board, btop = board_top_for_tt(top)
    (tmp_path / "board.v").write_text(board)
    r = ice40_bitstream([tmp_path / "core.v", tmp_path / "wrap.v", tmp_path / "board.v"], btop, tmp_path / "build")
    assert (tmp_path / "build" / "chip.bin").stat().st_size > 1000
    assert r["luts"] and r["luts"] < r["luts_available"]
    assert r["io_used"] == 18
