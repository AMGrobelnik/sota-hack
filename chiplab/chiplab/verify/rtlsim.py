"""Verification ladder level 3: the clocked streaming chip, simulated with cocotb + Icarus Verilog, must give the
integer model's answers frame by frame; plus a Verilator lint of the same RTL.

The testbench streams each input vector word by word exactly as a host would drive the pins (emit/stream.py
protocol), waits for `valid`, reads the outputs and compares them with ir.interp. Vectors come from the
scientist (real recordings, already encoded to integers) or are random within each input's range.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import numpy as np

from chiplab.config import OSS, oss_bin
from chiplab.emit.stream import emit_stream, frame_words, packed_outputs
from chiplab.ir.interp import run as interp

_TB = r'''
import json, os
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, ReadOnly

def _u(v):
    return v.to_unsigned() if hasattr(v, "to_unsigned") else int(v)

@cocotb.test()
async def stream_vectors(dut):
    cfg = json.load(open(os.environ["CHIPLAB_TB_JSON"]))
    tt = cfg["tt"]
    Clock(dut.clk, 10, unit="ns").start()
    if tt:
        dut.ena.value = 1; dut.ui_in.value = 0; dut.uio_in.value = 0
    else:
        dut.strobe.value = 0; dut.din.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)
    mism, first, got_all = 0, [], []
    for n, (words, exp) in enumerate(zip(cfg["words"], cfg["expected"])):
        for w in words:
            if tt:
                dut.ui_in.value = w & 0x7F; dut.uio_in.value = (w >> 7) & 0xFF
                await ClockCycles(dut.clk, 1)
                dut.ui_in.value = 0x80 | (w & 0x7F)
                await ClockCycles(dut.clk, 3)
                dut.ui_in.value = w & 0x7F
                await ClockCycles(dut.clk, 3)
            else:
                dut.din.value = w; await ClockCycles(dut.clk, 1)
                dut.strobe.value = 1; await ClockCycles(dut.clk, 3)
                dut.strobe.value = 0; await ClockCycles(dut.clk, 3)
        got, ok = None, False
        for _ in range(8):
            await RisingEdge(dut.clk); await ReadOnly()
            if tt:
                v = _u(dut.uo_out.value)
                if v >> 7:
                    got, ok = v & 0x7F, True; break
            else:
                if _u(dut.valid_o.value):
                    got, ok = _u(dut.dout.value), True; break
        await ClockCycles(dut.clk, 1)
        if not ok or got != exp:
            mism += 1
            if len(first) < 5:
                first.append({"vector": n, "expected": exp, "got": got, "valid": ok})
        got_all.append(got)
    json.dump({"vectors": len(cfg["words"]), "mismatches": mism, "first_mismatches": first},
              open(cfg["result"], "w"))
    assert mism == 0, f"{mism} mismatching frames, first: {first}"
'''


def lint(verilog: Path, top: str) -> dict:
    try:
        p = subprocess.run([oss_bin("verilator"), "--lint-only", "-Wall", "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL",
                            "--top-module", top, str(verilog)], capture_output=True, text=True, timeout=300)
        return {"ok": p.returncode == 0, "messages": [l for l in p.stderr.splitlines() if l.startswith("%")][:20]}
    except Exception as e:
        return {"ok": None, "messages": [f"verilator not run: {e}"]}


def random_inputs(ir: dict, n: int, seed: int = 0) -> dict:
    r = np.random.default_rng(seed)
    X = {}
    for p in ir["inputs"]:
        lo, hi = (-(1 << (p["bits"] - 1)), 1 << (p["bits"] - 1)) if p["signed"] else (0, 1 << p["bits"])
        X[p["name"]] = r.integers(lo, hi, size=(n, p["lanes"]))
    return X


def rtl_simulate(ir: dict, workdir: Path, X: dict | None = None, n: int = 1000, tt: bool = True, seed: int = 0,
                 timeout: int = 900, reference: dict | None = None, expected: dict | None = None) -> dict:
    """Stream vectors through the wrapper in Icarus via cocotb; compare with the integer model. Level 3.

    reference: another chipir/1 whose interpreter gives the expected outputs (default: ir itself).
    expected:  the scientist's expected outputs {output name: int [N, lanes]} instead of an interpreter.
    """
    workdir = Path(workdir); workdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    text, info = emit_stream(ir, tt=tt)
    vpath = workdir / f"{info['top']}.v"
    vpath.write_text(text)
    li = lint(vpath, info["top"])
    if X is None:
        X = random_inputs(ir, n, seed)
    elif not isinstance(X, dict):
        X = {ir["inputs"][0]["name"]: np.asarray(X)}
    N = len(next(iter(X.values())))
    words = frame_words(info["core"], X)
    ref_out = expected if expected is not None else interp(reference or ir, X)
    exp = packed_outputs(info["core"], ref_out, info["visible_output_bits"])
    cfgp, resp = workdir / "tb_vectors.json", workdir / "tb_result.json"
    cfgp.write_text(json.dumps({"tt": tt, "words": words.tolist(), "expected": [int(e) for e in exp], "result": str(resp)}))
    (workdir / "chiplab_stream_tb.py").write_text(_TB)
    if resp.exists():
        resp.unlink()
    err = _run_cocotb(vpath, info["top"], workdir, cfgp, timeout)
    res = json.loads(resp.read_text()) if resp.exists() else {"vectors": N, "mismatches": None, "first_mismatches": []}
    passed = res.get("mismatches") == 0 and res.get("vectors") == N
    return {"passed": bool(passed), "vectors": res.get("vectors"), "mismatches": res.get("mismatches"),
            "first_mismatches": res.get("first_mismatches"), "lint": li, "top": info["top"], "tt": tt,
            "transfers_per_frame": info["transfers_per_frame"], "visible_output_bits": info["visible_output_bits"],
            "truncated": info["truncated"], "verilog": str(vpath), "error": err,
            "verification_level": 3 if passed and li["ok"] else None, "seconds": round(time.time() - t0, 1),
            "simulator": "icarus via cocotb runner" + (" (OSS CAD Suite python)" if _oss_python() else " (lab venv)")}


_RUNNER = r'''
import sys
from pathlib import Path
from cocotb_tools.runner import get_runner
vpath, top, workdir, cfgp = sys.argv[1:5]
w = Path(workdir)
r = get_runner("icarus")
r.build(sources=[vpath], hdl_toplevel=top, build_dir=w / "sim_build", always=True, timescale=("1ns", "1ps"),
        log_file=w / "build.log")
r.test(hdl_toplevel=top, test_module="chiplab_stream_tb", test_dir=w, build_dir=w / "sim_build",
       extra_env={"CHIPLAB_TB_JSON": cfgp}, log_file=w / "sim.log")
'''


def _oss_python() -> str | None:
    """OSS CAD Suite ships its own Python with cocotb and a shared libpython (needed by Icarus' VPI), so it works
    even where the lab's Python is a static build (e.g. uv-managed Python on a fresh machine)."""
    from chiplab.config import find_bin
    roots = [Path(OSS)]
    iv = find_bin("iverilog")
    if iv:
        roots.append(Path(iv).resolve().parent.parent)
    for root in roots:
        for rel in ("py3bin/python3", "bin/python3"):
            p = root / rel
            if p.exists() and (root / "bin" / "cocotb-config").exists():
                return str(p)
    return None


def _run_cocotb(vpath: Path, top: str, workdir: Path, cfgp: Path, timeout: int) -> str | None:
    import subprocess
    py = _oss_python()
    if py:
        (workdir / "run_tb.py").write_text(_RUNNER)
        env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME")}
        env["PATH"] = f"{Path(py).parent.parent / 'bin'}:{env.get('PATH', '')}"
        try:
            p = subprocess.run([py, str(workdir / "run_tb.py"), str(vpath), top, str(workdir), str(cfgp)], cwd=workdir,
                               env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return f"timed out after {timeout}s"
        (workdir / "runner.log").write_text(p.stdout + p.stderr)
        return None if p.returncode == 0 else f"runner exit {p.returncode}: {(p.stderr or p.stdout)[-400:]}"
    from cocotb_tools.runner import get_runner  # fallback: the lab's own Python
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{Path(os.sys.executable).parent}:{old_path}"
    try:
        r = get_runner("icarus")
        r.build(sources=[vpath], hdl_toplevel=top, build_dir=workdir / "sim_build", always=True, timescale=("1ns", "1ps"),
                log_file=workdir / "build.log")
        r.test(hdl_toplevel=top, test_module="chiplab_stream_tb", test_dir=workdir, build_dir=workdir / "sim_build",
               extra_env={"CHIPLAB_TB_JSON": str(cfgp)}, log_file=workdir / "sim.log")
    except BaseException as e:  # cocotb's runner raises SystemExit on a failing test; the results file decides
        return f"{type(e).__name__}: {e}"
    finally:
        os.environ["PATH"] = old_path
    return None


def tt_project_test() -> str:
    """The streaming testbench as a Tiny Tapeout project test (test/test.py reading test/vectors.json)."""
    return _TB.replace('cfg = json.load(open(os.environ["CHIPLAB_TB_JSON"]))',
                       'from pathlib import Path\n    _here = Path(__file__).parent\n    cfg = json.load(open(_here / "vectors.json"))\n'
                       '    cfg["result"] = str(_here / "tb_result.json")')


def tt_vectors(ir: dict, n: int = 64, seed: int = 0, X: dict | None = None) -> dict:
    """Vectors for the TT project test: input words per frame and the expected visible outputs (integer model)."""
    from chiplab.emit.stream import emit_stream
    _, info = emit_stream(ir, tt=True)
    X = X or random_inputs(ir, n, seed)
    return {"tt": True, "words": frame_words(info["core"], X).tolist(),
            "expected": [int(e) for e in packed_outputs(info["core"], interp(ir, X), info["visible_output_bits"])]}
