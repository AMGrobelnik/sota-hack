"""MCP server for the chip lab (official MCP Python SDK): every registered tool, over stdio or streamable HTTP.

    chiplab mcp                         # stdio (an agent on this machine)
    chiplab serve --host 0.0.0.0        # streamable HTTP at /mcp + job workers + /events SSE + /files
HTTP needs a bearer token unless bound to localhost: set CHIPLAB_TOKEN, or one is generated and printed.
Other routes on the same app: GET /events/{run_id}?from_seq=N (SSE stream; ?format=jsonl for replay),
GET /files/{path} (artefacts under CHIPLAB_HOME/designs), GET /health.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import secrets
import subprocess
import sys
import typing
from pathlib import Path

from chiplab import config


def _all_tools() -> dict:
    from chiplab import tools
    import chiplab.tools_hw  # noqa: F401
    import chiplab.tools_jobs  # noqa: F401
    return tools.TOOLS


def _proxy(name: str, t: dict):
    """A function with an explicit signature (tool params + context args) so MCP derives a proper JSON schema."""
    from chiplab.tools import CONTEXT_ARGS
    orig = t["fn"].__wrapped__
    hints = typing.get_type_hints(orig)
    params = []
    for p in inspect.signature(orig).parameters.values():
        params.append(p.replace(annotation=hints.get(p.name, typing.Any), kind=inspect.Parameter.KEYWORD_ONLY))
    have = {p.name for p in params}
    for c in ("run_id", "session_id"):
        if c not in have:
            params.append(inspect.Parameter(c, inspect.Parameter.KEYWORD_ONLY, default=None, annotation=typing.Optional[str]))
    if "round" not in have:
        params.append(inspect.Parameter("round", inspect.Parameter.KEYWORD_ONLY, default=None, annotation=typing.Optional[int]))
    fn = t["fn"]

    def call(**kw):
        kw = {k: v for k, v in kw.items() if not (k in CONTEXT_ARGS and v is None)}
        return fn(**kw)

    call.__signature__ = inspect.Signature(params, return_annotation=dict)
    call.__name__ = name
    call.__annotations__ = {p.name: p.annotation for p in params} | {"return": dict}
    return call


def build_server():
    from mcp.server.mcpserver import MCPServer
    srv = MCPServer(name="chipin-chip-lab", instructions=(
        "chipin.space chip lab: turn a model into a verified, measured, manufacturable chip. Heavy tools: call "
        "submit_job(tool, args) and poll job_status/job_result. Every answer is JSON with `status`. Pass run_id to "
        "stream dashboard events. Read the agent_doc tool for the full workflow."))
    for name, t in _all_tools().items():
        desc = t["summary"] + "\n\nParameters:\n" + "\n".join(f"- {k}: {v}" for k, v in t["params"].items())
        desc += f"\n\nLane: {t.get('lane')}. Cacheable: {t.get('cacheable')}."
        srv.add_tool(_proxy(name, t), name=name, description=desc)

    def agent_doc() -> str:
        """The full tool reference and the typical workflow (AGENT.md)."""
        from chiplab.cli import agent_doc as doc
        return doc()
    srv.add_tool(agent_doc, name="agent_doc", description="The full tool reference and typical workflow (AGENT.md).")
    return srv


def _token() -> str:
    t = os.environ.get("CHIPLAB_TOKEN")
    p = config.home() / "token"
    if not t:
        t = p.read_text().strip() if p.exists() else secrets.token_urlsafe(24)
        p.write_text(t); os.chmod(p, 0o600)
    return t


def http_app(host: str):
    from mcp.server.transport_security import TransportSecuritySettings
    from sse_starlette.sse import EventSourceResponse
    from starlette.responses import FileResponse, JSONResponse, PlainTextResponse
    from starlette.routing import Route

    from chiplab import events

    srv = build_server()
    sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    app = srv.streamable_http_app(stateless_http=True, json_response=True, transport_security=sec, host=host)

    async def ev(request):
        run_id = request.path_params["run_id"]
        start = int(request.query_params.get("from_seq", 0))
        if request.query_params.get("format") == "jsonl":
            return PlainTextResponse("\n".join(json.dumps(e) for e in events.read(run_id, start)) + "\n")

        async def gen():
            seq = start
            while True:
                for e in events.read(run_id, seq):
                    seq = e["seq"] + 1
                    yield {"event": e["type"], "id": str(e["seq"]), "data": json.dumps(e)}
                await asyncio.sleep(0.5)
        return EventSourceResponse(gen())

    async def files(request):
        rel = Path(request.path_params["path"])
        base = (config.HOME / "designs").resolve()
        p = (base / rel).resolve()
        if base not in p.parents or not p.is_file():
            return JSONResponse({"status": "error", "error": "not found"}, status_code=404)
        return FileResponse(p)

    async def health(request):
        from chiplab.jobs import queue
        return JSONResponse({"status": "ok", "tools": len(_all_tools()), "lanes": queue.lane_load()})

    app.router.routes.extend([Route("/events/{run_id}", ev), Route("/files/{path:path}", files), Route("/health", health)])
    if host not in ("127.0.0.1", "localhost"):
        token = _token()
        inner = app

        async def guarded(scope, receive, send):
            if scope["type"] == "http":
                hdr = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
                q = scope.get("query_string", b"").decode()
                if hdr != f"Bearer {token}" and f"token={token}" not in q:
                    resp = JSONResponse({"status": "error", "error": "missing or wrong bearer token"}, status_code=401)
                    return await resp(scope, receive, send)
            return await inner(scope, receive, send)
        return guarded, token
    return app, None


def start_workers() -> list[subprocess.Popen]:
    from chiplab.jobs.queue import LANES
    procs = []
    for lane, n in LANES.items():
        procs.append(subprocess.Popen([sys.executable, "-m", "huey.bin.huey_consumer", f"chiplab.jobs.queue.HUEY_{lane.upper()}",
                                       "-w", str(n), "-k", "thread", "-q"], env={**os.environ, "PYTHONUNBUFFERED": "1"},
                                      stdout=open(config.home("jobs") / f"worker_{lane}.log", "a"), stderr=subprocess.STDOUT))
    return procs


def serve(host: str = "127.0.0.1", port: int = 8765, workers: bool = True) -> None:
    import uvicorn
    procs = start_workers() if workers else []
    app, token = http_app(host)
    print(json.dumps({"mcp": f"http://{host}:{port}/mcp", "events": f"http://{host}:{port}/events/<run_id>",
                      "token": token, "workers": {p.pid: " ".join(p.args[3:4]) for p in procs}}), flush=True)
    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    finally:
        for p in procs:
            p.terminate()


def stdio() -> None:
    build_server().run(transport="stdio")
