"""The optional training Python: how an agent finds an interpreter that can train.

The agent's own ``python3`` often has no numpy or torch, and the reference and
finetune stages then have to be skipped. One setting names a Python that can
train, without putting it first on the agent's ``PATH``:

- ``CHIPIN_TRAIN_PYTHON``: the path of a Python interpreter with the training
  libraries (for example the chip lab's ``.venv/bin/python``, which has numpy,
  torch, scikit-learn and xgboost). It passes to the agent unchanged, and the
  standing instructions tell the agent to run every training and data script
  with ``"$CHIPIN_TRAIN_PYTHON"``.

Unset (or not an executable file), training is off: the agent's environment
and instructions stay exactly as without it.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from loguru import logger

#: Path of a Python interpreter that can train; passed to the agent as is.
TRAIN_PYTHON_ENV = "CHIPIN_TRAIN_PYTHON"
#: The paragraph added to the agent's standing instructions when training is on.
TRAINING_INSTRUCTIONS_PATH = Path(__file__).parent / "api" / "training.md"


def train_env(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Agent environment entries naming the training Python; ``{}`` when training is off.

    ``source`` (default ``os.environ``) is the launcher's environment. A
    ``CHIPIN_TRAIN_PYTHON`` that is not an executable file is a
    misconfiguration: logged, and training stays off.
    """
    src = os.environ if source is None else source
    value = src.get(TRAIN_PYTHON_ENV, "").strip()
    if not value:
        return {}
    python = Path(value).expanduser()
    if not (python.is_file() and os.access(python, os.X_OK)):
        logger.warning("{} is set but {} is not an executable file; training off", TRAIN_PYTHON_ENV, python)
        return {}
    return {TRAIN_PYTHON_ENV: str(python)}


def train_available(source: Mapping[str, str] | None = None) -> bool:
    """Whether an agent started from ``source`` has a Python that can train."""
    return bool(train_env(source))


def training_instructions() -> str:
    """The training paragraph of the standing instructions."""
    return TRAINING_INSTRUCTIONS_PATH.read_text(encoding="utf-8")


__all__ = [
    "TRAINING_INSTRUCTIONS_PATH",
    "TRAIN_PYTHON_ENV",
    "train_available",
    "train_env",
    "training_instructions",
]
