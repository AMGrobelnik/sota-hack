"""Command line: ``chipmonk-backend run`` and ``chipmonk-backend config``.

Examples::

    chipmonk-backend config
    chipmonk-backend run --backend stub --prompt "hello"
    chipmonk-backend run --mode flex --prompt "Propose three sensor front-ends"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import get_args

from loguru import logger

from chipmonk_backend.agents.base import BACKENDS
from chipmonk_backend.agents.types import AgentSpec
from chipmonk_backend.config import ComputeTier, RunMode, load_config
from chipmonk_backend.log import setup_logging
from chipmonk_backend.orchestrate import run_agent


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chipmonk-backend", description=__doc__.splitlines()[0])
    parser.add_argument(
        "--config", type=Path, default=None, help="config YAML (default: config/backend.yaml)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("config", help="print the resolved config as JSON")
    run = sub.add_parser("run", help="run one agent and write a run folder")
    run.add_argument("--prompt", action="append", required=True, help="repeat for several turns")
    run.add_argument("--name", default="agent")
    run.add_argument("--backend", choices=sorted(BACKENDS), default=None)
    run.add_argument("--model", default=None)
    run.add_argument("--mode", choices=get_args(RunMode), default=None)
    run.add_argument("--tier", choices=get_args(ComputeTier), default=None)
    return parser


@logger.catch(onerror=lambda _: sys.exit(1))
def main(argv: list[str] | None = None) -> int:
    """Entry point; returns the process exit code."""
    args = _parser().parse_args(argv)
    config = load_config(args.config)
    log_file = setup_logging(config.resolved_log_dir(), level=config.log_level)
    logger.debug("logging to {}", log_file)
    if args.command == "config":
        print(json.dumps(config.model_dump(mode="json"), indent=2))
        return 0
    spec = AgentSpec(name=args.name, prompts=args.prompt, backend=args.backend, model=args.model)
    try:
        run, result = asyncio.run(run_agent(spec, config, run_mode=args.mode, tier=args.tier))
    except NotImplementedError as exc:
        logger.error("not built yet: {}", exc)
        return 2
    print(json.dumps({"run_dir": str(run.path), **result.to_dict()}, indent=2))
    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
