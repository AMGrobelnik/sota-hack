"""The job protocol between the launcher and a worker pod, both sides.

Pod side (:func:`create_app`, run by ``python -m chipmonk_backend.compute.runpod.worker``
as the image's command): an aiohttp app on port 8080 that accepts one job,
runs it with :class:`~chipmonk_backend.compute.local.LocalRunner`, and serves:

* ``POST /job``      body ``{"spec": AgentSpec.to_dict(), "run_id": str}`` -> 202
* ``GET  /events``   SSE stream of ``AgentEvent.to_dict()``, from ``?since=<n>``;
  ends with ``event: done``
* ``GET  /result``   ``AgentResult.to_dict()`` once done, else 204
* ``GET  /outputs``  the job's workspace as a ``.tar.gz`` once done
* ``GET  /health``   200 when the server is up
* ``POST /inject``   ``{"message": str}`` -> the running backend's ``inject``

Every route requires ``Authorization: Bearer <token>``, a random per-pod token
the launcher generates and passes in the pod env as :data:`WORKER_TOKEN_ENV`
(the worker is reachable by anyone who learns the pod id through RunPod's
proxy). A TTL watchdog ends the process at ``pod_timeout_s + 300`` so an
orphan cannot bill forever.

Ported from AI Inventor ``aii_lib/run/agent_worker_server.py`` (routes, SSE
buffer and resume, result-after-stream), ``aii_runpod/comms/entrypoint.py``
(TTL watchdog) and ``aii_runpod/comms/orchestrator_client.py`` (submit retries
through the proxy, SSE reconnect with ``since``, result polling). The shared
internal key and the server credential fetch are replaced by the per-pod
token; the DBOS journal by the run folder's ``events.jsonl``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import signal
import tarfile
import tempfile
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from aiohttp import web
from loguru import logger

from chipmonk_backend.agents.types import AgentEvent, AgentResult, AgentSpec
from chipmonk_backend.compute.local import LocalRunner
from chipmonk_backend.config import BackendConfig, load_config
from chipmonk_backend.log import setup_logging
from chipmonk_backend.runs import JsonlEventSink, RunDir

WORKER_PORT = 8080
WORKER_TOKEN_ENV = "CHIPMONK_WORKER_TOKEN"
TTL_GRACE_S = 300
#: RunPod's HTTP proxy in front of a pod's ``<port>/http``.
RUNPOD_PROXY_URL = "https://{pod_id}-{port}.proxy.runpod.net"
#: Proxy answers while the pod is still booting or briefly unwell.
_TRANSIENT_HTTP = frozenset({404, 502, 503, 504})
_SAFE_RUN_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")
_HEARTBEAT_S = 5.0
_STREAM_POLL_S = 0.2

_Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


class WorkerUnreachableError(RuntimeError):
    """The worker stopped answering (pod lost, proxy down) past the retry budget."""


# --------------------------------------------------------------------------
# Pod side
# --------------------------------------------------------------------------


class _BufferedSink(JsonlEventSink):
    """Writes ``events.jsonl`` like any run, and keeps the events in memory for SSE."""

    def __init__(self, path: Path, buffer: list[dict[str, Any]]) -> None:
        super().__init__(path)
        self._buffer = buffer

    def emit(self, event: AgentEvent) -> None:
        """Append to the file and to the in-memory buffer the stream serves."""
        super().emit(event)
        self._buffer.append(event.to_dict())


@dataclass(frozen=True)
class _WorkerRunDir(RunDir):
    """A run folder whose event sink also feeds the SSE buffer."""

    buffer: list[dict[str, Any]] = field(default_factory=list, compare=False)

    def event_sink(self) -> _BufferedSink:
        """A sink appending to ``events.jsonl`` and to :attr:`buffer`."""
        return _BufferedSink(self.events_path, self.buffer)


@dataclass
class _Job:
    """The one job this worker runs."""

    run: _WorkerRunDir
    runner: LocalRunner
    done: asyncio.Event = field(default_factory=asyncio.Event)
    result: dict[str, Any] | None = None
    task: asyncio.Task[None] | None = None


def _auth_middleware(token: str) -> Callable[[web.Request, _Handler], Awaitable[web.StreamResponse]]:
    """Reject any request without the pod's bearer token (constant-time compare)."""

    @web.middleware
    async def _auth(request: web.Request, handler: _Handler) -> web.StreamResponse:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer ") and secrets.compare_digest(header[7:], token):
            return await handler(request)
        return web.json_response({"error": "unauthorized"}, status=401)

    return _auth


def create_app(config: BackendConfig, *, token: str) -> web.Application:
    """The pod-side aiohttp application described in the module docstring."""
    if not token:
        raise ValueError("the worker needs a non-empty bearer token")
    app = web.Application(middlewares=[_auth_middleware(token)])
    state: dict[str, _Job | None] = {"job": None}

    async def health(_request: web.Request) -> web.Response:
        job = state["job"]
        status = "idle" if job is None else ("done" if job.done.is_set() else "running")
        return web.json_response({"status": "ok", "job": status})

    async def submit(request: web.Request) -> web.Response:
        if state["job"] is not None:
            return web.json_response({"error": "this worker already has a job"}, status=409)
        try:
            body = await request.json()
            spec = AgentSpec.from_dict(body["spec"])
            run_id = str(body["run_id"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return web.json_response({"error": f"bad job: {exc}"}, status=400)
        if not _SAFE_RUN_ID.fullmatch(run_id) or run_id in (".", ".."):
            return web.json_response({"error": f"bad run_id {run_id!r}"}, status=400)
        run = _WorkerRunDir(config.resolved_runs_dir() / run_id)
        run.workspace.mkdir(parents=True, exist_ok=True)
        # The launcher's workdir is a path on ITS machine; the pod uses its own.
        spec.workdir = None
        job = _Job(run=run, runner=LocalRunner(config))
        state["job"] = job
        job.task = asyncio.create_task(_drive(job, spec))
        logger.info("worker: job {} for agent {} started", run_id, spec.name)
        return web.json_response({"status": "started"}, status=202)

    async def events(request: web.Request) -> web.StreamResponse:
        job = state["job"]
        if job is None:
            return web.json_response({"error": "no job"}, status=409)
        try:
            index = max(0, int(request.query.get("since", "0")))
        except ValueError:
            index = 0
        response = web.StreamResponse(
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )
        await response.prepare(request)
        last_write = time.monotonic()
        try:
            while True:
                finished = job.done.is_set()  # read BEFORE draining, so nothing is missed
                for event in job.run.buffer[index:]:
                    await response.write(_sse(event, event_id=index))
                    index += 1
                    last_write = time.monotonic()
                if finished:
                    await response.write(b"event: done\ndata: {}\n\n")
                    break
                if time.monotonic() - last_write >= _HEARTBEAT_S:
                    await response.write(b": heartbeat\n\n")
                    last_write = time.monotonic()
                await asyncio.sleep(_STREAM_POLL_S)
        except (ConnectionResetError, ConnectionAbortedError):
            logger.debug("worker: event stream client went away at {}", index)
        return response

    async def result(_request: web.Request) -> web.Response:
        job = state["job"]
        if job is None:
            return web.json_response({"error": "no job"}, status=409)
        if not job.done.is_set() or job.result is None:
            return web.Response(status=204)
        return web.json_response(job.result)

    async def outputs(request: web.Request) -> web.StreamResponse:
        job = state["job"]
        if job is None or not job.done.is_set():
            return web.json_response({"error": "no finished job"}, status=409)
        archive = await asyncio.to_thread(_tar_workspace, job.run.workspace)
        response = web.StreamResponse(headers={"Content-Type": "application/gzip"})
        try:
            await response.prepare(request)
            with archive.open("rb") as handle:
                while chunk := handle.read(1 << 20):
                    await response.write(chunk)
            await response.write_eof()
        finally:
            archive.unlink(missing_ok=True)
        return response

    async def inject(request: web.Request) -> web.Response:
        job = state["job"]
        if job is None or job.done.is_set():
            return web.json_response({"error": "no running job"}, status=409)
        try:
            message = str((await request.json())["message"])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            return web.json_response({"error": f"bad message: {exc}"}, status=400)
        try:
            await job.runner.inject(message)
        except NotImplementedError as exc:
            return web.json_response({"error": str(exc)}, status=501)
        except RuntimeError as exc:
            return web.json_response({"error": str(exc)}, status=409)
        return web.json_response({"status": "queued"})

    async def _on_cleanup(_app: web.Application) -> None:
        job = state["job"]
        if job is not None and job.task is not None and not job.task.done():
            job.task.cancel()

    app.router.add_get("/health", health)
    app.router.add_post("/job", submit)
    app.router.add_get("/events", events)
    app.router.add_get("/result", result)
    app.router.add_get("/outputs", outputs)
    app.router.add_post("/inject", inject)
    app.on_cleanup.append(_on_cleanup)
    return app


async def _drive(job: _Job, spec: AgentSpec) -> None:
    """Run the job; any exception becomes a failed result so the launcher always gets one."""
    try:
        outcome = await job.runner.run(spec, job.run)
    except Exception as exc:
        logger.exception("worker: job for {} raised", spec.name)
        job.run.event_sink().emit(AgentEvent("error", spec.name, {"message": f"{type(exc).__name__}: {exc}"}))
        outcome = AgentResult(agent=spec.name, failed=True, error=f"{type(exc).__name__}: {exc}")
    job.result = outcome.to_dict()
    job.done.set()
    logger.info("worker: job for {} finished (failed={})", spec.name, outcome.failed)


def _sse(event: dict[str, Any], *, event_id: int) -> bytes:
    """One SSE frame carrying one event."""
    return f"id: {event_id}\nevent: agent_event\ndata: {json.dumps(event, ensure_ascii=False)}\n\n".encode()


def _tar_workspace(workspace: Path) -> Path:
    """The workspace as a temporary ``.tar.gz`` (members relative to it); caller deletes it."""
    handle, name = tempfile.mkstemp(suffix=".tar.gz")
    os.close(handle)
    with tarfile.open(name, "w:gz") as archive:
        for path in sorted(workspace.rglob("*")):
            if path.is_file() and not path.is_symlink():
                archive.add(path, arcname=str(path.relative_to(workspace)))
    return Path(name)


def start_ttl_watchdog(ttl_s: float) -> threading.Timer:
    """SIGTERM this process after ``ttl_s`` seconds, so an orphaned pod stops billing."""

    def _expire() -> None:
        logger.error("worker: TTL of {}s reached, terminating", ttl_s)
        os.kill(os.getpid(), signal.SIGTERM)

    timer = threading.Timer(ttl_s, _expire)
    timer.daemon = True
    timer.start()
    return timer


def main(argv: list[str] | None = None) -> None:
    """Pod entrypoint: read the token from the env, start the TTL watchdog, serve."""
    parser = argparse.ArgumentParser(description="Chipmonk worker pod server")
    parser.add_argument("--port", type=int, default=WORKER_PORT)
    parser.add_argument("--host", default="0.0.0.0")  # nosec B104: the pod proxy dials every interface
    parser.add_argument("--ttl-s", type=float, default=None, help="default: pod_timeout_s + 300")
    args = parser.parse_args(argv)
    token = os.environ.get(WORKER_TOKEN_ENV, "")
    if not token:
        raise SystemExit(f"{WORKER_TOKEN_ENV} is not set; refusing to serve without a token")
    config = load_config()
    setup_logging(config.resolved_log_dir(), level=config.log_level)
    ttl_s = args.ttl_s if args.ttl_s is not None else config.compute.runpod.pod_timeout_s + TTL_GRACE_S
    start_ttl_watchdog(ttl_s)
    logger.info("worker: serving on port {} (TTL {}s)", args.port, ttl_s)
    web.run_app(create_app(config, token=token), host=args.host, port=args.port, print=None)


# --------------------------------------------------------------------------
# Launcher side
# --------------------------------------------------------------------------


class WorkerClient:
    """Launcher side: talks to one worker pod through RunPod's HTTP proxy."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str,
        timeout_s: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.timeout_s = timeout_s
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(timeout_s, connect=15.0),
            transport=transport,
            follow_redirects=True,
        )
        #: Retry pacing; tests shrink these.
        self.retry_delay_s = 5.0
        self.max_retries = 8
        self.reconnect_delay_s = 3.0
        self.max_reconnects = 10

    async def aclose(self) -> None:
        """Close the connection pool."""
        await self._http.aclose()

    async def is_healthy(self) -> bool:
        """One ``/health`` probe; any transport error or non-200 is ``False``."""
        try:
            resp = await self._http.get("/health", timeout=15.0)
        except httpx.HTTPError:
            return False  # not serving yet; the caller's deadline bounds this
        return resp.status_code == 200

    async def wait_healthy(self, *, timeout_s: float, interval_s: float = 5.0) -> None:
        """Poll ``/health`` until 200; ``TimeoutError`` after ``timeout_s``."""
        deadline = time.monotonic() + timeout_s
        while not await self.is_healthy():
            if time.monotonic() >= deadline:
                raise TimeoutError(f"worker {self.base_url} not healthy after {timeout_s:.0f}s")
            await asyncio.sleep(interval_s)

    async def submit(self, spec: AgentSpec, *, run_id: str) -> None:
        """``POST /job``, retried through proxy hiccups.

        A 409 after an attempt that may have reached the worker (its answer
        lost) is that attempt's own job, so the submit succeeded.
        """
        body = {"spec": spec.to_dict(), "run_id": run_id}
        may_have_delivered = False
        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = await self._http.post("/job", json=body, timeout=httpx.Timeout(120.0, connect=15.0))
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            except httpx.TransportError as exc:
                may_have_delivered = True
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if resp.status_code == 202:
                    return
                if resp.status_code == 409 and may_have_delivered:
                    logger.warning("worker answered 409 after a lost answer: the job is running")
                    return
                if resp.status_code not in _TRANSIENT_HTTP:
                    raise RuntimeError(f"worker refused the job: HTTP {resp.status_code}: {resp.text[:300]}")
                may_have_delivered = True
                last_error = f"HTTP {resp.status_code}"
            logger.warning(
                "submit to {} failed ({}/{}): {}", self.base_url, attempt, self.max_retries, last_error
            )
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay_s)
        raise WorkerUnreachableError(
            f"could not submit the job after {self.max_retries} attempts: {last_error}"
        )

    async def events(self, *, since: int = 0) -> AsyncIterator[AgentEvent]:
        """``GET /events`` as an async iterator; resumes from ``since`` on reconnect.

        Ends after the worker's ``done`` frame. ``max_reconnects`` counts
        consecutive failures without new data, then raises
        :class:`WorkerUnreachableError`.
        """
        index = since
        failures = 0
        while True:
            try:
                async with self._http.stream(
                    "GET", f"/events?since={index}", timeout=httpx.Timeout(None)
                ) as resp:
                    if resp.status_code != 200:
                        raise _StreamError(f"HTTP {resp.status_code}")
                    async for kind, data in _parse_sse(resp.aiter_lines()):
                        if kind == "done":
                            return
                        if kind == "agent_event":
                            index += 1
                            failures = 0
                            yield AgentEvent.from_dict(json.loads(data))
                raise _StreamError("stream closed before done")
            except (httpx.HTTPError, _StreamError) as exc:
                failures += 1
                if failures > self.max_reconnects:
                    raise WorkerUnreachableError(
                        f"event stream lost after {self.max_reconnects} reconnects: {exc}"
                    ) from exc
                logger.debug(
                    "event stream from {} dropped ({}), reconnect {} at {}",
                    self.base_url,
                    exc,
                    failures,
                    index,
                )
                await asyncio.sleep(self.reconnect_delay_s * failures)

    async def result(self, *, poll_interval_s: float = 2.0) -> AgentResult:
        """``GET /result`` until the job is done (204 while it runs)."""
        failures, error = 0, ""
        while True:
            try:
                resp = await self._http.get("/result", timeout=httpx.Timeout(120.0, connect=15.0))
            except httpx.TransportError as exc:
                failures, error = failures + 1, f"{type(exc).__name__}: {exc}"
            else:
                if resp.status_code == 200:
                    return AgentResult.from_dict(resp.json())
                if resp.status_code == 204:
                    failures = 0
                elif resp.status_code in _TRANSIENT_HTTP:
                    failures, error = failures + 1, f"HTTP {resp.status_code}"
                else:
                    raise RuntimeError(f"worker /result: HTTP {resp.status_code}: {resp.text[:300]}")
            if failures > self.max_reconnects:
                raise WorkerUnreachableError(f"/result unreachable: {error}")
            await asyncio.sleep(poll_interval_s)

    async def download_outputs(self, dest: Path) -> list[str]:
        """Fetch ``/outputs`` and unpack it into ``dest``; the relative paths written."""
        dest.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(suffix=".tar.gz")
        os.close(handle)
        archive = Path(name)
        try:
            async with self._http.stream(
                "GET", "/outputs", timeout=httpx.Timeout(600.0, connect=15.0)
            ) as resp:
                if resp.status_code != 200:
                    raise RuntimeError(f"worker /outputs: HTTP {resp.status_code}")
                with archive.open("wb") as out:
                    async for chunk in resp.aiter_bytes():
                        out.write(chunk)
            return await asyncio.to_thread(_untar, archive, dest)
        finally:
            archive.unlink(missing_ok=True)

    async def inject(self, message: str) -> None:
        """``POST /inject``: a user message into the running agent."""
        resp = await self._http.post("/inject", json={"message": message})
        if resp.status_code != 200:
            raise RuntimeError(f"worker /inject: HTTP {resp.status_code}: {resp.text[:300]}")


class _StreamError(RuntimeError):
    """The event stream ended or answered wrongly; reconnect."""


async def _parse_sse(lines: AsyncIterator[str]) -> AsyncIterator[tuple[str, str]]:
    """``(event, data)`` pairs from SSE lines; comments (heartbeats) are skipped."""
    kind, data = "message", []
    async for line in lines:
        if not line:
            if data:
                yield kind, "\n".join(data)
            kind, data = "message", []
        elif line.startswith("event:"):
            kind = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())


def _untar(archive: Path, dest: Path) -> list[str]:
    """Unpack with the ``data`` filter (no absolute paths, no escapes, no devices)."""
    with tarfile.open(archive, "r:gz") as tar:
        members = [m.name for m in tar.getmembers() if m.isfile()]
        tar.extractall(dest, filter="data")
    return members


if __name__ == "__main__":
    main()


__all__ = [
    "RUNPOD_PROXY_URL",
    "TTL_GRACE_S",
    "WORKER_PORT",
    "WORKER_TOKEN_ENV",
    "WorkerClient",
    "WorkerUnreachableError",
    "create_app",
    "main",
    "start_ttl_watchdog",
]
