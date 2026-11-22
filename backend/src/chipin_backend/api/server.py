"""The local HTTP API the ChipIn dashboards talk to (contract version 1).

127.0.0.1 only. Every ``/api`` request carries the session token in the
``X-ChipIn-Token`` header (the event stream may pass it as ``?token=``, as
``EventSource`` cannot set headers); ``/api/health`` needs none. CORS is
granted to the origins in ``api.yaml``'s ``allowed_origins`` (by default
https://chipin.space and http://127.0.0.1, http://localhost and http://[::1]
on any port), nothing else; a request from any other origin is refused.

Routes::

    GET  /api/health
    POST /api/runs                   -> 201 {"id", "status": "running"}
    GET  /api/runs                   -> {"runs": [...]} newest first
    GET  /api/runs/{id}
    GET  /api/runs/{id}/events?token=...&from=<seq>   (text/event-stream)
    GET  /api/runs/{id}/evidence     -> the run's evidence (409 while it runs)
    GET  /api/runs/{id}/designs      -> {"designs": [...], "chosen"} latest record per design
    POST /api/runs/{id}/messages     -> 202 {"accepted", "id", "delivery"} (see api/steer.py)
    POST /api/runs/{id}/stop         -> 202
    GET  /api/runs/{id}/files        -> {"files": [{"path", "size"}]} the agent's working folder
    GET  /api/runs/{id}/file?path=workspace/report.md   -> the file as UTF-8 text
    POST /api/transcribe?lang=en     -> {"text", "model", "audio_seconds", "latency_ms"}

A preflight from a public page to this loopback server (Chrome's Private
Network Access) is answered with ``Access-Control-Allow-Private-Network``.
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aiohttp import web
from loguru import logger

from chipin_backend.api.config import ApiConfig
from chipin_backend.api.designs import designs_view
from chipin_backend.api.events import public_text
from chipin_backend.api.manager import ApiAgent, ApiRunner, RequestError, RunManager
from chipin_backend.api.transcribe import CONTEXT_HEADER, add_transcribe_route, transcribe_ready
from chipin_backend.config import BackendConfig
from chipin_backend.evidence import build_evidence
from chipin_backend.llm.providers import provider_status

API_VERSION = 1
HOST = "127.0.0.1"
TOKEN_HEADER = "X-ChipIn-Token"
ALLOWED_ORIGIN_RE = re.compile(r"^(https://chipin\.space|http://(127\.0\.0\.1|localhost)(:\d{1,5})?)$")
ALLOW_HEADERS = f"Content-Type, {TOKEN_HEADER}, {CONTEXT_HEADER}"
ALLOW_METHODS = "GET, POST, OPTIONS"

MANAGER = web.AppKey("manager", RunManager)
TOKEN = web.AppKey("token", str)
SETTINGS = web.AppKey("settings", ApiConfig)
CLOSING = web.AppKey("closing", asyncio.Event)
FRONTEND = web.AppKey("frontend", Path)

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def origin_allowed(origin: str | None, allowed: list[str] | None = None) -> bool:
    """Whether ``origin`` may call the API from a browser.

    ``allowed`` is ``api.yaml``'s ``allowed_origins`` (an entry ending in ``:*``
    allows that origin on any port); ``None`` keeps the built-in rule.
    """
    if not origin:
        return False
    if allowed is None:
        return ALLOWED_ORIGIN_RE.match(origin) is not None
    for entry in allowed:
        base = entry.removesuffix(":*")
        if origin in (entry, base):
            return True
        port = origin.removeprefix(f"{base}:")
        if entry.endswith(":*") and port != origin and port.isdigit() and len(port) <= 5:
            return True
    return False


def _json(data: Any, status: int = 200) -> web.Response:
    return web.json_response(data, status=status, dumps=lambda d: json.dumps(d, ensure_ascii=False))


def _error(message: str, status: int) -> web.Response:
    return _json({"error": public_text(message)}, status=status)


@web.middleware
async def guard(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Origin check, CORS preflight and the token check for ``/api``."""
    if not request.path.startswith("/api/"):
        return await handler(request)
    origin = request.headers.get("Origin")
    if origin is not None and not origin_allowed(origin, request.app[SETTINGS].allowed_origins):
        return _error("origin not allowed", 403)
    if request.method == "OPTIONS":
        return web.Response(status=204)
    if request.path != "/api/health":
        token = request.headers.get(TOKEN_HEADER)
        if token is None and request.path.endswith("/events"):
            token = request.query.get("token")
        if token is None or not secrets.compare_digest(token, request.app[TOKEN]):
            return _error("missing or wrong session token", 401)
    try:
        return await handler(request)
    except RequestError as exc:
        return _error(str(exc), exc.status)


async def _cors_headers(request: web.Request, response: web.StreamResponse) -> None:
    """Grant CORS to an allowed origin, on every response including streams."""
    origin = request.headers.get("Origin")
    if not request.path.startswith("/api/") or not origin_allowed(
        origin, request.app[SETTINGS].allowed_origins
    ):
        return
    response.headers["Access-Control-Allow-Origin"] = origin or ""
    response.headers["Vary"] = "Origin"
    if request.method == "OPTIONS":
        response.headers["Access-Control-Allow-Methods"] = ALLOW_METHODS
        response.headers["Access-Control-Allow-Headers"] = ALLOW_HEADERS
        response.headers["Access-Control-Max-Age"] = "600"
        if request.headers.get("Access-Control-Request-Private-Network") == "true":
            response.headers["Access-Control-Allow-Private-Network"] = "true"


async def health(request: web.Request) -> web.Response:
    """``{"ok": true, "version": 1, "defaults": {...}}``."""
    manager = request.app[MANAGER]
    return _json(
        {
            "ok": True,
            "version": API_VERSION,
            "defaults": {"agent": manager.agent, "runner": manager.runner},
            "transcribe": transcribe_ready(request.app),
            "providers": provider_status(manager.config.providers),
        }
    )


async def _body(request: web.Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise RequestError("the body must be JSON") from None
    if not isinstance(body, dict):
        raise RequestError("the body must be a JSON object")
    return body


async def create_run(request: web.Request) -> web.Response:
    """Start a run."""
    item = request.app[MANAGER].start(await _body(request))
    return _json({"id": item.id, "status": "running"}, status=201)


async def list_runs(request: web.Request) -> web.Response:
    """Every run, newest first."""
    return _json({"runs": request.app[MANAGER].listing()})


async def get_run(request: web.Request) -> web.Response:
    """One run with its summary and cost."""
    return _json(request.app[MANAGER].get(request.match_info["run_id"]).detail_view())


async def get_evidence(request: web.Request) -> web.Response:
    """Number check, weight bytes per decision and stage timings of a finished run, computed now."""
    item = request.app[MANAGER].get(request.match_info["run_id"])
    if item.record.get("status") == "running":
        raise RequestError("the run is still in progress", status=409)
    try:
        evidence = await asyncio.to_thread(build_evidence, item.run.path, write=False)
    except Exception as exc:  # a broken run folder must give a clean answer, not an unhandled 500
        logger.exception("run {}: evidence not computed", item.id)
        return _error(f"the evidence could not be computed ({type(exc).__name__})", 500)
    return _json(evidence)


async def get_designs(request: web.Request) -> web.Response:
    """The latest record of every candidate design the agent scored, and the chosen one."""
    item = request.app[MANAGER].get(request.match_info["run_id"])
    return _json(designs_view(item.run.path, item.log))


async def post_message(request: web.Request) -> web.Response:
    """A message from the user to the running agent."""
    body = await _body(request)
    answer = await request.app[MANAGER].message(request.match_info["run_id"], body.get("text"))  # type: ignore[arg-type]
    return _json(answer, status=202)


async def stop_run(request: web.Request) -> web.Response:
    """Stop a running agent (a finished run stays as it is)."""
    item = await request.app[MANAGER].stop(request.match_info["run_id"])
    return _json({"id": item.id, "status": item.record["status"]}, status=202)


async def list_files(request: web.Request) -> web.Response:
    """Every file in the run's working folder, as run-folder paths (like artifact paths)."""
    item = request.app[MANAGER].get(request.match_info["run_id"])
    return _json(
        {"files": workspace_files(item.run.path, item.run.workspace, request.app[SETTINGS].max_files)}
    )


async def read_file(request: web.Request) -> web.Response:
    """One file of the run's working folder as UTF-8 text, cut at ``file_max_bytes``."""
    item = request.app[MANAGER].get(request.match_info["run_id"])
    target = workspace_file(item.run.path, item.run.workspace, request.query.get("path", ""))
    limit = request.app[SETTINGS].file_max_bytes
    with target.open("rb") as handle:
        data = handle.read(limit + 1)
    headers = {"Cache-Control": "no-store"}
    if len(data) > limit:
        data, headers["X-ChipIn-Truncated"] = data[:limit], "true"
    return web.Response(
        text=data.decode("utf-8", errors="replace"), content_type="text/plain", headers=headers
    )


def _is_helper(rel: Path) -> bool:
    """The ``progress`` / ``subagent`` helpers, in the workspace or a subagent's ``agents/<id>/``."""
    parts = rel.parts
    if len(parts) == 1:
        return parts[0] in ("progress", "subagent")
    return len(parts) == 3 and parts[0] == "agents" and parts[2] == "progress"


def workspace_files(run_path: Path, workspace: Path, limit: int) -> list[dict[str, Any]]:
    """Files under ``workspace`` (no hidden ones, no helpers), first ``limit`` by path."""
    if not workspace.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(workspace.rglob("*")):
        rel = path.relative_to(workspace)
        if any(part.startswith(".") for part in rel.parts) or _is_helper(rel) or not path.is_file():
            continue
        out.append({"path": str(path.relative_to(run_path)), "size": path.stat().st_size})
        if len(out) >= limit:
            break
    return out


def workspace_file(run_path: Path, workspace: Path, rel: str) -> Path:
    """The file ``rel`` (a run-folder path) if it is inside ``workspace``; else ``RequestError``."""
    if not rel or "\x00" in rel:
        raise RequestError("path is required")
    target = (run_path / rel).resolve()
    root = workspace.resolve()
    if not target.is_relative_to(root):
        raise RequestError("path must be inside the run's workspace folder")
    inside = target.relative_to(root)
    # The same files as the listing: helpers and hidden files are not served.
    hidden = any(part.startswith(".") for part in inside.parts) or _is_helper(inside)
    if hidden or not target.is_file():
        raise RequestError(f"no file {rel!r}", status=404)
    return target


def _start_seq(request: web.Request) -> int:
    """``Last-Event-ID`` + 1 on a reconnect, else ``from`` (default 1)."""
    last = request.headers.get("Last-Event-ID", "")
    if last.isdigit():
        return int(last) + 1
    raw = request.query.get("from", "1")
    if not raw.isdigit():
        raise RequestError("from must be a whole number")
    return max(int(raw), 1)


async def stream_events(request: web.Request) -> web.StreamResponse:
    """Replay events from ``from``, then live ones; ends after ``run.finished``."""
    item = request.app[MANAGER].get(request.match_info["run_id"])
    seq = _start_seq(request)
    keepalive = request.app[SETTINGS].keepalive_s
    closing = request.app[CLOSING]
    response = web.StreamResponse(
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
    await response.prepare(request)
    try:
        while not closing.is_set():
            changed = item.log.changed
            for event in item.log.since(seq):
                payload = json.dumps(event, ensure_ascii=False)
                await response.write(f"id: {event['seq']}\ndata: {payload}\n\n".encode())
                seq = event["seq"] + 1
            if item.log.finished and seq > item.log.last_seq:
                break
            try:
                await asyncio.wait_for(changed.wait(), timeout=keepalive)
            except TimeoutError:
                await response.write(b": keep-alive\n\n")
    except (ConnectionResetError, ConnectionError):
        logger.debug("event stream for {} closed by the client", item.id)
    return response


async def index(request: web.Request) -> web.StreamResponse:
    """``index.html`` of the static frontend folder."""
    page = request.app[FRONTEND] / "index.html"
    if not page.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(page)


def create_app(
    config: BackendConfig,
    api: ApiConfig,
    *,
    token: str,
    agent: ApiAgent = "claude",
    runner: ApiRunner = "local",
    frontend: Path | None = None,
) -> web.Application:
    """The aiohttp application; ``token`` is the session token."""
    app = web.Application(middlewares=[guard])
    app[MANAGER] = RunManager(config, api, agent=agent, runner=runner)
    app[TOKEN] = token
    app[SETTINGS] = api
    app[CLOSING] = asyncio.Event()
    app.on_response_prepare.append(_cors_headers)
    app.router.add_get("/api/health", health)
    app.router.add_post("/api/runs", create_run)
    app.router.add_get("/api/runs", list_runs)
    app.router.add_get("/api/runs/{run_id}", get_run)
    app.router.add_get("/api/runs/{run_id}/events", stream_events)
    app.router.add_get("/api/runs/{run_id}/evidence", get_evidence)
    app.router.add_get("/api/runs/{run_id}/designs", get_designs)
    app.router.add_post("/api/runs/{run_id}/messages", post_message)
    app.router.add_post("/api/runs/{run_id}/stop", stop_run)
    app.router.add_get("/api/runs/{run_id}/files", list_files)
    app.router.add_get("/api/runs/{run_id}/file", read_file)
    add_transcribe_route(app, api.transcribe)
    if frontend is not None:
        app[FRONTEND] = frontend.resolve()
        app.router.add_get("/", index)
        app.router.add_static("/", frontend.resolve(), show_index=False, follow_symlinks=False)

    async def on_startup(app: web.Application) -> None:
        app[MANAGER].load()

    async def on_shutdown(app: web.Application) -> None:
        app[CLOSING].set()
        await app[MANAGER].shutdown()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app


async def serve(app: web.Application, port: int) -> web.AppRunner:
    """Bind ``app`` to 127.0.0.1:``port`` (0 = any free port) and start it."""
    runner = web.AppRunner(app, shutdown_timeout=5)
    await runner.setup()
    site = web.TCPSite(runner, HOST, port)
    await site.start()
    return runner


def new_token() -> str:
    """A fresh session token."""
    return secrets.token_urlsafe(24)


__all__ = [
    "ALLOWED_ORIGIN_RE",
    "API_VERSION",
    "HOST",
    "TOKEN_HEADER",
    "create_app",
    "new_token",
    "origin_allowed",
    "serve",
]
