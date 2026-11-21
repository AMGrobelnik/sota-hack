"""One agent run end to end: make the run folder, pick the runner, record the outcome.

This is the thin replacement for AI Inventor's DBOS pipeline: no workflow
engine, no database. Chipmonk's own steps (propose designs, fine-tune, compile,
verify) compose :func:`run_agent` calls.
"""

from __future__ import annotations

import asyncio
import shlex
import sys
import time
import weakref
from dataclasses import replace
from typing import Any

from loguru import logger

from chipmonk_backend.agents.types import AgentResult, AgentSpec, utc_now
from chipmonk_backend.compute.factory import runner_for
from chipmonk_backend.config import BackendConfig, ComputeTier, RunMode
from chipmonk_backend.runs import RunDir, RunRecord

#: Set in the agent's environment when the OpenRouter tool is on: where
#: ``python -m chipmonk_backend ask`` appends one JSON line per call.
LLM_CALLS_ENV = "CHIPMONK_LLM_CALLS"


def openrouter_tool_prompt(config: BackendConfig) -> str:
    """The instructions that tell an agent how to call OpenRouter models from its shell."""
    command = f"{shlex.quote(sys.executable)} -m chipmonk_backend ask"
    presets = ", ".join(f"{name} ({model})" for name, model in config.llm.presets.items()) or "none"
    return (
        "You can ask other LLMs on OpenRouter for a second opinion or a cheap sub-task. "
        f'Run in your shell: {command} --model <preset or OpenRouter model id> "<question>". '
        f"It prints the answer. Presets: {presets}. Each call costs money; use it only when it helps."
    )


def _with_openrouter_tool(spec: AgentSpec, run: RunDir, config: BackendConfig) -> AgentSpec:
    """``spec`` with the ``ask`` instructions and the call log path added."""
    tool = openrouter_tool_prompt(config)
    system_prompt = f"{spec.system_prompt}\n\n{tool}" if spec.system_prompt else tool
    env = {**spec.env, LLM_CALLS_ENV: str(run.llm_calls_path)}
    return replace(spec, system_prompt=system_prompt, env=env)


async def run_agent(
    spec: AgentSpec,
    config: BackendConfig,
    *,
    run_mode: RunMode | None = None,
    tier: ComputeTier | None = None,
    run_id: str | None = None,
) -> tuple[RunDir, AgentResult]:
    """Run ``spec`` once and return its run folder and result.

    ``run.json`` moves ``running`` -> ``succeeded`` | ``failed`` | ``stopped``
    and ends with the resolved config, timings, the costs known and the
    runner's ``compute`` facts (the file is the one record; every change goes
    through :meth:`RunDir.update_record`). An exception from the runner (no
    machine, no key, wrong OS) is recorded as ``failed`` and re-raised; Ctrl-C
    or cancellation is recorded as ``stopped`` and re-raised. Pods are
    terminated (``runner.close()``) on every path.

    At most ``compute.max_concurrent_agents`` runs execute at once per event
    loop; further calls wait for a slot before creating their run folder.
    """
    mode = run_mode or config.compute.run_mode
    chosen_tier = tier or config.compute.tier
    async with _agent_slots(config.compute.max_concurrent_agents):
        return await _run_agent(spec, config, mode=mode, tier=chosen_tier, run_id=run_id)


async def _run_agent(
    spec: AgentSpec, config: BackendConfig, *, mode: RunMode, tier: ComputeTier, run_id: str | None
) -> tuple[RunDir, AgentResult]:
    """:func:`run_agent` once a slot is held."""
    run = RunDir.create(config.resolved_runs_dir(), run_id)
    if config.agents.openrouter_tool:
        if mode == "on_demand":
            logger.warning("openrouter_tool is for local and flex runs; not offered on a pod")
        else:
            spec = _with_openrouter_tool(spec, run, config)
    run.write_record(
        RunRecord(
            run_id=run.run_id,
            run_mode=mode,
            agent=spec.to_dict(),
            tier=tier,
            config=config.model_dump(mode="json"),
            status="running",
        )
    )
    logger.info("run {} started: agent={} mode={} tier={}", run.run_id, spec.name, mode, tier)
    started = time.monotonic()
    runner = runner_for(config, mode)
    try:
        try:
            result = await runner.run(spec, run, tier=tier)
        finally:
            await runner.close()
    except (asyncio.CancelledError, KeyboardInterrupt):
        _finish(run, started, status="stopped", error="stopped before it finished (interrupted)")
        logger.warning("run {} stopped before it finished", run.run_id)
        raise
    except Exception as exc:
        _finish(run, started, status="failed", error=f"{type(exc).__name__}: {exc}")
        logger.exception("run {} failed in the runner", run.run_id)
        raise
    record = _finish(
        run,
        started,
        status="failed" if result.failed else "succeeded",
        error=result.error,
        result=result.to_dict(),
        agent_cost_usd=result.cost_usd,
    )
    logger.info(
        "run {} {} in {:.1f}s (agent ${:.4f}, OpenRouter ${:.4f} over {} calls)",
        run.run_id,
        record.status,
        record.duration_s,
        result.cost_usd,
        record.llm_cost_usd or 0.0,
        record.llm_calls,
    )
    return run, result


#: One semaphore per (event loop, limit): asyncio primitives belong to one loop.
_SLOTS: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[int, asyncio.Semaphore]] = (
    weakref.WeakKeyDictionary()
)


def _agent_slots(limit: int) -> asyncio.Semaphore:
    """The semaphore capping concurrent runs at ``limit`` on the running loop."""
    per_loop = _SLOTS.setdefault(asyncio.get_running_loop(), {})
    if limit not in per_loop:
        per_loop[limit] = asyncio.Semaphore(limit)
    return per_loop[limit]


def _finish(run: RunDir, started: float, **fields: Any) -> RunRecord:
    """Write the outcome ``fields`` plus the end time, wall clock and OpenRouter spend."""
    calls = run.read_llm_calls()
    costs = [call["cost_usd"] for call in calls if isinstance(call.get("cost_usd"), int | float)]
    return run.update_record(
        finished_at=utc_now(),
        duration_s=round(time.monotonic() - started, 3),
        llm_calls=len(calls),
        llm_cost_usd=sum(costs) if costs else None,
        **fields,
    )


__all__ = ["LLM_CALLS_ENV", "openrouter_tool_prompt", "run_agent"]
