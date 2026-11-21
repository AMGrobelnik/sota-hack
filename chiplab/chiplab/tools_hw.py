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

def _store_ir(ir: dict, meta: dict | None = None) -> dict:
    """Validate, emit, lint and store an IR as a design; returns compile_verilog's answer."""
    from chiplab.tools import TOOLS
    res = TOOLS["compile_verilog"]["fn"].__wrapped__(ir=ir)
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
       "trusted": "bool — allow unpickling (torchlogix)", "name": "str"}, lane="cpu", cacheable=True)
def ingest_model(format: str, model: dict | None = None, path: str | None = None, b64: str | None = None,
                 in_spec: dict | None = None, w_feature: int = 4, w_tree: int = 4, trusted: bool = False,
                 name: str = "model") -> dict:
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
        import xgboost as xgb
        from chiplab.ingest.treelut import from_xgboost
        blob = _read_blob(model, path, b64)
        raw = json.dumps(blob).encode() if isinstance(blob, dict) else blob
        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            f.write(raw); f.flush()
            booster = xgb.XGBClassifier(); booster.load_model(f.name)
        ir = from_xgboost(booster, w_feature, w_tree)
    elif fmt == "torchlogix":
        if not (path and trusted):
            raise ValueError("torchlogix models are pickles: pass a local path and trusted=true")
        import torch
        from chiplab.ingest.torchlogix import to_ir
        ir = to_ir(torch.load(path, weights_only=False), name=name)
    else:
        raise ValueError("format must be chipir, intnn, xgboost_json or torchlogix")
    res = _store_ir(ir, {"ingested_from": fmt, "name": name})
    return {**res, "format": fmt}


@tool("Build ONE chip from several model heads (multi-output, multi-input) with fusion logic between their "
      "decision outputs: and | or | kofn (k-of-n vote). Heads are design_ids or chipir/1 documents.",
      {"heads": "dict — head name -> design_id or chipir/1", "fusion": "list — [{name, op: and|or|kofn, k?, inputs: [<head>_<output>]}]",
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


@tool("Wrap a design for streaming hardware: inputs arrive one 15-bit word per strobe (ui_in[7]); outputs on "
      "uo_out[6:0] with valid on uo_out[7]. tt=true gives the Tiny Tapeout top (tt_um_chipin_<id>), else a generic "
      "top for FPGA boards.", {"design_id": "str", "tt": "bool (true)"}, lane="cpu", cacheable=True)
def compile_stream(design_id: str, tt: bool = True) -> dict:
    from chiplab.emit.stream import emit_stream
    d = _design_dir(design_id)
    ir = json.loads((d / "ir.json").read_text()); info = json.loads((d / "port.json").read_text())
    text, sinfo = emit_stream(ir, info, tt=tt)
    fn = "stream_tt.v" if tt else "stream.v"
    (d / fn).write_text(text)
    (d / (fn[:-2] + ".json")).write_text(json.dumps(sinfo, default=str))
    return {"design_id": design_id, "top": sinfo.get("top"), "verilog": str(d / fn), "files": [str(d / fn)],
            **{k: sinfo.get(k) for k in ("transfers_per_frame", "counter_bits", "truncated", "uo_map")}}


@tool("Verification level 3: cocotb + Icarus simulation of the streaming wrapper (frames streamed in, outputs "
      "compared with the integer model or with the scientist's expected outputs) plus a Verilator lint.",
      {"design_id": "str", "n": "int — random frames if no vectors (1000)", "vectors": "dict — port -> [[lane ints]] (optional)",
       "expected": "dict — output -> [[lane ints]] (optional)", "tt": "bool (true)"}, lane="cpu", cacheable=True)
def rtl_simulate(design_id: str, n: int = 1000, vectors: dict | None = None, expected: dict | None = None, tt: bool = True) -> dict:
    import numpy as np
    from chiplab.verify.rtlsim import rtl_simulate as _rs
    d = _design_dir(design_id)
    ir = json.loads((d / "ir.json").read_text())
    X = {k: np.asarray(v, dtype=np.int64) for k, v in vectors.items()} if vectors else None
    E = {k: np.asarray(v, dtype=np.int64) for k, v in expected.items()} if expected else None
    r = _rs(ir, d / ("rtlsim_tt" if tt else "rtlsim"), X=X, n=n, tt=tt, expected=E)
    (d / "rtlsim.json").write_text(json.dumps(r, default=str))
    return {"design_id": design_id, **{k: v for k, v in r.items() if k != "first_mismatches"},
            "first_mismatches": r.get("first_mismatches", [])[:5]}


# ------------------------------------------------------------------------------------------------ outputs (data only)

@tool("Manufacturing routes for a design (iCE40 FPGA, Tiny Tapeout sky130/GF180, wafer.space GF180, Pragmatic "
      "FlexIC): fits or not, cost, deadline, and the basis of each number.", {"design_id": "str"}, lane="inline")
def estimate_cost(design_id: str) -> dict:
    from chiplab.hw.cost import estimate
    d = _design_dir(design_id)
    rd = lambda f: json.loads((d / f).read_text()) if (d / f).exists() else {}
    syn, sky, ice = rd("synth.json"), rd("pdk_sky130.json"), rd("luts_ice40.json")
    tt = rd("tt.json").get("tiles_used") if (d / "tt.json").exists() else None
    r = estimate(syn.get("gates"), sky.get("area_um2"), tt, ice.get("luts"))
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


@tool("One-page chip report (markdown text): ports, hardware numbers with their basis, verification level and "
      "evidence, manufacturing routes and cost, published hardware for context, artefact paths.",
      {"design_id": "str", "name": "str — a readable name (optional)"}, lane="inline")
def chip_report(design_id: str, name: str | None = None) -> dict:
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
    cost = rd("cost.json") or estimate_cost.__wrapped__(design_id=design_id)
    base = compare_hw_baseline.__wrapped__(design_id=design_id)["baselines"]
    pdks = {p: rd(f"pdk_{p}.json") for p in ("sky130", "gf180", "ihp") if rd(f"pdk_{p}.json")}
    layouts = {}
    for p in ("sky130A", "gf180mcuD", "ihp-sg13g2"):
        m = rd(f"layout_{p}.json")
        if m:
            layouts[p] = {"summary": ", ".join(f"{k}={m[k]}" for k in ("area_um2", "die_mm2", "timing_ws_ns", "power_uw") if m.get(k) is not None),
                          "basis": m.get("basis", "")}
    luts = {f: rd(f"luts_{f}.json") for f in ("xc7", "ice40") if rd(f"luts_{f}.json")}
    arte = {f.name: str(f) for f in sorted(d.glob("*")) if f.suffix in (".v", ".json", ".gds", ".png", ".bin", ".vcd")}
    tpl = jinja2.Template((PKG_DIR / "report_template.md.j2").read_text(), trim_blocks=False)
    md = tpl.render(name=name or meta.get("name") or ir.get("name"), design_id=design_id, when=time.strftime("%Y-%m-%d %H:%M"),
                    ladder=lad, ports=rd("port.json"), source=meta.get("ingested_from") or ("training batch " + str(meta.get("batch_id")) if meta.get("batch_id") else "chipir"),
                    ops=sorted({n["op"] for n in ir["nodes"]}), synth=rd("synth.json"), luts=luts, pdks=pdks, layouts=layouts,
                    fpga=rd("bitstream.json"), cost=cost, baselines=base, artefacts=arte)
    (d / "report.md").write_text(md)
    return {"design_id": design_id, "report_md": md, "digest": hashlib.sha256(md.encode()).hexdigest()[:12],
            "files": [str(d / "report.md")], "verilog_url": f"/files/{design_id}/design.v",
            "netlist_json_url": f"/files/{design_id}/synth/net.json",
            "layout_png_url": next((f"/files/{design_id}/{p.relative_to(d)}" for p in d.rglob("*.png")), None)}


# ------------------------------------------------------------------------------------------------ agent-written RTL

@tool("Submit hand- or agent-written Verilog safely. It is screened (no system tasks or includes), linted and "
      "synthesised inside a locked-down container, then checked bit for bit against a reference: a chipir/1 model "
      "(reference_ir) or the scientist's vectors + expected outputs. Ports must follow the lab convention "
      "(port_spec: inputs/outputs with lanes, bits, signed). Accepted designs get a design_id like any other.",
      {"verilog": "str — the source", "top": "str — top module name", "port_spec": "dict — {inputs:[{name,lanes,bits,signed}], outputs:[...]}",
       "reference_ir": "dict — chipir/1 model the circuit must equal (optional)", "vectors": "dict — port -> [[ints]] (optional)",
       "expected": "dict — output -> [[ints]] (optional)", "n": "int — random vectors when checking against reference_ir (20000)"},
      lane="cpu")
def submit_verilog(verilog: str, top: str, port_spec: dict, reference_ir: dict | None = None, vectors: dict | None = None,
                   expected: dict | None = None, n: int = 20000) -> dict:
    import hashlib
    import numpy as np
    from chiplab import config
    from chiplab.verify.bitexact import circuit_outputs
    from chiplab.verify.sandbox import check_verilog
    if reference_ir is None and not (vectors and expected):
        raise ValueError("a reference is required: reference_ir, or vectors + expected")
    sid = "v" + hashlib.sha256((verilog + top + json.dumps(port_spec, sort_keys=True)).encode()).hexdigest()[:11]
    d = config.home("designs", sid)
    r = check_verilog(verilog, top, d / "sandbox")
    if not r["accepted"]:
        return {"design_id": None, "accepted": False, **r}
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

_PDK_ALIAS = {"sky130": "sky130A", "sky130A": "sky130A", "gf180": "gf180mcuD", "gf180mcuD": "gf180mcuD",
              "ihp": "ihp-sg13g2", "ihp-sg13g2": "ihp-sg13g2"}


def _layout(design_id: str, pdk: str, clock_period_ns: float, core_util: int, activity_vcd: str | None, timeout: int) -> dict:
    from pathlib import Path
    from chiplab.hw.librelane import timing_power_layout
    d = _design_dir(design_id)
    info = json.loads((d / "port.json").read_text())
    p = _PDK_ALIAS[pdk]
    r = timing_power_layout([d / "design.v"], info["top"], d / f"layout_{p}", pdk=p, clock_period_ns=clock_period_ns,
                            activity_vcd=Path(activity_vcd) if activity_vcd else None, core_util=core_util, timeout=timeout)
    pw = r.get("power_w")
    out = {"design_id": design_id, "pdk": p, "area_um2": r.get("area_um2"), "die_area_um2": r.get("die_area_um2"),
           "core_mm2": round(r["area_um2"] / 1e6, 6) if r.get("area_um2") else None,
           "die_mm2": round(r["die_area_um2"] / 1e6, 6) if r.get("die_area_um2") else None,
           "timing_ws_ns": r.get("timing_ws_ns"), "critical_path_ns": r.get("critical_path_ns"),
           "power_uw": round(pw * 1e6, 3) if pw is not None else None,
           "leakage_uw": round(r["leakage_w"] * 1e6, 6) if r.get("leakage_w") is not None else None,
           "energy_per_decision_pj": r.get("energy_per_decision_pj_vectorless"), "power_basis": r.get("power_basis"),
           "gate_equivalents_layout": r.get("gate_equivalents_layout"), "gds": r.get("gds"), "png": r.get("png"),
           "gds_url": f"/files/{design_id}/{Path(r['gds']).relative_to(d)}" if r.get("gds") else None,
           "png_url": f"/files/{design_id}/{Path(r['png']).relative_to(d)}" if r.get("png") else None,
           "basis": r.get("basis", "librelane-layout"), "hw_kind": "layout", "metrics": r.get("metrics"),
           "clock_period_ns": clock_period_ns, "seconds": r.get("seconds"),
           "files": [f for f in (r.get("gds"), r.get("png"), r.get("netlist")) if f]}
    (d / f"layout_{p}.json").write_text(json.dumps(out, default=str))
    return out


@tool("Place and route the chip with LibreLane (Docker): real cell area, die area, timing slack against a clock, "
      "power (vectorless, or from an activity VCD), GDS and the KLayout image. Validated on sky130; gf180 and ihp use "
      "the same flow (validated up to configuration).",
      {"design_id": "str", "pdk": "str — sky130|gf180|ihp (sky130)", "clock_period_ns": "float — decision clock for timing (20)",
       "core_util": "int — target utilisation % (40)", "activity_vcd": "str — VCD of real activity for power (optional)",
       "timeout": "int seconds (3600)"}, lane="docker", cacheable=True)
def layout(design_id: str, pdk: str = "sky130", clock_period_ns: float = 20.0, core_util: int = 40,
           activity_vcd: str | None = None, timeout: int = 3600) -> dict:
    return _layout(design_id, pdk, clock_period_ns, core_util, activity_vcd, timeout)


@tool("Timing and power of the laid-out chip (same LibreLane run as layout; cached, so calling both costs one run).",
      {"design_id": "str", "pdk": "str — sky130|gf180|ihp (sky130)", "clock_period_ns": "float (20)",
       "activity_vcd": "str — optional VCD for activity-based power"}, lane="docker", cacheable=True)
def timing_power(design_id: str, pdk: str = "sky130", clock_period_ns: float = 20.0, activity_vcd: str | None = None) -> dict:
    from chiplab.tools import TOOLS
    r = TOOLS["layout"]["fn"](design_id=design_id, pdk=pdk, clock_period_ns=clock_period_ns, activity_vcd=activity_vcd)
    return {k: v for k, v in r.items() if k not in ("cost", "cached", "status")}


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
    d = _design_dir(design_id)
    ir = json.loads((d / "ir.json").read_text())
    s = TOOLS["compile_stream"]["fn"].__wrapped__(design_id=design_id, tt=True)
    meta = {"title": title or f"chipin.space chip {design_id}", "author": "chipin.space chip lab",
            "description": "A fixed-weight integer model wired into logic gates",
            "how": "Inputs are streamed as 15-bit words ({uio_in, ui_in[6:0]}) on rising edges of ui_in[7]; when a frame "
                   "is complete the decision appears on uo_out[6:0] with valid on uo_out[7]."}
    r = _tt([d / "stream_tt.v"], s["top"], d / "tt", meta, tiles=tiles, harden=harden, pdk=_PDK_ALIAS.get(pdk, pdk),
            vectors=tt_vectors(ir, vectors), clock_hz=clock_hz, test_py=tt_project_test())
    (d / "tt_package.json").write_text(json.dumps(r, default=str))
    (d / "tt.json").write_text(json.dumps({"tiles_used": r.get("tiles"), "harden_ok": r.get("harden_ok")}))
    return {"design_id": design_id, **{k: r.get(k) for k in ("folder", "top", "tiles", "tile_um", "pdk", "user_config_ok",
            "rtl_test_passed", "harden_ok", "gl_test_passed", "gds", "png", "error", "seconds")},
            "cloud_build": "commit the folder under chiplab/tt_projects/ and run: gh workflow run tt-gds.yaml -f project_dir=<path>",
            "files": [r.get("folder")]}


@tool("Sequential equivalence (eqy) of the streaming wrapper against its synthesised netlist: verification level 2 "
      "for clocked designs. Works on small chips; may time out on large ones (reported honestly).",
      {"design_id": "str", "timeout": "int seconds (600)"}, lane="cpu", cacheable=True)
def prove_sequential(design_id: str, timeout: int = 600) -> dict:
    from chiplab.tools import TOOLS
    from chiplab.verify.eqy import prove_sequential as _ps
    d = _design_dir(design_id)
    s = TOOLS["compile_stream"]["fn"].__wrapped__(design_id=design_id, tt=True)
    r = _ps([d / "stream_tt.v"], s["top"], d / "eqy", timeout=timeout)
    (d / "eqy.json").write_text(json.dumps(r, default=str))
    return {"design_id": design_id, **r}


@tool("The chip's verification level (1 bit-exact, 2 formal, 3 streaming RTL sim + lint, 4 TT gate-level test, "
      "5 hardware) with the evidence behind it and what to run next.", {"design_id": "str"}, lane="inline")
def verification_level(design_id: str) -> dict:
    from chiplab.verify.ladder import stamp
    return {"design_id": design_id, **stamp(_design_dir(design_id))}
