"""The optional chip lab: how an agent finds the ``chiplab`` command and its install.

The chip lab (``chiplab/`` in the sota-hack repository) turns a trained model
into a verified, measured chip. When a lab tool runs in an agent's working
folder it reports through the ``./progress`` helper by itself, so the backend
only has to let the agent reach the lab:

- ``CHIPIN_CHIPLAB_BIN``: a folder holding the ``chiplab`` command (the
  launcher the lab's ``scripts/install.sh`` writes, or the lab's
  ``.venv/bin``). It goes first on the agent's ``PATH``.
- ``CHIPLAB_CONFIG`` and ``CHIPLAB_USER_DIR``: the lab's own settings for an
  install outside ``~/.chiplab`` and ``~/.config/chiplab``. They are paths,
  not secrets, and pass to the agent unchanged when set.

When the lab is on, the agent also gets ``CHIPIN_PROGRESS_CHIP=1``: the
``./progress`` helper takes ``metric ... --chip <design_id>`` and
``chosen <design_id>``, so the lab tags each number with its chip.

With none of these set, the lab counts as present only when ``chiplab`` is
already on the agent's ``PATH`` (the lab's default install puts it in
``~/.local/bin``). Otherwise it is off: the agent's environment and
instructions stay exactly as without a lab.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from pathlib import Path

from loguru import logger

#: Folder holding the ``chiplab`` command; put first on the agent's PATH.
CHIPLAB_BIN_ENV = "CHIPIN_CHIPLAB_BIN"
#: The lab's own variables, passed to the agent when set.
CHIPLAB_PASSED_NAMES: tuple[str, ...] = ("CHIPLAB_CONFIG", "CHIPLAB_USER_DIR")
CHIPLAB_COMMAND = "chiplab"
#: Set to ``1`` for the agent when the lab is on: this backend's ``./progress``
#: takes ``metric ... --chip <design_id>`` and ``chosen <design_id>``.
PROGRESS_CHIP_ENV = "CHIPIN_PROGRESS_CHIP"
#: The paragraph added to the agent's standing instructions when the lab is on.
CHIPLAB_INSTRUCTIONS_PATH = Path(__file__).parent / "api" / "chiplab.md"


def chiplab_env(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Agent environment entries that let it call the lab; ``{}`` when the lab is off.

    ``source`` (default ``os.environ``) is the launcher's environment. A
    ``CHIPIN_CHIPLAB_BIN`` without an executable ``chiplab`` in it is a
    misconfiguration: logged, and the lab stays off.
    """
    src = os.environ if source is None else source
    path = src.get("PATH", "")
    bin_dir = src.get(CHIPLAB_BIN_ENV, "").strip()
    if bin_dir:
        command = Path(bin_dir).expanduser() / CHIPLAB_COMMAND
        if not (command.is_file() and os.access(command, os.X_OK)):
            logger.warning(
                "{} is set but {} is not an executable chiplab command; chip lab off",
                CHIPLAB_BIN_ENV,
                command,
            )
            return {}
        path = os.pathsep.join(p for p in (str(command.parent), path) if p)
    elif not path or shutil.which(CHIPLAB_COMMAND, path=path) is None:
        return {}
    env = {"PATH": path, PROGRESS_CHIP_ENV: "1"}
    env.update({name: src[name] for name in CHIPLAB_PASSED_NAMES if src.get(name)})
    return env


def chiplab_available(source: Mapping[str, str] | None = None) -> bool:
    """Whether an agent started from ``source`` can call the chip lab."""
    return bool(chiplab_env(source))


def chiplab_instructions() -> str:
    """The chip-lab paragraph of the standing instructions."""
    return CHIPLAB_INSTRUCTIONS_PATH.read_text(encoding="utf-8")


__all__ = [
    "CHIPLAB_BIN_ENV",
    "CHIPLAB_COMMAND",
    "CHIPLAB_INSTRUCTIONS_PATH",
    "CHIPLAB_PASSED_NAMES",
    "PROGRESS_CHIP_ENV",
    "chiplab_available",
    "chiplab_env",
    "chiplab_instructions",
]
