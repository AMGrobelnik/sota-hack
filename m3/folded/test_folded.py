"""Tests for the folded-feasibility scripts. Run with the lab environment:

  LAB_HOME=<lab install> bash m3/folded/run.sh pytest m3/folded -q

Tests that need Yosys or Icarus skip when the lab's tool install is not found.
"""
from __future__ import annotations

import re
import shutil

import pytest

import estimate
from rom_bench import TERNARY_CODE, pack, rom_verilog, weights


def _tools() -> bool:
    try:
        from chiplab.config import oss_bin
        return all(shutil.which(oss_bin(t)) for t in ("yosys", "iverilog"))
    except (ImportError, FileNotFoundError, RuntimeError):
        return False


needs_tools = pytest.mark.skipif(not _tools(), reason="lab tool install (yosys, iverilog) not found")


def test_weight_statistics():
    t = weights("ternary", 20000, 1)
    assert set(t) == {-1, 0, 1}
    assert 0.47 < t.count(0) / len(t) < 0.53
    u = weights("uniform4", 20000, 1)
    assert min(u) == -8 and max(u) == 7


@pytest.mark.parametrize("stats,word", [("ternary", 16), ("uniform4", 16), ("uniform4", 4), ("ternary", 64)])
def test_rom_verilog_round_trip(stats, word):
    b = 2 if stats == "ternary" else 4
    ws = weights(stats, 64 * word // b, 3)
    v = rom_verilog(pack(stats, ws, word), word)
    words = [int(h, 16) for h in re.findall(r"'d\d+: d = \d+'h([0-9a-f]+);", v)]
    assert len(words) == 64
    back = []
    inv = {c: w for w, c in TERNARY_CODE.items()}
    for x in words:
        for j in range(word // b):
            f = (x >> (j * b)) & ((1 << b) - 1)
            back.append(inv[f] if stats == "ternary" else (f - 16 if f >= 8 else f))
    assert back == ws


def test_cycles_per_decision():
    # 128 serial input loads + 224 neurons x (128/P + 2) + 4 neurons x (224/P + 2)
    assert estimate.WEIGHTS == 29568
    assert estimate.cycles(1) == 128 + 224 * 130 + 4 * 226
    assert estimate.cycles(4) == 128 + 224 * 34 + 4 * 58


def test_fit_is_least_squares():
    a, b = estimate.fit([0, 1, 2], [1, 3, 5])
    assert (round(a, 9), round(b, 9)) == (1, 2)


@needs_tools
def test_rom_synthesis_keeps_every_word(tmp_path):
    from rom_bench import job
    from verify_rom import verify
    r = job(1, "uniform4", "generic", 16, tmp_path, seed=5)
    assert r["gates"] > 100
    assert verify(tmp_path, "generic")["ok"]
    # a corrupted RTL constant must be caught
    rtl = (tmp_path / "rom.v").read_text()
    first = re.search(r"6'd7: d = 16'h([0-9a-f]{4});", rtl)
    flipped = f"{int(first.group(1), 16) ^ 1:04x}"
    (tmp_path / "rom.v").write_text(rtl.replace(first.group(0), f"6'd7: d = 16'h{flipped};"))
    assert verify(tmp_path, "generic")["mismatches"] == 1


@needs_tools
def test_power_totals_match_mapped_area(tmp_path):
    from power import totals
    from rom_bench import job
    r = job(1, "ternary", "sky130", 16, tmp_path, seed=2)
    t = totals(r["cells_by_type"], "sky130")
    assert not t["unknown"]
    assert abs(t["area_um2"] - r["area_um2"]) < 0.01
    assert t["leak_nw"] > 0 and t["cin_pf"] > 0 and t["flops"] == 6 + 16   # address counter + output register


@needs_tools
@pytest.mark.parametrize("mutate,want", [(False, "PASS"), (True, "FAIL")])
def test_bmc_proof_of_tiny_folded_neuron(tmp_path, mutate, want):
    import json
    import subprocess
    import sys
    from pathlib import Path
    out = tmp_path / "prove.json"
    cmd = [sys.executable, str(Path(__file__).parent / "proto" / "prove_proto.py"), "--n", "8", "--timeout", "120",
           "--out", str(out), "--work", str(tmp_path)] + (["--mutate"] if mutate else [])
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
    assert json.loads(out.read_text())["status"] == want


@needs_tools
@pytest.mark.parametrize("wtype,p", [("ternary", 1), ("ternary", 4), ("uniform4", 1), ("uniform4", 4)])
def test_folded_neuron_matches_integer_model(tmp_path, wtype, p):
    from proto.folded_proto import sim
    r = sim(32, p, wtype, 40, 7, tmp_path)
    assert r["ok"] and r["vectors"] == 40
    assert r["cycles_per_output"] == 32 // p
    assert len(r["output_histogram"]) > 3          # outputs are spread, not one clipped value
