"""`chiplab <tool> --json '{...}'` -> one JSON object on stdout. Also: list-tools, describe <tool>, agent-doc.

Arguments can come from --json, --json-file, or stdin. Exit code 0 on status ok, 1 on error.
"""
from __future__ import annotations

import json
import sys


def _tools():
    from chiplab import tools
    from chiplab import tools_hw  # noqa: F401  (registers hardware/verification tools beyond the core set)
    from chiplab import tools_jobs  # noqa: F401  (async jobs, batches, estimates)
    return tools.TOOLS


def agent_doc() -> str:
    T = _tools()
    lines = ["# chipin.space chip lab: tools for the AI scientist", "",
             "Call any tool as `chiplab <tool-name> --json '{...}'` (or `from chiplab.tools import TOOLS`). Every call "
             "returns one JSON object with `status` and is logged. Over MCP the same tools exist with the same "
             "names (`chiplab mcp` for stdio, `chiplab serve` for streamable HTTP at /mcp).", "",
             "Typical run (model -> chip): ingest-model or compile-ir -> estimate-batch (rank, labelled estimates) -> "
             "synthesize -> simulate (bit-exact, level 1) -> prove-equivalence (level 2) -> map-to-process (area, GE) -> "
             "timing-power / layout -> bitstream / tt-package -> chip-report. Heavy steps: submit-job / submit-batch, "
             "then job-status / job-result. Every tool accepts run_id, session_id and round for dashboard events, and "
             "force=true to bypass the cache.", ""]
    for name, t in T.items():
        lines.append(f"## {name.replace('_', '-')}")
        lines.append(t["summary"] + f"  _(lane: {t.get('lane')}{', cached' if t.get('cacheable') else ''})_")
        for p, d in t["params"].items():
            lines.append(f"- `{p}`: {d}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip()); print("\ntools:", ", ".join(n.replace("_", "-") for n in _tools())); return 0
    cmd = argv.pop(0).replace("-", "_")
    if cmd == "list_tools":
        print(json.dumps({n.replace("_", "-"): t["summary"] for n, t in _tools().items()}, indent=1)); return 0
    if cmd == "describe":
        t = _tools()[argv[0].replace("-", "_")]
        print(json.dumps({"summary": t["summary"], "params": t["params"]}, indent=1)); return 0
    if cmd == "agent_doc":
        from chiplab import docs
        if "--write" in argv:
            print(json.dumps({"written": docs.write()})); return 0
        print(docs.agent_md()); return 0
    if cmd == "doctor":
        from chiplab.doctor import run, run_agent_env
        r = run_agent_env() if "--agent-env" in argv else run()
        print(json.dumps(r, indent=1, default=str)); return 0 if r["ok"] else 1
    if cmd == "mcp":
        from chiplab.mcp_server import stdio
        stdio(); return 0
    if cmd == "serve":
        from chiplab.mcp_server import serve
        host = argv[argv.index("--host") + 1] if "--host" in argv else "127.0.0.1"
        port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
        serve(host, port, workers="--no-workers" not in argv); return 0
    if cmd == "workers":
        from chiplab.mcp_server import start_workers
        procs = start_workers(); print(json.dumps({"workers": [p.pid for p in procs]}))
        for p in procs:
            p.wait()
        return 0
    T = _tools()
    if cmd not in T:
        print(json.dumps({"status": "error", "error": f"unknown tool {cmd}; try `chiplab list-tools`"})); return 1
    args = {}
    if "--json" in argv:
        args = json.loads(argv[argv.index("--json") + 1])
    elif "--json-file" in argv:
        args = json.loads(open(argv[argv.index("--json-file") + 1]).read())
    elif not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        args = json.loads(data) if data else {}
    res = T[cmd]["fn"](**args)
    print(json.dumps(res, indent=1, default=str))
    from chiplab.tools import STATUS_RC
    return STATUS_RC.get(res.get("status"), 1)  # 0 ok, 1 error, 2 a check failed, 3 timeout


if __name__ == "__main__":
    sys.exit(main())
