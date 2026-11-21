"""The local runner on this machine with a real job: a Python script in a subprocess."""

from __future__ import annotations

import json
import os

import pytest

from chipin_backend.agents.types import AgentSpec
from chipin_backend.config import BackendConfig
from chipin_backend.orchestrate import run_agent
from script_backend import use_script_backend

WRITES_RESULT = """
import json, pathlib
print("step 1: training")
print("step 2: compiling")
pathlib.Path("out").mkdir()
pathlib.Path("out/result.json").write_text(json.dumps({"gates": 42}))
print("done")
"""

FAILS = """
print("about to fail")
raise SystemExit(3)
"""

HANGS = """
import os, pathlib, time
pathlib.Path("pid").write_text(str(os.getpid()))
print("started", flush=True)
time.sleep(60)
"""


@pytest.fixture(autouse=True)
def _script(monkeypatch: pytest.MonkeyPatch) -> None:
    use_script_backend(monkeypatch)


async def test_job_streams_its_log_and_returns_its_outputs(config: BackendConfig) -> None:
    spec = AgentSpec(name="job", prompts=[WRITES_RESULT], backend="script")  # type: ignore[arg-type]
    run, result = await run_agent(spec, config, run_mode="local")

    assert not result.failed
    assert result.files == ["out/result.json"]
    assert json.loads((run.workspace / "out" / "result.json").read_text()) == {"gates": 42}
    texts = [e.data["text"] for e in run.read_events() if e.kind == "text"]
    assert texts == ["step 1: training", "step 2: compiling", "done"]
    assert json.loads(run.record_path.read_text())["status"] == "succeeded"


async def test_failing_job_is_a_failed_result_with_its_exit_status(config: BackendConfig) -> None:
    spec = AgentSpec(name="job", prompts=[FAILS], backend="script")  # type: ignore[arg-type]
    run, result = await run_agent(spec, config, run_mode="local")

    assert result.failed and result.error == "exit status 3"
    assert [e.data["text"] for e in run.read_events() if e.kind == "text"] == ["about to fail"]
    assert json.loads(run.record_path.read_text())["status"] == "failed"


async def test_job_past_its_timeout_is_stopped_and_failed(config: BackendConfig) -> None:
    spec = AgentSpec(name="job", prompts=[HANGS], backend="script", timeout_s=2)  # type: ignore[arg-type]
    run, result = await run_agent(spec, config, run_mode="local")

    assert result.failed and result.error == "timed out after 2s"
    assert result.duration_s < 10
    kinds = [e.kind for e in run.read_events()]
    assert "text" in kinds and kinds[-1] == "error"
    pid = int((run.workspace / "pid").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)  # the script was killed, not left running
