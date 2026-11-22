"""Post-processing (smoothing, k-of-N, duration timer, alarm hold) and channel-serial mode of the streaming wrapper.

Three layers: the pure-Python reference against independent brute-force definitions; the RTL against the reference
in cocotb + Icarus on random and edge frame sequences (with a negative control); the channel-serial semantics
against the parallel fusion version (C copies of the core). Sequential equivalence (eqy) and area are in
test_postproc_formal.py (slow).
"""
import json
from pathlib import Path

import numpy as np
import pytest

from chiplab import config
from chiplab.emit import postproc as ppm
from chiplab.emit.postproc import PostprocError, channel_frames, parallel_ir, reference
from chiplab.emit.stream import emit_stream, packed_outputs
from chiplab.emit.verilog import emit
from chiplab.ingest.intnn import to_ir
from chiplab.ir.interp import run as interp
from chiplab.ir.schema import validate
from chiplab.verify.rtlsim import lint, random_inputs, rtl_simulate

ROOT = Path(__file__).resolve().parent.parent
needs_sim = pytest.mark.skipif(not (config.find_bin("iverilog") and config.find_bin("verilator")),
                               reason="Icarus/Verilator not installed")


def score_ir(bits=6, signed=True):
    """Per-channel toy model: score s = x (so tests can drive any score sequence), decision d = s > 0."""
    return validate({"ir": "chipir/1", "name": f"score{bits}{'s' if signed else 'u'}",
                     "inputs": [{"name": "x", "lanes": 1, "bits": bits, "signed": signed}],
                     "nodes": [{"id": "m", "op": "matvec", "src": "x", "W": [[1]]},
                               {"id": "c", "op": "cmp", "src": "m", "rel": "gt", "t": [0]}],
                     "outputs": [{"name": "s", "src": "m"}, {"name": "d", "src": "c"}]})


def spike():
    return to_ir(json.loads((ROOT / "fixtures" / "spike_best.json").read_text()))


def scored_spike():
    """The spike model with its pre-threshold score exposed as an output (a real per-channel model)."""
    ir = json.loads(json.dumps(spike()))
    ir["outputs"] = [{"name": "score", "src": ir["nodes"][-1]["src"]}] + ir["outputs"]
    return validate(ir)


def edge_frames(lo, hi, seed=0):
    """Score sequences that hit every corner: constant runs at both extremes, alternation, runs of every length
    1..8 around the timer and window lengths, then random values."""
    r = np.random.default_rng(seed)
    seq = [hi] * 12 + [lo] * 12 + [hi, lo] * 6 + [0] * 4
    for k in range(1, 9):
        seq += [hi] * k + [lo] * (9 - k)
    seq += list(r.integers(lo, hi + 1, size=60)) + list(r.choice([lo, 0, 1, hi], size=40))
    return {"x": np.asarray(seq, dtype=np.int64).reshape(-1, 1)}


# ------------------------------------------------------------------------------------------------ reference model

def _brute(pp, values, bits):
    """Independent definitions: windows over the whole history, run lengths, OR over the last H+1 events."""
    sm, M, H = pp.get("smooth"), pp.get("min_duration", 1), pp.get("hold", 0)
    n = sm["n"] if sm else 1
    vb = [0] * (n - 1) + list(bits)
    vv = [0] * (n - 1) + list(values)
    if sm is None:
        s = list(bits)
    elif sm["mode"] == "average":
        s = [int(np.sum(vv[t:t + n]) >= sm["threshold"] * n) for t in range(len(values))]
    else:
        k = sm.get("k", n // 2 + 1)
        s = [int(np.sum(vb[t:t + n]) >= k) for t in range(len(values))]
    run, d = 0, []
    for x in s:
        run = run + 1 if x else 0
        d.append(int(run >= M))
    return [int(any(d[max(0, t - H):t + 1])) for t in range(len(d))]


PP_CASES = [
    {"smooth": {"mode": "kofn", "n": 5, "k": 3}},
    {"smooth": {"mode": "majority", "n": 4}},
    {"smooth": {"mode": "majority", "n": 1}},
    {"smooth": {"mode": "average", "n": 4, "threshold": 5}},
    {"smooth": {"mode": "average", "n": 3, "threshold": -7}},
    {"min_duration": 4},
    {"hold": 3},
    {"smooth": {"mode": "kofn", "n": 3, "k": 2}, "min_duration": 3, "hold": 4},
    {"smooth": {"mode": "average", "n": 2, "threshold": 0}, "min_duration": 2, "hold": 1},
    {},
]


@pytest.mark.parametrize("pp", PP_CASES, ids=[json.dumps(p, sort_keys=True) for p in PP_CASES])
def test_reference_matches_brute_force(pp):
    ir = score_ir()
    info = emit(ir)[1]
    X = edge_frames(-32, 31)
    outs = interp(ir, X)
    full = {"output": "s", "threshold": 1, **pp}
    ref = reference(info, outs, postproc=full)
    vals = [int(v) for v in outs["s"][:, 0]]
    assert ref["fields"]["alarm"] == _brute(pp, vals, [int(v >= 1) for v in vals])
    assert ref["event_frames"] == list(range(len(vals)))
    core = [int(v) for v in packed_outputs(info, outs)]
    assert ref["packed"] == [a | (c << 1) for a, c in zip(ref["fields"]["alarm"], core)]


def test_reference_hand_examples():
    pp = {"smooth": {"mode": "kofn", "n": 3, "k": 2}, "min_duration": 2, "hold": 2}
    bits = [1, 0, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0]
    # kofn(3,2): 0 0 1 1 1 0 0 0 0 0 0 0; duration 2: 0 0 0 1 1 0 ...; hold 2: 0 0 0 1 1 1 1 0 ...
    assert ppm._alarm_seq(ppm.normalize_postproc({**pp, "output": "d"}, emit(score_ir())[1]), bits, bits) == \
        [0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0]
    # a breathing pause of at least 20 s at one decision per second: the alarm rises on the 20th frame
    pause = ppm.normalize_postproc({"output": "d", "min_duration": 20}, emit(score_ir())[1])
    a = ppm._alarm_seq(pause, [1] * 25, [1] * 25)
    assert a.index(1) == 19 and sum(a) == 6
    assert ppm._alarm_seq(pause, [1] * 19 + [0] + [1] * 19, [1] * 19 + [0] + [1] * 19) == [0] * 39


def test_channel_serial_reference():
    ir = score_ir()
    info = emit(ir)[1]
    s = [3, -5, 9, 1, -2, -2, -8, -1, 30, 0, 0, 0]
    outs = interp(ir, {"x": np.asarray(s).reshape(-1, 1)})
    r = reference(info, outs, channel_serial={"channels": 4, "reduce": "max", "threshold": 5, "output": "s"})
    assert r["event_frames"] == [3, 7, 11] and r["fields"]["acc"] == [9, -1, 30] and r["fields"]["decision"] == [1, 0, 1]
    r = reference(info, outs, channel_serial={"channels": 3, "reduce": "sum", "threshold": -3, "output": "s"},
                  postproc={"hold": 1})
    assert r["fields"]["acc"] == [7, -3, 21, 0] and r["fields"]["decision"] == [1, 1, 1, 1]
    assert r["out_bits"] == 2 + 6 + 2 and r["packed"][1] == 1 | (1 << 1) | ((-3 % 256) << 2)


@pytest.mark.parametrize("bad", [
    ({"smooth": {"mode": "median", "n": 3}}, None),
    ({"smooth": {"mode": "kofn", "n": 3, "k": 4}}, None),
    ({"smooth": {"mode": "average", "n": 3}}, None),
    ({"min_duration": 0}, None),
    ({"hold": -1}, None),
    ({"output": "nope"}, None),
    ({"bogus": 1}, None),
    ({"threshold": 2}, {"channels": 4, "reduce": "max", "threshold": 1}),
    (None, {"channels": 1, "reduce": "max", "threshold": 1}),
    (None, {"channels": 4, "reduce": "min", "threshold": 1}),
    (None, {"channels": 4, "reduce": "max"}),
])
def test_bad_options_raise(bad):
    pp, cs = bad
    with pytest.raises(PostprocError):
        emit_stream(score_ir(), postproc=pp, channel_serial=cs)


# ------------------------------------------------------------------------------------------------ parallel baseline

@pytest.mark.parametrize("C,reduce", [(4, "max"), (18, "max"), (4, "sum"), (18, "sum")])
def test_channel_serial_equals_parallel_fusion(C, reduce):
    core = scored_spike()
    Xp = random_inputs(parallel_ir(core, {"channels": C, "reduce": reduce, "threshold": 0, "output": "score"}), 300, seed=C)
    frames = interp(core, channel_frames(Xp, C))
    probe = reference(emit(core)[1], frames, channel_serial={"channels": C, "reduce": reduce, "threshold": 0, "output": "score"})
    T = int(np.median(probe["fields"]["acc"]))           # a threshold that splits the decisions
    cs = {"channels": C, "reduce": reduce, "threshold": T, "output": "score"}
    po = interp(parallel_ir(core, cs), Xp)
    r = reference(emit(core)[1], frames, channel_serial=cs)
    assert r["fields"]["decision"] == [int(v) for v in po["decision"][:, 0]]
    assert r["fields"]["acc"] == [int(v) for v in po["acc"][:, 0]]
    assert 0 < sum(r["fields"]["decision"]) < len(r["fields"]["decision"])   # the test sees both answers


# ------------------------------------------------------------------------------------------------ RTL == reference

RTL_CASES = [
    ("kofn+timer+hold", score_ir(), {"output": "s", "threshold": 1, "smooth": {"mode": "kofn", "n": 5, "k": 3},
                                     "min_duration": 3, "hold": 4}, None, True),
    ("average signed", score_ir(), {"output": "s", "smooth": {"mode": "average", "n": 4, "threshold": -3}, "hold": 2},
     None, False),
    ("majority on decision", score_ir(), {"output": "d", "smooth": {"mode": "majority", "n": 3}}, None, True),
    ("timer only", score_ir(5, False), {"output": "s", "threshold": 9, "min_duration": 6}, None, False),
    ("serial max", score_ir(), None, {"channels": 4, "reduce": "max", "threshold": 10, "output": "s"}, True),
    ("serial sum unsigned", score_ir(4, False), None, {"channels": 3, "reduce": "sum", "threshold": 20, "output": "s"}, False),
    ("serial sum + postproc", score_ir(), {"smooth": {"mode": "kofn", "n": 3, "k": 2}, "min_duration": 2, "hold": 3},
     {"channels": 3, "reduce": "sum", "threshold": -5, "output": "s"}, False),
    ("serial max + average", score_ir(), {"smooth": {"mode": "average", "n": 3, "threshold": 4}},
     {"channels": 2, "reduce": "max", "threshold": 0, "output": "s"}, True),
]


@needs_sim
@pytest.mark.parametrize("name,ir,pp,cs,tt", RTL_CASES, ids=[c[0] for c in RTL_CASES])
def test_rtl_equals_reference_on_edge_sequences(tmp_path, name, ir, pp, cs, tt):
    p = ir["inputs"][0]
    lo, hi = (-(1 << (p["bits"] - 1)), (1 << (p["bits"] - 1)) - 1) if p["signed"] else (0, (1 << p["bits"]) - 1)
    X = edge_frames(lo, hi)
    r = rtl_simulate(ir, tmp_path, X=X, tt=tt, postproc=pp, channel_serial=cs)
    assert r["passed"] and r["lint"]["ok"] and r["verification_level"] == 3, r
    C = cs["channels"] if cs else 1
    assert r["decisions"] == len(X["x"]) // C
    if pp:
        assert 0 < r["alarm_on_fraction"] < 1, r      # the sequence exercises both alarm states


@needs_sim
def test_rtl_real_model_random(tmp_path):
    core = scored_spike()
    pp = {"smooth": {"mode": "majority", "n": 3}, "hold": 2}
    cs = {"channels": 4, "reduce": "max", "threshold": 2, "output": "score"}
    r = rtl_simulate(core, tmp_path, n=60, tt=True, postproc=pp, channel_serial=cs, seed=3)
    assert r["passed"] and r["vectors"] == 240 and r["decisions"] == 60, r


@needs_sim
def test_negative_control_detects_wrong_reference(tmp_path, monkeypatch):
    real = ppm._alarm_seq
    monkeypatch.setattr(ppm, "_alarm_seq", lambda pp, v, b: [1 - a for a in real(pp, v, b)])
    r = rtl_simulate(score_ir(), tmp_path, X=edge_frames(-32, 31), postproc={"output": "s", "hold": 2})
    assert not r["passed"] and r["mismatches"] > 0


def test_extended_wrapper_lints_and_maps_bits(tmp_path):
    if not config.find_bin("verilator"):
        pytest.skip("verilator not installed")
    text, info = emit_stream(score_ir(), tt=True, postproc={"output": "s", "hold": 1},
                             channel_serial=None)
    assert info["uo_map"][0] == {"output": "alarm", "lane": 0, "bit": 0} and info["output_bits"] == 1 + 6 + 1
    assert info["frames_per_decision"] == 1 and info["truncated"]
    (tmp_path / "w.v").write_text(text)
    assert lint(tmp_path / "w.v", info["top"])["ok"]
    text, info = emit_stream(score_ir(), tt=False, channel_serial={"channels": 18, "reduce": "sum", "threshold": 0})
    assert [f["name"] for f in info["output_fields"]] == ["decision", "acc"] and info["channel_serial"]["acc_bits"] == 6 + 5
    assert info["frames_per_decision"] == 18 and "valid rises after every 18 frames" in info["protocol"]
    (tmp_path / "g.v").write_text(text)
    assert lint(tmp_path / "g.v", info["top"])["ok"]
