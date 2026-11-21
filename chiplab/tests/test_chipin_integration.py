"""The lab inside a real ChipIn run, against the backend's own code (origin/amg/backend, read-only).

1. Export the backend source (git archive, read-only) and run it in its own locked environment (uv, the
   backend's uv.lock), so nothing is stubbed and the lab's environment gets no extra dependencies.
2. The REAL write_helper() puts ./progress in a run workspace; the REAL build_agent_env() gives the agent's
   environment (CHIPLAB_*, DOCKER_HOST, PDK_ROOT stripped), with HOME pointing at a temp folder whose
   ~/.config/chiplab/config.json copies this machine's (lab home redirected to a temp folder).
3. Lab tools run as `chiplab <tool>` from the workspace under that environment.
4. The REAL ProgressTailer + EventLog read progress.jsonl: every line must become an event (no warnings),
   metrics must use chiplab.progress.METRIC_KEYS with numeric values, artifacts must be files inside the run
   folder (workspace/chips/<design_id>/...), and stage events must come only from the progress_stages call.
Skips cleanly when the branch, uv or the network (first resolution of the backend's lock) is unavailable.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chiplab import config

ROOT = Path(__file__).resolve().parent.parent          # chiplab/ project folder
CLI = str(Path(sys.executable).parent / "chiplab")
REF = "origin/amg/backend"

BACKEND_SIDE = r'''
import asyncio, json, sys
from pathlib import Path
mode, run = sys.argv[1], Path(sys.argv[2])
ws = run / "workspace"
if mode == "probe":
    import chipin_backend.api.progress, chipin_backend.agents.env  # noqa: F401
    print("{}")
elif mode == "prepare":
    from chipin_backend.api.progress import PROGRESS_FILE, write_helper
    from chipin_backend.agents.env import build_agent_env
    ws.mkdir(parents=True, exist_ok=True)
    helper = write_helper(ws, run / PROGRESS_FILE)
    base = json.loads(Path(sys.argv[3]).read_text())
    print(json.dumps({"helper": str(helper), "env": build_agent_env(base=base)}))
else:
    from loguru import logger
    from chipin_backend.api.events import EventLog
    from chipin_backend.api.progress import PROGRESS_FILE, ProgressTailer
    warnings = []
    logger.remove()
    logger.add(lambda m: warnings.append(str(m).strip()), level="WARNING")
    loop = asyncio.new_event_loop()
    log = EventLog(run / "events.jsonl", "chiplab-integration-test", loop)
    tailer = ProgressTailer(run / PROGRESS_FILE, log, run, ws)
    tailer.drain()
    lines = [l for l in (run / PROGRESS_FILE).read_text().splitlines() if l.strip()] if (run / PROGRESS_FILE).exists() else []
    print(json.dumps({"events": log.since(1), "warnings": warnings, "lines": [json.loads(l) for l in lines]}))
    loop.close()
'''


def _git(*args, check=True):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=check)


@pytest.fixture(scope="module")
def backend(tmp_path_factory):
    try:
        import chiplab.progress  # noqa: F401  (the bridge)
    except ImportError:
        pytest.skip("chiplab.progress (the ChipIn bridge) is not built yet")
    uv = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")
    if not Path(uv).exists() and not shutil.which(uv):
        pytest.skip("uv not available")
    _git("fetch", "-q", "origin", "+refs/heads/amg/backend:refs/remotes/origin/amg/backend", check=False)  # explicit refspec (CI clones shallow)
    if _git("rev-parse", "--verify", "-q", REF, check=False).returncode != 0:
        pytest.skip(f"{REF} not available")
    top = _git("rev-parse", "--show-toplevel").stdout.strip()
    tmp = tmp_path_factory.mktemp("chipin_backend")
    arch = subprocess.run(f"git -C '{top}' archive {REF} backend | tar -x -C '{tmp}'", shell=True, capture_output=True, text=True)
    if arch.returncode != 0 or not (tmp / "backend" / "src" / "chipin_backend").is_dir():
        pytest.skip(f"cannot export {REF}: {arch.stderr[-200:]}")
    subprocess.run(["chmod", "-R", "a-w", str(tmp / "backend")], check=False)   # read-only: we never edit it
    script = tmp / "backend_side.py"
    script.write_text(BACKEND_SIDE)
    # the backend's own locked environment (its uv.lock), outside its read-only source folder
    sync = subprocess.run([uv, "sync", "--project", str(tmp / "backend"), "--frozen", "--no-install-project", "--no-dev", "-q"],
                          capture_output=True, text=True, env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(tmp / "venv")}, timeout=900)
    if sync.returncode != 0:
        pytest.skip(f"backend environment unavailable (network?): {sync.stderr[-300:]}")
    py = str(tmp / "venv" / "bin" / "python")
    env = {**os.environ, "PYTHONPATH": str(tmp / "backend" / "src")}
    env.pop("VIRTUAL_ENV", None)

    def run_backend(*args, timeout=600):
        return subprocess.run([py, str(script), *args], capture_output=True, text=True, env=env, timeout=timeout)
    probe = run_backend("probe", str(tmp))
    assert probe.returncode == 0, f"backend code does not import: {probe.stderr[-600:]}"
    return run_backend


def _lab(tool, args, cwd, env, timeout=900):
    p = subprocess.run([CLI, tool, "--json", json.dumps(args)], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    try:
        return p.returncode, json.loads(p.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"{tool}: not JSON (rc {p.returncode}): {p.stdout[-300:]} {p.stderr[-300:]}")


def test_lab_reports_through_the_real_progress_helper(backend, tmp_path):
    from chiplab.progress import METRIC_KEYS
    run = tmp_path / "runs" / "r1"
    run.mkdir(parents=True)
    # hermetic HOME: this machine's lab config, with the lab's home in a temp folder
    home = tmp_path / "home"
    cfg = json.loads(config.CONFIG_FILE.read_text()) if config.CONFIG_FILE.exists() else {}
    cfg["home"] = str(tmp_path / "labhome")
    (home / ".config" / "chiplab").mkdir(parents=True)
    (home / ".config" / "chiplab" / "config.json").write_text(json.dumps(cfg))
    base = {**os.environ, "HOME": str(home), "PATH": os.environ.get("PATH", "")}
    (tmp_path / "base_env.json").write_text(json.dumps(base))
    prep = backend("prepare", str(run), str(tmp_path / "base_env.json"))
    assert prep.returncode == 0, prep.stderr[-800:]
    out = json.loads(prep.stdout)
    agent_env = out["env"]
    assert not any(k.startswith("CHIPLAB_") for k in agent_env) and "PDK_ROOT" not in agent_env
    ws = run / "workspace"
    assert (ws / "progress").exists()

    spike = json.loads((ROOT / "fixtures" / "spike_best.json").read_text())
    rc, r = _lab("ingest-model", {"format": "intnn", "model": spike, "name": "spike"}, ws, agent_env)
    assert rc == 0, r
    d = r["design_id"]
    calls = [("synthesize", {"design_id": d, "progress_stages": True}),            # the only call that marks stages
             ("simulate", {"design_id": d, "inputs": "random", "n": 2000}),
             ("prove-equivalence", {"design_id": d}),
             ("estimate-batch", {"designs": [d]}),
             ("chip-report", {"design_id": d})]
    try:
        from chiplab.hw.pdk import liberty
        liberty("sky130")
        calls.insert(3, ("map-to-process", {"design_id": d, "pdk": "sky130"}))
    except Exception:
        pass
    for tool, args in calls:
        rc, r = _lab(tool, args, ws, agent_env)
        assert rc == 0 and r.get("status") == "ok", (tool, r)

    cons = backend("consume", str(run))
    assert cons.returncode == 0, cons.stderr[-800:]
    got = json.loads(cons.stdout)
    events, warnings, lines = got["events"], got["warnings"], got["lines"]
    if os.environ.get("CHIPLAB_TEST_VERBOSE"):
        from collections import Counter
        print("\nlines", len(lines), "events", len(events), Counter(e["type"] for e in events))
        print("metrics", {e["key"]: e["value"] for e in events if e["type"] == "metric"})
        print("artifacts", [(e["kind"], e["path"]) for e in events if e["type"] == "artifact"])
        print("stages", [(e["name"], e["state"]) for e in events if e["type"] == "stage"])
        print("status", [e["text"] for e in events if e["type"] == "status"][:4])
    assert lines, "the lab reported nothing through ./progress"
    assert not warnings, f"the backend rejected progress lines: {warnings[:5]}"
    seen, dup_artifacts = set(), 0
    for ln in lines:
        if ln.get("type") == "artifact":
            if ln["path"] in seen:
                dup_artifacts += 1
            seen.add(ln["path"])
    assert len(events) == len(lines) - dup_artifacts, "every progress line must become exactly one event"

    metrics = [e for e in events if e["type"] == "metric"]
    assert metrics, "no metrics reported"
    for m in metrics:
        assert m["key"] in METRIC_KEYS, f"unknown metric key {m['key']}"
        assert isinstance(m["value"], (int, float)) and not isinstance(m["value"], bool)
    keys = {m["key"] for m in metrics}
    assert {"gates", "depth"} <= keys and ({"vectors_checked", "mismatches"} & keys)
    gates = next(m["value"] for m in metrics if m["key"] == "gates")
    assert gates > 100

    assert any(e["type"] == "status" and e["text"].startswith("ChipIn is") for e in events)

    arts = [e for e in events if e["type"] == "artifact"]
    assert arts, "no artifacts reported"
    for a in arts:
        assert a["path"].startswith(f"workspace/chips/{d}/") or a["path"].startswith("workspace/chips/"), a
        assert (run / a["path"]).is_file() or (run / a["path"]).is_dir(), a
        assert a["kind"] in ("file", "report", "chip")
    assert any(a["kind"] == "report" for a in arts), "chip-report should give a report artifact"

    stages = [e for e in events if e["type"] == "stage"]
    assert stages, "progress_stages=true should mark its stage"
    assert {s["name"] for s in stages} == {"compile"}, stages
    assert [s["state"] for s in stages] == ["started", "done"], stages
