"""`chiplab <tool> --json '{...}'` -> one JSON object on stdout. Also: list-tools, describe <tool>, agent-doc.

Arguments can come from --json, --json-file, or stdin. Exit code 0 on status ok, 1 on error.
"""
from __future__ import annotations

import json
import sys


def _tools():
    from chiplab import tools
    from chiplab import tools_hw  # noqa: F401  (registers hardware/verification tools beyond the core set)
    return tools.TOOLS


def agent_doc() -> str:
    T = _tools()
    lines = ["# chipin.space chip lab: tools for the AI scientist", "",
             "Call any tool as `chiplab <tool-name> --json '{...}'` (or `from chiplab.tools import TOOLS`). Every call "
             "returns one JSON object with `status` and is logged. Typical run: define-task -> load-data -> "
             "propose-designs -> train-batch -> compile-verilog -> synthesize -> simulate -> evaluate-clinical "
             "(val) -> ... -> evaluate-clinical (test, budgeted) -> map-to-process / timing-power / package.", ""]
    for name, t in T.items():
        lines.append(f"## {name.replace('_', '-')}")
        lines.append(t["summary"])
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
        print(agent_doc()); return 0
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
    return 0 if res.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
