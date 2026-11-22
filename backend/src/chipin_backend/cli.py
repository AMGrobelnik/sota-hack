"""Command line: ``chipin-backend run``, ``ask``, ``serve``, ``evidence`` and ``config``.

Examples::

    chipin-backend config
    chipin-backend run --backend stub --prompt "hello"
    chipin-backend run --config config/example.yaml --prompt-file examples/seizure_eeg_prompt.md
    chipin-backend run --preset pro --prompt-file examples/seizure_eeg_prompt.md
    chipin-backend ask --model cheap "Name one low-power EEG seizure feature"
    chipin-backend serve --agent stub
    chipin-backend evidence 20261122-001507-0ef5bb --json
    chipin-backend summarise 20261122-001507-0ef5bb --items
    chipin-backend skill export <project>/.claude/skills

``python -m chipin_backend`` is the same command.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, get_args

from dotenv import load_dotenv
from loguru import logger

from chipin_backend.agents.base import BACKENDS
from chipin_backend.agents.types import AgentSpec, utc_now
from chipin_backend.api.cli import add_serve_parser, run_serve
from chipin_backend.api.config import Preset, load_api_config
from chipin_backend.api.manager import ApiAgent, RequestError, RunManager
from chipin_backend.api.summaries import ModelSummariser, load_level_settings, outline, summarise_folder
from chipin_backend.chiplab import SKILL_NAME, TOOLS_REFERENCE, chiplab_available, write_skill
from chipin_backend.config import BackendConfig, ComputeTier, RunMode, load_config
from chipin_backend.evidence import build_evidence, render_markdown
from chipin_backend.llm import MissingKeyError, OpenRouterClient, expand_preset
from chipin_backend.llm.providers import ProviderError, resolve_provider
from chipin_backend.log import setup_logging
from chipin_backend.orchestrate import LLM_CALLS_ENV, run_agent
from chipin_backend.runs import is_safe_run_id


def _common() -> argparse.ArgumentParser:
    """Options every command takes, before or after the command name."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config",
        type=Path,
        default=argparse.SUPPRESS,
        help="config YAML (default: $CHIPIN_CONFIG or config/backend.yaml)",
    )
    common.add_argument(
        "--env-file",
        type=Path,
        default=argparse.SUPPRESS,
        help="extra .env file to load keys from (by name; values are never printed)",
    )
    return common


def _parser() -> argparse.ArgumentParser:
    common = _common()
    parser = argparse.ArgumentParser(
        prog="chipin-backend", description=__doc__.splitlines()[0], parents=[common]
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("config", parents=[common], help="print the resolved config as JSON")
    run = sub.add_parser("run", parents=[common], help="run one agent and write a run folder")
    run.add_argument("--prompt", action="append", default=[], help="repeat for several turns")
    run.add_argument("--prompt-file", type=Path, action="append", default=[], help="a prompt from a file")
    run.add_argument("--name", default="agent")
    run.add_argument("--backend", choices=sorted(BACKENDS), default=None)
    run.add_argument("--model", default=None)
    run.add_argument("--provider", default=None, help="model provider from the config (openrouter backend)")
    run.add_argument("--mode", choices=get_args(RunMode), default=None)
    run.add_argument("--tier", choices=get_args(ComputeTier), default=None)
    run.add_argument("--timeout", type=int, default=None, help="whole-run wall clock in seconds")
    run.add_argument(
        "--no-summary", action="store_true", help="skip the OpenRouter run summary written into run.json"
    )
    run.add_argument(
        "--preset",
        choices=get_args(Preset),
        default=None,
        help="run it as the dashboard does, on this Mac: standing instructions, ./progress, "
        "contract events.jsonl; the prompts are joined into one brief",
    )
    ask = sub.add_parser("ask", parents=[common], help="one OpenRouter chat call; prints the answer")
    ask.add_argument("question")
    ask.add_argument("--model", default=None, help="preset name or model id of the provider")
    ask.add_argument("--provider", default=None, help="model provider from the config (default openrouter)")
    ask.add_argument("--max-tokens", type=int, default=4096)
    evidence = sub.add_parser(
        "evidence",
        parents=[common],
        help="check the report numbers against their sources, weight bytes per decision, stage timings",
    )
    evidence.add_argument("run", help="a run id under the runs folder, or a run folder")
    evidence.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    summ = sub.add_parser(
        "summarise",
        parents=[common],
        help="write every level of summaries for a recorded run into its summaries.jsonl",
    )
    summ.add_argument("run", help="a run id under the runs folder, or a run folder")
    summ.add_argument("--items", action="store_true", help="show the item lines in the outline too")
    summ.add_argument("--no-model", action="store_true", help="own first lines only: no model calls")
    summ.add_argument("--max-usd", type=float, default=None, help="model spend cap (default: summaries.yaml)")
    add_serve_parser(sub, common)
    skill = sub.add_parser("skill", parents=[common], help="the chip-lab agent skill")
    skill_sub = skill.add_subparsers(dest="skill_command", required=True)
    export = skill_sub.add_parser(
        "export",
        parents=[common],
        help="write the chiplab skill folder into FOLDER (as FOLDER/chiplab), with the installed "
        "lab's reference when the lab is on",
    )
    export.add_argument("folder", type=Path, help="where to write it, e.g. <project>/.claude/skills")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns the process exit code.

    A provider or key problem is one clear error line and exit code 2, never a trace.
    """
    try:
        return _main(argv)
    except (ProviderError, MissingKeyError) as exc:
        logger.error("{}", exc)
        return 2


@logger.catch(onerror=lambda _: sys.exit(1), exclude=(ProviderError, MissingKeyError))
def _main(argv: list[str] | None) -> int:
    args = _parser().parse_args(argv)
    env_file: Path | None = getattr(args, "env_file", None)
    if env_file is not None:
        if not env_file.is_file():
            raise FileNotFoundError(f"--env-file {env_file} does not exist")
        load_dotenv(env_file, override=False)
    config = load_config(getattr(args, "config", None))
    log_file = setup_logging(config.resolved_log_dir(), level=config.log_level)
    logger.debug("logging to {}", log_file)
    if args.command == "config":
        print(json.dumps(config.model_dump(mode="json"), indent=2))
        return 0
    if args.command == "serve":
        return run_serve(args, config)
    if args.command == "evidence":
        return _evidence(config, args.run, as_json=args.json)
    if args.command == "summarise":
        return asyncio.run(
            _summarise(config, args.run, items=args.items, no_model=args.no_model, max_usd=args.max_usd)
        )
    if args.command == "skill":
        return _skill_export(args.folder)
    if args.command == "ask":
        return asyncio.run(
            _ask(config, args.question, model=args.model, max_tokens=args.max_tokens, provider=args.provider)
        )
    prompts = list(args.prompt) + [path.read_text(encoding="utf-8").strip() for path in args.prompt_file]
    if not prompts:
        logger.error("give at least one --prompt or --prompt-file")
        return 2
    backend = args.backend
    if args.preset is not None:
        return asyncio.run(_dashboard_run(config, args, prompts))
    if args.provider is not None:
        if backend not in (None, "openrouter"):
            logger.error("--provider needs the openrouter backend, not {}", backend)
            return 2
        backend = "openrouter"
        resolve_provider(config.providers, args.provider).api_key()  # fail early, naming the variable
    spec = AgentSpec(
        name=args.name,
        prompts=prompts,
        backend=backend,
        model=expand_preset(args.model, args.provider, config.llm.presets),
        provider=args.provider,
        timeout_s=args.timeout,
    )
    try:
        run, result = asyncio.run(
            run_agent(spec, config, run_mode=args.mode, tier=args.tier, summary=not args.no_summary)
        )
    except NotImplementedError as exc:
        logger.error("not built yet: {}", exc)
        return 2
    print(json.dumps({"run_dir": str(run.path), **result.to_dict()}, indent=2))
    return 1 if result.failed else 0


def _run_folder(config: BackendConfig, run: str) -> Path | None:
    """``run`` as a folder, or as a run id under the runs folder; ``None`` (logged) if neither."""
    folder = Path(run).expanduser()
    if folder.is_dir():
        return folder
    if not is_safe_run_id(run):
        logger.error("no run folder {}", run)
        return None
    folder = config.resolved_runs_dir() / run
    if not folder.is_dir():
        logger.error("no run folder {} (nor {} under {})", run, run, config.resolved_runs_dir())
        return None
    return folder


def _evidence(config: BackendConfig, run: str, *, as_json: bool) -> int:
    """``evidence``: compute it, write ``evidence.json`` and ``evidence.md`` into the run, print one."""
    folder = _run_folder(config, run)
    if folder is None:
        return 2
    evidence = build_evidence(folder)
    print(json.dumps(evidence, indent=2, ensure_ascii=False) if as_json else render_markdown(evidence))
    return 0


class _NoModel:
    """``summarise --no-model``: every line is its own first line."""

    def unavailable(self) -> str:
        return "--no-model"

    async def __call__(self, *, system: str, prompt: str, max_tokens: int) -> Any:
        raise RuntimeError("no model calls")


async def _summarise(
    config: BackendConfig, run: str, *, items: bool, no_model: bool, max_usd: float | None = None
) -> int:
    """``summarise``: replay the run's events into every level; print the outline, then the stats."""
    folder = _run_folder(config, run)
    if folder is None:
        return 2
    settings = load_level_settings()
    if max_usd is not None:
        settings = settings.model_copy(update={"max_usd_per_run": max_usd})
    summariser = _NoModel() if no_model else ModelSummariser(settings)
    try:
        summaries, stats = await summarise_folder(folder, settings, summariser)
    except FileNotFoundError as exc:
        logger.error("{}", exc)
        return 2
    print(outline(summaries, items=items))
    print(json.dumps({"summaries": len(summaries), **stats}, indent=2))
    return 0


def _skill_export(folder: Path) -> int:
    """``skill export FOLDER``: write the chip-lab skill to ``FOLDER/chiplab``; print its path.

    Refuses a folder inside a hidden folder of the home directory (``~/.claude``,
    ``~/.agents``, ``~/.openhands`` and the like): those make the skill global for
    every session of a tool, and this command only writes where a project asks.
    """
    target = (folder.expanduser() / SKILL_NAME).resolve()
    home = Path.home().resolve()
    if target.is_relative_to(home) and target.relative_to(home).parts[0].startswith("."):
        logger.error("refusing to write into {}: a tool folder in the home directory", folder)
        return 2
    if not chiplab_available():
        logger.warning("the chip lab is off here; the skill is written without the lab's tool reference")
    dest = write_skill(target)
    print(json.dumps({"skill": str(dest), "tools_reference": (dest / TOOLS_REFERENCE).is_file()}))
    return 0


#: ``run --backend`` -> the dashboard's agent name.
DASHBOARD_AGENTS: dict[str, ApiAgent] = {"claude_cli": "claude", "openrouter": "openrouter", "stub": "stub"}


async def _dashboard_run(config: BackendConfig, args: argparse.Namespace, prompts: list[str]) -> int:
    """``run --preset``: one run exactly as ``POST /api/runs`` starts it, without the HTTP server.

    The run folder gets the dashboard's files (``events.jsonl`` with contract
    events, ``progress.jsonl``, ``workspace/progress``, ``api.json``); the
    agent gets the standing instructions, with the chip-lab paragraph when
    the lab is reachable. Prints the run's view as JSON; exit 1 unless it
    succeeded, 2 for a bad request.
    """
    if args.mode is not None or args.tier is not None:
        logger.error("--preset runs on this Mac (the dashboard's local runner); drop --mode and --tier")
        return 2
    agent = DASHBOARD_AGENTS.get(args.backend or config.agents.default_backend)
    if agent is None:
        logger.error("--preset takes the backends {}", ", ".join(sorted(DASHBOARD_AGENTS)))
        return 2
    api = load_api_config()
    if args.timeout is not None:
        api = api.model_copy(update={"run_timeout_s": args.timeout})
    body: dict[str, Any] = {"prompt": "\n\n".join(prompts), "preset": args.preset}
    body.update({k: v for k, v in (("provider", args.provider), ("model", args.model)) if v is not None})
    manager = RunManager(config, api, agent=agent, summary=not args.no_summary)
    try:
        item = manager.start(body)
    except RequestError as exc:
        logger.error("{}", exc)
        return 2
    try:
        if item.task is not None:
            await item.task
    except (asyncio.CancelledError, KeyboardInterrupt):
        await manager.shutdown()
        raise
    print(json.dumps({"run_dir": str(item.run.path), **item.detail_view()}, indent=2, ensure_ascii=False))
    return 0 if item.record.get("status") == "succeeded" else 1


async def _ask(
    config: BackendConfig, question: str, *, model: str | None, max_tokens: int, provider: str | None = None
) -> int:
    """Answer ``question`` with one OpenRouter call; log the call for the run record.

    An empty answer cut off at the token limit (a reasoning model that spent
    ``max_tokens`` thinking) is a failure: warn and return 1.
    """
    endpoint = resolve_provider(config.providers, provider) if provider else None
    async with OpenRouterClient(config.llm, endpoint=endpoint) as client:
        result = await client.chat(
            [{"role": "user", "content": question}], model=model, max_tokens=max_tokens
        )
    truncated_empty = not result.text.strip() and result.finish_reason in ("length", "max_tokens")
    if truncated_empty:
        logger.warning(
            "ask: {} / {} returned no text and stopped at the token limit; raise --max-tokens (now {})",
            result.provider,
            result.model,
            max_tokens,
        )
    print(result.text)
    logger.info(
        "ask: {} / {} answered, {} in / {} out tokens, ${:.6f}",
        result.provider,
        result.model,
        result.input_tokens,
        result.output_tokens,
        result.cost_usd,
    )
    calls_file = os.environ.get(LLM_CALLS_ENV)
    if calls_file:
        entry: dict[str, Any] = {
            "ts": utc_now(),
            "provider": result.provider,
            "model": result.model,
            "question": question,
            "answer": result.text,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": result.cost_usd,
        }
        try:
            with Path(calls_file).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("could not record the call in {}: {}", calls_file, exc)
    return 1 if truncated_empty else 0


if __name__ == "__main__":
    sys.exit(main())
