"""Scale sweep: every model in models/ through the lab's batch tools, largest first, results to results.json.

Per model, two designs: the default emitter and optimizer=alkaid (ingest-batch, all ingests in one batch). Then,
largest design first, per design: synthesize (submit-batch, so the synthesis time cap can be raised above the
900 s default), count-luts xc7 (submit-batch), map-to-process sky130 / gf180 / ihp (submit-batch), and once its
synthesis is done: simulate (simulate-batch, random inputs, bit-exact) and prove-equivalence golden=true
(submit-batch, per-attempt time cap --prove-timeout). Workers: the lab's own Huey workers (CHIPLAB_CPU_WORKERS).

Peak RAM: a sampler reads `ps` every --sample-s seconds and keeps, per design and step, the largest resident set
of the step's yosys process plus its yosys-abc children (and of yosys-abc runs the formal check starts directly,
matched by their working directory). Yosys's own end-of-run "MEM: ... peak" line is read from each log as well.
Processes left behind after a step ended (a yosys-abc whose yosys is gone, still running) are recorded as orphans.

results.json is rewritten after every finished job, so another reader sees the sweep as it progresses.

Usage (lab environment set: CHIPLAB_HOME, CHIPLAB_CONFIG, CHIPLAB_USER_DIR, CHIPLAB_CPU_WORKERS ...):
    python sweep.py --models models --out results.json [--only ternary_1k,q4_1k] [--prove-timeout 1200]
A rerun in the same lab home is served from the lab's result cache for every step that finished (status ok); the
cached answers keep their original timings. --skip-steps count_luts leaves out a step that is known to time out.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import threading
import time
from pathlib import Path

from chiplab import config
from chiplab.cli import _tools

TOOLS = _tools()
PDKS = ("sky130", "gf180", "ihp")
SIZE_ORDER = {"30k": 0, "10k": 1, "5k": 2, "1k": 3}
STYLE_ORDER = {"q4": 0, "ternary": 1}
TERMINAL = ("done", "failed", "timeout", "cancelled")


def call(name: str, /, **kw) -> dict:
    return TOOLS[name]["fn"](**kw)


# ------------------------------------------------------------------------------------------------ RAM sampler

class Sampler(threading.Thread):
    """Peak RSS (MB) per (design id, step) of yosys + its yosys-abc children; orphaned solvers."""

    LOG_RE = re.compile(r"-l (\S+/designs/([^/]+)/([^/]+)/(\S+?)\.log)")

    def __init__(self, every: float, limit_mb: float):
        super().__init__(daemon=True)
        self.every, self.stop, self.limit_mb = every, threading.Event(), limit_mb
        self.peak: dict[tuple[str, str], float] = {}
        self.orphans: dict[int, dict] = {}
        self.guard_kills: list[dict] = []
        self.alkaid_peak_mb = 0.0
        self.max_total_mb = 0.0

    def guard(self, owner: dict, sums: dict, total: float) -> None:
        """Keep the sweep under its memory budget: past limit_mb, kill the largest step (its yosys and children)."""
        if total <= self.limit_mb or not sums:
            return
        worst = max(sums, key=sums.get)
        pids = [p for p, k in owner.items() if k == worst]
        for p in pids:
            try:
                os.kill(p, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.guard_kills.append({"design_id": worst[0], "step": worst[1], "rss_mb": round(sums[worst]),
                                 "total_mb": round(total), "pids": pids, "t": time.time()})

    def _cwd(self, pid: int) -> str:
        try:
            out = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], capture_output=True, text=True,
                                 timeout=10).stdout
        except subprocess.TimeoutExpired:
            return ""
        return next((ln[1:] for ln in out.splitlines() if ln.startswith("n")), "")

    def sample(self) -> None:
        out = subprocess.run(["ps", "-Ao", "pid=,ppid=,rss=,etime=,command="], capture_output=True, text=True,
                             timeout=30).stdout
        procs = {}
        for ln in out.splitlines():
            p = ln.split(None, 4)
            if len(p) == 5:
                procs[int(p[0])] = (int(p[1]), int(p[2]) / 1024, p[3], p[4])
        keys, total = {}, 0.0
        for pid, (ppid, rss, et, cmd) in procs.items():
            exe = Path(cmd.split()[0]).name
            if exe == "yosys":
                m = self.LOG_RE.search(cmd)
                if m and str(config.HOME) in m.group(1):
                    keys[pid] = (m.group(2), f"{m.group(3)}/{m.group(4)}")
            if "chiplab.emit.alkaid_worker" in cmd:
                self.alkaid_peak_mb = max(self.alkaid_peak_mb, rss)
        owner = dict(keys)  # pid -> (design id, step) for every process the sweep's steps started
        for pid, (ppid, rss, et, cmd) in procs.items():
            exe = Path(cmd.split()[0]).name
            if exe != "yosys-abc" or pid in owner:
                continue
            up = ppid  # Yosys starts ABC as `sh -c yosys-abc ...`: walk up past the shell
            while up in procs and up not in keys and up != 1 and Path(procs[up][3].split()[0]).name == "sh":
                up = procs[up][0]
            if up in keys:
                owner[pid] = keys[up]
            elif up == 1:  # its yosys is gone; only ours (working directory inside this lab home) count
                if pid not in self.orphans:
                    cwd = self._cwd(pid)
                    if str(config.HOME) not in cwd:
                        continue
                    self.orphans[pid] = {"pid": pid, "cmd": cmd[:200], "cwd_in_home": cwd.split(str(config.HOME))[-1],
                                         "first_seen": time.time()}
                self.orphans[pid].update(last_seen=time.time(), etime=et, rss_mb=round(rss))
            else:
                cwd = self._cwd(pid)
                m = re.search(r"/designs/([^/]+)/(.+)$", cwd)
                if m and str(config.HOME) in cwd:
                    owner[pid] = (m.group(1), f"{m.group(2)}/yosys-abc")
        sums: dict[tuple[str, str], float] = {}
        for pid, k in owner.items():
            sums[k] = sums.get(k, 0.0) + procs[pid][1]
        for k, v in sums.items():
            self.peak[k] = max(self.peak.get(k, 0.0), v)
            total += v
        self.max_total_mb = max(self.max_total_mb, total)
        self.guard(owner, sums, total)

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                self.sample()
            except Exception:  # a failed sample must never stop the sweep
                pass
            self.stop.wait(self.every)


def yosys_log_peak(log: Path) -> float | None:
    if not log.exists():
        return None
    m = re.findall(r"MEM:\s*([\d.]+)\s*MB peak", log.read_text(errors="replace")[-4000:])
    return float(m[-1]) if m else None


# ------------------------------------------------------------------------------------------------ sweep

class Sweep:
    def __init__(self, a: argparse.Namespace):
        self.a = a
        self.models = []
        for p in sorted(Path(a.models).glob("*.json")):
            if p.name == "index.json":
                continue
            d = json.loads(p.read_text())
            if a.only and d["meta"]["name"] not in a.only.split(","):
                continue
            self.models.append(d)
        self.models.sort(key=lambda d: (SIZE_ORDER[d["meta"]["size"]], STYLE_ORDER[d["meta"]["style"]]))
        self.jobs: dict[str, dict] = {}       # job id -> {kind, design key, ...}
        self.designs: dict[str, dict] = {}    # key "<name>/<variant>" -> record
        self.t0 = time.time()
        self.sampler = Sampler(a.sample_s, a.rss_limit_gb * 1024)
        self.skip = set(filter(None, a.skip_steps.split(",")))
        self.proof_wait: list[str] = []      # design keys whose proof waits for a free proof slot

    def key_order(self, key: str) -> tuple:
        name, var = key.split("/")
        meta = self.designs[key]["model"]
        return (SIZE_ORDER[meta["size"]], STYLE_ORDER[meta["style"]], var != "default")

    def track(self, job_ids: list[str], kind: str, keys: list[str], extra: list[dict] | None = None) -> None:
        for i, (j, k) in enumerate(zip(job_ids, keys)):
            self.jobs[j] = {"kind": kind, "key": k, "submitted": time.time(), **((extra or [{}] * len(keys))[i])}

    def submit_hw(self, key: str) -> None:
        d = self.designs[key]["design_id"]
        r = call("submit_batch", tool="synthesize", args_list=[{"design_id": d, "target": "generic",
                                                                "timeout": self.a.synth_timeout}])
        self.track(r["job_ids"], "synthesize", [key])
        if "count_luts" not in self.skip:
            r = call("submit_batch", tool="count_luts", args_list=[{"design_id": d, "family": "xc7"}])
            self.track(r["job_ids"], "count_luts", [key])
        r = call("submit_batch", tool="map_to_process", args_list=[{"design_id": d, "pdk": p} for p in PDKS])
        self.track(r["job_ids"], "map_to_process", [key] * len(PDKS), [{"pdk": p} for p in PDKS])

    def submit_checks(self, key: str) -> None:
        d = self.designs[key]["design_id"]
        r = call("simulate_batch", design_ids=[d], inputs="random", n=self.a.sim_n)
        self.track(r["job_ids"], "simulate", [key])
        self.proof_wait.append(key)

    def submit_proofs(self) -> None:
        """At most --prove-concurrency proofs at once (the golden miter needs GBs on large chips), largest first."""
        busy = sum(1 for j in self.jobs.values() if j["kind"] == "prove_equivalence" and not j.get("finished"))
        self.proof_wait.sort(key=lambda k: -(self.designs[k].get("gates") or 0))
        while self.proof_wait and busy < self.a.prove_concurrency:
            key = self.proof_wait.pop(0)
            r = call("submit_batch", tool="prove_equivalence",
                     args_list=[{"design_id": self.designs[key]["design_id"], "golden": True,
                                 "timeout": self.a.prove_timeout}])
            self.track(r["job_ids"], "prove_equivalence", [key])
            busy += 1

    def on_done(self, jid: str, st: dict) -> None:
        job = self.jobs[jid]
        key, kind = job["key"], job["kind"]
        rec = self.designs[key]
        res = st.get("result") or {"status": st["state"], "error": st.get("error")}
        wall = (res.get("cost") or {}).get("wall_s")
        step = {"state": st["state"], "status": res.get("status"), "wall_s": wall, "run_s": st.get("run_s"),
                "queued_s": st.get("queued_s"), "cached": bool(res.get("cached"))}
        if res.get("status") != "ok":
            step["error"] = str(res.get("error") or res.get("detail") or "")[-1500:]
        if kind == "ingest":
            if res.get("status") == "ok":
                rec["design_id"] = res["design_id"]
                rec["verilog_lines"] = res.get("lines")
                rec["lint_ok"] = (res.get("lint") or {}).get("ok")
                opt = (res.get("ports") or {}).get("optimizer")
                if opt:
                    rec["alkaid_nodes"] = opt.get("nodes")
            rec["steps"]["ingest"] = step
        elif kind == "synthesize":
            if res.get("status") == "ok":
                m = res["metrics"]
                rec.update(gates=m["gates"], depth=m["depth"], transistors_est=m.get("transistors_est"),
                           cells_by_type=res.get("cells_by_type"), synth_yosys_s=res.get("seconds"))
                rec["gates_per_weight"] = round(m["gates"] / rec["model"]["weights"], 2)
                rec["gates_per_nonzero_weight"] = round(m["gates"] / rec["model"]["nonzero_weights"], 2)
            rec["steps"]["synthesize"] = step
        elif kind == "count_luts":
            if res.get("status") == "ok":
                m = res["metrics"]
                rec.update(luts_xc7=m.get("luts"), carry4_xc7=m.get("carry4"), muxf_xc7=m.get("muxf"))
            rec["steps"]["count_luts"] = step
        elif kind == "map_to_process":
            p = job["pdk"]
            if res.get("status") == "ok":
                m = res["metrics"]
                rec.setdefault("area_um2", {})[p] = m["area_um2"]
                rec.setdefault("gate_equivalents", {})[p] = m["gate_equivalents"]
                rec.setdefault("std_cells", {})[p] = m["std_cells"]
                if m.get("tt_tiles_est"):
                    rec["tt_tiles_est_lab"] = m["tt_tiles_est"]
            rec["steps"][f"map_{p}"] = step
        elif kind == "simulate":
            if res.get("status") == "ok":
                rec.update(bit_exact=res.get("bit_exact"), sim_n=res.get("n"), sim_device=res.get("device"),
                           sim_pairs=res.get("pairs"))
            rec["steps"]["simulate"] = step
        elif kind == "prove_equivalence":
            rec["proof"] = {k: res.get(k) for k in ("proved", "against", "method", "seconds", "verification_level")}
            rec["proof"]["nodes"] = (res.get("nodes") or [])[:3]
            if res.get("golden_attempt"):
                ga = res["golden_attempt"]
                rec["proof"]["golden_attempt"] = {"proved": ga.get("proved"), "seconds": ga.get("seconds"),
                                                  "n_nodes_tried": len(ga.get("nodes") or [])}
            rec["proof"]["detail_tail"] = str(res.get("detail") or res.get("error") or "")[-600:]
            rec["steps"]["prove_equivalence"] = step
        if kind == "synthesize":
            if res.get("status") == "ok":
                self.submit_checks(key)
            else:
                rec["steps"]["simulate"] = {"state": "not run", "reason": "synthesis did not finish"}
                rec["steps"]["prove_equivalence"] = {"state": "not run", "reason": "synthesis did not finish"}

    def write(self, final: bool = False) -> None:
        S = self.sampler
        for key, rec in self.designs.items():
            did = rec.get("design_id")
            if not did:
                continue
            ram = {f"{d_step}": round(v) for (d, d_step), v in S.peak.items() if d == did}
            rec["peak_rss_mb_sampled"] = ram
            dd = config.HOME / "designs" / did
            logs = {"synth/synth_generic": dd / "synth" / "synth_generic.log",
                    "luts_xc7/luts_xc7": dd / "luts_xc7" / "luts_xc7.log",
                    **{f"pdk_{p}/map_{p}": dd / f"pdk_{p}" / f"map_{p}.log" for p in PDKS}}
            rec["yosys_mem_peak_mb"] = {k: yosys_log_peak(v) for k, v in logs.items() if v.exists()}
        open_jobs = sum(1 for j in self.jobs.values() if not j.get("finished"))
        out = {"schema": "scale/1", "updated": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "final": final,
               "elapsed_s": round(time.time() - self.t0), "open_jobs": open_jobs,
               "settings": {"cpu_workers": config.lanes()["cpu"], "prove_timeout_s": self.a.prove_timeout,
                            "synth_timeout_s": self.a.synth_timeout, "sim_n": self.a.sim_n},
               "max_concurrent_yosys_rss_mb": round(S.max_total_mb), "alkaid_worker_peak_rss_mb": round(S.alkaid_peak_mb),
               "orphaned_solvers": list(S.orphans.values()), "rss_guard_kills": S.guard_kills,
               "rss_limit_gb": self.a.rss_limit_gb,
               "designs": [self.designs[k] for k in sorted(self.designs, key=self.key_order)]}
        tmp = Path(self.a.out).with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=1, default=str))
        tmp.replace(self.a.out)

    def run(self) -> None:
        from chiplab.jobs import queue
        from chiplab.mcp_server import start_workers
        self.sampler.start()
        procs = start_workers()
        try:
            items, keys = [], []
            for var in ("default", "alkaid"):
                for d in self.models:
                    meta = d["meta"]
                    key = f"{meta['name']}/{var}"
                    self.designs[key] = {"key": key, "name": meta["name"], "variant": var, "model": meta, "steps": {}}
                    items.append({"format": "intnn", "model": d["model"], "name": meta["name"],
                                  **({"optimizer": "alkaid"} if var == "alkaid" else {})})
                    keys.append(key)
            r = call("ingest_batch", models=items)
            self.track(r["job_ids"], "ingest", keys)
            pending_default = {k for k in keys if k.endswith("/default")}
            while any(not j.get("finished") for j in self.jobs.values()) or self.proof_wait:
                changed = False
                self.submit_proofs()
                for jid, job in list(self.jobs.items()):
                    if job.get("finished"):
                        continue
                    st = queue.status(jid, with_result=True)
                    if st["state"] in TERMINAL:
                        job["finished"] = time.time()
                        self.on_done(jid, st)
                        changed = True
                        if job["kind"] == "ingest" and job["key"].endswith("/alkaid") and \
                                self.designs[job["key"]].get("design_id"):
                            self.submit_hw(job["key"])
                        if job["kind"] == "ingest" and pending_default is not None:
                            pending_default.discard(job["key"])
                        print(json.dumps({"t": round(time.time() - self.t0), "job": job["kind"], "key": job["key"],
                                          "pdk": job.get("pdk"), "state": st["state"],
                                          "status": (st.get("result") or {}).get("status")}), flush=True)
                # every default design is ingested in seconds: submit their hardware jobs together, largest first
                if pending_default is not None and not pending_default:
                    for k in sorted((k for k in keys if k.endswith("/default") and self.designs[k].get("design_id")),
                                    key=self.key_order):
                        self.submit_hw(k)
                    pending_default = None
                if changed:
                    self.write()
                time.sleep(2)
        finally:
            self.sampler.stop.set()
            self.write(final=True)
            for p in procs:
                p.terminate()
            for p in procs:
                try:
                    p.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    p.kill()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--prove-timeout", type=int, default=1200)
    ap.add_argument("--synth-timeout", type=int, default=3600)
    ap.add_argument("--sim-n", type=int, default=100000)
    ap.add_argument("--sample-s", type=float, default=2.0)
    ap.add_argument("--prove-concurrency", type=int, default=2)
    ap.add_argument("--rss-limit-gb", type=float, default=64.0)
    ap.add_argument("--skip-steps", default="", help="comma list of steps not to submit, e.g. count_luts (a rerun)")
    Sweep(ap.parse_args()).run()


if __name__ == "__main__":
    main()
