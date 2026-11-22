"""Matvec rows longer than MAX_SUM_TERMS are emitted as balanced partial sums (Yosys's parser crashes on a single
sum of ~700 terms); shorter rows keep the one-expression form, so existing designs emit byte-identical Verilog."""
import re
from pathlib import Path

import numpy as np
import pytest

from chiplab import config
from chiplab.emit.verilog import MAX_SUM_TERMS, emit

N = 1024
HAVE_YOSYS = bool(config.find_bin("yosys") and config.find_bin("yosys-abc"))


def long_ir(n: int = N, seed: int = 0) -> dict:
    r = np.random.default_rng(seed)
    w = [int(v) for v in r.choice([-1, 1], size=n)]           # powers of two: exactly one term per weight
    short = [int(v) for v in r.choice([-2, 1, 0], size=n)]
    short[200:] = [0] * (n - 200)                             # a 200-weight row stays one expression
    return {"ir": "chipir/1", "name": "longrow", "inputs": [{"name": "x", "lanes": n, "bits": 4, "signed": True}],
            "nodes": [{"id": "s", "op": "matvec", "src": "x", "W": [w, short], "b": [5, -3]}],
            "outputs": [{"name": "y", "src": "s"}], "meta": {}}


def _sum_lines(text: str, lane: int) -> list[str]:
    return [ln for ln in text.splitlines() if re.match(rf"\s*wire \[\d+:0\] n_s_{lane}(_t\d+)? =", ln)]


def test_long_row_split_short_row_kept():
    text, _ = emit(long_ir())
    long_lines, short_lines = _sum_lines(text, 0), _sum_lines(text, 1)
    assert len(long_lines) == 1 + -(-N // MAX_SUM_TERMS)      # partial sums plus their total
    lanes = [set(re.findall(r"\bi_x_\d+\b", ln)) for ln in long_lines]
    assert all(len(s) <= MAX_SUM_TERMS for s in lanes)
    assert sum(len(s) for s in lanes) == N and len(set().union(*lanes)) == N
    assert len(short_lines) == 1 and "_t" not in short_lines[0]


@pytest.mark.skipif(not HAVE_YOSYS, reason="yosys not installed")
def test_long_row_synthesises_bit_exact(tmp_path):
    from chiplab.hw.yosys import synth_generic
    from chiplab.verify.bitexact import check
    ir = long_ir()
    text, info = emit(ir)
    (tmp_path / "d.v").write_text(text)
    syn = synth_generic(tmp_path / "d.v", info["top"], tmp_path / "syn", timeout=600)
    X = np.random.default_rng(1).integers(-8, 8, size=(2000, N))
    X[:4] = [[-8] * N, [7] * N, [0] * N, [-1] * N]              # extremes of the sum
    res = check(ir, syn["netlist_json"], info, X)
    assert res["bit_exact"], res.get("pairs")


@pytest.mark.slow
@pytest.mark.skipif(not HAVE_YOSYS, reason="yosys not installed")
def test_long_row_proved_against_golden(tmp_path):
    from chiplab.hw.yosys import synth_generic
    from chiplab.verify.formal import prove
    ir = long_ir()
    text, info = emit(ir)
    (tmp_path / "d.v").write_text(text)
    syn = synth_generic(tmp_path / "d.v", info["top"], tmp_path / "syn", timeout=600)
    r = prove(ir, info, Path(syn["gate_verilog"]), tmp_path / "d.v", tmp_path / "p", timeout=300, golden=True)
    assert r["proved"] is True, r
    assert "golden" in r["against"] or "golden_attempt" in r, r
