"""Write m3/examples/RESULTS.md from every <name>/meta.json (generator) and <name>/result.json (run_gallery.py).

    python3 m3/examples/make_results.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[1]


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, timeout=30).stdout.strip()


def short_det(d: dict) -> str:
    if "sensitivity" in d:
        return f"Se {d['sensitivity']:.2f} Sp {d['specificity']:.2f}"
    return f"acc {d['accuracy']:.2f}"


def long_det(d: dict) -> str:
    if "sensitivity" in d:
        return (f"sensitivity {d['sensitivity']:.3f} ({d['events'] - d['missed']} of {d['events']} events), "
                f"specificity {d['specificity']:.3f} ({d['false_alarms']} false alarms), accuracy "
                f"{d['accuracy']:.3f}")
    rec = ", ".join(f"{c} {r:.3f}" for c, r in d["recall"].items())
    return f"accuracy {d['accuracy']:.3f}; recall per class {rec}"


def vectors_exact(r: dict) -> tuple[int, int, bool]:
    pairs = r.get("sim_vectors_pairs") or {}
    circ = [v for k, v in pairs.items() if k.startswith("circuit_vs")]
    n = r.get("sim_vectors_n") or 0
    same = min((v.get("identical", 0) for v in circ), default=0)
    return same, n, bool(r.get("sim_vectors_bit_exact")) and same == n and n > 0


def main() -> None:
    meta_run = json.loads((OUT / "run_meta.json").read_text()) if (OUT / "run_meta.json").exists() else {}
    names = sorted(p.name for p in OUT.iterdir() if (p / "meta.json").exists())
    rows, paras, all_ok = [], [], True
    for n in names:
        m = json.loads((OUT / n / "meta.json").read_text())
        r = json.loads((OUT / n / "result.json").read_text()) if (OUT / n / "result.json").exists() else {}
        same, nv, exact = vectors_exact(r)
        rand = r.get("sim_random_bit_exact")
        prove = (r.get("prove") or {}).get("proved")
        rt, rg = r.get("rtlsim_tt") or {}, r.get("rtlsim_generic") or {}
        ok = exact and rand is True and prove is True and rt.get("passed") is True
        all_ok &= ok
        main_det = next(iter(m["detection"].values()))
        tiles = r.get("tt_package_tiles") or "-"
        rows.append(f"| `{n}` | {m['model_kind'].split(' (')[0]} | {r.get('gates', '-')} | "
                    f"{r.get('ge_sky130', '-')} | {r.get('luts_xc7', '-')} | {tiles} | "
                    f"{same}/{nv} {'yes' if ok else 'NO'} | {r.get('level', '-')} | {short_det(main_det)} |")
        dets = "; ".join(f"`{k}`: {long_det(v)}" for k, v in m["detection"].items())
        bits = [f"{same} of {nv} test windows identical between the synthesized circuit and the model "
                f"({'all equal' if exact else 'NOT all equal'})",
                f"100,000 random inputs {'bit-exact' if rand else 'NOT bit-exact: ' + str(rand)}",
                f"formal equivalence {'proved' if prove else 'not proved'} "
                f"({(r.get('prove') or {}).get('method')})",
                f"Tiny Tapeout streaming wrapper RTL simulation {'passed' if rt.get('passed') else 'FAILED'} on "
                f"{rt.get('vectors')} windows ({rt.get('transfers_per_frame')} transfers per frame"
                + (", only the low 7 output bits visible" if rt.get("truncated") else "") + ")"]
        if rg:
            bits.append(f"generic wrapper (every output bit) {'passed' if rg.get('passed') else 'FAILED'}")
        errs = {k: v for k, v in (r.get("errors") or {}).items() if k not in ("ingest",) or not r.get("design_id")}
        paras.append("\n".join([
            f"### {m['title']} (`{n}`)", "",
            f"{m['task']} Simulated: {m['signal']} Model: {m['model_kind']}, {m['model_size']}. "
            f"Chip (CLI, ingested via {r.get('ingested_via')}): {r.get('gates')} gates, logic depth "
            f"{r.get('depth')}, {r.get('ge_sky130')} gate equivalents and {round(r.get('area_um2_sky130') or 0, 1)} um2 in "
            f"sky130 before layout, {r.get('luts_xc7')} LUTs on xc7 and {r.get('luts_ice40')} on ice40, Tiny "
            f"Tapeout tiles {tiles} (sky130 estimate {r.get('tt_tiles_est_sky130')}), verification level "
            f"{r.get('level')} ({r.get('level_meaning')}). Bit-exact: " + "; ".join(bits) + ". "
            f"Detection on {main_det['windows']} SYNTHETIC test windows (the chip's outputs equal the model's on "
            f"all of them, so these are the chip's figures too): {dets}."
            + (f" Errors recorded: {json.dumps(errs)[:400]}." if errs else ""), ""]))
    lab = git("log", "-1", "--format=%h %s", "--", "chiplab")
    head = [
        "# P5 example gallery: medical-sensing detectors on chip", "",
        "Ten small detectors for medical-sensing tasks, each trained on seeded SYNTHETIC sensor windows and taken "
        "model to chip through the lab's CLI only. The data is simulated (one line per example below says how), it "
        "is not patient data, and the detection figures are on synthetic test windows: they show the detector "
        "and its chip agree bit for bit, and make no clinical claim.", "",
        "How measured: `m3/examples/gen_gallery.py` builds models and test vectors; `m3/examples/run_gallery.py` "
        "pushes all ten through the lab's batch lanes in one run (parallel ingest-model CLI calls, then "
        "submit-batch / synthesize-batch jobs on `chiplab workers`: 15 CPU, 1 GPU and 3 Docker workers, the lab's defaults for this Mac); every "
        "number is what the CLI printed (saved in `<name>/cli/*.json`, home path replaced by ~). Machine: Apple "
        f"M3 Max, 16 cores, 128 GB, shared with other packages. Runs: one batch run on lab commit `{lab}`, "
        f"{meta_run.get('examples')} examples, {meta_run.get('wall_s_all_stages')} s wall for all stages, finished "
        f"{meta_run.get('finished')}. Detection figures: numpy on the generator's ground truth.", "",
        f"All ten bit-exact on every check: {'yes' if all_ok and len(names) == 10 else 'NO, see the rows'}.", "",
        "| Example | Model | Gates | GE | LUT | TT | Exact | Lv | Detect |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *rows, "",
        "Gates: Yosys generic cells. GE: sky130 gate equivalents before layout. LUT: xc7. TT: Tiny Tapeout tiles "
        "from tt-package. Exact: test windows identical / total, and yes only when 100,000 random vectors, formal "
        "equivalence and the Tiny Tapeout RTL testbench also passed. Lv: the lab's verification level. Detect: "
        "on the synthetic test windows (Se sensitivity, Sp specificity, acc accuracy).", "",
        "## Examples", "", *paras,
        "## Lab issues met here", "",
        "- `ingest-model` format xgboost_json fails with `TypeError: 'NoneType' object cannot be interpreted as an "
        "integer`: a reloaded XGBClassifier has n_estimators=None, which TreeLUT needs. Fix: "
        "`proposed/xgboost-json-reload.patch`. Until then the runner ingests the lab's own TreeLUT conversion "
        "(`chipir.json`) and records both answers.",
        "- In the shared job worker an xgboost_json ingest next to a torchlogix ingest crashed the CPU lane (two "
        "OpenMP runtimes in one process on macOS). The runner therefore runs ingest-model as parallel CLI "
        "processes; every later stage runs on the job lanes.",
        "- `tt-package` without harden reports `user_config_ok: false` on this Mac (cairo library not found by "
        "the Tiny Tapeout tools); the tile count is still printed.", "",
        "Rebuild: `chiplab/.venv/bin/python m3/examples/gen_gallery.py`, start `chiplab workers`, then "
        "`chiplab/.venv/bin/python m3/examples/run_gallery.py` and `python3 m3/examples/make_results.py`.", ""]
    (OUT / "RESULTS.md").write_text("\n".join(head))
    print("RESULTS.md written;", len(names), "examples; all bit-exact:", all_ok)


if __name__ == "__main__":
    main()
