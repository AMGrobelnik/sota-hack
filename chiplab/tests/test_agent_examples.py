"""Every example in AGENT.md runs as written and returns exit code 0 with status ok.

Examples run in the documented order in a fresh CHIPLAB_HOME. Examples whose requirements are missing on this machine
(Docker image, PDK, Tiny Tapeout tools, iCE40 tools) are skipped, so CI runs the Docker-free ones on Linux and macOS.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chiplab import config
from chiplab.docs import EXAMPLES, REQUIRES, example_cli

ROOT = Path(__file__).resolve().parent.parent
CLI = str(Path(sys.executable).parent / "chiplab")
STATE: dict = {}


def _have(req: str) -> bool:
    if req == "pdk":
        try:
            from chiplab.hw.pdk import liberty
            liberty("sky130"); return True
        except Exception:
            return False
    if req == "docker":
        if not shutil.which("docker"):
            return False
        return subprocess.run(["docker", "image", "inspect", config.LIBRELANE_IMAGE], capture_output=True).returncode == 0
    if req == "tt":
        return (Path(config.TT_TOOLS) / "tt_tool.py").exists() and bool(config.TT_PYTHON)
    if req == "ice40":
        return bool(config.find_bin("nextpnr-ice40") and config.find_bin("icepack"))
    return True


@pytest.fixture(scope="module")
def home(tmp_path_factory):
    return tmp_path_factory.mktemp("chiplab_home")


@pytest.mark.parametrize("name", list(EXAMPLES))
def test_example(name, home):
    missing = [r for r in REQUIRES.get(name, []) if not _have(r)]
    if missing:
        pytest.skip(f"needs {', '.join(missing)}")
    if name in ("tt_readiness", "tt_export") and STATE.get("tt_package") != "ok":
        pytest.skip("tt_package did not run")
    if name in ("job_status", "job_result") and "job_id" not in STATE:
        pytest.skip("submit_job did not run")
    env = {**os.environ, "CHIPLAB_HOME": str(home)}
    if name == "ingest_model":
        p = subprocess.run(["bash", "-c", example_cli(name, EXAMPLES[name]).replace("chiplab ", f"{CLI} ", 1)],
                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    else:
        args = json.loads(json.dumps(EXAMPLES[name]).replace('"@job_id"', json.dumps(STATE.get("job_id"))))
        p = subprocess.run([CLI, name.replace("_", "-"), "--json", json.dumps(args)], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=900)
    try:
        res = json.loads(p.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"{name}: not JSON (rc {p.returncode}): {p.stdout[-300:]} {p.stderr[-300:]}")
    STATE[name] = res.get("status")
    if name == "submit_job":
        STATE["job_id"] = res.get("job_id")
    assert p.returncode == 0 and res.get("status") == "ok", f"{name}: rc {p.returncode}, {json.dumps(res)[:600]}"
