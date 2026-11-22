"""``chipin-backend serve``: run the local API server until interrupted."""

from __future__ import annotations

import argparse
import asyncio
import signal
from pathlib import Path

from loguru import logger

from chipin_backend.api.config import ApiConfig, load_api_config
from chipin_backend.api.server import HOST, create_app, new_token, serve
from chipin_backend.config import BackendConfig


def add_serve_parser(
    sub: argparse._SubParsersAction,  # type: ignore[type-arg]
    common: argparse.ArgumentParser,
) -> None:
    """Register ``serve``; ``common`` adds ``--config`` and ``--env-file``."""
    serve_p = sub.add_parser("serve", parents=[common], help="serve the local API for the ChipIn dashboards")
    serve_p.add_argument("--port", type=int, default=None, help="default: api.yaml port (8797)")
    serve_p.add_argument(
        "--site",
        "--frontend",
        dest="frontend",
        type=Path,
        default=None,
        help="a checkout of the site: served at / from the same origin as the API",
    )
    serve_p.add_argument(
        "--agent",
        choices=["claude", "stub", "openrouter"],
        default="claude",
        help="stub: scripted, no model calls",
    )
    serve_p.add_argument(
        "--stub-step", type=float, default=None, help="seconds between the stub agent's steps (default 0.4)"
    )
    serve_p.add_argument(
        "--runner", choices=["local"], default="local", help="local: this Mac (the backend's flex mode)"
    )


def run_serve(args: argparse.Namespace, config: BackendConfig) -> int:
    """Start the server, print the ready-to-open link, serve until SIGINT or SIGTERM."""
    if args.frontend is not None and not args.frontend.is_dir():
        logger.error("--site {} is not a folder", args.frontend)
        return 2
    api = load_api_config()
    if args.stub_step is not None:
        api = api.model_copy(update={"stub_step_s": max(0.0, args.stub_step)})
    return asyncio.run(_serve(config, api, args))


async def _serve(config: BackendConfig, api: ApiConfig, args: argparse.Namespace) -> int:
    port = args.port if args.port is not None else api.port
    token = new_token()
    app = create_app(config, api, token=token, agent=args.agent, runner=args.runner, frontend=args.frontend)
    try:
        runner = await serve(app, port)
    except OSError as exc:
        logger.error("cannot listen on {}:{}: {}", HOST, port, exc)
        return 1
    bound = runner.addresses[0][1] if runner.addresses else port
    print(
        f"ChipIn backend ready (agent {args.agent}, runner {args.runner}): http://{HOST}:{bound}/#token={token}"
    )
    print("Ctrl-C stops it.", flush=True)
    logger.info("serving on {}:{} (agent {}, runner {})", HOST, bound, args.agent, args.runner)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        await stop.wait()
    finally:
        logger.info("shutting down: stopping running agents")
        await runner.cleanup()
    return 0


__all__ = ["add_serve_parser", "run_serve"]
