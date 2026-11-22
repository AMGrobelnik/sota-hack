"""Opt-in alkaid emission: same function as the default emitter (ABC cec), gates bit-exact vs the IR, and the
default emitter's output is unaffected."""
import json

import numpy as np
import pytest

from chiplab.emit.optimized import available as _alkaid_installed  # noqa: E402  (checks without importing alkaid)

if not _alkaid_installed():
    pytest.skip("alkaid not installed", allow_module_level=True)
# never `import alkaid` here: its native solver in the pytest process crashes later torch tests on macOS

from chiplab.config import find_bin  # noqa: E402
from chiplab.emit.optimized import emit_optimized  # noqa: E402
from chiplab.emit.verilog import emit  # noqa: E402
from chiplab.hw.yosys import synth_generic  # noqa: E402
from chiplab.verify.bitexact import check  # noqa: E402
from chiplab.verify.formal import prove  # noqa: E402
from chiplab.verify.formal_extra import prove_same_function  # noqa: E402

pytestmark = pytest.mark.skipif(not (find_bin("yosys") and find_bin("yosys-abc")), reason="yosys not installed")


def small_net(seed=0, signed=False):
    r = np.random.default_rng(seed)
    return {"ir": "chipir/1", "name": f"alk{seed}", "inputs": [{"name": "x", "lanes": 6, "bits": 5, "signed": signed}],
            "nodes": [{"id": "h0", "op": "matvec", "src": "x", "b": r.integers(-4, 5, 5).tolist(),
                       "W": (r.integers(-3, 4, (5, 6)) * (r.random((5, 6)) > 0.3)).tolist() + [], },
                      {"id": "h1", "op": "shift", "src": "h0", "k": 1},
                      {"id": "h2", "op": "clip", "src": "h1", "lo": 0, "hi": 15},
                      {"id": "s", "op": "matvec", "src": "h2", "W": [r.integers(-2, 3, 5).tolist(), [0] * 5, [4, 0, 0, 0, 0]],
                       "b": [-1, 3, 0]},
                      {"id": "y", "op": "argmax", "src": "s"}],
            "outputs": [{"name": "y", "src": "y"}, {"name": "s", "src": "s"}], "meta": {}}


TINY = {"ir": "chipir/1", "name": "tiny", "inputs": [{"name": "x", "lanes": 4, "bits": 4, "signed": False}],
        "nodes": [{"id": "m", "op": "matvec", "src": "x", "W": [[1, -1, 0, 1], [0, 1, 1, -1], [3, 1, -2, 0], [0, 0, 0, 0], [8, 0, 0, 0]],
                   "b": [1, 0, -2, 5, 0]}], "outputs": [{"name": "y", "src": "m"}], "meta": {}}


def test_tiny_matvec_fast(tmp_path):
    """Constant row, power-of-two row (implied trailing zeros), bias: same function, bit-exact, node proof."""
    from chiplab.verify.formal_extra import prove_matvec_nodes
    td, di = emit(TINY); ta, ai = emit_optimized(TINY, "alkaid")
    (tmp_path / "d.v").write_text(td); (tmp_path / "a.v").write_text(ta)
    assert prove_same_function(tmp_path / "d.v", tmp_path / "a.v", di["top"], ai["top"], tmp_path / "same", 120)["proved"] is True
    pn = prove_matvec_nodes(TINY, ta, tmp_path / "nodes", 120)
    assert pn["proved"] is True and all(n.get("same_module", True) for n in pn["nodes"]), pn
    syn = synth_generic(tmp_path / "a.v", ai["top"], tmp_path / "syn")
    X = np.random.default_rng(0).integers(0, 16, size=(20000, 4))
    assert check(TINY, syn["netlist_json"], ai, X)["bit_exact"]


@pytest.mark.slow
@pytest.mark.parametrize("seed,signed", [(0, False), (1, True), (2, False)])
def test_alkaid_same_function_and_bit_exact(seed, signed, tmp_path):
    ir = small_net(seed, signed)
    td, di = emit(ir)
    ta, ai = emit_optimized(ir, "alkaid")
    assert di["top"] == ai["top"] and di["inputs"] == ai["inputs"] and di["outputs"] == ai["outputs"]
    assert any(n["impl"] == "alkaid" for n in ai["optimizer"]["nodes"]), ai["optimizer"]
    (tmp_path / "d.v").write_text(td); (tmp_path / "a.v").write_text(ta)
    same = prove_same_function(tmp_path / "d.v", tmp_path / "a.v", di["top"], ai["top"], tmp_path / "same", 300)
    assert same["proved"] is True, same
    syn = synth_generic(tmp_path / "a.v", ai["top"], tmp_path / "syn")
    r = np.random.default_rng(seed)
    lo, hi = (-16, 16) if signed else (0, 32)
    res = check(ir, syn["netlist_json"], ai, r.integers(lo, hi, size=(20000, 6)))
    assert res["bit_exact"], res["pairs"]
    pf = prove(ir, ai, __import__("pathlib").Path(syn["gate_verilog"]), tmp_path / "a.v", tmp_path / "formal", 300)
    assert pf["proved"] is True, pf


def test_default_emit_unchanged_by_hook():
    ir = small_net(3)
    assert emit(ir)[0] == emit(ir, None, node_impl=None)[0]
    assert emit_optimized(ir, "none")[0] == emit(ir)[0]


@pytest.mark.slow
def test_negative_control_wrong_rtl_is_refuted(tmp_path):
    ir = small_net(4)
    td, di = emit(ir)
    bad = json.loads(json.dumps(ir)); bad["nodes"][0]["b"][0] += 1
    ta, ai = emit_optimized(bad, "alkaid", top=di["top"])
    (tmp_path / "d.v").write_text(td); (tmp_path / "a.v").write_text(ta)
    same = prove_same_function(tmp_path / "d.v", tmp_path / "a.v", di["top"], ai["top"], tmp_path / "same", 300)
    assert same["proved"] is False, same


def test_alkaid_runs_after_torch_is_loaded():
    """macOS CI (5b15d6c): alkaid's CMVM aborted a process that had imported torch (two OpenMP runtimes). alkaid now
    runs in a worker process; a fresh interpreter that imports torch first must still emit, and stay alive."""
    import subprocess
    import sys
    pytest.importorskip("torch")
    code = ("import json, sys, torch\n"
            "from chiplab.emit.optimized import emit_optimized\n"
            "torch.ones(4).sum()\n"
            "ir = json.loads(sys.argv[1])\n"
            "t, i = emit_optimized(ir, 'alkaid')\n"
            "assert i['optimizer']['name'] == 'alkaid' and any(n['impl'] == 'alkaid' for n in i['optimizer']['nodes'])\n"
            "print('ok')\n")
    p = subprocess.run([sys.executable, "-c", code, json.dumps(TINY)], capture_output=True, text=True, timeout=600)
    assert p.returncode == 0 and p.stdout.strip().endswith("ok"), (p.returncode, p.stderr[-800:])


def test_worker_matches_in_process():
    """The worker gives what alkaid gives in-process. The in-process reference runs in a fresh interpreter that never
    loads torch: running alkaid inside pytest (torch loaded) is exactly what aborts on macOS."""
    import subprocess
    import sys
    via_worker = emit_optimized(TINY, "alkaid")
    code = ("import json, sys\n"
            "assert 'torch' not in sys.modules\n"
            "from chiplab.emit.optimized import emit_optimized_local\n"
            "sys.stdout.write(json.dumps(emit_optimized_local(json.loads(sys.argv[1]), 'alkaid'), default=str))\n")
    p = subprocess.run([sys.executable, "-c", code, json.dumps(TINY)], capture_output=True, text=True, timeout=600)
    assert p.returncode == 0, p.stderr[-800:]
    assert json.loads(p.stdout) == json.loads(json.dumps(list(via_worker), default=str))


def test_alkaid_never_loaded_into_this_process():
    """macOS CI (ec334aa): with alkaid's native solver imported into the pytest process (importorskip at collection),
    a later torch test segfaulted. alkaid must only ever run in its worker process."""
    import sys
    emit_optimized(TINY, "alkaid")
    assert not [m for m in sys.modules if m == "alkaid" or m.startswith("alkaid.")]


def _alkaid_template_lines() -> list[str]:
    """Distinctive lines of alkaid's Verilog templates and of its own Verilog generator, read from the installed
    package's files (never imported here)."""
    import importlib.util
    from pathlib import Path
    root = Path(importlib.util.find_spec("alkaid").submodule_search_locations[0]) / "codegen" / "rtl" / "verilog"
    out = []
    for f in sorted((root / "source").glob("*.v")):
        for ln in f.read_text().splitlines():
            ln = ln.strip()
            if len(ln) > 24 and not ln.startswith("//") and ln not in ("endmodule", "end", "begin"):
                out.append(ln)
    assert len(out) > 10, "alkaid's Verilog templates not found"
    return out + ["Explicit quantization operation will drop bits", "verilator lint_off UNUSEDSIGNAL"]


def test_no_alkaid_template_text_in_generated_rtl():
    """Licence: alkaid is LGPL-3.0; the generated RTL holds only chiplab-written Verilog (graph from alkaid's solver)."""
    import re
    ta, ai = emit_optimized(TINY, "alkaid")
    assert any(n["impl"] == "alkaid" for n in ai["optimizer"]["nodes"]), ai["optimizer"]
    assert ai["optimizer"]["solver_options"] == {"binary_lut": False}
    assert "chipin_alk_" not in ta
    for name in ("binop", "multiplier", "mux", "negative", "shift_adder", "ternary_adder", "timescale"):
        assert not re.search(rf"\b{name}\b", ta), name
    hits = [ln for ln in _alkaid_template_lines() if ln in ta]
    assert not hits, hits[:3]


def test_committed_alk_designs_have_no_alkaid_template_text():
    """The M3 run's committed -alk chips were regenerated with the clean emitter."""
    from pathlib import Path
    chips = Path(__file__).resolve().parent.parent.parent / "m3" / "e2e" / "run" / "workspace" / "chips"
    files = sorted(chips.glob("*-alk/design.v"))
    if not files:
        pytest.skip("m3 run outputs not in this checkout")
    lines = _alkaid_template_lines()
    for f in files:
        text = f.read_text()
        assert "chipin_alk_" not in text and not [ln for ln in lines if ln in text], f.parent.name


def test_graph_rtl_rejects_operations_it_does_not_write():
    """A graph node other than a shifted sum (here a multiplication) raises Unsupported, so the matvec falls back to
    standard code instead of emitting wrong logic. Plain stand-ins for alkaid's graph, alkaid not imported."""
    from types import SimpleNamespace as NS
    from chiplab.emit.optimized import Unsupported, graph_rtl
    q = NS(kif=(0, 4, 0))
    ops = [NS(opcode=-1, addr=(), data=(0,), qint=q), NS(opcode=-1, addr=(), data=(1,), qint=q),
           NS(opcode=7, addr=(0, 1), data=(), qint=NS(kif=(0, 8, 0)))]
    comb = NS(ops=ops, out_idxs=[2], inp_kifs=np.array([[0, 0], [4, 4], [0, 0]]), out_kifs=np.array([[0], [8], [0]]))
    with pytest.raises(Unsupported, match="graph operation 7"):
        graph_rtl(comb, "m")
    ops[2] = NS(opcode=1, addr=(0, 1), data=(2,), qint=NS(kif=(1, 6, 0)))
    comb = NS(ops=ops, out_idxs=[2], inp_kifs=np.array([[0, 0], [4, 4], [0, 0]]), out_kifs=np.array([[1], [6], [0]]))
    text = graph_rtl(comb, "m")
    assert "module m (" in text and "- ({" in text and "<< 2)" in text and "assign model_out[6:0] = v2;" in text
