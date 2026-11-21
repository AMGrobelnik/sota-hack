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
            "tt_python": str(TT_PYTHON), "librelane_image": LIBRELANE_IMAGE}
