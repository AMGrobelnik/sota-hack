"""Hardware and verification tools beyond the core set: formal proof, process mapping, timing/power, packaging,
cost. Registered into tools.TOOLS on import."""
from __future__ import annotations

import json

from chiplab import log
from chiplab.tools import _design_dir, _ensure_synth, tool


@tool("Verification level 2: prove the gate netlist equals the model for every possible input (ABC equivalence "
      "check against an independent golden model of the IR; falls back to proving synthesis if inconclusive).",
      {"design_id": "str", "timeout": "int seconds per proof attempt (600)",
       "golden": "bool — also try the proof against the independent golden model (small chips; slow on large ones)"},
      lane="cpu", cacheable=True)
def prove_equivalence(design_id: str, timeout: int = 600, golden: bool = False) -> dict:
    from chiplab.verify.formal import prove
    d = _design_dir(design_id)
    syn = _ensure_synth(design_id)
    ir = json.loads((d / "ir.json").read_text()); info = json.loads((d / "port.json").read_text())
    r = prove(ir, info, __import__("pathlib").Path(syn["gate_verilog"]), d / "design.v", d / "formal", timeout, golden=golden)
    (d / "formal.json").write_text(json.dumps(r))
    log.event("check", design_id=design_id, formal=r["proved"], against=r["against"])
    return {"design_id": design_id, **r}


@tool("Map a design onto a real process's standard cells: area in µm², gate-equivalents (area / NAND2), cell "
      "counts and an estimate of Tiny Tapeout tiles.", {"design_id": "str", "pdk": "str — sky130|gf180|ihp"}, lane="cpu", cacheable=True)
def map_to_process(design_id: str, pdk: str = "sky130") -> dict:
    from chiplab.hw.pdk import map_to_process as _map
    d = _design_dir(design_id)
    info = json.loads((d / "port.json").read_text())
    r = _map(d / "design.v", info["top"], d / f"pdk_{pdk}", pdk)
    (d / f"pdk_{pdk}.json").write_text(json.dumps(r))
    log.event("stage", stage="map_to_process", design_id=design_id, pdk=pdk, area_um2=r["area_um2"])
    return {"design_id": design_id, "hw_kind": "synthesized", "metrics": {k: r[k] for k in ("area_um2", "gate_equivalents",
            "std_cells", "tt_tiles_est")}, **{k: r[k] for k in ("pdk", "library", "note", "seconds")},
            "files": [r["mapped_netlist"]]}


# ------------------------------------------------------------------------------------------------ model ingest

def _store_ir(ir: dict, meta: dict | None = None, optimizer: str | None = None) -> dict:
    """Validate, emit, lint and store an IR as a design; returns compile_verilog's answer."""
    from chiplab.tools import TOOLS
    res = TOOLS["compile_verilog"]["fn"].__wrapped__(ir=ir, optimizer=optimizer)
    if meta:
        d = _design_dir(res["design_id"])
        old = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
        (d / "meta.json").write_text(json.dumps({**old, **meta}))
    return res


def _read_blob(model=None, path: str | None = None, b64: str | None = None):
    import base64
    if model is not None:
        return model
    if b64 is not None:
        return base64.b64decode(b64)
    if path is not None:
        from pathlib import Path
        return Path(path).read_bytes()
    raise ValueError("give model (JSON), path (file on this machine) or b64 (file content)")


@tool("Bring a trained model into the lab and compile it to a chip design. Formats: chipir (chipir/1 JSON), intnn "
      "(integer-network params: cfg/W1/b1/shift/W2/b2/amax or the multi-layer form), xgboost_json (an XGBoost model "
      "saved as JSON + w_feature/w_tree quantisation, converted via TreeLUT), torchlogix (a saved torchlogix module, "
      "local path only, trusted=true required because it is a pickle). Returns design_id, ports and lint.",
      {"format": "str — chipir|intnn|xgboost_json|torchlogix", "model": "dict — the model JSON (chipir/intnn/xgboost_json)",
       "path": "str — file on this machine", "b64": "str — base64 file content (xgboost_json)",
       "in_spec": "dict — intnn input port {lanes, bits, signed} if not in the params",
       "w_feature": "int — TreeLUT input bits (xgboost_json)", "w_tree": "int — TreeLUT leaf bits (xgboost_json)",
       "trusted": "bool — allow unpickling (torchlogix)", "name": "str",
       "optimizer": "str — none (default) | alkaid (smaller constant multiplies; design id gets -alk)"}, lane="cpu", cacheable=True)
def ingest_model(format: str, model: dict | None = None, path: str | None = None, b64: str | None = None,
                 in_spec: dict | None = None, w_feature: int = 4, w_tree: int = 4, trusted: bool = False,
                 name: str = "model", optimizer: str | None = None) -> dict:
    fmt = format.lower()
    if fmt == "chipir":
        from chiplab.ingest.chipir import load
        blob = _read_blob(model, path, b64)
        ir = load(json.loads(blob) if isinstance(blob, (bytes, str)) else blob)
    elif fmt == "intnn":
        from chiplab.ingest.intnn import to_ir
        blob = _read_blob(model, path, b64)
        ir = to_ir(json.loads(blob) if isinstance(blob, (bytes, str)) else blob, in_spec=in_spec, name=name)
    elif fmt == "xgboost_json":
        import tempfile
        from chiplab.ingest.xgb_worker import run_worker  # xgboost runs in its own process (OpenMP clash on macOS)
        blob = _read_blob(model, path, b64)
        raw = json.dumps(blob).encode() if isinstance(blob, dict) else blob
        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            f.write(raw); f.flush()
            ir = run_worker(["convert", f.name, str(w_feature), str(w_tree), name])
    elif fmt == "torchlogix":
        import os
        if not (path and trusted):
            raise ValueError("torchlogix models are pickles (loading one can run code): pass a local path and trusted=true")
        if os.environ.get("CHIPLAB_REMOTE") and not os.environ.get("CHIPLAB_ALLOW_PICKLE"):
            raise ValueError("refused over the network server: set CHIPLAB_ALLOW_PICKLE=1 on the lab machine to allow pickles")
        import torch
        from chiplab.ingest.torchlogix import to_ir
        ir = to_ir(torch.load(path, weights_only=False), name=name)
    else:
        raise ValueError("format must be chipir, intnn, xgboost_json or torchlogix")
    res = _store_ir(ir, {"ingested_from": fmt, "name": name}, optimizer=optimizer)
    return {**res, "format": fmt}


@tool("Build ONE chip from several model heads (multi-output, multi-input) with fusion logic between their "
      "decision outputs: and | or | kofn (k-of-n vote), or score-level fusion of multi-bit head scores: max | sum "
      "then a threshold compare (1-bit decision; e.g. one per-channel model on several channel ports, "
      "shared_inputs=false). Heads are design_ids or chipir/1 documents.",
      {"heads": "dict — head name -> design_id or chipir/1",
       "fusion": "list — [{name, op: and|or|kofn, k?, inputs: [<head>_<output>]}] or "
                 "[{name, op: max|sum, t, rel? (ge), score? (false: also output <name>_score), inputs}]",
       "shared_inputs": "bool — heads read the same input port (true) or each keeps its own port (false)", "name": "str"},
      lane="cpu", cacheable=True)
def compose_chip(heads: dict, fusion: list | None = None, shared_inputs: bool = True, name: str = "composed") -> dict:
    from chiplab.ingest.compose import compose, io_spec
    irs = {}
    for k, v in heads.items():
        irs[k] = json.loads((_design_dir(v) / "ir.json").read_text()) if isinstance(v, str) else v
    ir = compose(irs, fusion or [], shared_inputs=shared_inputs, name=name)
    res = _store_ir(ir, {"composed_from": {k: (v if isinstance(v, str) else "inline") for k, v in heads.items()}})
    return {**res, "io_spec": io_spec(ir)}


_STREAM_OPTS = {
    "postproc": "dict — optional on-chip post-processing of the per-frame decision: {output?, lane?, threshold? "
                "(frame bit = value >= threshold), smooth?: {mode: majority|kofn|average, n, k?, threshold?}, "
                "min_duration? (frames the condition must last), hold? (frames the alarm stays on)}; alarm on bit 0",
    "channel_serial": "dict — optional {channels: C, reduce: max|sum, threshold: T, output?, lane?}: each frame is "
                      "ONE channel's input to ONE per-channel model; decision = reduce(score over C frames) >= T, "
                      "valid every C frames; outputs decision then acc (one model copy instead of C)",
}


@tool("Wrap a design for streaming hardware: inputs arrive one 15-bit word per strobe (ui_in[7]); outputs on "
      "uo_out[6:0] with valid on uo_out[7]. tt=true gives the Tiny Tapeout top (tt_um_chipin_<id>), else a generic "
      "top for FPGA boards. Optional postproc (smoothing, k-of-N, duration timer, alarm hold) and channel_serial "
      "(max or sum over C channels with one model copy) blocks; area=true also reports flip-flops and gates "
      "(and, with channel_serial, the parallel version with C copies of the core).",
      {"design_id": "str", "tt": "bool (true)", **_STREAM_OPTS,
       "area": "bool — synthesise and report flip-flops and gates (false)"}, lane="cpu", cacheable=True)
def compile_stream(design_id: str, tt: bool = True, postproc: dict | None = None, channel_serial: dict | None = None,
                   area: bool = False) -> dict:
    from chiplab.emit.stream import emit_stream
    d = _design_dir(design_id)
    ir = json.loads((d / "ir.json").read_text()); info = json.loads((d / "port.json").read_text())
    core_text = (d / "design.v").read_text() if info.get("optimizer") else None   # keep the optimised core
    text, sinfo = emit_stream(ir, info, tt=tt, core_text=core_text, postproc=postproc, channel_serial=channel_serial)
    fn = "stream_tt.v" if tt else "stream.v"
    (d / fn).write_text(text)
    (d / (fn[:-2] + ".json")).write_text(json.dumps(sinfo, default=str))
    out = {"design_id": design_id, "top": sinfo.get("top"), "verilog": str(d / fn), "files": [str(d / fn)],
           **{k: sinfo.get(k) for k in ("transfers_per_frame", "counter_bits", "truncated", "uo_map")}}
    if not (postproc or channel_serial):   # the plain wrapper's own flip-flops and sky130 area, apart from the core
        try:                               # (answer only: the stream files stay byte-identical)
            from chiplab.ir.estimate import stream_wrapper
            out.update(stream_wrapper(ir, tt=tt))
        except (KeyError, ValueError, TypeError):
            pass
    if postproc or channel_serial:
        out.update({k: sinfo.get(k) for k in ("postproc", "channel_serial", "frames_per_decision", "output_fields")})
    if area:
        from chiplab.emit.postproc import area_compare
        out["area"] = area_compare(ir, channel_serial, d / "stream_area", postproc=postproc)
    return out


@tool("Verification level 3: cocotb + Icarus simulation of the streaming wrapper (frames streamed in, outputs "
      "compared with the integer model or with the scientist's expected outputs) plus a Verilator lint.",
      {"design_id": "str", "n": "int — random frames if no vectors (1000)", "vectors": "dict — port -> [[lane ints]] (optional)",
       "expected": "dict — output -> [[lane ints]] (optional)", "tt": "bool (true)", **_STREAM_OPTS},
      lane="cpu", cacheable=True)
def rtl_simulate(design_id: str, n: int = 1000, vectors: dict | None = None, expected: dict | None = None, tt: bool = True,
                 postproc: dict | None = None, channel_serial: dict | None = None) -> dict:
    import numpy as np
    from chiplab.verify.rtlsim import rtl_simulate as _rs
    d = _design_dir(design_id)
    ir = json.loads((d / "ir.json").read_text())
    X = {k: np.asarray(v, dtype=np.int64) for k, v in vectors.items()} if vectors else None
    E = {k: np.asarray(v, dtype=np.int64) for k, v in expected.items()} if expected else None
    pinfo = json.loads((d / "port.json").read_text())
    core_text = (d / "design.v").read_text() if pinfo.get("optimizer") else None   # simulate the design's own core
    ext = {"postproc": postproc, "channel_serial": channel_serial} if (postproc or channel_serial) else {}
    if ext and E is not None:
        raise ValueError("expected is not used with postproc/channel_serial (the sequence model gives the answers)")
    r = _rs(ir, d / ("rtlsim_tt" if tt else "rtlsim"), X=X, n=n, tt=tt, expected=E, core_text=core_text, **ext)
    (d / "rtlsim.json").write_text(json.dumps(r, default=str))
    return {"design_id": design_id, **{k: v for k, v in r.items() if k != "first_mismatches"},
            "first_mismatches": r.get("first_mismatches", [])[:5]}


# ------------------------------------------------------------------------------------------------ outputs (data only)

@tool("Manufacturing routes for a design (iCE40 FPGA, Tiny Tapeout sky130/GF180/IHP, wafer.space GF180 slots, "
      "ChipFoundry chipIgnite, EUROPRACTICE GF180/IHP, Pragmatic FlexIC): fits or not, cost, deadline, the basis "
      "of each number, and per figure whether it was read on the vendor's page or is unverified.",
      {"design_id": "str"}, lane="inline")
def estimate_cost(design_id: str) -> dict:
    from chiplab.hw.cost import estimate
    d = _design_dir(design_id)
    rd = lambda f: json.loads((d / f).read_text()) if (d / f).exists() else {}
    syn, sky, ice = rd("synth.json"), rd("pdk_sky130.json"), rd("luts_ice40.json")
    tt = rd("tt.json").get("tiles_used") if (d / "tt.json").exists() else None
    if isinstance(tt, str) and "x" in tt:  # tile shape "AxB" -> number of tiles
        a, b = tt.lower().split("x"); tt = int(a) * int(b)
    other = {p: rd(f"pdk_{p}.json").get("area_um2") for p in ("gf180", "ihp")}
    r = estimate(syn.get("gates"), sky.get("area_um2"), tt, ice.get("luts"),
                 area_by_pdk={p: a for p, a in other.items() if a}, tt_pdk=rd("tt.json").get("pdk") or "sky130A")
    (d / "cost.json").write_text(json.dumps(r))
    return {"design_id": design_id, **r}


@tool("Compare a design with published hardware from the lab's registry. Only entries with the same task, "
      "dataset and protocol (as you declare them) count as comparable; others are shown for context only.",
      {"design_id": "str", "task": "str — e.g. af_vs_normal (optional)", "dataset": "str — what the model was "
       "tested on (optional)", "protocol": "str — e.g. 'record-level, split by patient' (optional)"}, lane="inline")
def compare_hw_baseline(design_id: str, task: str | None = None, dataset: str | None = None, protocol: str | None = None) -> dict:
    import yaml
    from chiplab.config import PKG_DIR
    d = _design_dir(design_id)
    reg = yaml.safe_load((PKG_DIR / "hw" / "baselines.yaml").read_text())
    rd = lambda f: json.loads((d / f).read_text()) if (d / f).exists() else {}
    ours = {"gate_equivalents": rd("pdk_sky130.json").get("gate_equivalents"), "luts_xc7": rd("luts_xc7.json").get("luts"),
            "gates": rd("synth.json").get("gates")}
    out = []
    for b in reg:
        same = bool(task and dataset and protocol and b["task"] == task and dataset.lower() in b["dataset"].lower()
                    and protocol.lower() == str(b["protocol"]).lower())
        common = {k: {"ours": ours[k], "theirs": b["metrics"][k], "unit": b["units"].get(k)}
                  for k in ("gate_equivalents", "luts_xc7") if k in b["metrics"] and ours.get(k) is not None}
        out.append({**b, "common_metrics": common,
                    "comparable": "comparable (same task, dataset and protocol)" if same else
                                  "context only: task, dataset or protocol differ, not a like-for-like comparison"})
    return {"design_id": design_id, "ours": ours, "baselines": out}


@tool("Gate activity as raw numbers: run the scientist's input sequence (or random vectors) through the gate "
      "netlist and return, per net, how often it switches (toggle rate) and how often it is 1. Optionally writes a "
      "VCD of the ports. Data for power estimates and for whoever draws the 'chip lighting up' view.",
      {"design_id": "str", "vectors": "dict — port -> [[lane ints]] in time order (optional)", "n": "int — random vectors if none (2000)",
       "vcd": "bool — also write ports.vcd (false)", "top": "int — how many most active nets to return inline (50)"},
      lane="cpu", cacheable=True)
def gate_activity(design_id: str, vectors: dict | None = None, n: int = 2000, vcd: bool = False, top: int = 50, seed: int = 0) -> dict:
    import numpy as np
    from chiplab.verify.netlist_eval import Netlist, lanes_to_bits
    d = _design_dir(design_id)
    syn = _ensure_synth(design_id)
    info = json.loads((d / "port.json").read_text())
    if vectors:
        X = {k: np.asarray(v, dtype=np.int64) for k, v in vectors.items()}
    else:
        rng = np.random.default_rng(seed); X = {}
        for p in info["inputs"]:
            lo, hi = (-(1 << (p["bits"] - 1)), 1 << (p["bits"] - 1)) if p["signed"] else (0, 1 << p["bits"])
            X[p["name"]] = rng.integers(lo, hi, size=(n, p["lanes"]))
    net = Netlist(syn["netlist_json"], info["top"])
    bits = {p["name"]: lanes_to_bits(X[p["name"]], p["bits"]) for p in info["inputs"]}
    act = net.activity(bits)
    full = {"design_id": design_id, "steps": act["steps"], "source": "scientist vectors" if vectors else f"{n} random vectors",
            "toggle_rate": {str(k): round(v, 5) for k, v in act["toggle_rate"].items()},
            "ones": {str(k): round(v, 5) for k, v in act["ones"].items()},
            "cells": [{"type": t, "inputs": [str(i) for i in ins if i is not None], "output": str(y)} for t, ins, y in net.order]}
    (d / "gate_activity.json").write_text(json.dumps(full))
    rates = sorted(full["toggle_rate"].items(), key=lambda kv: -kv[1])
    files = [str(d / "gate_activity.json")]
    if vcd:
        from vcd import VCDWriter
        outs = net.evaluate(bits)
        with open(d / "ports.vcd", "w") as f, VCDWriter(f, timescale="1 ns", date="today") as w:
            vs = {p: w.register_var(info["top"], p, "wire", size=bits[p].shape[1]) for p in bits}
            vs.update({p: w.register_var(info["top"], p, "wire", size=outs[p].shape[1]) for p in outs if not p.startswith("_")})
            for t in range(next(iter(bits.values())).shape[0]):
                for p, b in list(bits.items()) + [(k, v) for k, v in outs.items() if not k.startswith("_")]:
                    w.change(vs[p], t, int("".join("1" if x else "0" for x in b[t][::-1]), 2))
        files.append(str(d / "ports.vcd"))
    mean = float(np.mean(list(full["toggle_rate"].values()))) if full["toggle_rate"] else 0.0
    return {"design_id": design_id, "steps": act["steps"], "nets": len(rates), "mean_toggle_rate": round(mean, 4),
            "wire_toggle_top": dict(rates[:top]), "files": files,
            "note": "net ids are Yosys netlist bit ids (see netlist JSON); toggle rates use the vectors' order as time"}


#: The instruction ChipIn agents get about chip-report (docs/CHIPIN_INTEGRATION.md section 6; same text in chiplab.md).
CHIP_REPORT_SENTENCE = ('Before you mark report done, call `chiplab chip-report --json \'{"design_id": "<the chip you chose>", "decision_rate_hz": <decisions per second>}\'` on the one chip you chose: the chip figures the user sees (area, power, energy, cost, verification) come from that call.')


@tool("One-page chip report (markdown text): ports, hardware numbers with their basis, verification level and "
      "evidence, manufacturing routes and cost, published hardware for context, artefact paths. With "
      "decision_rate_hz (or a rate given to layout earlier) it shows power at that decision rate. Also returns "
      "`figures`: the chip's full figure set, which a ChipIn run's dashboard shows. " + CHIP_REPORT_SENTENCE,
      {"design_id": "str", "name": "str — a readable name (optional)",
       "decision_rate_hz": "float — decisions per second the device needs (optional)"}, lane="inline")
def chip_report(design_id: str, name: str | None = None, decision_rate_hz: float | None = None) -> dict:
    import hashlib
    import time
    import jinja2
    from chiplab.config import PKG_DIR
    d = _design_dir(design_id)
    rd = lambda f: json.loads((d / f).read_text()) if (d / f).exists() else None
    ir = rd("ir.json"); meta = rd("meta.json") or {}
    try:
        from chiplab.verify.ladder import stamp
        lad = stamp(d)
    except Exception as e:
        lad = {"verification_level": 0, "evidence": [f"ladder not available: {e}"]}
    lad.setdefault("label", {0: "not verified", 1: "bit-exact simulation", 2: "formal proof", 3: "streaming RTL simulation",
                             4: "gate-level test after layout", 5: "running on hardware"}.get(lad.get("verification_level", 0), ""))
    fig = chip_figures(design_id, decision_rate_hz)          # fills cheap gaps (synthesis, sky130 mapping, cost) first
    cost = rd("cost.json") or estimate_cost.__wrapped__(design_id=design_id)
    base = compare_hw_baseline.__wrapped__(design_id=design_id)["baselines"]
    pdks = {p: rd(f"pdk_{p}.json") for p in ("sky130", "gf180", "ihp") if rd(f"pdk_{p}.json")}
    layouts, rate_rows = {}, []
    for p in ("sky130A", "gf180mcuD", "ihp-sg13g2"):
        m = rd(f"layout_{p}.json")
        if m:
            layouts[p] = {"summary": ", ".join(f"{k}={m[k]}" for k in ("area_um2", "die_mm2", "timing_ws_ns", "power_uw") if m.get(k) is not None),
                          "basis": m.get("basis", "")}
            rate = decision_rate_hz if decision_rate_hz is not None else m.get("decision_rate_hz")
            pwr = rate_power(m.get("energy_per_decision_pj"), m.get("leakage_uw"), rate)
            if pwr is not None:
                rate_rows.append({"pdk": p, "rate_hz": float(rate), "power_uw": pwr, "energy_pj": m.get("energy_per_decision_pj"),
                                  "leakage_uw": m.get("leakage_uw"), "clock_ns": m.get("clock_period_ns"),
                                  "power_basis": m.get("power_basis") or "vectorless"})
    luts = {f: rd(f"luts_{f}.json") for f in ("xc7", "ice40") if rd(f"luts_{f}.json")}
    arte = {f.name: str(f) for f in sorted(d.glob("*")) if f.suffix in (".v", ".json", ".gds", ".png", ".bin", ".vcd")}
    tpl = jinja2.Template((PKG_DIR / "report_template.md.j2").read_text(), trim_blocks=False)
    md = tpl.render(name=name or meta.get("name") or ir.get("name"), design_id=design_id, when=time.strftime("%Y-%m-%d %H:%M"),
                    ladder=lad, ports=rd("port.json"), source=meta.get("ingested_from") or ("training batch " + str(meta.get("batch_id")) if meta.get("batch_id") else "chipir"),
                    ops=sorted({n["op"] for n in ir["nodes"]}), synth=rd("synth.json"), luts=luts, pdks=pdks, layouts=layouts,
                    fpga=rd("bitstream.json"), cost=cost, baselines=base, artefacts=arte, rate_rows=rate_rows)
    (d / "report.md").write_text(md)
    out = {"design_id": design_id, "report_md": md, "digest": hashlib.sha256(md.encode()).hexdigest()[:12],
           "figures": fig["figures"], "figures_basis": fig["basis"]}
    if rate_rows:
        out["power_at_rate"] = rate_rows
    return {**out,
            "files": [str(d / "report.md")], "verilog_url": f"/files/{design_id}/design.v",
            "netlist_json_url": f"/files/{design_id}/synth/net.json",
            "layout_png_url": next((f"/files/{design_id}/{p.relative_to(d)}" for p in d.rglob("*.png")), None)}


#: The figure set of one chip, in the order the ChipIn dashboard receives it (chiplab.progress.METRIC_KEYS units).
FIGURE_KEYS = ("gates", "depth", "transistors", "luts_ice40", "luts_xc7", "area_um2", "ge", "tt_tiles", "cost_eur",
               "verification_level", "timing_slack_ns", "fmax_mhz", "energy_pj", "leakage_uw", "power_uw_at_rate")


def chip_figures(design_id: str, decision_rate_hz: float | None = None, fill: bool = True) -> dict:
    """Every figure of ONE chip, from its own results, so a dashboard never mixes two circuits. With fill, the cheap
    missing ones are made first (synthesis, sky130 cell mapping, cost: seconds); layout, LUT counts and bitstreams
    are used only if they were already run. Returns {"figures": {key: number}, "basis": {key: text}}."""
    import math
    d = _design_dir(design_id)
    rd = lambda f: json.loads((d / f).read_text()) if (d / f).exists() else {}
    if fill:
        try:
            _ensure_synth(design_id)
        except Exception:
            pass
        if not (d / "pdk_sky130.json").exists():
            try:
                from chiplab.hw.pdk import liberty
                liberty("sky130")
                map_to_process.__wrapped__(design_id=design_id, pdk="sky130")
            except Exception:
                pass
        try:
            estimate_cost.__wrapped__(design_id=design_id)        # pure arithmetic on the files above: always fresh
        except Exception:
            pass
    f, b = {}, {}

    def put(k, v, basis):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            return
        f[k] = round(v, 6) if isinstance(v, float) else v
        b[k] = basis
    syn = rd("synth.json")
    put("gates", syn.get("gates"), "synthesized (Yosys, simple 2-input gates)")
    put("depth", syn.get("depth"), "synthesized (logic levels on the longest path)")
    put("transistors", syn.get("transistors_est"), "estimate (Yosys CMOS cost model)")
    ice, xc7, bit = rd("luts_ice40.json"), rd("luts_xc7.json"), rd("bitstream.json")
    put("luts_ice40", ice.get("luts") if ice else (bit.get("metrics") or bit).get("luts"), "synthesized (iCE40UP5K LUT4)")
    put("luts_xc7", xc7.get("luts"), "synthesized (AMD 7-series LUT6)")
    sky = rd("pdk_sky130.json")
    put("area_um2", sky.get("area_um2"), "synthesized onto sky130 cells (before layout)")
    put("ge", sky.get("gate_equivalents"), "synthesized (sky130 area / one NAND2 cell)")
    put("tt_tiles", sky.get("tt_tiles_est"), "estimate (sky130 area at 60% utilisation)")
    tt = next((r for r in rd("cost.json").get("routes", []) if r.get("route") == "tt_sky130"), None)
    if tt:
        put("cost_eur", tt.get("cost"), f"price list checked {tt.get('checked')} (Tiny Tapeout sky130); {tt.get('basis')}")
        put("tt_tiles", tt.get("tiles"), f"the tiles the Tiny Tapeout price is for: {tt.get('basis')}")
    try:
        from chiplab.verify.ladder import stamp
        put("verification_level", stamp(d).get("verification_level"), "verification ladder (0 to 5), from this chip's own checks")
    except Exception:
        pass
    lay, lp = None, None
    for p in ("sky130A", "ihp-sg13g2", "gf180mcuD"):
        if (d / f"layout_{p}.json").exists():
            lay, lp = rd(f"layout_{p}.json"), p
            break
    if lay and not lay.get("error"):
        clk = lay.get("clock_period_ns")
        if lp == "sky130A":
            put("area_um2", lay.get("area_um2"), "sky130 after place and route (LibreLane)")
        put("timing_slack_ns", lay.get("timing_ws_ns"), f"{lp} layout, static timing at a {clk} ns clock")
        cp = lay.get("critical_path_ns")
        if isinstance(cp, (int, float)) and cp > 0:
            put("fmax_mhz", round(1000.0 / cp, 2), f"{lp} layout: 1000 / critical path ({cp} ns)")
        put("energy_pj", lay.get("energy_per_decision_pj"), f"{lp} layout, vectorless energy per decision")
        put("leakage_uw", lay.get("leakage_uw"), f"{lp} layout (standby power)")
        rate = decision_rate_hz if decision_rate_hz is not None else lay.get("decision_rate_hz")
        put("power_uw_at_rate", rate_power(lay.get("energy_per_decision_pj"), lay.get("leakage_uw"), rate),
            f"energy per decision x {rate} decisions/s + leakage")
    if "fmax_mhz" not in f and bit:
        fm = (bit.get("metrics") or bit).get("fmax_mhz")
        put("fmax_mhz", min(fm.values()) if isinstance(fm, dict) and fm else fm, "iCE40 place and route (nextpnr)")
    return {"design_id": design_id, "figures": {k: f[k] for k in FIGURE_KEYS if k in f},
            "basis": {k: b[k] for k in FIGURE_KEYS if k in b}}


# ------------------------------------------------------------------------------------------------ agent-written RTL

@tool("Submit hand- or agent-written Verilog safely. It is screened (no system tasks or includes), linted and "
      "synthesised inside a locked-down container, then checked bit for bit against a reference: a chipir/1 model "
      "(reference_ir) or the scientist's vectors + expected outputs. Ports must follow the lab convention "
      "(port_spec: inputs/outputs with lanes, bits, signed). Accepted designs get a design_id like any other.",
      {"verilog": "str — the source", "top": "str — top module name", "port_spec": "dict — {inputs:[{name,lanes,bits,signed}], outputs:[...]}",
       "reference_ir": "dict — chipir/1 model the circuit must equal (optional)", "vectors": "dict — port -> [[ints]] (optional)",
       "expected": "dict — output -> [[ints]] (optional)", "n": "int — random vectors when checking against reference_ir (20000)",
       "allow_host": "bool — run lint/synthesis on this machine if the sandbox container is missing (default false: refuse)"},
      lane="cpu")
def submit_verilog(verilog: str, top: str, port_spec: dict, reference_ir: dict | None = None, vectors: dict | None = None,
                   expected: dict | None = None, n: int = 20000, allow_host: bool = False) -> dict:
    import hashlib
    import numpy as np
    from chiplab import config
    from chiplab.verify.bitexact import circuit_outputs
    from chiplab.verify.sandbox import check_verilog
    if reference_ir is None and not (vectors and expected):
        raise ValueError("a reference is required: reference_ir, or vectors + expected")
    sid = "v" + hashlib.sha256((verilog + top + json.dumps(port_spec, sort_keys=True)).encode()).hexdigest()[:11]
    d = config.home("designs", sid)
    r = check_verilog(verilog, top, d / "sandbox", allow_host=allow_host)
    if not r["accepted"]:
        return {"design_id": None, **r, "accepted": False, "error": "; ".join(r.get("problems") or ["rejected"])}
    info = {"top": top, "inputs": port_spec["inputs"], "outputs": port_spec["outputs"]}
    if vectors:
        X = {k: np.asarray(v, dtype=np.int64) for k, v in vectors.items()}
    else:
        rng = np.random.default_rng(0); X = {}
        for p in info["inputs"]:
            lo, hi = (-(1 << (p["bits"] - 1)), 1 << (p["bits"] - 1)) if p["signed"] else (0, 1 << p["bits"])
            X[p["name"]] = rng.integers(lo, hi, size=(n, p["lanes"]))
    circ = circuit_outputs(r["netlist_json"], info, X)
    if reference_ir is not None:
        from chiplab.ir.interp import run as interp
        ref = interp(reference_ir, X)
    else:
        ref = {k: np.asarray(v, dtype=np.int64) for k, v in expected.items()}
    mism = {o["name"]: int((circ[o["name"]] != ref[o["name"]].reshape(circ[o["name"]].shape)).any(axis=1).sum()) for o in info["outputs"]}
    ok = all(v == 0 for v in mism.values())
    (d / "design.v").write_text(verilog)
    (d / "port.json").write_text(json.dumps(info))
    (d / "meta.json").write_text(json.dumps({"source": "agent_verilog", "sandbox": r["sandbox"]}))
    if reference_ir is not None:
        (d / "ir.json").write_text(json.dumps(reference_ir))
    (d / "simulate_vectors.json").write_text(json.dumps({"bit_exact": ok, "n": len(next(iter(X.values()))), "mismatches": mism}))
    return {"design_id": sid, "accepted": True, "bit_exact": ok, "mismatches": mism, "vectors": len(next(iter(X.values()))),
            "gates": r["gates"], "lint": r["lint"], "sandbox": r["sandbox"], "verification_level": 1 if ok else 0}


# ------------------------------------------------------------------------------------------------ layout, FPGA, TT

#: Clock used for timing when the caller gives none: 20 MHz (10 MHz on the slower GF180), which closes for chips of a
#: few thousand gates and is far faster than any sensor needs (decisions per second, not per microsecond).
DEFAULT_CLOCK_NS = {"sky130A": 50.0, "ihp-sg13g2": 50.0, "gf180mcuD": 100.0}
_PDK_ALIAS = {"sky130": "sky130A", "sky130A": "sky130A", "gf180": "gf180mcuD", "gf180mcuD": "gf180mcuD",
              "ihp": "ihp-sg13g2", "ihp-sg13g2": "ihp-sg13g2"}


def _librelane_run(design_id: str, p: str, clock_period_ns: float, core_util: int, activity_vcd: str | None,
                   timeout: int) -> dict:
    """The expensive part of layout/timing_power: one LibreLane run, cached on its own key (design, PDK, clock,
    utilisation, activity), so derived numbers such as power at a decision rate never trigger a new run."""
    from pathlib import Path
    from chiplab import cache
    from chiplab.hw.librelane import timing_power_layout
    key = {"design_id": design_id, "pdk": p, "clock_period_ns": float(clock_period_ns), "core_util": int(core_util),
           "activity_vcd": activity_vcd}
    hit = cache.get("_librelane_run", key)
    if hit is not None:
        return {k: v for k, v in hit.items() if k != "status"}
    d = _design_dir(design_id)
    info = json.loads((d / "port.json").read_text())
    r = timing_power_layout([d / "design.v"], info["top"], d / f"layout_{p}", pdk=p, clock_period_ns=clock_period_ns,
                            activity_vcd=Path(activity_vcd) if activity_vcd else None, core_util=core_util, timeout=timeout)
    if r.get("area_um2") is not None and not r.get("error"):
        cache.put("_librelane_run", key, {**r, "status": "ok"})
    return r


def rate_power(energy_per_decision_pj: float | None, leakage_uw: float | None, decision_rate_hz: float | None) -> float | None:
    """Average power at a decision rate, µW: dynamic energy per decision (pJ) x decisions/s x 1e-6, plus leakage."""
    if decision_rate_hz is None or energy_per_decision_pj is None:
        return None
    return round(energy_per_decision_pj * float(decision_rate_hz) * 1e-6 + (leakage_uw or 0.0), 6)


def _layout(design_id: str, pdk: str, clock_period_ns: float | None, core_util: int, activity_vcd: str | None, timeout: int,
            decision_rate_hz: float | None = None) -> dict:
    from pathlib import Path
    d = _design_dir(design_id)
    p = _PDK_ALIAS[pdk]
    clock_period_ns = clock_period_ns or DEFAULT_CLOCK_NS.get(p, 50.0)
    r = _librelane_run(design_id, p, clock_period_ns, core_util, activity_vcd, timeout)
    pw = r.get("power_w")
    leak = round(r["leakage_w"] * 1e6, 6) if r.get("leakage_w") is not None else None
    energy = r.get("energy_per_decision_pj_vectorless")
    out = {"design_id": design_id, "pdk": p, "area_um2": r.get("area_um2"), "die_area_um2": r.get("die_area_um2"),
           "core_mm2": round(r["area_um2"] / 1e6, 6) if r.get("area_um2") else None,
           "die_mm2": round(r["die_area_um2"] / 1e6, 6) if r.get("die_area_um2") else None,
           "timing_ws_ns": r.get("timing_ws_ns"), "critical_path_ns": r.get("critical_path_ns"),
           "fmax_mhz": round(1000.0 / r["critical_path_ns"], 2) if (r.get("critical_path_ns") or 0) > 0 else None,
           "fmax_basis": "1000 / critical path after layout (the fastest clock this chip runs at)",
           "timing_met": (r["timing_ws_ns"] >= 0) if r.get("timing_ws_ns") is not None else None,
           "power_uw": round(pw * 1e6, 3) if pw is not None else None,
           "power_uw_at_clock": round(pw * 1e6, 3) if pw is not None else None,
           "power_at_clock_basis": (f"LibreLane {r.get('power_basis') or 'vectorless'} power with the logic evaluated every "
                                    f"{clock_period_ns} ns clock cycle (a worst case for a slow sensor)"),
           "leakage_uw": leak,
           "energy_per_decision_pj": energy,
           "energy_basis": (f"dynamic (internal + switching) {r.get('power_basis') or 'vectorless'} power at the "
                            f"{clock_period_ns} ns clock x one clock period = energy of one decision"),
           "power_basis": r.get("power_basis"),
           "gate_equivalents_layout": r.get("gate_equivalents_layout"), "gds": r.get("gds"), "png": r.get("png"),
           "gds_url": f"/files/{design_id}/{Path(r['gds']).relative_to(d)}" if r.get("gds") else None,
           "png_url": f"/files/{design_id}/{Path(r['png']).relative_to(d)}" if r.get("png") else None,
           "basis": r.get("basis", "librelane-layout"), "hw_kind": "layout", "metrics": r.get("metrics"),
           "clock_period_ns": clock_period_ns, "seconds": r.get("seconds"),
           "files": [f for f in (r.get("gds"), r.get("png"), r.get("netlist")) if f]}
    if r.get("error"):
        out["error"] = r["error"]
    if decision_rate_hz is not None:
        out["decision_rate_hz"] = float(decision_rate_hz)
        out["power_uw_at_rate"] = rate_power(energy, leak, decision_rate_hz)
        out["power_at_rate_basis"] = (f"dynamic energy per decision from LibreLane {r.get('power_basis') or 'vectorless'} "
                                      f"power at the {clock_period_ns} ns clock ({energy} pJ), times {float(decision_rate_hz)} "
                                      f"decisions per second, plus leakage ({leak} µW)")
    (d / f"layout_{p}.json").write_text(json.dumps(out, default=str))
    return out


@tool("Place and route the chip with LibreLane (Docker): real cell area, die area, timing slack against a clock, "
      "power (vectorless, or from an activity VCD), GDS and the KLayout image. Power is given at the clock "
      "(power_uw_at_clock) and, with decision_rate_hz, at the rate the sensor actually needs decisions "
      "(power_uw_at_rate = energy per decision x rate + leakage). Changing the rate never re-runs LibreLane.",
      {"design_id": "str", "pdk": "str — sky130|gf180|ihp (sky130)", "clock_period_ns": "float — clock for timing (default 50 ns = 20 MHz; 100 ns on gf180)",
       "core_util": "int — target utilisation % (40)", "activity_vcd": "str — VCD of real activity for power (optional)",
       "timeout": "int seconds (3600)", "decision_rate_hz": "float — decisions per second the device needs (optional)"},
      lane="docker", cacheable=True)
def layout(design_id: str, pdk: str = "sky130", clock_period_ns: float | None = None, core_util: int = 40,
           activity_vcd: str | None = None, timeout: int = 3600, decision_rate_hz: float | None = None) -> dict:
    return _layout(design_id, pdk, clock_period_ns, core_util, activity_vcd, timeout, decision_rate_hz)


@tool("Timing and power of the laid-out chip (same LibreLane run as layout; cached, so calling both costs one run). "
      "With decision_rate_hz it adds power_uw_at_rate: energy per decision x decisions per second + leakage.",
      {"design_id": "str", "pdk": "str — sky130|gf180|ihp (sky130)", "clock_period_ns": "float (default 50 ns = 20 MHz; 100 ns on gf180)",
       "activity_vcd": "str — optional VCD for activity-based power",
       "decision_rate_hz": "float — decisions per second the device needs (optional)"}, lane="docker", cacheable=True)
def timing_power(design_id: str, pdk: str = "sky130", clock_period_ns: float | None = None, activity_vcd: str | None = None,
                 decision_rate_hz: float | None = None) -> dict:
    from chiplab.tools import TOOLS
    r = TOOLS["layout"]["fn"](design_id=design_id, pdk=pdk, clock_period_ns=clock_period_ns, activity_vcd=activity_vcd,
                              decision_rate_hz=decision_rate_hz)
    if r.get("status") != "ok":
        return r
    return {k: v for k, v in r.items() if k not in ("cost", "status")}


@tool("iCE40UP5K bitstream (UPduino class board): the streaming wrapper plus a board top (clk, rst_n, ui_in, uo_out "
      "on pins), synthesised, placed and routed; LUTs, pins, maximum clock. Pass a .pcf for a specific board's pins.",
      {"design_id": "str", "pcf": "str — pin constraints file (optional; unconstrained otherwise)", "freq_mhz": "float (12)"},
      lane="cpu", cacheable=True)
def bitstream(design_id: str, pcf: str | None = None, freq_mhz: float = 12.0) -> dict:
    from pathlib import Path
    from chiplab.hw.fpga import board_top_for_tt, ice40_bitstream
    from chiplab.tools import TOOLS
    d = _design_dir(design_id)
    s = TOOLS["compile_stream"]["fn"].__wrapped__(design_id=design_id, tt=True)
    btxt, btop = board_top_for_tt(s["top"])
    (d / "board_top.v").write_text(btxt)
    r = ice40_bitstream([d / "stream_tt.v", d / "board_top.v"], btop, d / "ice40", pcf=Path(pcf) if pcf else None, freq_mhz=freq_mhz)
    (d / "bitstream.json").write_text(json.dumps(r, default=str))
    return {"design_id": design_id, "bin": r.get("bin"), "metrics": {k: r.get(k) for k in ("luts", "ff", "carries", "fmax_mhz",
            "io_used", "logic_cells") if k in r}, "pins": "unconstrained (pass pcf for a real board)" if not pcf else pcf,
            "files": [r.get("bin")] if r.get("bin") else [], **{k: r[k] for k in ("seconds",) if k in r}}


@tool("Tiny Tapeout project for the chip: streaming top tt_um_chipin_<id>, info.yaml, docs, a cocotb test with "
      "vectors from the integer model, Tiny Tapeout user config. harden=true also builds the GDS locally (Docker) "
      "and runs the gate-level test (verification level 4); otherwise commit the folder and run the tt-gds workflow.",
      {"design_id": "str", "harden": "bool (false)", "tiles": "str — auto|1x1|1x2|2x2|... (auto)", "pdk": "str — sky130A|gf180mcuD|ihp-sg13g2",
       "vectors": "int — test vectors from the integer model (64)", "clock_hz": "int (25000000)", "title": "str (optional)"},
      lane="docker", cacheable=True)
def tt_package(design_id: str, harden: bool = False, tiles: str = "auto", pdk: str = "sky130A", vectors: int = 64,
               clock_hz: int = 25_000_000, title: str | None = None) -> dict:
    from chiplab.hw.tinytapeout import tt_package as _tt
    from chiplab.tools import TOOLS
    from chiplab.verify.rtlsim import tt_project_test, tt_vectors
    from chiplab.hw.tt_submit import refuse_lgpl_rtl
    d = _design_dir(design_id)
    refuse_lgpl_rtl([d / "design.v"])   # Tiny Tapeout is Apache-2.0: no alkaid LGPL helper modules
    ir = json.loads((d / "ir.json").read_text())
    s = TOOLS["compile_stream"]["fn"].__wrapped__(design_id=design_id, tt=True)
    meta = {"title": title or f"chipin.space chip {design_id}", "author": "chipin.space chip lab",
            "description": "A fixed-weight integer model wired into logic gates",
            "how": "Inputs are streamed as 15-bit words ({uio_in, ui_in[6:0]}) on rising edges of ui_in[7]; when a frame "
                   "is complete the decision appears on uo_out[6:0] with valid on uo_out[7]."}
    from chiplab.hw.tt_submit import _info_md, stream_pinout
    sinfo = json.loads((d / "stream_tt.json").read_text())
    meta["pinout"] = stream_pinout(sinfo)         # every TT pin documented, so the project is submission-ready
    meta["info_md"] = _info_md(sinfo, meta["title"])
    r = _tt([d / "stream_tt.v"], s["top"], d / "tt", meta, tiles=tiles, harden=harden, pdk=_PDK_ALIAS.get(pdk, pdk),
            vectors=tt_vectors(ir, vectors), clock_hz=clock_hz, test_py=tt_project_test())
    (d / "tt_package.json").write_text(json.dumps(r, default=str))
    (d / "tt.json").write_text(json.dumps({"tiles_used": r.get("tiles"), "harden_ok": r.get("harden_ok"), "pdk": r.get("pdk")}))
    return {"design_id": design_id, **{k: r.get(k) for k in ("folder", "top", "tiles", "tile_um", "pdk", "user_config_ok",
            "rtl_test_passed", "harden_ok", "gl_test_passed", "gds", "png", "error", "seconds")},
            "cloud_build": "commit the folder under chiplab/tt_projects/ and run: gh workflow run tt-gds.yaml -f project_dir=<path>",
            "files": [r.get("folder")]}


@tool("Sequential equivalence (eqy) of the streaming wrapper against its synthesised netlist: verification level 2 "
      "for clocked designs. Compositional by default: the combinational core is a black box here (prove it with "
      "prove_equivalence), so the proof covers only the clocked wrapper and takes seconds at any model size "
      "(spike: 3 s). whole=true proves the flattened design instead (small chips only, a few hundred gates).",
      {"design_id": "str", "timeout": "int seconds (600)", "whole": "bool — prove the whole flattened design (false)",
       **_STREAM_OPTS}, lane="cpu", cacheable=True)
def prove_sequential(design_id: str, timeout: int = 600, whole: bool = False, postproc: dict | None = None,
                     channel_serial: dict | None = None) -> dict:
    from chiplab.tools import TOOLS
    from chiplab.verify.eqy import prove_sequential as _ps
    d = _design_dir(design_id)
    ext = {"postproc": postproc, "channel_serial": channel_serial} if (postproc or channel_serial) else {}
    s = TOOLS["compile_stream"]["fn"].__wrapped__(design_id=design_id, tt=True, **ext)
    pinfo = json.loads((d / "port.json").read_text())
    core = pinfo["top"]
    stub = d / "core_stub.v"   # ports only: the black box's declaration for the gate side
    ports = [f"input wire [{p['lanes'] * p['bits'] - 1}:0] {p['name']}" for p in pinfo["inputs"]] + \
            [f"output wire [{o['lanes'] * o['bits'] - 1}:0] {o['name']}" for o in pinfo["outputs"]]
    stub.write_text(f"(* blackbox *)\nmodule {core} ({', '.join(ports)});\nendmodule\n")
    nm = {}
    if ext:   # the blocks' combinational wires are not cut points (registers and core outputs stay matched)
        from chiplab.emit.postproc import Extension
        nm = {"nomatch": Extension(pinfo, postproc, channel_serial).wires()}
    r = _ps([d / "stream_tt.v"], s["top"], d / ("eqy_whole" if whole else "eqy"), timeout=timeout,
            blackbox=None if whole else [core], blackbox_sources=None if whole else [stub], **nm)
    if ext:
        r = {**r, **{k: s.get(k) for k in ("postproc", "channel_serial", "frames_per_decision")}}
    (d / "eqy.json").write_text(json.dumps(r, default=str))
    return {"design_id": design_id, **r}


@tool("The chip's verification level (1 bit-exact, 2 formal, 3 streaming RTL sim + lint, 4 TT gate-level test, "
      "5 hardware) with the evidence behind it and what to run next.", {"design_id": "str"}, lane="inline")
def verification_level(design_id: str) -> dict:
    from chiplab.verify.ladder import stamp
    return {"design_id": design_id, **stamp(_design_dir(design_id))}



@tool("Tiny Tapeout submission readiness of a design's TT project (made by tt_package): info.yaml, pinout, docs, top "
      "ports, lint, licence, RTL test, and TT's official precheck if the project was hardened. Never submits or pays.",
      {"design_id": "str", "run_tests": "bool (true)", "precheck": "bool — run TT precheck if hardened (true)"}, lane="docker")
def tt_readiness(design_id: str, run_tests: bool = True, precheck: bool = True) -> dict:
    from chiplab.hw.tt_submit import readiness
    d = _design_dir(design_id)
    projs = sorted((d / "tt").glob("tt_*")) if (d / "tt").exists() else []
    if not projs:
        raise ValueError("no Tiny Tapeout project for this design: run tt_package first")
    r = readiness(projs[0], run_tests=run_tests, run_precheck_if_hardened=precheck)
    (d / "tt_readiness.json").write_text(json.dumps(r, default=str))
    out = {"design_id": design_id, "project": str(projs[0]), **r}
    if not r.get("ready"):
        out["status"] = "fail"   # the check ran; the project is not ready yet (see blocking)
    return out


@tool("Export a design's TT project as a standalone repo shaped like Tiny Tapeout's template (or staged under "
      "chiplab/tt_projects/ for the tt-gds workflow), ready for a human to push and submit. Creates no remote repo.",
      {"design_id": "str", "out_dir": "str — where to write (optional)", "mode": "str — standalone|monorepo (standalone)"}, lane="cpu")
def tt_export(design_id: str, out_dir: str | None = None, mode: str = "standalone") -> dict:
    from chiplab.hw.tt_submit import export_submission_repo
    d = _design_dir(design_id)
    projs = sorted((d / "tt").glob("tt_*")) if (d / "tt").exists() else []
    if not projs:
        raise ValueError("no Tiny Tapeout project for this design: run tt_package first")
    r = export_submission_repo(projs[0], out_dir, mode)
    return {"design_id": design_id, **r, "files": [r.get("repo")]}
