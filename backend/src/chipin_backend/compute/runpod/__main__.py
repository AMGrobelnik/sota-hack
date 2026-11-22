"""RunPod checks that create nothing: ``python -m chipin_backend.compute.runpod <command>``.

* ``check``    authenticate, list pods, print stock and price for each tier chain
* ``dry-run``  print the exact create request each run mode would send
* ``reap``     list our leftover pods by name prefix (``--delete`` to terminate
  those older than the longest a live pod can run; this sweep, run on a
  schedule, is the safety net for pods whose launcher died)

``--env-file`` reads ``RUNPOD_API_KEY`` (and nothing else) from a dotenv file;
otherwise the key comes from the environment. The key is never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import get_args

from dotenv import dotenv_values
from loguru import logger

from chipin_backend.compute.modes import RUN_MODES, chain_for_tier, rents_pods
from chipin_backend.compute.runpod.api import RUNPOD_KEY_ENV, RunPodAPI, offer_for
from chipin_backend.compute.runpod.reaper import reap_orphans
from chipin_backend.compute.runpod.runner import RunPodRunner, max_pod_lifetime_s
from chipin_backend.config import BackendConfig, ComputeTier, load_config


def _api(env_file: Path | None) -> RunPodAPI:
    """A client whose key comes from ``env_file`` when given, else the environment."""
    if env_file is None:
        return RunPodAPI()
    key = dotenv_values(env_file).get(RUNPOD_KEY_ENV) or ""
    if not key:
        raise SystemExit(f"{RUNPOD_KEY_ENV} is not set in {env_file}")
    return RunPodAPI(key)


async def _check(config: BackendConfig, api: RunPodAPI) -> None:
    """Read-only: the listing proves the key; the catalog gives stock and price."""
    rp = config.compute.runpod
    async with api:
        pods = await api.list_pods()
        ours = [p for p in pods if p.name.startswith(rp.pod_name_prefix)]
        print(f"auth ok: {len(pods)} pod(s) on the account, {len(ours)} named {rp.pod_name_prefix}*")
        offers = await api.offers(cloud=rp.cloud_type)
        print(f"catalog: {len(offers)} machine types ({rp.cloud_type} cloud)")
        for tier in get_args(ComputeTier):
            print(f"\n{tier} (cap ${rp.max_usd_per_hr:.2f}/hr):")
            for machine in chain_for_tier(rp.tier_chains.get(tier, []), tier):
                offer = offer_for(machine, offers)
                stock = (offer.stock or "out") if offer else "unknown"
                price = f"${offer.usd_per_hr:.3f}/hr" if offer and offer.usd_per_hr is not None else "?"
                print(f"  {machine:34s} {stock:8s} {price}")


async def _dry_run(config: BackendConfig, api: RunPodAPI, tier: ComputeTier) -> None:
    """Print what each run mode would send to RunPod for one agent on ``tier``."""
    runner = RunPodRunner(config, api=api)
    try:
        for mode in RUN_MODES:
            print(f"== {mode}")
            if not rents_pods(mode):
                print(
                    "   no pod request: the agent runs in this process"
                    + (" on a Mac" if mode == "flex" else "")
                )
                continue
            machines = await runner.candidates(tier)
            request = runner.dry_run_request(run_id="dryrun", agent="agent", machine=machines[0])
            print(f"   tier {tier}, machines in order: {machines}")
            print("   POST " + api.base_url + "/pods")
            print("   " + json.dumps(request, indent=2).replace("\n", "\n   "))
    finally:
        await runner.close()


async def _reap(
    config: BackendConfig, api: RunPodAPI, *, prefix: str, older_than_s: int, delete: bool
) -> None:
    """List (and with ``delete``, terminate) pods named ``prefix*``."""
    async with api:
        pods = await reap_orphans(api, prefix=prefix, older_than_s=older_than_s, dry_run=not delete)
    verb = "terminated" if delete else "would terminate"
    print(f"{verb} {len(pods)} pod(s) named {prefix}* older than {older_than_s}s")
    for pod in pods:
        print(f"  {pod.id}  {pod.name}  {pod.desired_status}  ${pod.usd_per_hr or 0:.3f}/hr")


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns the exit code."""
    parser = argparse.ArgumentParser(prog="python -m chipin_backend.compute.runpod", description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--env-file", type=Path, default=None, help=f"dotenv file holding {RUNPOD_KEY_ENV}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="auth, pod listing, stock and price (read-only)")
    dry = sub.add_parser("dry-run", help="print the create request per run mode")
    dry.add_argument("--tier", choices=get_args(ComputeTier), default=None)
    reap = sub.add_parser("reap", help="our leftover pods by prefix (report only unless --delete)")
    reap.add_argument("--prefix", default=None, help="default: compute.runpod.pod_name_prefix")
    reap.add_argument(
        "--older-than-s",
        type=int,
        default=None,
        help="minimum pod age; default 0 when listing, and with --delete the longest a live pod "
        "can run (health check + pod_timeout_s + graces), so teammates' live pods are never hit",
    )
    reap.add_argument("--delete", action="store_true")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    if args.command == "reap" and args.delete and args.older_than_s is not None and args.older_than_s <= 0:
        parser.error("--delete needs --older-than-s > 0: live runs share the prefix")
    api = _api(args.env_file)
    if args.command == "check":
        asyncio.run(_check(config, api))
    elif args.command == "dry-run":
        asyncio.run(_dry_run(config, api, args.tier or config.compute.tier))
    else:
        prefix = args.prefix or config.compute.runpod.pod_name_prefix
        older_than_s = args.older_than_s
        if older_than_s is None:
            older_than_s = max_pod_lifetime_s(config.compute.runpod) if args.delete else 0
        asyncio.run(_reap(config, api, prefix=prefix, older_than_s=older_than_s, delete=args.delete))
    return 0


if __name__ == "__main__":
    sys.exit(main())
