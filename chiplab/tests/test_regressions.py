"""Regression tests for the findings from the Apple Silicon install check (M3 P1/P4)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import chiplab.api as lab
from chiplab.tools import STATUS_RC, normalize_args, outcome

ROOT = Path(__file__).resolve().parent.parent
CLI = str(Path(sys.executable).parent / "chiplab")
TINY = {"ir": "chipir/1", "name": "rt", "inputs": [{"name": "x", "lanes": 3, "bits": 3, "signed": False}],
        "nodes": [{"id": "s", "op": "matvec", "src": "x", "W": [[1, -1, 1]], "b": [-2]},
                  {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}], "outputs": [{"name": "y", "src": "y"}], "meta": {}}
ADD_PORT = {"inputs": [{"name": "x", "lanes": 1, "bits": 4, "signed": False}], "outputs": [{"name": "y", "lanes": 1, "bits": 5, "signed": False}]}
ADD_IR = {"ir": "chipir/1", "name": "xx", "inputs": ADD_PORT["inputs"], "nodes": [{"id": "s", "op": "add", "a": "x", "b": "x"}],
          "outputs": [{"name": "y", "src": "s"}], "meta": {}}


def cli(tool, args, home):
    p = subprocess.run([CLI, tool, "--json", json.dumps(args)], cwd=ROOT, env={**os.environ, "CHIPLAB_HOME": str(home)},
                       capture_output=True, text=True, timeout=600)
    return p.returncode, json.loads(p.stdout)


# 1. exit codes follow the status
def test_outcome_mapping():
    assert outcome({"status": "ok"}) == "ok"
    assert outcome({"status": "ok", "error": "timed out after 300s"}) == "timeout"
    assert outcome({"status": "ok", "error": "boom"}) == "error"
    assert outcome({"status": "ok", "proved": None, "detail": "timed out after 300s"}) == "timeout"
    assert outcome({"status": "ok", "bit_exact": False}) == "fail"
    assert outcome({"status": "ok", "accepted": False}) == "error"
    assert STATUS_RC == {"ok": 0, "error": 1, "fail": 2, "timeout": 3}


def test_cli_exit_codes(tmp_path):
    rc, r = cli("synthesize", {"design_id": "does-not-exist"}, tmp_path)
    assert rc == 1 and r["status"] == "error"
    rc, r = cli("submit-verilog", {"verilog": 'module m; initial $system("x"); endmodule', "top": "m",
                                   "port_spec": ADD_PORT, "reference_ir": ADD_IR}, tmp_path)
    assert rc == 1 and r["status"] == "error" and r["accepted"] is False
    rc, r = cli("compile-ir", {"ir": TINY}, tmp_path)
    assert rc == 0
    rc, r = cli("submit-job", {"tool": "synthesize", "args": {"design_id": r["design_id"]}}, tmp_path)
    assert rc == 0 and r["status"] == "ok" and r["state"] == "queued"   # queued is success, not an error


def test_failed_check_is_rc2(tmp_path):
    wrong = "module xx(input [3:0] x, output [4:0] y); assign y = x + 5'd1; endmodule"
    rc, r = cli("submit-verilog", {"verilog": wrong, "top": "xx", "port_spec": ADD_PORT, "reference_ir": ADD_IR,
                                   "n": 64, "allow_host": True}, tmp_path)
    assert rc == 2 and r["status"] == "fail" and r["bit_exact"] is False


# 2. Verilator EOFNEWLINE: source without a trailing newline is accepted
def test_submit_verilog_without_trailing_newline():
    src = "module xx(input [3:0] x, output [4:0] y); assign y = x + x; endmodule"   # no "\n"
    r = lab.submit_verilog(verilog=src, top="xx", port_spec=ADD_PORT, reference_ir=ADD_IR, n=64, allow_host=True)
    assert r["status"] == "ok" and r["accepted"] and r["bit_exact"], r


# 5. sandbox refuses to run on the host without the container unless allowed
def test_sandbox_refuses_without_container(monkeypatch, tmp_path):
    from chiplab.verify import sandbox
    monkeypatch.setattr(sandbox, "_docker_ok", lambda: False)
    r = sandbox.check_verilog("module xx(input a, output y); assign y = a; endmodule\n", "xx", tmp_path / "a")
    assert r["accepted"] is False and "not available" in r["problems"][0]
    r = sandbox.check_verilog("module xx(input a, output y); assign y = a; endmodule\n", "xx", tmp_path / "b", allow_host=True)
    assert r["accepted"] is True and "local" in r["sandbox"]


# patch 02: top must be a plain identifier
def test_top_identifier_validated():
    from chiplab.verify.sandbox import check_verilog
    r = check_verilog("module m; endmodule\n", "m; read_verilog /etc/passwd", Path("/tmp/never"))
    assert r["accepted"] is False and any("identifier" in p for p in r["problems"])


# 6. torchlogix pickles need trusted=true, and are refused over the network server
def test_torchlogix_requires_trust(monkeypatch, tmp_path):
    f = tmp_path / "m.pt"; f.write_bytes(b"not a model")
    r = lab.ingest_model(format="torchlogix", path=str(f))
    assert r["status"] == "error" and "trusted" in r["error"]
    monkeypatch.setenv("CHIPLAB_REMOTE", "1")
    r = lab.ingest_model(format="torchlogix", path=str(f), trusted=True)
    assert r["status"] == "error" and "CHIPLAB_ALLOW_PICKLE" in r["error"]


# 7. equivalent calls share one cache entry
def test_cache_key_normalised():
    from chiplab.tools import TOOLS
    fn = TOOLS["layout"]["fn"].__wrapped__
    assert normalize_args(fn, {"design_id": "d", "clock_period_ns": 20}) == \
        normalize_args(fn, {"design_id": "d", "pdk": "sky130", "clock_period_ns": 20.0, "activity_vcd": None})


# 8. Docker found through DOCKER_HOST / known sockets
def test_docker_host_respected(monkeypatch):
    from chiplab import config
    monkeypatch.setenv("DOCKER_HOST", "unix:///tmp/some.sock")
    assert config.ensure_docker_host() == "unix:///tmp/some.sock"


# 11. golden model keeps genuinely 64-bit ports intact, and the whole-design golden proof works
def test_golden_keeps_64bit_ports(tmp_path):
    ir = {"ir": "chipir/1", "name": "w64", "inputs": [{"name": "x", "lanes": 2, "bits": 32, "signed": True}],
          "nodes": [{"id": "s", "op": "add", "a": "x", "b": "x"}], "outputs": [{"name": "y", "src": "s"}], "meta": {}}
    from chiplab.emit.golden import emit_golden
    from chiplab.emit.verilog import emit
    _, info = emit(ir)
    assert "[63:0] x" in emit_golden(ir, "g", info)          # the 2 x 32-bit input port is 64 bits wide
    d = lab.compile_ir(ir=ir)["design_id"]
    r = lab.prove_equivalence(design_id=d, golden=True)
    assert r["status"] == "ok" and r["proved"] is True and "golden" in r["against"], r


# 4 / 10. sequential proof is compositional and fast
def test_prove_sequential_compositional():
    d = lab.compile_ir(ir=TINY)["design_id"]
    r = lab.prove_sequential(design_id=d, timeout=300)
    assert r["status"] == "ok" and r["proved"] is True and r["blackboxed"], r
