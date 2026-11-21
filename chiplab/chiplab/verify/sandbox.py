"""Safety for agent-written raw Verilog: static screening, then lint + synthesis inside a locked-down container.

Screening rejects system tasks other than $signed/$unsigned/$clog2 (no $system, $fopen, $readmem*, $dump*, ...),
any `include, compiler directives that pull in files, and oversized sources. Lint and synthesis then run in the
LibreLane image with no network, memory/CPU/process limits, a read-only source mount and a hard timeout. Without
Docker they run locally under `timeout` with the same screening, and the result says so.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from chiplab import config

MAX_BYTES = 2_000_000
ALLOWED_SYS = {"$signed", "$unsigned", "$clog2"}
BAD_DIRECTIVES = re.compile(r"`\s*(include|line|resetall|pragma|begin_keywords)\b")


def screen(text: str) -> list[str]:
    problems = []
    if len(text.encode()) > MAX_BYTES:
        problems.append(f"source larger than {MAX_BYTES} bytes")
    stripped = re.sub(r"//.*?$|/\*.*?\*/", "", text, flags=re.S | re.M)
    for m in set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", stripped)):
        if m not in ALLOWED_SYS:
            problems.append(f"system task {m} is not allowed")
    if BAD_DIRECTIVES.search(stripped):
        problems.append("`include and file-related directives are not allowed")
    return sorted(problems)


def _docker_ok() -> bool:
    if not shutil.which("docker"):
        return False
    r = subprocess.run(["docker", "image", "inspect", config.LIBRELANE_IMAGE], capture_output=True)
    return r.returncode == 0


def run_isolated(workdir: Path, cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
    """Run cmd with workdir mounted (sources read-only under /src, outputs to /out)."""
    workdir = workdir.resolve()
    (workdir / "out").mkdir(exist_ok=True)
    if _docker_ok():
        full = ["docker", "run", "--rm", "--network", "none", "--memory", "2g", "--cpus", "2", "--pids-limit", "256",
                "--read-only", "--tmpfs", "/tmp:rw,size=256m", "-u", "1000:1000",
                "-v", f"{workdir / 'src'}:/src:ro", "-v", f"{workdir / 'out'}:/out:rw", "-w", "/out",
                config.LIBRELANE_IMAGE] + cmd
        mode = "docker (no network, 2 GB, 2 CPUs, 256 pids, read-only source)"
    else:
        full = ["timeout", str(timeout)] + [c.replace("/src/", str(workdir / "src") + "/").replace("/out/", str(workdir / "out") + "/") for c in cmd]
        full[2] = config.find_bin(full[2]) or full[2]
        mode = "local process with timeout (Docker not available)"
    try:
        p = subprocess.run(full, capture_output=True, text=True, timeout=timeout + 30)
        return p.returncode, p.stdout + p.stderr, mode
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s", mode


def check_verilog(text: str, top: str, workdir: Path, timeout: int = 300) -> dict:
    problems = screen(text)
    if problems:
        return {"accepted": False, "problems": problems}
    (workdir / "src").mkdir(parents=True, exist_ok=True)
    (workdir / "src" / "design.v").write_text(text)
    rc, lint_out, mode = run_isolated(workdir, ["verilator", "--lint-only", "-Wall", "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL",
                                                "--top-module", top, "/src/design.v"], timeout)
    lint = {"ok": rc == 0, "messages": [l for l in lint_out.splitlines() if l.startswith("%")][:20]}
    if rc != 0 and not any("%Warning" in m for m in lint["messages"]):
        return {"accepted": False, "problems": ["verilator lint failed"], "lint": lint, "sandbox": mode}
    ys = (f"read_verilog /src/design.v; hierarchy -check -top {top}; synth -top {top} -flatten -noabc; "
          f"abc -g AND,NAND,OR,NOR,XOR,XNOR,ANDNOT,ORNOT,MUX -script \"+strash;dc2;map\"; opt_clean -purge; "
          f"write_json /out/net.json; write_verilog -noattr /out/gates.v; tee -q -o /out/stat.json stat -json")
    rc, syn_out, mode = run_isolated(workdir, ["yosys", "-q", "-p", ys], timeout)
    if rc != 0 or not (workdir / "out" / "net.json").exists():
        return {"accepted": False, "problems": ["synthesis failed"], "detail": syn_out[-800:], "lint": lint, "sandbox": mode}
    stat = json.loads((workdir / "out" / "stat.json").read_text())
    mod = next(iter(stat.get("modules", {}).values()), {})
    return {"accepted": True, "lint": lint, "sandbox": mode, "netlist_json": str(workdir / "out" / "net.json"),
            "gate_verilog": str(workdir / "out" / "gates.v"), "gates": mod.get("num_cells")}
