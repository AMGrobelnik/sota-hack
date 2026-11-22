"""Licence hygiene: Tiny Tapeout (Apache-2.0) refuses RTL with alkaid's LGPL-3.0 helper modules, and the lab ships
its own licence and third-party notices."""
from pathlib import Path

import pytest
import yaml

from chiplab.hw.tt_submit import export_submission_repo, lgpl_modules, readiness, refuse_lgpl_rtl

LGPL_RTL = ("module tt_um_chipin_x (input wire [7:0] ui_in, output wire [7:0] uo_out, input wire [7:0] uio_in,\n"
            "  output wire [7:0] uio_out, output wire [7:0] uio_oe, input wire ena, input wire clk, input wire rst_n);\n"
            "  chipin_alk_negative #(.BW_IN(8)) u0 (.in(ui_in), .out(uo_out));\n"
            "  assign uio_out = 0; assign uio_oe = 0;\nendmodule\n"
            "module chipin_alk_negative #(parameter BW_IN = 8) (input [BW_IN-1:0] in, output [BW_IN-1:0] out);\n"
            "  assign out = -in;\nendmodule\n")
TINY = {"ir": "chipir/1", "name": "lic_tiny", "inputs": [{"name": "x", "lanes": 3, "bits": 4, "signed": False}],
        "nodes": [{"id": "s", "op": "matvec", "src": "x", "W": [[1, -1, 1]], "b": [-2]},
                  {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}],
        "outputs": [{"name": "y", "src": "y"}], "meta": {}}


def _project(tmp_path: Path, rtl: str) -> Path:
    proj = tmp_path / "tt_um_chipin_x"
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "core.v").write_text(rtl)
    (proj / "info.yaml").write_text(yaml.safe_dump({"yaml_version": 6, "project": {
        "title": "t", "author": "a", "description": "d", "language": "Verilog", "clock_hz": 1, "tiles": "1x1",
        "top_module": "tt_um_chipin_x", "source_files": ["core.v"]}}))
    return proj


def test_lgpl_modules_found():
    assert lgpl_modules(LGPL_RTL) == ["chipin_alk_negative"]
    assert lgpl_modules("module m_mv_h0 (input a, output b); assign b = a; endmodule") == []


def test_refuse_lgpl_rtl(tmp_path):
    (tmp_path / "bad.v").write_text(LGPL_RTL)
    (tmp_path / "ok.v").write_text("module ok; endmodule\n")
    refuse_lgpl_rtl([tmp_path / "ok.v", tmp_path / "missing.v"])
    with pytest.raises(ValueError, match="LGPL-3.0.*Apache-2.0.*regenerate the design with the clean emitter"):
        refuse_lgpl_rtl([tmp_path / "ok.v", tmp_path / "bad.v"])


def test_readiness_blocks_lgpl_rtl(tmp_path):
    r = readiness(_project(tmp_path, LGPL_RTL), run_tests=False, run_precheck_if_hardened=False)
    ck = next(c for c in r["checks"] if c["check"] == "no LGPL code in RTL (Apache-2.0)")
    assert not ck["ok"] and "chipin_alk_negative" in ck["detail"] and "clean emitter" in ck["fix"]
    assert "no LGPL code in RTL (Apache-2.0)" in r["blocking"] and not r["ready"]


def test_readiness_passes_clean_rtl(tmp_path):
    clean = LGPL_RTL.replace("chipin_alk_negative", "tt_um_chipin_x_neg")
    r = readiness(_project(tmp_path, clean), run_tests=False, run_precheck_if_hardened=False)
    assert next(c for c in r["checks"] if c["check"] == "no LGPL code in RTL (Apache-2.0)")["ok"]


def test_export_refuses_lgpl_rtl(tmp_path):
    with pytest.raises(ValueError, match="clean emitter"):
        export_submission_repo(_project(tmp_path, LGPL_RTL), tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_tt_package_refuses_lgpl_design():
    """The tt_package tool refuses before any packaging work (no tt-support-tools or Docker needed)."""
    import chiplab.api as lab
    from chiplab import config
    d = lab.compile_ir(ir=TINY)["design_id"]
    dv = config.HOME / "designs" / d / "design.v"
    good = dv.read_text()
    try:
        dv.write_text(good + "\n" + LGPL_RTL.split("endmodule\n", 1)[1])
        r = lab.tt_package(design_id=d, force=True)
        assert r["status"] == "error" and "LGPL-3.0" in r["error"] and "clean emitter" in r["error"], r
    finally:
        dv.write_text(good)
