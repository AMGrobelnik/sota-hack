"""Verification-level stamping: highest contiguous level with evidence; failures never raise the level."""
import json

from chiplab.verify.ladder import stamp


def _w(d, name, obj):
    (d / name).write_text(json.dumps(obj))


def test_empty_is_level_0(tmp_path):
    assert stamp(tmp_path)["verification_level"] == 0


def test_contiguous_levels(tmp_path):
    _w(tmp_path, "simulate_val.json", {"bit_exact": True, "n": 3688, "inputs": "val"})
    assert stamp(tmp_path)["verification_level"] == 1
    _w(tmp_path, "rtlsim.json", {"passed": True, "lint_ok": True})       # level 3 without level 2 does not count
    assert stamp(tmp_path)["verification_level"] == 1
    _w(tmp_path, "formal.json", {"proved": True, "method": "abc cec"})
    assert stamp(tmp_path)["verification_level"] == 3
    _w(tmp_path, "tt_package.json", {"gl_test_passed": True})
    s = stamp(tmp_path)
    assert s["verification_level"] == 4 and s["missing_next"] == "measured on real hardware"


def test_failure_blocks(tmp_path):
    _w(tmp_path, "simulate_val.json", {"bit_exact": True, "n": 10})
    _w(tmp_path, "simulate_random.json", {"bit_exact": False, "n": 10})
    _w(tmp_path, "formal.json", {"proved": False})
    s = stamp(tmp_path)
    assert s["verification_level"] == 1
    assert len(s["failed_checks"]) == 2
