"""Post-processing and channel-serial wrappers through the lab tools: compile-stream (default files byte-identical
to the base branch), prove-sequential (eqy, wrapper RTL == its gate netlist) and the area comparison with the
parallel fusion version (C copies of the core)."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from chiplab import config
from chiplab.emit.postproc import area_compare

from test_postproc import score_ir, scored_spike
from test_stream_golden import GOLDEN, fixture_irs

ROOT = Path(__file__).resolve().parent.parent
CLI = str(Path(sys.executable).parent / "chiplab")
PP = {"smooth": {"mode": "kofn", "n": 3, "k": 2}, "min_duration": 3, "hold": 4}
CS = {"channels": 4, "reduce": "max", "threshold": 2, "output": "score"}
needs_yosys = pytest.mark.skipif(not config.find_bin("yosys"), reason="yosys not installed")
needs_eqy = pytest.mark.skipif(not config.find_bin("eqy"), reason="eqy not installed")


def cli(tool, args, home, timeout=900):
    p = subprocess.run([CLI, tool, "--json", json.dumps(args)], cwd=ROOT, env={**os.environ, "CHIPLAB_HOME": str(home)},
                       capture_output=True, text=True, timeout=timeout)
    return p.returncode, json.loads(p.stdout)


def test_compile_stream_tool_default_files_are_byte_identical(tmp_path):
    gold = json.loads(GOLDEN.read_text())
    for name in ("spike_best", "wide"):
        rc, d = cli("ingest-model", {"format": "chipir", "model": fixture_irs()[name]}, tmp_path)
        assert rc == 0, d
        for tt, fn in ((True, "stream_tt"), (False, "stream")):
            rc, r = cli("compile-stream", {"design_id": d["design_id"], "tt": tt}, tmp_path)
            assert rc == 0 and "postproc" not in r and "area" not in r, r
            folder = Path(r["verilog"]).parent
            g = gold[f"{name}_{'tt' if tt else 'generic'}"]
            assert hashlib.sha256((folder / f"{fn}.v").read_bytes()).hexdigest() == g["verilog_sha256"]
            assert hashlib.sha256((folder / f"{fn}.json").read_bytes()).hexdigest() == g["info_sha256"]


def test_compile_stream_tool_with_blocks(tmp_path):
    rc, d = cli("ingest-model", {"format": "chipir", "model": scored_spike()}, tmp_path)
    rc, r = cli("compile-stream", {"design_id": d["design_id"], "postproc": PP, "channel_serial": CS}, tmp_path)
    assert rc == 0, r
    assert r["frames_per_decision"] == 4 and r["uo_map"][:2] == [{"output": "alarm", "lane": 0, "bit": 0},
                                                                 {"output": "decision", "lane": 0, "bit": 0}]
    rc, r = cli("compile-stream", {"design_id": d["design_id"], "postproc": {"smooth": {"mode": "nope", "n": 2}}}, tmp_path)
    assert rc != 0


@pytest.mark.slow
@needs_eqy
def test_prove_sequential_extended_wrappers(tmp_path):
    rc, d = cli("ingest-model", {"format": "chipir", "model": scored_spike()}, tmp_path)
    rc, r = cli("prove-sequential", {"design_id": d["design_id"], "timeout": 300, "postproc": PP, "channel_serial": CS},
                tmp_path)
    assert rc == 0 and r["proved"] is True and r["frames_per_decision"] == 4, r
    pp = {"output": "score", "smooth": {"mode": "average", "n": 3, "threshold": 2}, "hold": 2}
    rc, r = cli("prove-sequential", {"design_id": d["design_id"], "timeout": 300, "postproc": pp}, tmp_path)
    assert rc == 0 and r["proved"] is True, r
    # window over acc, part of it shown on uo_out (taken from the output register) and part not (own flip-flops)
    rc, r = cli("prove-sequential", {"design_id": d["design_id"], "timeout": 300,
                                     "postproc": {"smooth": {"mode": "average", "n": 3, "threshold": 1}},
                                     "channel_serial": {**CS, "reduce": "sum"}}, tmp_path)
    assert rc == 0 and r["proved"] is True, r
    # whole design (core included) on a two-word toy: a single-word frame cannot be proven by eqy even without the
    # blocks (its 1-bit word counter is optimised away), so the toy streams two words
    toy = json.loads(json.dumps(score_ir()))
    toy["inputs"][0]["lanes"] = 2
    toy["nodes"][0]["W"] = [[1, -1]]
    rc, d = cli("ingest-model", {"format": "chipir", "model": toy}, tmp_path)
    pp = {"output": "s", "threshold": 3, "smooth": {"mode": "majority", "n": 4}, "min_duration": 2, "hold": 3}
    rc, r = cli("prove-sequential", {"design_id": d["design_id"], "timeout": 300, "whole": True, "postproc": pp,
                                     "channel_serial": None}, tmp_path)
    assert rc == 0 and r["proved"] is True and r["scope"] == "whole design", r


@pytest.mark.slow
@needs_yosys
@pytest.mark.parametrize("C", [4, 18])
def test_area_channel_serial_vs_parallel(tmp_path, C):
    r = area_compare(scored_spike(), {**CS, "channels": C}, tmp_path)
    s, p = r["serial"], r["parallel"]
    assert p["copies_of_core"] == C and s["flip_flops"] > 0 and p["flip_flops"] > s["flip_flops"]
    assert p["gates"] > 2 * s["gates"], r
