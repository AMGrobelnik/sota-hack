"""The job protocol between the launcher and a worker pod, both sides.

Pod side (:func:`create_app`, run by ``python -m chipmonk_backend.compute.runpod.worker``
as the image's entrypoint): an aiohttp app on port 8080 that accepts one job,
runs it with :class:`~chipmonk_backend.compute.local.LocalRunner`, and serves:

* ``POST /job``      body ``{"spec": AgentSpec.to_dict(), "run_id": str}`` -> 202
* ``GET  /events``   SSE stream of ``AgentEvent.to_dict()``, from ``?since=<n>``
* ``GET  /result``   ``AgentResult.to_dict()`` once done, else 404
* ``GET  /health``   200 when ready for a job
* ``POST /inject``   ``{"message": str}`` -> backend ``inject``

Every route requires ``Authorization: Bearer <token>``, a random per-pod token
the launcher generates and passes in the pod env as :data:`WORKER_TOKEN_ENV`.
A TTL watchdog ends the process at ``pod_timeout_s + 300`` so an orphan cannot
bill forever.

STUB: port from AI Inventor ``aii_lib/run/agent_worker_server.py``,
``aii_lib/run/_job_core.py``, ``aii_lib/run/_agent_worker/*``,
``aii_runpod/comms/entrypoint.py`` (pod side) and
``aii_runpod/comms/orchestrator_client.py`` (launcher side), replacing the
internal-auth bearer and the server credential fetch.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from chipmonk_backend.agents.types import AgentEvent, AgentResult, AgentSpec
from chipmonk_backend.config import BackendConfig

if TYPE_CHECKING:
    from aiohttp import web

WORKER_PORT = 8080
WORKER_TOKEN_ENV = "CHIPMONK_WORKER_TOKEN"
TTL_GRACE_S = 300


def create_app(config: BackendConfig, *, token: str) -> web.Application:
    """The pod-side aiohttp application described in the module docstring."""
    raise NotImplementedError("worker app: port aii_lib/run/agent_worker_server.py")


class WorkerClient:
    """Launcher side: talks to one worker pod through RunPod's HTTP proxy."""

    def __init__(self, base_url: str, *, token: str, timeout_s: float = 30.0) -> None:
        self.base_url = base_url
        self._token = token
        self.timeout_s = timeout_s

    async def wait_healthy(self, *, timeout_s: float) -> None:
        """Poll ``/health`` until 200; ``TimeoutError`` after ``timeout_s``."""
        raise NotImplementedError("WorkerClient.wait_healthy: port pod_infra/readiness.py")

    async def submit(self, spec: AgentSpec, *, run_id: str) -> None:
        """``POST /job``."""
        raise NotImplementedError("WorkerClient.submit: port orchestrator_client.submit_job")

    def events(self, *, since: int = 0) -> AsyncIterator[AgentEvent]:
        """``GET /events`` as an async iterator; resumes from ``since`` on reconnect."""
        raise NotImplementedError("WorkerClient.events: port orchestrator_client.stream_telemetry")

    async def result(self) -> AgentResult:
        """``GET /result`` once the job is done."""
        raise NotImplementedError("WorkerClient.result: port orchestrator_client.poll_until_done")


def main() -> None:
    """Pod entrypoint: read the token from the env, start the TTL watchdog, serve."""
    raise NotImplementedError("worker entrypoint: port aii_runpod/comms/entrypoint.py")


if __name__ == "__main__":
    main()


__all__ = ["TTL_GRACE_S", "WORKER_PORT", "WORKER_TOKEN_ENV", "WorkerClient", "create_app", "main"]
