"""Collect every runs/<batch>/results.jsonl into results/all.jsonl (home path replaced with ~) and print a short table.

usage: python collect.py   (paths are relative to this file; no chiplab import needed)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = str(Path.home())


def short(r: dict) -> str:
    if "golden_proved" in r:  # golden_proof.py (chain recipe)
        steps = {k: (v.get("proved"), v.get("seconds")) for k, v in r["steps"].items()}
        return f"chain golden={r['golden_proved']} wall={r['wall_s']}s steps={steps}"
    if "B_only" in r or "against" in r:
        return json.dumps(r)[:300]
    nodes = r.get("nodes")
    extra = f" B={r.get('B_proved')}/{r.get('B_seconds')}s nodes={[(n['id'], n['proved'], n.get('seconds')) for n in nodes]}" if nodes else ""
    return (f"{r['scope']}:{r['method']} proved={r['proved']} {r['seconds']}s (limit {r.get('timeout')})"
            f"{' MUTANT' if r.get('mutant') else ''}{extra}")


def main() -> None:
    out = ROOT / "results" / "all.jsonl"
    out.parent.mkdir(exist_ok=True)
    rows = []
    for f in sorted((ROOT / "runs").glob("*/results.jsonl")):
        for line in f.read_text().splitlines():
            if line.strip():
                r = json.loads(line.replace(HOME, "~"))
                r["batch"] = f.parent.name
                rows.append(r)
                print(f"[{f.parent.name}] {r.get('design', r.get('design_id'))} {short(r)}")
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"{len(rows)} rows -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
