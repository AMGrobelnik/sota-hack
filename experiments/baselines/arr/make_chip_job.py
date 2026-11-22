"""Build a chip-lab job: designs plus the held-out test beats' actual chip inputs and the integer
model's outputs on them (for bit-exact simulation).

Usage:
  python -I make_chip_job.py <beats.npz> <fold irs json> <folds.json> <fold> <out json> [designs,...]
  python -I make_chip_job.py <beats.npz> <ds_irs.json> DS2 -1 <out json> [designs,...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from arrlib import load_beats, run_ir

DS2 = [100, 103, 105, 111, 113, 117, 121, 123, 200, 202, 210, 212, 213, 214, 219, 221, 222, 228, 231, 232, 233, 234]
AAMI_SYMS = set("NLRejAaJSVEF/fQ")


def main(beats: Path, irs_path: Path, folds_arg: str, fold: int, out: Path, names: list[str] | None) -> None:
    B = load_beats(beats)
    bits = B.bits
    irs = json.loads(irs_path.read_text())
    if fold < 0:
        te = np.isin(B.rec, DS2) & np.isin(B.sym, [ord(c) for c in AAMI_SYMS])
        flat = {f"{d}_{h}": ir for d, heads in irs.items() for h, ir in heads.items()}
        prefix = "DS2"
    else:
        f = json.loads(Path(folds_arg).read_text())[fold]
        te = np.isin(B.rec, f["test"])
        flat = irs
        prefix = f"fold{fold:02d}"
    job = []
    for name, ir in flat.items():
        if names and not any(name.startswith(n) for n in names):
            continue
        vec = {}
        for p in ir["inputs"]:
            if p["name"] == "b":
                vec["b"] = bits[te][:, ir["meta"]["bit_features"]].tolist()
            elif p["name"] == "rr":
                vec["rr"] = B.rr[te].tolist()
        expected = run_ir(ir, bits[te], B.rr[te])["y"][:, 0].tolist()
        job.append({"key": f"{prefix}_{name}", "ir": ir, "vectors": vec, "expected": expected})
    out.write_text(json.dumps({"designs": job}))
    print(len(job), "designs,", int(te.sum()), "test beats")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], int(sys.argv[4]), Path(sys.argv[5]), sys.argv[6].split(",") if len(sys.argv) > 6 else None)
