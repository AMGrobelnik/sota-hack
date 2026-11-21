"""Extra formal checks: prove two RTL implementations compute the same function for every input (ABC cec).

Used to guarantee that an optimised emission (emit/optimized.py) is functionally identical to the default
emitter's RTL, independent of any test vectors.
"""
from __future__ import annotations

import time
from pathlib import Path

from chiplab.hw.yosys import SynthError
from chiplab.verify.formal import _blif, _cec


def prove_same_function(rtl_a: Path, rtl_b: Path, top_a: str, top_b: str, workdir: Path, timeout: int = 600) -> dict:
    """Both designs are flattened and mapped to simple gates, then ABC proves (or refutes) equivalence of every
    output bit for every input. Ports are matched by name, so both must use the same port names."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        a = _blif(Path(rtl_a), top_a, "same_a", workdir, timeout, synth=True)
        b = _blif(Path(rtl_b), top_b, "same_b", workdir, timeout, synth=True)
        ok, detail = _cec(a, b, workdir, timeout)
    except SynthError as e:
        ok, detail = None, str(e)[-400:]
    return {"proved": ok, "method": "abc cec (both RTLs flattened to gates)", "detail": detail,
            "seconds": round(time.time() - t0, 1)}


def prove_matvec_nodes(ir: dict, optimized_text: str, workdir: Path, timeout: int = 600, node_timeout: int = 120) -> dict:
    """Scalable proof that an alkaid-optimised design equals the default design, node by node.

    The optimised emission differs from the default only inside matvec nodes (every other line is produced by the
    same code). For each matvec node, a sub-design (free inputs clamped to the node's derived input ranges, then
    the node) is emitted both ways and proved equal with ABC cec. The alkaid module generated for the sub-design
    is checked to be textually identical to the one inside the full optimised design, so the proof covers it.
    Returns {proved, nodes: [{id, proved, same_module, seconds}], seconds}.
    """
    import re
    from chiplab.emit.optimized import emit_optimized
    from chiplab.emit.verilog import emit
    from chiplab.ir.ranges import ranges as ir_ranges
    from chiplab.verify.formal import _node_subir
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    R = ir_ranges(ir)
    t0, results = time.time(), []

    def body(text: str, mod: str) -> str | None:
        m = re.search(rf"module {re.escape(mod)} \((.*?)endmodule", text, flags=re.S)
        return m.group(1) if m else None

    from chiplab.ir.schema import top_name
    full_top = top_name(ir)
    for nd in ir.get("nodes", []):
        if nd["op"] != "matvec":
            continue
        sub = _node_subir(ir, nd, R)
        d = workdir / f"node_{nd['id']}"
        d.mkdir(exist_ok=True)
        td, di = emit(sub, top=f"d_{nd['id']}")
        ta, ai = emit_optimized(sub, "alkaid", top=f"a_{nd['id']}")
        impl = next((n for n in ai["optimizer"]["nodes"] if n["node"] == nd["id"]), {})
        if impl.get("impl") != "alkaid":
            results.append({"id": nd["id"], "proved": True, "note": "standard code (not optimised)"})
            continue
        same_mod = body(ta, f"a_{nd['id']}_mv_{nd['id']}") == body(optimized_text, f"{full_top}_mv_{nd['id']}")
        (d / "d.v").write_text(td); (d / "a.v").write_text(ta)
        left = max(10, int(timeout - (time.time() - t0)))
        t1 = time.time()
        r = prove_same_function(d / "d.v", d / "a.v", di["top"], ai["top"], d, min(left, node_timeout))
        how = "whole node"
        if r["proved"] is None:
            # fallback: one output row's logic cone at a time (same multi-row alkaid module; unused rows are
            # removed by synthesis), which together prove the whole node
            how, rows_ok = "row by row", True
            for j in range(len(nd["W"])):
                subj = dict(sub, nodes=sub["nodes"] + [{"id": "pick", "op": "gather", "src": nd["id"], "idx": [j]}],
                            outputs=[{"name": "o", "src": "pick"}])
                tdj, dij = emit(subj, top=f"d_{nd['id']}_{j}")
                taj, aij = emit_optimized(subj, "alkaid", top=f"a_{nd['id']}_{j}")
                dj = d / f"row_{j}"; dj.mkdir(exist_ok=True)
                (dj / "d.v").write_text(tdj); (dj / "a.v").write_text(taj)
                left = max(10, int(timeout - (time.time() - t0)))
                rj = prove_same_function(dj / "d.v", dj / "a.v", dij["top"], aij["top"], dj, left)
                if rj["proved"] is not True:
                    rows_ok = rj["proved"]; break
            r = {"proved": True if rows_ok is True else rows_ok}
        results.append({"id": nd["id"], "proved": r["proved"], "same_module": same_mod, "how": how,
                        "seconds": round(time.time() - t1, 1)})
        if r["proved"] is not True:
            break
    ok = all(x["proved"] is True and x.get("same_module", True) for x in results)
    bad = any(x["proved"] is False for x in results)
    return {"proved": True if ok else (False if bad else None), "nodes": results, "seconds": round(time.time() - t0, 1),
            "method": "per-matvec-node abc cec on the node's derived input ranges; all other logic is identical code"}
