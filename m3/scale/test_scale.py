"""Tests for the scale package's generator and results builder (no lab, no EDA tools).

Run: python -m pytest m3/scale/test_scale.py   (numpy needed; the chip lab's venv has it)
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"scale_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = _load("gen_models")
mr = _load("make_results")


@pytest.mark.parametrize("size", ["1k", "5k"])
@pytest.mark.parametrize("style", ["ternary", "q4"])
def test_make_is_deterministic_and_in_range(size, style):
    m1, i1 = gen.make(size, style, 7)
    m2, i2 = gen.make(size, style, 7)
    assert m1 == m2 and i1 == i2
    lo, hi = (-1, 1) if style == "ternary" else (-8, 7)
    flat = [w for L in m1["layers"] for row in L["W"] for w in row] + m1["Wo"][0]
    assert min(flat) >= lo and max(flat) <= hi
    assert len(flat) == i1["weights"]
    assert all(L["amax"] == gen.STYLES[style] for L in m1["layers"])


def test_committed_models_match_generator():
    index = json.loads((HERE / "models" / "index.json").read_text())
    assert [i["name"] for i in index] == [f"{s}_{z}" for s in gen.STYLES for z in gen.SIZES]
    info = next(i for i in index if i["name"] == "ternary_1k")
    model, again = gen.make("1k", "ternary", info["seed"])
    assert again == info
    assert json.loads((HERE / "models" / "ternary_1k.json").read_text())["model"] == model


def test_scrub_removes_personal_paths():
    x = {"a": ["err at /Users/someone/x/y/luts.log", "/home/u/z.txt ok"], "b": 3}
    out = json.dumps(mr.scrub(x))
    assert "/Users/" not in out and "/home/" not in out
    assert "<path>/luts.log" in out and out.count("<path>/") == 2


def test_powerlaw_recovers_exponent_and_inverts():
    pts = [(w, 3.0 * w ** 1.2) for w in (1000, 5000, 10000, 30000)]
    a, b = mr.powerlaw(pts)
    assert a == pytest.approx(3.0, rel=1e-6) and b == pytest.approx(1.2, rel=1e-6)
    assert mr.max_weights((a, b), 3.0 * 2000 ** 1.2) == pytest.approx(2000, rel=1e-6)
    assert mr.powerlaw([(1000, 5.0)]) is None
    assert mr.max_weights((a, b), -1) == 0.0


def test_fits_serial_close_to_single_and_parallel_smaller():
    f = (50.0, 1.1)
    r = mr.fits(f, "sky130", 10e6, 0.6)
    assert r["parallel18"] < r["serial18"] <= r["single"]
    assert r["serial18"] > 0.99 * r["single"]


def test_label():
    assert mr.label(0.5) == "none"
    assert mr.label(655) == "655 (extrap.)"
    assert mr.label(2400) == "2.4k"
    assert mr.label(54000) == "54k (extrap.)"


def _rec(step_status: str, proof=None):
    return {"key": "k", "steps": {"synthesize": {"status": step_status, "wall_s": 1.0}}, "proof": proof,
            "peak_rss_mb_sampled": {"synth/x": 10}}


def test_merge_keeps_ok_step_and_takes_later_proof():
    r1 = {"designs": [_rec("ok")]}
    r2 = {"designs": [{**_rec("timeout", proof={"proved": True}), "peak_rss_mb_sampled": {"synth/x": 30}}]}
    m = mr.merge([r1, r2])
    d = m["designs"][0]
    assert d["steps"]["synthesize"]["status"] == "ok"
    assert d["proof"] == {"proved": True}
    assert d["peak_rss_mb_sampled"]["synth/x"] == 30
    assert [r["run"] for r in m["runs"]] == [1, 2]
    r3 = {"designs": [_rec("ok")]}
    assert mr.merge([{"designs": [_rec("timeout")]}, r3])["designs"][0]["steps"]["synthesize"]["status"] == "ok"


def test_lut_estimates_only_fill_missing():
    rows = [{"emitter": "default", "gates": 100, "luts_xc7": 30}, {"emitter": "default", "gates": 200, "luts_xc7": 60},
            {"emitter": "default", "gates": 1000, "luts_xc7": None}]
    mr.lut_estimates(rows)
    assert rows[2]["luts_xc7_est"] == 300 and rows[2]["luts_xc7_est_basis"].startswith("estimate")
    assert "luts_xc7_est" not in rows[0]


def test_published_results_have_no_personal_paths():
    text = (HERE / "results.json").read_text()
    assert "/Users/" not in text and "/home/" not in text
    d = json.loads(text)
    assert len(d["summary"]) == 16
