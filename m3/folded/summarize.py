"""Per-bit and per-weight cost tables from results/rom*.json (markdown on stdout)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def rows(paths: list[Path]) -> list[dict]:
    out = []
    for p in paths:
        out += [r for r in json.loads(p.read_text()) if r.get("status") == "ok"]
    return out


def table(rs: list[dict], word: int | None) -> str:
    key = {}
    for r in rs:
        if word is not None and r["word_bits"] != word:
            continue
        key[(r["size_kbit"], r["word_bits"], r["stats"], r["target"])] = r
    lines = ["| kbit | word | stats | gen g/bit | sky GE/bit | sky um2/bit | gf GE/bit | gf um2/bit |",
             "|---:|---:|---|---:|---:|---:|---:|---:|"]
    for (s, w, st) in sorted({k[:3] for k in key}, key=lambda k: (k[0], k[1], k[2])):
        g, sk, gf = (key.get((s, w, st, t)) for t in ("generic", "sky130", "gf180"))
        b = (g or sk or gf)["stored_bits"]

        def f(r, k, d=3):
            return f"{r[k] / b:.{d}f}" if r else "-"
        lines.append(f"| {s} | {w} | {st} | {f(g, 'gates')} | {f(sk, 'gate_equivalents')} | {f(sk, 'area_um2', 2)} | "
                     f"{f(gf, 'gate_equivalents')} | {f(gf, 'area_um2', 2)} |")
    return "\n".join(lines)


if __name__ == "__main__":
    files = [Path(a) for a in sys.argv[1:]] or sorted((HERE / "results").glob("rom*.json"))
    rs = rows(files)
    print("word 16, all sizes\n")
    print(table(rs, 16))
    print("\nall word widths\n")
    print(table(rs, None))
