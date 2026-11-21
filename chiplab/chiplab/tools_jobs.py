"""Job, batch and estimate tools: how several agents use the lab at once without blocking each other."""
from __future__ import annotations

import json

from chiplab import cache, config
from chiplab.tools import TOOLS, ToolError, tool


@tool("Run any tool asynchronously on its resource lane (cpu, gpu, docker). Returns a job_id immediately; poll "
      "job_status / job_result. Identical work from any agent is served from the cache.",
      {"tool": "str — tool name, e.g. synthesize", "args": "dict — the tool's arguments", "lane": "str — override lane (optional)"},
      lane="inline")
def submit_job(tool: str, args: dict | None = None, lane: str | None = None, session_id: str | None = None) -> dict:
    from chiplab.jobs import queue
    return queue.submit(tool.replace("-", "_"), args or {}, session_id=session_id, lane=lane)


@tool("Submit many jobs of one tool at once (e.g. synthesize 50 candidates). Returns the job ids in order.",
      {"tool": "str", "args_list": "list[dict] — one argument dict per job"}, lane="inline")
def submit_batch(tool: str, args_list: list, session_id: str | None = None) -> dict:
    from chiplab.jobs import queue
    jobs = [queue.submit(tool.replace("-", "_"), a, session_id=session_id) for a in args_list]
    return {"job_ids": [j["job_id"] for j in jobs], "n": len(jobs), "lane": jobs[0]["lane"] if jobs else None}


@tool("State of a job: queued | running | done | failed | cancelled, with timings.", {"job_id": "str"}, lane="inline")
def job_status(job_id: str) -> dict:
    from chiplab.jobs import queue
    return queue.status(job_id)


@tool("Result of a finished job (the tool's own JSON answer).", {"job_id": "str"}, lane="inline")
def job_result(job_id: str) -> dict:
    from chiplab.jobs import queue
    s = queue.status(job_id, with_result=True)
    if s["state"] not in ("done", "failed", "timeout"):
        return {"job_id": job_id, "state": s["state"], "ready": False}
    return {"job_id": job_id, "state": s["state"], "ready": True, "result": s.get("result")}


@tool("Cancel a queued job (running jobs finish).", {"job_id": "str"}, lane="inline")
def cancel_job(job_id: str) -> dict:
    from chiplab.jobs import queue
    return queue.cancel(job_id)


@tool("List recent jobs (optionally one session's) and the load on each lane.", {"limit": "int (100)"}, lane="inline")
def list_jobs(limit: int = 100, session_id: str | None = None) -> dict:
    from chiplab.jobs import queue
    return {"jobs": queue.listing(session_id, limit), "lanes": queue.lane_load()}


@tool("Cache statistics: entries, hits, misses, bytes.", {}, lane="inline")
def cache_stats() -> dict:
    return cache.stats()


@tool("Fast pre-synthesis gate estimates for many designs (chipir/1 documents or design ids), labelled as "
      "estimates. Use it to rank candidates; only finalists need real synthesis. Optionally keep the best N.",
      {"designs": "list — chipir/1 dicts or design_id strings", "keep": "int — how many smallest to mark kept (optional)"},
      lane="inline")
def estimate_batch(designs: list, keep: int | None = None) -> dict:
    from chiplab.ir.estimate import estimate
    from chiplab.ir.schema import design_id
    ids, est = [], []
    for d in designs:
        if isinstance(d, str):
            d = json.loads((config.HOME / "designs" / d / "ir.json").read_text())
        ids.append(design_id(d)); est.append(estimate(d))
    order = sorted(range(len(ids)), key=lambda i: est[i]["gates_est"])
    kept = [ids[i] for i in order[:keep]] if keep else None
    return {"ids": ids, "gates_est": [e["gates_est"] for e in est], "features": est, "kept_ids": kept,
            "est_basis": est[0]["basis"] if est else None}


@tool("Synthesize many designs at once (fans out over the CPU lane). Returns job ids.",
      {"design_ids": "list[str]", "target": "str — generic|xc7|ice40"}, lane="inline")
def synthesize_batch(design_ids: list, target: str = "generic", session_id: str | None = None, run_id: str | None = None) -> dict:
    return submit_batch.__wrapped__("synthesize", [{"design_id": d, "target": target, **({"run_id": run_id} if run_id else {})}
                                                    for d in design_ids], session_id=session_id)


@tool("Ingest many models at once: each item is an ingest_model argument dict ({format, model|path|b64, name, ...}). "
      "They run in parallel on the CPU lane (start workers with `chiplab workers`). Returns job ids; with wait=true it "
      "waits and returns the design ids in the same order (null where an ingest failed).",
      {"models": "list[dict] — ingest_model arguments, one per model", "wait": "bool — wait for all and return design ids (false)",
       "wait_timeout": "int seconds to wait (900)"}, lane="inline")
def ingest_batch(models: list, wait: bool = False, wait_timeout: int = 900, session_id: str | None = None,
                 run_id: str | None = None) -> dict:
    import time
    from chiplab.jobs import queue
    args = [{**m, **({"run_id": run_id} if run_id else {})} for m in models]
    jobs = submit_batch.__wrapped__("ingest_model", args, session_id=session_id)
    out = {"job_ids": jobs["job_ids"], "n": jobs["n"], "lane": jobs["lane"], "candidates": jobs["n"]}
    if not wait:
        return out
    t0, results = time.time(), {}
    while len(results) < len(jobs["job_ids"]):
        for j in jobs["job_ids"]:
            if j not in results:
                s = queue.status(j, with_result=True)
                if s["state"] in ("done", "failed", "timeout", "cancelled"):
                    results[j] = s.get("result") or {"status": s["state"], "error": s.get("error")}
        if len(results) < len(jobs["job_ids"]):
            if time.time() - t0 > wait_timeout:
                out.update(status="timeout", error=f"timed out after {wait_timeout}s waiting for {len(jobs['job_ids']) - len(results)} "
                                                   f"ingest jobs (are workers running? `chiplab workers`)")
                break
            time.sleep(0.5)
    ids = [results.get(j, {}).get("design_id") if results.get(j, {}).get("status") == "ok" else None for j in jobs["job_ids"]]
    out.update(design_ids=ids, failed=[{"index": k, "job_id": j, "error": results.get(j, {}).get("error")}
                                       for k, (j, d) in enumerate(zip(jobs["job_ids"], ids)) if d is None])
    if out.get("status") != "timeout" and out["failed"]:
        out["status"] = "error" if len(out["failed"]) == len(ids) else "ok"
    return out


@tool("Bit-exact check many designs at once on the GPU lane. Returns job ids.",
      {"design_ids": "list[str]", "inputs": "str — random|val|vectors", "n": "int"}, lane="inline")
def simulate_batch(design_ids: list, inputs: str = "random", n: int = 100000, session_id: str | None = None,
                   run_id: str | None = None) -> dict:
    return submit_batch.__wrapped__("simulate", [{"design_id": d, "inputs": inputs, "n": n, "device": "auto",
                                                  **({"run_id": run_id} if run_id else {})} for d in design_ids],
                                    session_id=session_id)


@tool("Compile a chipir/1 document directly (no training batch): validates, emits Verilog, lints. Same as "
      "compile_verilog(ir=...).", {"ir": "dict — chipir/1"}, lane="cpu", cacheable=True)
def compile_ir(ir: dict) -> dict:
    return TOOLS["compile_verilog"]["fn"].__wrapped__(ir=ir)


def _unused():  # keep ToolError imported for plugins that extend this module
    return ToolError
