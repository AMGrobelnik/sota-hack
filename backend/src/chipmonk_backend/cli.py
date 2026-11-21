"""Command line: ``chipmonk-backend run``, ``ask`` and ``config``.

Examples::

    chipmonk-backend config
    chipmonk-backend run --backend stub --prompt "hello"
    chipmonk-backend run --config config/example.yaml --prompt-file examples/seizure_eeg_prompt.md
    chipmonk-backend ask --model cheap "Name one low-power EEG seizure feature"

``python -m chipmonk_backend`` is the same command.
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

from chipmonk_backend.agents.base import BACKENDS
from chipmonk_backend.agents.types import AgentResult, AgentSpec, utc_now
from chipmonk_backend.config import BackendConfig, ComputeTier, RunMode, load_config
from chipmonk_backend.llm import OpenRouterClient
from chipmonk_backend.llm.keys import OPENROUTER_KEY_ENV, has_openrouter_key
from chipmonk_backend.llm.summarise import Summary, label_output, load_summary_settings, summarise_run
from chipmonk_backend.log import setup_logging
from chipmonk_backend.orchestrate import LLM_CALLS_ENV, run_agent
from chipmonk_backend.runs import RunDir


def _common() -> argparse.ArgumentParser:
    """Options every command takes, before or after the command name."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config",
        type=Path,
        default=argparse.SUPPRESS,
        help="config YAML (default: $CHIPMONK_CONFIG or config/backend.yaml)",
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
        prog="chipmonk-backend", description=__doc__.splitlines()[0], parents=[common]
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("config", parents=[common], help="print the resolved config as JSON")
    run = sub.add_parser("run", parents=[common], help="run one agent and write a run folder")
    run.add_argument("--prompt", action="append", default=[], help="repeat for several turns")
    run.add_argument("--prompt-file", type=Path, action="append", default=[], help="a prompt from a file")
    run.add_argument("--name", default="agent")
    run.add_argument("--backend", choices=sorted(BACKENDS), default=None)
    run.add_argument("--model", default=None)
    run.add_argument("--mode", choices=get_args(RunMode), default=None)
    run.add_argument("--tier", choices=get_args(ComputeTier), default=None)
    run.add_argument("--timeout", type=int, default=None, help="whole-run wall clock in seconds")
    run.add_argument(
        "--no-summary", action="store_true", help="skip the OpenRouter run summary written into run.json"
    )
    ask = sub.add_parser("ask", parents=[common], help="one OpenRouter chat call; prints the answer")
    ask.add_argument("question")
    ask.add_argument("--model", default=None, help="preset name or OpenRouter model id")
    ask.add_argument("--max-tokens", type=int, default=4096)
    return parser


@logger.catch(onerror=lambda _: sys.exit(1))
def main(argv: list[str] | None = None) -> int:
    """Entry point; returns the process exit code."""
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
    if args.command == "ask":
        return asyncio.run(_ask(config, args.question, model=args.model, max_tokens=args.max_tokens))
    prompts = list(args.prompt) + [path.read_text(encoding="utf-8").strip() for path in args.prompt_file]
    if not prompts:
        logger.error("give at least one --prompt or --prompt-file")
        return 2
    spec = AgentSpec(
        name=args.name, prompts=prompts, backend=args.backend, model=args.model, timeout_s=args.timeout
    )
    try:
        run, result = asyncio.run(run_agent(spec, config, run_mode=args.mode, tier=args.tier))
    except NotImplementedError as exc:
        logger.error("not built yet: {}", exc)
        return 2
    if not args.no_summary:
        asyncio.run(summarise_into_record(run, result))
    print(json.dumps({"run_dir": str(run.path), **result.to_dict()}, indent=2))
    return 1 if result.failed else 0


async def summarise_into_record(run: RunDir, result: AgentResult) -> None:
    """Summarise a finished run on OpenRouter and write it into ``run.json``.

    ``result.summary["run"]`` is three bullets on the whole run; a final answer
    longer than ``label_min_output_chars`` also gets ``output_label``. Each
    carries its own cost. A summary that cannot be written is logged; it never
    fails the run.
    """
    try:
        settings = load_summary_settings()
        if not has_openrouter_key():
            logger.warning("no run summary: {} is not set", OPENROUTER_KEY_ENV)
            summaries = {"run": Summary(error=f"{OPENROUTER_KEY_ENV} is not set").to_dict()}
        else:
            run_summary = await summarise_run(run.read_events(), result, settings=settings)
            summaries = {"run": run_summary.to_dict()}
            if len(result.final_text) > settings.label_min_output_chars:
                summaries["output_label"] = (
                    await label_output(result.final_text, settings=settings)
                ).to_dict()
        result.summary = summaries
        run.update_record(result=result.to_dict())
    except (OSError, ValueError, TypeError) as exc:
        logger.error("run {}: summary not written: {}", run.run_id, exc)
        return
    cost = sum(float(entry.get("cost_usd") or 0.0) for entry in summaries.values())
    logger.info("run {}: summary written (${:.6f})", run.run_id, cost)


async def _ask(config: BackendConfig, question: str, *, model: str | None, max_tokens: int) -> int:
    """Answer ``question`` with one OpenRouter call; log the call for the run record.

    An empty answer cut off at the token limit (a reasoning model that spent
    ``max_tokens`` thinking) is a failure: warn and return 1.
    """
    async with OpenRouterClient(config.llm) as client:
        result = await client.chat(
            [{"role": "user", "content": question}], model=model, max_tokens=max_tokens
        )
    truncated_empty = not result.text.strip() and result.finish_reason in ("length", "max_tokens")
    if truncated_empty:
        logger.warning(
            "ask: {} returned no text and stopped at the token limit; raise --max-tokens (now {})",
            result.model,
            max_tokens,
        )
    print(result.text)
    logger.info(
        "ask: {} answered, {} in / {} out tokens, ${:.6f}",
        result.model,
        result.input_tokens,
        result.output_tokens,
        result.cost_usd,
    )
    calls_file = os.environ.get(LLM_CALLS_ENV)
    if calls_file:
        entry: dict[str, Any] = {
            "ts": utc_now(),
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
