"""Put the final (trained-on-all-AFDB) designs through the chip lab: compile, synthesise, map to sky130 / gf180 /
IHP, bit-exact simulation on the real held-out windows, formal proof, streaming wrapper + sequential proof,
streaming RTL simulation, iCE40 bitstream, and the full sequential area (window registers included).

Usage: python -I -m afchip.chip_run --models <final_models.json> --afdb <dir> --ltafdb <dir> --out <dir>
  [--only key ...] ; needs CHIPLAB_* in the environment and --chiplab <bin dir>.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from afchip.chip_ir import build_ir
from afchip.features import int_features, set_featureset
from afchip.models import predict
from afchip.run_eval import DASH_EXCLUDED, load_db, windows

PDKS = ("sky130", "gf180", "ihp")


def call(bin_dir: Path, tool: str, args: dict, out: Path, timeout: int) -> dict:
    """One lab call in its own process group; on timeout the whole group is killed."""
    out.parent.mkdir(parents=True, exist_ok=True)
    argf = out.with_suffix(".args.json")
    argf.write_text(json.dumps(args))
    t0 = time.time()
    p = subprocess.Popen([str(bin_dir / "chiplab"), tool, "--json-file", str(argf)], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, start_new_session=True, text=True)
    try:
        so, se = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        r = {"status": "timeout", "tool": tool, "seconds": time.time() - t0}
        out.write_text(json.dumps(r, indent=1))
        return r
    try:
        r = json.loads(so)
    except json.JSONDecodeError:
        r = {"status": "error", "stdout": so[-2000:], "stderr": se[-2000:]}
    argf.unlink(missing_ok=True)
    out.write_text(json.dumps(r, indent=1))
    return r


def seqmap(bin_dir: Path, stream_v: str, top: str, wd: Path, pdk: str, timeout: int) -> dict:
    helper = Path(__file__).with_name("lab_seqmap.py")
    p = subprocess.Popen([str(bin_dir / "python"), "-I", str(helper), stream_v, top, str(wd), pdk],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, text=True,
                         cwd=str(wd.parent))
    try:
        so, se = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        return {"status": "timeout"}
    try:
        return json.loads(so.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"status": "error", "stderr": se[-2000:]}


def run_design(key: str, model: dict, data: dict, bin_dir: Path, out: Path) -> dict:
    n = int(key.rsplit("_n", 1)[1])
    d = out / key
    d.mkdir(parents=True, exist_ok=True)
    ir = build_ir(model, n, f"af_{key}")
    (d / "ir.json").write_text(json.dumps(ir))
    res: dict = {"key": key, "n": n, "model": model}
    c = call(bin_dir, "compile-ir", {"ir": ir}, d / "compile.json", 300)
    if c.get("status") != "ok":
        res["error"] = c
        return res
    did = c["design_id"]
    res["design_id"] = did
    res["synth"] = call(bin_dir, "synthesize", {"design_id": did}, d / "synth.json", 900)
    res["map"] = {p: call(bin_dir, "map-to-process", {"design_id": did, "pdk": p}, d / f"map_{p}.json", 900) for p in PDKS}
    # bit-exact on the actual held-out inputs (LTAFDB windows; the final model never saw them) and on AFDB
    res["sim"] = {}
    for db in ("ltafdb", "afdb"):
        X = data[db][n]
        exp = predict(int_features(X), model)
        res["sim"][db] = call(bin_dir, "simulate", {"design_id": did, "inputs": "vectors", "vectors": {"rr": X.tolist()},
                                                    "expected": exp.tolist(), "device": "numpy"}, d / f"sim_{db}.json", 1800)
        res["sim"][db]["expected_af"] = int(exp.sum())
    res["prove"] = call(bin_dir, "prove-equivalence", {"design_id": did, "golden": True, "timeout": 600}, d / "prove.json", 1500)
    st = call(bin_dir, "compile-stream", {"design_id": did, "tt": False}, d / "stream.json", 300)
    res["stream"] = st
    if st.get("status") == "ok":
        res["seqmap"] = {p: seqmap(bin_dir, st["verilog"], st["top"], d / f"seqmap_{p}", p, 900) for p in PDKS}
    call(bin_dir, "compile-stream", {"design_id": did, "tt": True}, d / "stream_tt.json", 300)
    res["prove_seq"] = call(bin_dir, "prove-sequential", {"design_id": did, "timeout": 600}, d / "prove_seq.json", 900)
    Xs = data["ltafdb"][n][:200]
    es = predict(int_features(Xs), model)
    res["rtl_sim"] = call(bin_dir, "rtl-simulate", {"design_id": did, "vectors": {"rr": Xs.tolist()},
                                                    "expected": {"af": [[int(v)] for v in es]}}, d / "rtl_sim.json", 1200)
    res["bitstream"] = call(bin_dir, "bitstream", {"design_id": did}, d / "bitstream.json", 900)
    res["vlevel"] = call(bin_dir, "verification-level", {"design_id": did}, d / "vlevel.json", 120)
    (d / "summary.json").write_text(json.dumps(res, indent=1, default=str))
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", type=Path, required=True)
    ap.add_argument("--afdb", type=Path, required=True)
    ap.add_argument("--ltafdb", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--chiplab", type=Path, required=True)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--features", default="v2", choices=["v1", "v2"])
    a = ap.parse_args()
    set_featureset(a.features)
    models = json.loads(a.models.read_text())
    keys = a.only or list(models)
    ns = sorted({int(k.rsplit("_n", 1)[1]) for k in keys})
    afdb = load_db(a.afdb, "qrs", DASH_EXCLUDED)
    lt = load_db(a.ltafdb, "atr", set())
    data = {"afdb": {n: windows(afdb, n)[0] for n in ns}, "ltafdb": {n: windows(lt, n)[0] for n in ns}}
    for k in keys:
        t0 = time.time()
        r = run_design(k, models[k], data, a.chiplab, a.out)
        g = r.get("synth", {}).get("metrics", {}).get("gates")
        be = {db: r.get("sim", {}).get(db, {}).get("bit_exact") for db in ("ltafdb", "afdb")}
        print(f"{k}: design {r.get('design_id')} gates {g} bit_exact {be} prove {r.get('prove', {}).get('status')} "
              f"seq {r.get('prove_seq', {}).get('status')} rtl {r.get('rtl_sim', {}).get('status')} {time.time() - t0:.0f}s", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
