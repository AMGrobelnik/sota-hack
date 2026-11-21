"""Logging: loguru to stderr plus a rotating file sink under ``log_dir``."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

LOG_FILE_NAME = "backend.log"


def setup_logging(log_dir: Path, *, level: str = "INFO") -> Path:
    """Send logs to stderr at ``level`` and to ``log_dir/backend.log`` at DEBUG.

    Safe to call more than once: earlier sinks are removed first. Returns the
    log file path. Never log a secret value; refer to keys by name.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / LOG_FILE_NAME
    logger.remove()
    logger.add(sys.stderr, level=level)
    logger.add(log_file, level="DEBUG", rotation="10 MB", retention=5, encoding="utf-8")
    return log_file


__all__ = ["LOG_FILE_NAME", "setup_logging"]
