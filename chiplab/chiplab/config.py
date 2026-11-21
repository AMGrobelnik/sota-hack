"""Paths and tool locations. Everything can be overridden with environment variables."""
from __future__ import annotations

import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent          # chiplab/chiplab
PROJECT_DIR = PKG_DIR.parent                        # chiplab/

HOME = Path(os.environ.get("CHIPLAB_HOME", PROJECT_DIR / "runs"))
DATA = Path(os.environ.get("CHIPLAB_DATA", Path.home() / "chiplab-data"))
OSS = Path(os.environ.get("CHIPLAB_OSS", Path.home() / "tools" / "oss-cad-suite"))
PDK_ROOT = Path(os.environ.get("PDK_ROOT", Path.home() / "ttsetup" / "pdk"))
LIBRELANE_IMAGE = os.environ.get("CHIPLAB_LIBRELANE_IMAGE", "ghcr.io/librelane/librelane:3.0.14")


def oss_bin(name: str) -> str:
    """Absolute path of an OSS CAD Suite binary (never `source environment`: it swaps python)."""
    p = OSS / "bin" / name
    if not p.exists():
        raise FileNotFoundError(f"{name} not found at {p}; set CHIPLAB_OSS or run scripts/setup_toolchain.sh")
    return str(p)


def home(*parts: str) -> Path:
    p = HOME.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p
