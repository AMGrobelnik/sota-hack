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


class SandboxUnavailable(RuntimeError):
    pass


def run_isolated(workdir: Path, cmd: list[str], timeout: int = 300, allow_host: bool = False) -> tuple[int, str, str]:
    """Run cmd with workdir mounted (sources read-only under /src, outputs to /out). Without the container this
    refuses, unless allow_host=True (the caller accepts running unvetted RTL tools on the host)."""
    workdir = workdir.resolve()
    (workdir / "out").mkdir(exist_ok=True)
    if not _docker_ok() and not allow_host:
        raise SandboxUnavailable(f"the sandbox container ({config.LIBRELANE_IMAGE}) is not available: start Docker and "
                                 f"pull the image, or pass allow_host=true to run the checks on this machine without isolation")
    if _docker_ok():
        full = ["docker", "run", "--rm", "--network", "none", "--memory", "2g", "--cpus", "2", "--pids-limit", "256",
                "--read-only", "--tmpfs", "/tmp:rw,size=256m", "-u", "1000:1000",
                "-v", f"{workdir / 'src'}:/src:ro", "-v", f"{workdir / 'out'}:/out:rw", "-w", "/out",
                config.LIBRELANE_IMAGE] + cmd
        mode = "docker (no network, 2 GB, 2 CPUs, 256 pids, read-only source)"
    else:
        # no GNU `timeout` (absent on macOS): subprocess.run's own timeout below enforces the limit
        full = [c.replace("/src/", str(workdir / "src") + "/").replace("/out/", str(workdir / "out") + "/") for c in cmd]
        full[0] = config.find_bin(full[0]) or full[0]
        mode = "local process with timeout (Docker not available)"
    try:
        p = subprocess.run(full, capture_output=True, text=True, timeout=timeout if mode.startswith("local") else timeout + 30)
        return p.returncode, p.stdout + p.stderr, mode
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s", mode


def check_verilog(text: str, top: str, workdir: Path, timeout: int = 300, allow_host: bool = False) -> dict:
    problems = screen(text)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", top or ""):
        problems.append("top must be a plain Verilog identifier")
    if problems:
        return {"accepted": False, "problems": problems}
    if not text.endswith("\n"):
        text += "\n"
    (workdir / "src").mkdir(parents=True, exist_ok=True)
    (workdir / "src" / "design.v").write_text(text)
    try:
        rc, lint_out, mode = run_isolated(workdir, ["verilator", "--lint-only", "-Wall", "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL",
                                                    "-Wno-EOFNEWLINE", "--top-module", top, "/src/design.v"], timeout, allow_host)
    except SandboxUnavailable as e:
        return {"accepted": False, "problems": [str(e)], "sandbox": "unavailable"}
    lint = {"ok": rc == 0, "messages": [l for l in lint_out.splitlines() if l.startswith("%")][:20]}
    if rc != 0 and not any("%Warning" in m for m in lint["messages"]):
        return {"accepted": False, "problems": ["verilator lint failed"], "lint": lint, "sandbox": mode}
    ys = (f"read_verilog /src/design.v; hierarchy -check -top {top}; synth -top {top} -flatten -noabc; "
          f"abc -g AND,NAND,OR,NOR,XOR,XNOR,ANDNOT,ORNOT,MUX -script \"+strash;dc2;map\"; opt_clean -purge; "
          f"write_json /out/net.json; write_verilog -noattr /out/gates.v; tee -q -o /out/stat.json stat -json")
    rc, syn_out, mode = run_isolated(workdir, ["yosys", "-q", "-p", ys], timeout, allow_host)
    if rc != 0 or not (workdir / "out" / "net.json").exists():
        return {"accepted": False, "problems": ["synthesis failed"], "detail": syn_out[-800:], "lint": lint, "sandbox": mode}
    stat = json.loads((workdir / "out" / "stat.json").read_text())
    mod = next(iter(stat.get("modules", {}).values()), {})
    return {"accepted": True, "lint": lint, "sandbox": mode, "netlist_json": str(workdir / "out" / "net.json"),
            "gate_verilog": str(workdir / "out" / "gates.v"), "gates": mod.get("num_cells")}
