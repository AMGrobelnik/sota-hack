"""`chiplab doctor`: check every tool, library, PDK, Docker and the compute device; say what is missing and how
to fix it. Output is one JSON object; `ok` is true when everything the core flow needs is present."""
from __future__ import annotations

import importlib
import platform
import shutil
import subprocess
from pathlib import Path

from chiplab import config

INSTALL = "scripts/install.sh"
# (binary, needed for, required for the core flow?)
BINARIES = [("yosys", "synthesis, LUT counts, PDK mapping, formal", True), ("yosys-abc", "logic optimisation, equivalence proofs", True),
            ("iverilog", "RTL simulation (level 3)", True), ("vvp", "RTL simulation (level 3)", True),
            ("verilator", "lint", True), ("nextpnr-ice40", "iCE40 place and route", False), ("icepack", "iCE40 bitstream", False),
            ("icetime", "iCE40 timing", False), ("eqy", "sequential equivalence", False), ("sby", "formal back end for eqy", False)]
PY = [("numpy", True), ("torch", True), ("huey", True), ("diskcache", True), ("jinja2", True), ("yaml", True),
      ("xgboost", False), ("cocotb", False), ("torchlogix", False), ("alkaid", False), ("vcd", False), ("mcp", False)]


def _ver(binary: str) -> str:
    for flag in ("-V", "--version", "-v"):
        try:
            p = subprocess.run([binary, flag], capture_output=True, text=True, timeout=20)
            out = (p.stdout or p.stderr).strip().splitlines()
            if out:
                return out[0][:80]
        except Exception:
            continue
    return "?"


def run() -> dict:
    checks = []

    def add(name, ok, detail, fix=None, required=True):
        checks.append({"check": name, "ok": bool(ok), "required": required, "detail": detail, **({"fix": fix} if not ok and fix else {})})

    add("platform", True, f"{platform.system()} {platform.machine()}, python {platform.python_version()}", required=False)
    add("config", True, config.summary(), required=False)
    for mod, req in PY:
        try:
            m = importlib.import_module(mod)
            add(f"python:{mod}", True, getattr(m, "__version__", "ok"), required=req)
        except Exception as e:
            extra = {"cocotb": "sim", "torchlogix": "ingest", "alkaid": "ingest", "mcp": "mcp"}.get(mod)
            fix = f"uv sync --extra {extra}" if extra else "uv sync"
            if mod == "xgboost" and platform.system() == "Darwin":
                fix = "brew install libomp   (XGBoost needs the OpenMP runtime on macOS)"
            add(f"python:{mod}", False, str(e)[:160], fix, required=req)
    from chiplab.device import describe
    dev = describe()
    add("compute", True, dev, required=False)
    L = config.lanes()
    add("job_lanes", True, {**L, "threads_per_layout": config.threads_per_docker_job(),
                            "override": "CHIPLAB_CPU_WORKERS / CHIPLAB_GPU_WORKERS / CHIPLAB_DOCKER_WORKERS or config 'lanes'"}, required=False)
    for b, why, req in BINARIES:
        p = config.find_bin(b)
        add(f"tool:{b}", p is not None, {"path": p, "version": _ver(p) if p else None, "for": why},
            f"{INSTALL} (installs OSS CAD Suite) or set CHIPLAB_OSS", required=req)
    dk = shutil.which("docker")
    if dk:
        info = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=30)
        up = info.returncode == 0
        add("docker", up, info.stdout.strip() or info.stderr.strip()[:160], "start Docker Desktop / the docker daemon", required=False)
        if up:
            img = subprocess.run(["docker", "image", "inspect", config.LIBRELANE_IMAGE, "--format", "{{.Architecture}}"],
                                 capture_output=True, text=True, timeout=30)
            add("docker:librelane", img.returncode == 0, {"image": config.LIBRELANE_IMAGE, "arch": img.stdout.strip()},
                f"docker pull {config.LIBRELANE_IMAGE}", required=False)
    else:
        add("docker", False, "docker not found", "install Docker (needed for LibreLane layout, timing/power, Tiny Tapeout harden)", required=False)
    from chiplab.hw.pdk import PDKS, liberty
    for pdk in PDKS:
        try:
            add(f"pdk:{pdk}", True, str(liberty(pdk)), required=(pdk == "sky130"))
        except Exception as e:
            add(f"pdk:{pdk}", False, str(e)[:160], f"{INSTALL} (fetches PDKs with ciel into PDK_ROOT)", required=(pdk == "sky130"))
    tt = Path(config.TT_TOOLS) / "tt_tool.py"
    add("tinytapeout:tools", tt.exists(), str(tt), f"{INSTALL} (clones tt-support-tools)", required=False)
    try:
        config.home(".doctor").rmdir()
        add("workspace", True, str(config.HOME), required=True)
    except Exception as e:
        add("workspace", False, str(e), "set CHIPLAB_HOME to a writable folder", required=True)
    missing_req = [c["check"] for c in checks if c["required"] and not c["ok"]]
    missing_opt = [c["check"] for c in checks if not c["required"] and not c["ok"]]
    return {"status": "ok", "ok": not missing_req, "missing_required": missing_req, "missing_optional": missing_opt,
            "checks": checks}
