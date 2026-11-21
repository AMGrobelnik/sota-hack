"""One agent run end to end: make the run folder, pick the runner, record the outcome.

This is the thin replacement for AI Inventor's DBOS pipeline: no workflow
engine, no database. Chipmonk's own steps (propose designs, fine-tune, compile,
verify) compose :func:`run_agent` calls.
"""

from __future__ import annotations

from loguru import logger

from chipmonk_backend.agents.types import AgentResult, AgentSpec
from chipmonk_backend.compute.factory import runner_for
from chipmonk_backend.config import BackendConfig, ComputeTier, RunMode
from chipmonk_backend.runs import RunDir, RunRecord


async def run_agent(
    spec: AgentSpec,
    config: BackendConfig,
    *,
    run_mode: RunMode | None = None,
    tier: ComputeTier | None = None,
    run_id: str | None = None,
) -> tuple[RunDir, AgentResult]:
    """Run ``spec`` once and return its run folder and result.

    ``run.json`` moves ``running`` -> ``succeeded`` | ``failed``. An exception
    from the runner (no machine, no key, wrong OS) is recorded as ``failed``
    with the error and then re-raised.
    """
    mode = run_mode or config.compute.run_mode
    chosen_tier = tier or config.compute.tier
    run = RunDir.create(config.resolved_runs_dir(), run_id)
    record = RunRecord(run_id=run.run_id, run_mode=mode, agent=spec.to_dict(), tier=chosen_tier)
    record.status = "running"
    run.write_record(record)
    logger.info("run {} started: agent={} mode={} tier={}", run.run_id, spec.name, mode, chosen_tier)
    runner = runner_for(config, mode)
    try:
        result = await runner.run(spec, run, tier=chosen_tier)
    except Exception as exc:
        record.status = "failed"
        record.error = f"{type(exc).__name__}: {exc}"
        run.write_record(record)
        logger.exception("run {} failed in the runner", run.run_id)
        raise
    finally:
        await runner.close()
    record.status = "failed" if result.failed else "succeeded"
    record.result = result.to_dict()
    record.error = result.error
    run.write_record(record)
    logger.info("run {} {} (cost ${:.4f})", run.run_id, record.status, result.cost_usd)
    return run, result


__all__ = ["run_agent"]
