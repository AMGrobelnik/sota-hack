"""ingest_batch: many models in parallel on the CPU lane (finding 15). Huey immediate mode runs the jobs in this
process, so no worker processes are needed in CI."""
import json
from pathlib import Path

import pytest

import chiplab.api as lab
from chiplab.jobs import queue

FX = json.loads((Path(__file__).resolve().parent.parent / "fixtures" / "spike_best.json").read_text())


@pytest.fixture
def immediate(monkeypatch):
    monkeypatch.setattr(queue.HUEY_CPU, "immediate", True)
    yield


def _variant(k):
    m = json.loads(json.dumps(FX))
    m["W1"][k] = [0] * len(m["W1"][k]); m["W2"][k] = 0          # prune hidden unit k
    return m


def test_ingest_batch_wait(immediate):
    models = [{"format": "intnn", "model": _variant(k), "name": f"v{k}"} for k in range(4)]
    r = lab.ingest_batch(models=models, wait=True, wait_timeout=120)
    assert r["status"] == "ok" and r["n"] == 4 and r["lane"] == "cpu", r
    assert all(isinstance(d, str) for d in r["design_ids"]) and not r["failed"]
    single = lab.ingest_model(format="intnn", model=_variant(2), name="v2")
    assert single["design_id"] == r["design_ids"][2]                 # same design as a one-off ingest


def test_ingest_batch_reports_failures(immediate):
    r = lab.ingest_batch(models=[{"format": "intnn", "model": _variant(0)}, {"format": "nope", "model": {}}], wait=True, wait_timeout=60)
    assert r["design_ids"][0] and r["design_ids"][1] is None and r["failed"][0]["index"] == 1


def test_ingest_batch_async_returns_job_ids(immediate):
    r = lab.ingest_batch(models=[{"format": "intnn", "model": FX}])
    assert r["status"] == "ok" and len(r["job_ids"]) == 1 and "design_ids" not in r
