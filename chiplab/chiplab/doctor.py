"""`chiplab doctor`: check every tool, library, PDK, Docker and the compute device; say what is missing and how
to fix it. Output is one JSON object; `ok` is true when everything the core flow needs is present."""
from __future__ import annotations

import importlib
import os
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
        add("docker", up, {"server": info.stdout.strip() or info.stderr.strip()[:160], "DOCKER_HOST": os.environ.get("DOCKER_HOST")},
            "start Docker (Docker Desktop, colima start, or OrbStack); with colima/OrbStack you can also set DOCKER_HOST=unix://<socket>",
            required=False)
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
    if platform.system() == "Darwin":
        libs = [Path(d) / "libcairo.2.dylib" for d in ("/opt/homebrew/lib", "/usr/local/lib")]
        found = next((str(l) for l in libs if l.exists()), None)
        add("macos:cairo", bool(found), found or "libcairo not found", "brew install cairo   (Tiny Tapeout PNG export)", required=False)
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


# The ChipIn backend's agent environment allowlist (backend/src/chipin_backend/agents/env.py on origin/amg/backend):
# only these names reach an agent process, so the lab must work from ~/.config/chiplab/config.json alone.
AGENT_ENV_ALLOWED = {"HOME", "PATH", "PWD", "SHELL", "TERM", "TMPDIR", "TZ", "USER", "LOGNAME", "LANG", "LANGUAGE", "COLUMNS",
                     "LINES", "NO_COLOR", "FORCE_COLOR", "VIRTUAL_ENV", "PYTHONPATH", "PYTHONUNBUFFERED", "PYTHONIOENCODING",
                     "NODE_PATH", "CUDA_VISIBLE_DEVICES", "HF_HOME", "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_ENABLE_TELEMETRY",
                     "DISABLE_AUTOUPDATER", "IS_SANDBOX", "OPENROUTER_API_KEY", "HF_TOKEN"}


#: The lab's own variables the backend passes to agents unchanged when set (chipin_backend.chiplab.CHIPLAB_PASSED_NAMES).
AGENT_ENV_CHIPLAB_PASSED = ("CHIPLAB_CONFIG", "CHIPLAB_USER_DIR")
#: Folder holding the chiplab command; the backend puts it first on the agent's PATH (chipin_backend.chiplab).
CHIPLAB_BIN_ENV = "CHIPIN_CHIPLAB_BIN"


def agent_env(base: dict | None = None) -> dict:
    """The environment ChipIn gives an agent: its allowlist, plus the lab's passed variables and bin folder."""
    src = dict(os.environ if base is None else base)
    env = {k: v for k, v in src.items() if k in AGENT_ENV_ALLOWED or k.startswith("LC_")}
    env.update({k: src[k] for k in AGENT_ENV_CHIPLAB_PASSED if src.get(k)})
    bin_dir = (src.get(CHIPLAB_BIN_ENV) or "").strip()
    if bin_dir:
        env["PATH"] = os.pathsep.join(x for x in (str(Path(bin_dir).expanduser()), env.get("PATH", "")) if x)
    env.update({"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "DISABLE_AUTOUPDATER": "1"})
    return env


def run_agent_env() -> dict:
    """Re-run the doctor in a child process that only sees the agent allowlist (like env -i + the allowed names)."""
    import json as _json
    import subprocess
    import sys
    env = agent_env()
    launcher = shutil.which("chiplab", path=env.get("PATH"))
    p = subprocess.run([sys.executable, "-m", "chiplab.cli", "doctor"], env=env, capture_output=True, text=True, timeout=600)
    try:
        r = _json.loads(p.stdout)
    except ValueError:
        r = {"status": "error", "ok": False, "checks": [], "error": (p.stderr or p.stdout)[-600:]}
    kept = [k for k in AGENT_ENV_CHIPLAB_PASSED if k in env]
    r["agent_env"] = {"names_passed": sorted(env), "chiplab_on_path": launcher, "chiplab_vars_kept": kept,
                      "chiplab_bin": os.environ.get(CHIPLAB_BIN_ENV) or None,
                      "note": ("Same rule as ChipIn's backend: CHIPLAB_CONFIG and CHIPLAB_USER_DIR are kept when set "
                               f"(kept here: {', '.join(kept) or 'none set'}) and CHIPIN_CHIPLAB_BIN goes first on PATH; "
                               "every other CHIPLAB_* variable, DOCKER_HOST and PDK_ROOT is stripped, so those settings "
                               "must come from the config file")}
    if not launcher:
        r["ok"] = False
        r.setdefault("missing_required", []).append("launcher:chiplab")
        r.setdefault("checks", []).append({"check": "launcher:chiplab", "ok": False, "required": True,
                                           "detail": f"chiplab not found on the PATH an agent gets: {env.get('PATH')}",
                                           "fix": "put ~/.local/bin on PATH for whoever starts the backend (zsh: add "
                                                  "'export PATH=\"$HOME/.local/bin:$PATH\"' to ~/.zprofile; bash: ~/.bashrc or "
                                                  "~/.profile), or have the agent call ~/.local/bin/chiplab by its full path"})
    return r
