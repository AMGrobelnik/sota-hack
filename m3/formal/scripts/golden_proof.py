"""Fast golden proof for a chiplab design: gate netlist == independent golden model of the WHOLE IR, every input.

usage: golden_proof.py <design_id> [--timeout S] [--out DIR] [--engines cec,bitwuzla] [--split] [--mutants] [--direct]
  e.g. bash env.sh ../../../chiplab/.venv/bin/python golden_proof.py 765fa47586bd --split --mutants --out /tmp/g

Recipe ("chain", whole-design proofs all run in parallel, no range assumptions anywhere):
  P1  production RTL (design.v) == golden model of the whole IR (emit/golden.py), for all 2^n input values.
      Engines race on the same miter, first conclusive answer wins (--engines):
      cec      both sides lowered with `techmap` (no alumacc/maccmap), so each `a + b + c` stays a ripple-adder chain
               in source order; the golden and the production emitter add the same terms in the same order, so the
               partial sums are equal signals and ABC `&cec` (simulation + SAT sweeping) merges them one by one.
      iprove   the same techmapped miter, ABC `iprove` (rewriting, fraiging and SAT on the single miter output);
               fastest on the 3-head chip, where &cec spends minutes on the 2-of-3 vote cone.
      bitwuzla the miter as a SymbiYosys assertion, word-level SMT (smtbmc bitwuzla), BMC depth 1 (no state).
      --split: one P1 miter per output port (that port's cone), all in parallel.
  P2  gate netlist (synth/gates.v) == production RTL: the lab's own proof B (verify/formal.py `_blif` + ABC `cec`).
  P1 and P2 together: gates == golden for every input (equality is transitive; both are full input-space proofs).
--direct: also try the one-step miter golden vs gates.v (the lab's synthesis reshapes the adders, so this is
          the slow, structurally dissimilar case; reported for comparison).
--mutants: soundness self-test. Three mutated IRs (one weight sign flipped, one bias +1, the final threshold +1)
          must each come back NOT equivalent with the same recipe; a recipe that "proves" a mutant is broken.

Prints one JSON object; also appended to OUT/results.jsonl. Uses chiplab unchanged (emit_golden, verify.formal),
plus a local fix for emit_golden's port widths (a 64-bit-wide port is corrupted by its "[63:0]" rewrite; see
../proposed/formal.patch). Run with the chiplab venv python and CHIPLAB_USER_DIR / CHIPLAB_CONFIG set.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import re
import signal
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from chiplab import config
from chiplab.config import oss_bin
from chiplab.emit.golden import emit_golden
from chiplab.hw.yosys import SynthError
from chiplab.verify.formal import _blif, _cec


def golden_fixed(ir: dict, module: str, info: dict) -> str:
    """emit_golden with the port declarations restored to their true widths (works around the [63:0] rewrite)."""
    text = emit_golden(ir, module, info)
    ports = [("input", p["name"], p["lanes"] * p["bits"]) for p in ir["inputs"]]
    ports += [("output", o["name"], o["lanes"] * o["bits"]) for o in info["outputs"]]
    for kind, name, w in ports:
        text = re.sub(rf"(\n  {kind} wire )\[\d+:0\] {name}(,?\n)", rf"\g<1>[{w - 1}:0] {name}\g<2>", text, count=1)
    return text


class Race:
    """Processes of one portfolio check; the first conclusive engine stops (kills) the others."""

    def __init__(self) -> None:
        self.stop, self.procs, self.lock = threading.Event(), [], threading.Lock()

    def run(self, cmd: list[str], cwd: Path, timeout: int, log: str) -> tuple[int | None, str]:
        if self.stop.is_set():
            return None, "stopped"
        p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             start_new_session=True)
        with self.lock:
            self.procs.append(p)
        try:
            out, rc = p.communicate(timeout=timeout)[0], p.returncode
        except subprocess.TimeoutExpired:
            self.kill(p)
            out, rc = f"TIMEOUT after {timeout}s", None
        if self.stop.is_set() and rc != 0:
            out, rc = out + "\nstopped: another engine finished first", None
        (cwd / log).write_text(out)
        return rc, out

    @staticmethod
    def kill(p: subprocess.Popen) -> None:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        p.wait()

    def finish(self) -> None:
        self.stop.set()
        with self.lock:
            for p in self.procs:
                if p.poll() is None:
                    self.kill(p)


def run(cmd: list[str], cwd: Path, timeout: int, log: str, race: Race | None = None) -> tuple[int | None, str]:
    return (race or Race()).run(cmd, cwd, timeout, log)


def verdict(out: str) -> bool | None:
    """ABC's final word: last 'Networks are ...' line, or a CEX for the miter output."""
    lines = [ln for ln in out.splitlines() if "Networks are" in ln or "was asserted" in ln]
    if not lines:
        return None
    last = lines[-1].lower()
    if "not equivalent" in last or "was asserted" in last:
        return False
    if "networks are equivalent" in last:
        return True
    return None  # UNDECIDED


def iprove_verdict(out: str) -> bool | None:
    """ABC iprove on a single-output miter: UNSATISFIABLE = the miter never fires = equivalent; SATISFIABLE = CEX."""
    last = [ln.strip() for ln in out.splitlines() if "SATISFIABLE" in ln][-1:]
    if not last:
        return None
    return True if last[0].startswith("UNSATISFIABLE") else (False if last[0].startswith("SATISFIABLE") else None)


def eng_cec(cwd: Path, gtop: str, itop: str, timeout: int, race: Race, prep: str = "techmap",
            abc: str = "cec") -> dict:
    """Miter gold vs impl lowered by `prep` (techmap keeps adder chains in source order), then ABC on it:
    abc='cec' runs `&cec -m` (SAT sweeping), abc='iprove' runs `iprove` (rewriting + fraiging + SAT on the miter)."""
    low = "techmap\nopt -fast\n" if prep == "techmap" else "synth -flatten -noabc -top miter\n"
    aig = f"miter_{abc}.aig"
    (cwd / f"miter_{abc}.ys").write_text(
        f"read_verilog gold.v\nread_verilog impl.v\nproc\nopt_clean\nmiter -equiv -flatten {gtop} {itop} miter\n"
        f"hierarchy -top miter\nflatten\n{low}aigmap\nopt_clean\nwrite_aiger -zinit {aig}\n")
    t0 = time.time()
    rc, out = race.run([oss_bin("yosys"), "-q", "-s", f"miter_{abc}.ys"], cwd, timeout, f"miter_{abc}.log")
    t_miter = time.time() - t0
    if rc != 0:
        return {"proved": None, "error": out[-400:], "seconds": round(t_miter, 2)}
    left = max(5, int(timeout - t_miter))
    cmd = f"read_aiger {aig}; print_stats; " + ("&get; &cec -m" if abc == "cec" else "iprove")
    rc, out = race.run([oss_bin("yosys-abc"), "-c", cmd], cwd, left, f"abc_{abc}.log")
    v = (verdict(out) if abc == "cec" else iprove_verdict(out)) if rc is not None else None
    return {"proved": v, "seconds": round(time.time() - t0, 2),
            "miter_s": round(t_miter, 2), "abc_s": round(time.time() - t0 - t_miter, 2)}


def eng_iprove(cwd: Path, gtop: str, itop: str, timeout: int, race: Race) -> dict:
    return eng_cec(cwd, gtop, itop, timeout, race, abc="iprove")


def eng_sby(cwd: Path, gtop: str, itop: str, timeout: int, race: Race, solver: str = "bitwuzla") -> dict:
    """Same miter as a SymbiYosys assertion, word-level SMT (smtbmc) with `solver`; depth 1 = all inputs (no state)."""
    (cwd / "eq.sby").write_text(
        f"[options]\nmode bmc\ndepth 1\n\n[engines]\nsmtbmc {solver}\n\n[script]\nread_verilog gold.v\n"
        f"read_verilog impl.v\nproc\nopt_clean\nmiter -equiv -flatten -make_assert {gtop} {itop} miter\n"
        f"hierarchy -top miter\nflatten\nopt -fast\n\n[files]\ngold.v\nimpl.v\n")
    t0 = time.time()
    rc, out = race.run([oss_bin("sby"), "-f", "-d", f"sby_{solver}", "eq.sby"], cwd, timeout, f"sby_{solver}.log")
    v = True if "DONE (PASS" in out else (False if "DONE (FAIL" in out else None)
    return {"proved": v if rc is not None or v is not None else None, "seconds": round(time.time() - t0, 2)}


ENGINES = {"cec": eng_cec, "iprove": eng_iprove, "bitwuzla": eng_sby}


def miter_cec(gold_v: str, impl: Path, gtop: str, itop: str, cwd: Path, timeout: int, extra_v: str = "",
              engines: tuple[str, ...] = ("cec",)) -> dict:
    """gold vs impl on every input. Several engines race in parallel; the first conclusive answer wins."""
    cwd.mkdir(parents=True, exist_ok=True)
    (cwd / "gold.v").write_text(gold_v)
    (cwd / "impl.v").write_text(impl.read_text() + extra_v)
    race, t0 = Race(), time.time()
    with ThreadPoolExecutor(max_workers=len(engines)) as ex:
        futs = {ex.submit(ENGINES[e], cwd, gtop, itop, timeout, race): e for e in engines}
        res = {}
        for f in as_completed(futs):
            res[futs[f]] = f.result()
            if res[futs[f]]["proved"] is not None:
                race.finish()
    win = next((e for e in engines if res[e]["proved"] is not None), None)
    return {"proved": res[win]["proved"] if win else None, "engine": win, "seconds": round(time.time() - t0, 2),
            "engines": res}


def proof_b(rtl: Path, gate: Path, top: str, cwd: Path, timeout: int) -> dict:
    """The lab's proof B unchanged: gates == production RTL (ABC cec on two BLIFs)."""
    cwd.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        r = _blif(rtl, top, "rtl", cwd, timeout, synth=True)
        g = _blif(gate, top, "gate", cwd, timeout, synth=False)
        ok, _ = _cec(r, g, cwd, timeout)
    except SynthError as e:
        return {"proved": None, "error": str(e)[-300:], "seconds": round(time.time() - t0, 2)}
    return {"proved": ok, "seconds": round(time.time() - t0, 2)}


def mutants(ir: dict) -> dict[str, dict]:
    """Three single-point mutations of the IR, each of which changes the function (checked by the proof failing)."""
    out = {}
    mv = next(n for n in ir["nodes"] if n["op"] == "matvec")
    m = copy.deepcopy(ir); nd = next(n for n in m["nodes"] if n["id"] == mv["id"])
    j, k = next((j, k) for j, row in enumerate(nd["W"]) for k, w in enumerate(row) if w)
    nd["W"][j][k] = -nd["W"][j][k]; out[f"weight_sign_{mv['id']}_{j}_{k}"] = m
    m = copy.deepcopy(ir); nd = next(n for n in m["nodes"] if n["id"] == mv["id"])
    nd["b"] = [v + (1 if i == j else 0) for i, v in enumerate(nd.get("b") or [0] * len(nd["W"]))]
    out[f"bias_plus1_{mv['id']}_{j}"] = m
    cmp_ = [n for n in ir["nodes"] if n["op"] == "cmp" and "t" in n]
    if cmp_:
        m = copy.deepcopy(ir); nd = next(n for n in m["nodes"] if n["id"] == cmp_[-1]["id"])
        nd["t"] = nd["t"] + 1 if isinstance(nd["t"], int) else [t + 1 for t in nd["t"]]
        out[f"threshold_plus1_{cmp_[-1]['id']}"] = m
    return out


def p1_jobs(ir: dict, info: dict, rtl: Path, base: Path, name: str, split: bool, timeout: int,
            engines: tuple[str, ...]) -> dict:
    """P1 (RTL == golden of `ir`) as one whole miter, or one miter per output port (its cone) when split."""
    top = info["top"]
    if not split:
        return {name: lambda: miter_cec(golden_fixed(ir, "gold_top", info), rtl, "gold_top", top,
                                        base / name.lower(), timeout, engines=engines)}
    jobs = {}
    for o in info["outputs"]:
        ir1 = dict(ir, outputs=[x for x in ir["outputs"] if x["name"] == o["name"]])
        info1 = dict(info, outputs=[o])
        ins = [f"input wire [{p['lanes'] * p['bits'] - 1}:0] {p['name']}" for p in ir["inputs"]]
        conns = [f".{p['name']}({p['name']})" for p in ir["inputs"]]
        conns += [f".{x['name']}({x['name'] if x['name'] == o['name'] else ''})" for x in info["outputs"]]
        wrap = (f"\nmodule wrap_top ({', '.join(ins)}, output wire [{o['lanes'] * o['bits'] - 1}:0] {o['name']});\n"
                f"  {top} u ({', '.join(conns)});\nendmodule\n")
        jobs[f"{name}[{o['name']}]"] = (lambda ir1=ir1, info1=info1, wrap=wrap, o=o: miter_cec(
            golden_fixed(ir1, "gold_top", info1), rtl, "gold_top", "wrap_top", base / f"{name.lower()}_{o['name']}",
            timeout, extra_v=wrap, engines=engines))
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", type=Path, default=Path("golden_runs"))
    ap.add_argument("--mutants", action="store_true")
    ap.add_argument("--direct", action="store_true")
    ap.add_argument("--engines", default="cec,bitwuzla", help="comma list from: " + ",".join(ENGINES))
    ap.add_argument("--split", action="store_true", help="one P1 miter per output port (cone), all in parallel")
    a = ap.parse_args()
    d = config.HOME / "designs" / a.design
    ir = json.loads((d / "ir.json").read_text())
    info = json.loads((d / "port.json").read_text())
    gate = Path(json.loads((d / "synth.json").read_text())["gate_verilog"])
    rtl, top = d / "design.v", info["top"]
    base = a.out / a.design
    gold_all = golden_fixed(ir, "gold_top", info)
    eng = tuple(a.engines.split(","))
    jobs = {"P2_gates_eq_rtl": lambda: proof_b(rtl, gate, top, base / "p2_gates_rtl", a.timeout)}
    jobs.update(p1_jobs(ir, info, rtl, base, "P1_rtl_eq_golden", a.split, a.timeout, eng))
    if a.direct:
        jobs["direct_gates_eq_golden"] = lambda: miter_cec(gold_all, gate, "gold_top", top,
                                                           base / "direct_gates_golden", a.timeout, engines=eng)
    if a.mutants:
        for name, mir in mutants(ir).items():
            # the production RTL stays the real one; only the golden model is mutated
            jobs.update(p1_jobs(mir, info, rtl, base, f"mutant_{name}", a.split, a.timeout, eng))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = {k: ex.submit(f) for k, f in jobs.items()}
        res = {k: f.result() for k, f in futs.items()}
    p1s = [v["proved"] for k, v in res.items() if k.startswith("P1_")]
    p1 = True if all(v is True for v in p1s) else (False if False in p1s else None)
    p2 = res["P2_gates_eq_rtl"]["proved"]
    golden = True if (p1 is True and p2 is True) else (False if False in (p1, p2) else None)
    muts = {k.split("[")[0] for k in res if k.startswith("mutant_")}
    # a mutant is caught when at least one of its (per-output) checks finds a counterexample
    mut_ok = all(any(v["proved"] is False for k, v in res.items() if k.split("[")[0] == m) for m in muts) \
        if a.mutants else None
    r = {"design": a.design, "golden_proved": golden, "wall_s": round(time.time() - t0, 2), "steps": res,
         "mutants_all_caught": mut_ok, "machine": f"{platform.machine()} {platform.system()} (this run)",
         "tools": "yosys + yosys-abc from the lab's OSS CAD Suite"}
    line = json.dumps(r)
    print(json.dumps(r, indent=1))
    base.mkdir(parents=True, exist_ok=True)
    with (a.out / "results.jsonl").open("a") as f:
        f.write(line + "\n")


if __name__ == "__main__":
    main()
