"""Hardware and verification tools beyond the core set: formal proof, process mapping, timing/power, packaging,
cost. Registered into tools.TOOLS on import."""
from __future__ import annotations

import json

from chiplab import log
from chiplab.tools import _design_dir, _ensure_synth, tool


@tool("Verification level 2: prove the gate netlist equals the model for every possible input (ABC equivalence "
      "check against an independent golden model of the IR; falls back to proving synthesis if inconclusive).",
      {"design_id": "str", "timeout": "int seconds per proof attempt (600)"})
def prove_equivalence(design_id: str, timeout: int = 600) -> dict:
    from chiplab.verify.formal import prove
    d = _design_dir(design_id)
    syn = _ensure_synth(design_id)
    ir = json.loads((d / "ir.json").read_text()); info = json.loads((d / "port.json").read_text())
    r = prove(ir, info, __import__("pathlib").Path(syn["gate_verilog"]), d / "design.v", d / "formal", timeout)
    (d / "formal.json").write_text(json.dumps(r))
    log.event("check", design_id=design_id, formal=r["proved"], against=r["against"])
    return {"design_id": design_id, **r}


@tool("Map a design onto a real process's standard cells: area in µm², gate-equivalents (area / NAND2), cell "
      "counts and an estimate of Tiny Tapeout tiles.", {"design_id": "str", "pdk": "str — sky130|gf180|ihp"})
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
