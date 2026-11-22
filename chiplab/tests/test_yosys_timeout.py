"""A timed-out Yosys run must not leave the processes it started (yosys-abc, shell commands) running."""
import os
import subprocess
import time
import uuid

import pytest

from chiplab import config
from chiplab.hw import yosys
from chiplab.hw.yosys import SynthError, run

pytestmark = pytest.mark.skipif(not config.find_bin("yosys"), reason="yosys not installed")


def _alive(marker: str) -> list[str]:
    out = subprocess.run(["ps", "-Ao", "command="], capture_output=True, text=True, timeout=30).stdout
    return [ln for ln in out.splitlines() if marker in ln and "ps -Ao" not in ln]


def test_timeout_kills_yosys_children(tmp_path):
    # Yosys `!` runs a shell command as its child, the same way its abc pass starts yosys-abc
    secs = f"{37 + uuid.uuid4().int % 1000 / 1000:.3f}"
    with pytest.raises(SynthError, match="timed out"):
        run(f"! sleep {secs}\n", tmp_path, timeout=2, name="hang")
    time.sleep(0.5)
    assert _alive(f"sleep {secs}") == []


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="needs POSIX process groups")
def test_timed_out_synthesis_leaves_no_child(tmp_path, monkeypatch):
    # A wide multiplier keeps ABC's default script busy for minutes; the timeout fires while yosys-abc runs.
    started = []
    real_popen = yosys.subprocess.Popen

    def popen(*a, **kw):
        p = real_popen(*a, **kw)
        started.append(p.pid)
        return p

    monkeypatch.setattr(yosys.subprocess, "Popen", popen)
    rtl = tmp_path / "mul.v"
    rtl.write_text("module mul(input [47:0] a, input [47:0] b, output [95:0] y); assign y = a * b; endmodule\n")
    try:
        yosys.synth_generic(rtl, "mul", tmp_path / "wd", effort="high", timeout=15)
    except SynthError as e:
        assert "timed out" in str(e)
    else:
        pytest.skip("synthesis finished before the timeout on this machine")
    assert "Executing ABC pass" in (tmp_path / "wd" / "synth_generic.log").read_text()
    time.sleep(0.5)
    with pytest.raises(ProcessLookupError):  # the whole group (yosys, its shell, yosys-abc) is gone
        os.killpg(started[0], 0)


def test_normal_run_unchanged(tmp_path):
    r = run("! true\n", tmp_path, timeout=60, name="ok")
    assert r["seconds"] >= 0 and (tmp_path / "ok.log").exists()
