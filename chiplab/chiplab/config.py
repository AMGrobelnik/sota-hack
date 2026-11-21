"""Where things are. Resolution order for every setting: environment variable, then the config file
(CHIPLAB_CONFIG or ~/.config/chiplab/config.json, written by scripts/install.sh), then a default. Tools are
also found on PATH. Nothing is tied to one machine: run `chiplab doctor` to see what resolved and what is missing.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent          # chiplab/chiplab
PROJECT_DIR = PKG_DIR.parent                        # chiplab/
USER_DIR = Path(os.environ.get("CHIPLAB_USER_DIR", Path.home() / ".chiplab"))
CONFIG_FILE = Path(os.environ.get("CHIPLAB_CONFIG", Path.home() / ".config" / "chiplab" / "config.json"))


def _file() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}
    except Exception:
        return {}


_CFG = _file()


def setting(env: str, key: str, default):
    v = os.environ.get(env) or _CFG.get(key)
    return Path(v).expanduser() if isinstance(default, Path) and v else (v or default)


def _default_home() -> Path:
    p = PROJECT_DIR / "runs"
    try:
        p.mkdir(parents=True, exist_ok=True)
        return p
    except OSError:
        return USER_DIR / "runs"


HOME = setting("CHIPLAB_HOME", "home", None) or _default_home()
HOME = Path(HOME)
DATA = setting("CHIPLAB_DATA", "data", USER_DIR / "data")
OSS = setting("CHIPLAB_OSS", "oss", USER_DIR / "oss-cad-suite")
PDK_ROOT = setting("PDK_ROOT", "pdk_root", USER_DIR / "pdk")
TT_TOOLS = setting("CHIPLAB_TT_TOOLS", "tt_tools", USER_DIR / "tt")
TT_PYTHON = setting("CHIPLAB_TT_PYTHON", "tt_python", "")          # python with tt-support-tools requirements
LIBRELANE_IMAGE = os.environ.get("CHIPLAB_LIBRELANE_IMAGE") or _CFG.get("librelane_image") or "ghcr.io/librelane/librelane:3.0.14"


DOCKER_SOCKETS = ["~/.colima/default/docker.sock", "~/.orbstack/run/docker.sock", "~/.docker/run/docker.sock",
                  "~/.rd/docker.sock", "/var/run/docker.sock"]


def ensure_docker_host() -> str | None:
    """Make Docker reachable for every subprocess: keep DOCKER_HOST if set; otherwise, if the default socket is
    missing, use the docker CLI's current context, then known sockets (colima, OrbStack, Docker Desktop, Rancher)."""
    if os.environ.get("DOCKER_HOST"):
        return os.environ["DOCKER_HOST"]
    cfg_host = _CFG.get("docker_host") or ""   # written by install.sh (agent environments strip DOCKER_HOST)
    if cfg_host.startswith("unix://") and Path(cfg_host[7:]).exists() and cfg_host != "unix:///var/run/docker.sock":
        os.environ["DOCKER_HOST"] = cfg_host
        return cfg_host
    if Path("/var/run/docker.sock").exists():
        return None
    import subprocess
    if shutil.which("docker"):
        try:
            h = subprocess.run(["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
                               capture_output=True, text=True, timeout=5).stdout.strip()
            if h.startswith("unix://") and Path(h[7:]).exists():
                os.environ["DOCKER_HOST"] = h
                return h
        except Exception:
            pass
    for c in DOCKER_SOCKETS:
        p = Path(c).expanduser()
        if p.exists():
            os.environ["DOCKER_HOST"] = f"unix://{p}"
            return os.environ["DOCKER_HOST"]
    return None


ensure_docker_host()


def _docker_mem_gb() -> float | None:
    import subprocess
    if not shutil.which("docker"):
        return None
    try:
        out = subprocess.run(["docker", "info", "--format", "{{.MemTotal}}"], capture_output=True, text=True, timeout=10).stdout.strip()
        return int(out) / 2 ** 30 if out.isdigit() else None
    except Exception:
        return None


def lanes() -> dict:
    """Worker counts per job lane, sized to this machine (env CHIPLAB_*_WORKERS or config 'lanes' override):
    cpu = cores - 1 (Yosys/ABC/Icarus are single-threaded, so one job per core); docker = Docker memory / 12 GB,
    1..4 (each LibreLane run needs ~8-12 GB); gpu = 1."""
    cfg = _CFG.get("lanes", {}) if isinstance(_CFG.get("lanes"), dict) else {}
    cores = os.cpu_count() or 2

    def pick(env, key, default):
        v = os.environ.get(env) or cfg.get(key)
        return max(1, int(v)) if v else default
    mem = _docker_mem_gb()
    return {"cpu": pick("CHIPLAB_CPU_WORKERS", "cpu", max(1, cores - 1)),
            "gpu": pick("CHIPLAB_GPU_WORKERS", "gpu", 1),
            "docker": pick("CHIPLAB_DOCKER_WORKERS", "docker", max(1, min(4, int(mem // 12))) if mem else 1),
            "cores": cores, "docker_mem_gb": round(mem, 1) if mem else None}


def threads_per_docker_job() -> int:
    """CPU threads one LibreLane run may use so parallel runs don't oversubscribe the machine."""
    L = lanes()
    return max(1, (L["cores"]) // max(1, L["docker"]))


def find_bin(name: str) -> str | None:
    """OSS CAD Suite binary: CHIPLAB_OSS/bin, then the config file's oss, then PATH."""
    for base in (OSS,):
        p = Path(base) / "bin" / name
        if p.exists():
            return str(p)
    return shutil.which(name)


def oss_bin(name: str) -> str:
    p = find_bin(name)
    if p is None:
        raise FileNotFoundError(f"{name} not found (looked in {OSS}/bin and PATH). Run scripts/install.sh, or set "
                                f"CHIPLAB_OSS to an OSS CAD Suite folder; `chiplab doctor` shows what is missing.")
    return p


def home(*parts: str) -> Path:
    p = HOME.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def summary() -> dict:
    return {"config_file": str(CONFIG_FILE), "config_file_found": CONFIG_FILE.exists(), "home": str(HOME),
            "data": str(DATA), "oss": str(OSS), "pdk_root": str(PDK_ROOT), "tt_tools": str(TT_TOOLS),
            "tt_python": str(TT_PYTHON), "librelane_image": LIBRELANE_IMAGE, "lanes": lanes()}
