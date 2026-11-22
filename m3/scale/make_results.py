"""Turn the sweep's raw results.json into the published one: paths removed, per-design summary, fit per route.

Fit model: per (style, emitter, process) a power law area = a * weights^b through the measured designs (1k to 30k
weights), inverted to the largest model that fits a route's usable cell area. Usable area = route area x
utilisation (UTIL, and UTIL_LOW as the conservative case). Window registers are added: L x 6 input bits per
held window (L = 64 inputs, the 30k design's input count), at the process's D flip-flop area.
  single     : one model, one window (one EEG channel)
  parallel18 : 18 model copies, 18 windows (18-channel EEG, one copy per channel, as wired today)
  serial18   : one model copy evaluated per channel in turn (channel-serial), one window plus an 18-bit result
               register; the host streams one channel's window at a time, as the lab's streaming wrapper does
fmax estimate (no layout): 1000 / (logic depth x ns per generic-gate level), the ns per level measured on the
M3 layouts (m3/layouts: critical path / depth of the same lab's chips), so it ignores the longer wires of a big die.

Several sweep runs merge per design (a later run's step replaces an earlier one unless the earlier one finished and
the later one did not); --luts adds lut_retry.py's longer-cap LUT counts; --reaped adds reap_orphans.py's logs.

Usage: python make_results.py --raw run1.json [--raw run2.json] [--luts lut_retry.json] [--reaped log ...]
                              --out results.json [--md tables.md]
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
from pathlib import Path

UTIL, UTIL_LOW = 0.60, 0.40
CHANNELS = 18
WINDOW_BITS = 64 * 6
DFF_UM2 = {"sky130": 20.0192, "gf180": 63.6608, "ihp": 48.9888}   # dfxtp_1, dffq_1, dfrbpq_1 (Liberty, typical)
NS_PER_LEVEL = {"sky130": 0.395, "gf180": 1.03, "ihp": 0.21}       # m3/layouts: critical path / synthesized depth
TT_SKY_TILE = 161.0 * 111.52
TT_GF_TILE = 346.64 * 160.72
ROUTES = [
    {"id": "tt_sky130", "name": "Tiny Tapeout sky130, 16 tiles", "pdk": "sky130", "um2": 16 * TT_SKY_TILE,
     "basis": "16 tiles of 161 x 111.52 um"},
    {"id": "tt_gf180", "name": "Tiny Tapeout GF180, 4x8 tiles", "pdk": "gf180", "um2": 32 * TT_GF_TILE,
     "basis": "32 tiles of 346.64 x 160.72 um"},
    {"id": "ws_quarter", "name": "wafer.space GF180 quarter", "pdk": "gf180", "um2": 1.73e6, "basis": "1.73 mm2 core"},
    {"id": "ws_half", "name": "wafer.space GF180 half", "pdk": "gf180", "um2": 4.46e6,
     "basis": "4.46 mm2 core (4.46 to 5.02; lower bound used)"},
    {"id": "ws_full", "name": "wafer.space GF180 full", "pdk": "gf180", "um2": 12.92e6, "basis": "12.92 mm2 core"},
    {"id": "chipfoundry", "name": "ChipFoundry sky130, about 10 mm2", "pdk": "sky130", "um2": 10.0e6,
     "basis": "about 10 mm2 user area"},
]
PATH_RE = re.compile(r"/(?:Users|home|private|var/folders)/[^\s\"']*")


def scrub(x):
    if isinstance(x, str):
        return PATH_RE.sub(lambda m: "<path>/" + m.group(0).rsplit("/", 1)[-1], x)
    if isinstance(x, list):
        return [scrub(v) for v in x]
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items()}
    return x


def powerlaw(pts: list[tuple[float, float]]) -> tuple[float, float] | None:
    pts = [(w, a) for w, a in pts if w and a]
    if len(pts) < 2:
        return None
    xs, ys = [math.log(w) for w, _ in pts], [math.log(a) for _, a in pts]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return math.exp(my - b * mx), b


def max_weights(fit: tuple[float, float], budget_um2: float) -> float:
    a, b = fit
    return (budget_um2 / a) ** (1 / b) if budget_um2 > 0 else 0.0


def fits(fit, pdk: str, route_um2: float, util: float) -> dict:
    usable = route_um2 * util
    reg = WINDOW_BITS * DFF_UM2[pdk]
    return {"single": max_weights(fit, usable - reg),
            "parallel18": max_weights(fit, usable / CHANNELS - reg),
            "serial18": max_weights(fit, usable - reg - CHANNELS * DFF_UM2[pdk])}


def label(w: float) -> str:
    if w < 1:
        return "none"
    s = f"{w:.0f}" if w < 1000 else (f"{w / 1000:.1f}k" if w < 10000 else f"{w / 1000:.0f}k")
    return s + (" (extrap.)" if w < 1000 or w > 30000 else "")


def summary(rec: dict) -> dict:
    m = rec["model"]
    st = rec.get("steps", {})
    out = {"key": rec["key"], "design_id": rec.get("design_id"), "style": m["style"], "size": m["size"],
           "emitter": rec["variant"], "weights": m["weights"], "nonzero_weights": m["nonzero_weights"],
           "inputs": m["inputs"], "hidden": m["hidden"], "gates": rec.get("gates"),
           "gates_per_weight": rec.get("gates_per_weight"), "gates_per_nonzero_weight": rec.get("gates_per_nonzero_weight"),
           "depth": rec.get("depth"), "luts_xc7": rec.get("luts_xc7"), "area_um2": rec.get("area_um2", {}),
           "synth_s": (st.get("synthesize") or {}).get("wall_s"), "bit_exact": rec.get("bit_exact"),
           "sim_vectors": rec.get("sim_n")}
    if rec["variant"] == "alkaid":
        out["alkaid_ingest_s"] = (st.get("ingest") or {}).get("wall_s")
    out["fmax_mhz_est"] = {p: round(1000 / (rec["depth"] * NS_PER_LEVEL[p]), 1) for p in NS_PER_LEVEL} \
        if rec.get("depth") else {}
    pr = rec.get("proof") or {}
    ps = st.get("prove_equivalence") or {}
    out["proof"] = {"proved": pr.get("proved"), "against": pr.get("against"), "seconds": pr.get("seconds"),
                    "wall_s": ps.get("wall_s"), "state": ps.get("state"), "status": ps.get("status")}
    ram = rec.get("peak_rss_mb_sampled") or {}
    out["peak_rss_mb"] = {"synthesize": sum(v for k, v in ram.items() if k.startswith("synth/")) or None,
                          "count_luts": sum(v for k, v in ram.items() if k.startswith("luts_xc7/")) or None,
                          "map_max": max([v for k, v in ram.items() if k.startswith("pdk_")] or [0]) or None,
                          "prove": max([v for k, v in ram.items() if k.startswith("formal/")] or [0]) or None}
    out["failed_steps"] = {k: (v.get("error") or v.get("reason") or v.get("state"))[-300:]
                           for k, v in st.items() if v.get("status") not in ("ok", None) or v.get("state") == "not run"}
    return out


def merge(runs: list[dict]) -> dict:
    base = copy.deepcopy(runs[0])
    base["runs"] = []
    by = {r["key"]: r for r in base["designs"]}
    for i, run in enumerate(runs):
        base["runs"].append({"run": i + 1, "elapsed_s": run.get("elapsed_s"), "final": run.get("final"),
                             "open_jobs": run.get("open_jobs"), "settings": run.get("settings")})
        if i == 0:
            continue
        for k in ("orphaned_solvers", "rss_guard_kills"):
            base[k] = (base.get(k) or []) + (run.get(k) or [])
        base["max_concurrent_yosys_rss_mb"] = max(base.get("max_concurrent_yosys_rss_mb") or 0,
                                                  run.get("max_concurrent_yosys_rss_mb") or 0)
        for rec in run["designs"]:
            old = by.get(rec["key"])
            if old is None:
                by[rec["key"]] = rec
                base["designs"].append(rec)
                continue
            for step, st in rec.get("steps", {}).items():
                prev = old["steps"].get(step)
                if prev is None or prev.get("status") != "ok" or st.get("status") == "ok":
                    old["steps"][step] = st
            for f in ("proof", "bit_exact", "sim_n", "sim_device", "sim_pairs"):
                if rec.get(f) is not None:
                    old[f] = rec[f]
            ram = old.setdefault("peak_rss_mb_sampled", {})
            for k, v in (rec.get("peak_rss_mb_sampled") or {}).items():
                ram[k] = max(ram.get(k, 0), v)
    return base


def add_luts(raw: dict, luts: dict) -> None:
    for rec in raw["designs"]:
        r = luts.get(rec.get("design_id"))
        if not r:
            continue
        rec["steps"]["count_luts_retry"] = {k: r.get(k) for k in ("state", "status", "cap_s", "run_s", "wall_s", "error")}
        if r.get("status") == "ok":
            rec.update(luts_xc7=r["luts"], carry4_xc7=r.get("carry4"), muxf_xc7=r.get("muxf"),
                       luts_basis=f"synthesize target=xc7 with a {r['cap_s']} s cap (count-luts hit its 900 s cap)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, action="append", required=True)
    ap.add_argument("--luts", type=Path)
    ap.add_argument("--reaped", type=Path, nargs="*", default=[])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--md", type=Path)
    a = ap.parse_args()
    raw = scrub(merge([json.loads(p.read_text()) for p in a.raw]))
    if a.luts and a.luts.exists():
        add_luts(raw, json.loads(a.luts.read_text()))
    raw["orphans_reaped"] = [json.loads(ln) for p in a.reaped if p.exists()
                             for ln in p.read_text().splitlines() if ln.startswith("{")]
    rows = [summary(r) for r in raw["designs"]]
    fitd, fit_rows = {}, []
    for style in ("ternary", "q4"):
        for em in ("default", "alkaid"):
            for pdk in ("sky130", "gf180", "ihp"):
                pts = [(r["weights"], r["area_um2"].get(pdk)) for r in rows if r["style"] == style and r["emitter"] == em]
                f = powerlaw(pts)
                if f:
                    fitd[(style, em, pdk)] = f
                    fit_rows.append({"style": style, "emitter": em, "pdk": pdk, "a": f[0], "b": round(f[1], 3),
                                     "points": len([p for p in pts if p[1]])})
    route_rows = []
    for rt in ROUTES:
        for style in ("ternary", "q4"):
            for em in ("default", "alkaid"):
                f = fitd.get((style, em, rt["pdk"]))
                if not f:
                    continue
                route_rows.append({"route": rt["id"], "style": style, "emitter": em,
                                   "util": {str(u): {k: round(v) for k, v in fits(f, rt["pdk"], rt["um2"], u).items()}
                                            for u in (UTIL, UTIL_LOW)}})
    w30 = []
    for r in rows:
        if r["size"] != "30k":
            continue
        for rt in ROUTES:
            area = r["area_um2"].get(rt["pdk"])
            if not area:
                continue
            reg = WINDOW_BITS * DFF_UM2[rt["pdk"]]
            need = {"single": area + reg, "parallel18": CHANNELS * (area + reg),
                    "serial18": area + reg + CHANNELS * DFF_UM2[rt["pdk"]]}
            w30.append({"key": r["key"], "route": rt["id"],
                        "fill_at_60pct": {k: round(v / (rt["um2"] * UTIL), 3) for k, v in need.items()}})
    out = {**{k: v for k, v in raw.items() if k != "designs"},
           "assumptions": {"utilisation": UTIL, "utilisation_conservative": UTIL_LOW, "channels": CHANNELS,
                           "window_bits": WINDOW_BITS, "dff_um2": DFF_UM2, "ns_per_level": NS_PER_LEVEL,
                           "routes": ROUTES},
           "summary": rows, "area_fit": fit_rows, "fit": route_rows, "fit_30k": w30, "designs": raw["designs"]}
    a.out.write_text(json.dumps(out, indent=1, default=str))
    if a.md:
        a.md.write_text(markdown(rows, route_rows, w30))


def markdown(rows, route_rows, w30) -> str:
    L = ["| Design | Gates | G/w | Depth | LUTs | sky130 um2 | gf180 um2 | ihp um2 |",
         "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        ar = r["area_um2"]
        f = lambda v: f"{v:,.0f}" if v else "-"  # noqa: E731
        L.append(f"| {r['key']} | {f(r['gates'])} | {r['gates_per_weight'] or '-'} | {r['depth'] or '-'} | "
                 f"{f(r['luts_xc7'])} | {f(ar.get('sky130'))} | {f(ar.get('gf180'))} | {f(ar.get('ihp'))} |")
    L += ["", "| Design | Synth s | Peak MB | Sim | Proof | Proof s | fmax sky/gf est |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        p = r["proof"]
        pv = {True: "proved", False: "REFUTED", None: "inconclusive"}.get(p["proved"], "-") \
            if p["state"] == "done" else (p["state"] or "-")
        fm = r["fmax_mhz_est"]
        L.append(f"| {r['key']} | {r['synth_s'] or '-'} | {r['peak_rss_mb']['synthesize'] or '-'} | "
                 f"{'bit-exact' if r['bit_exact'] else r['bit_exact']} | {pv} | {p['wall_s'] or '-'} | "
                 f"{fm.get('sky130', '-')} / {fm.get('gf180', '-')} |")
    for u in (str(UTIL), str(UTIL_LOW)):
        L += ["", f"Weights that fit, utilisation {float(u):.0%} (single / 18 parallel / channel-serial):", "",
              "| Route | Style | Emitter | Single | 18 par. | Serial |", "| --- | --- | --- | --- | --- | --- |"]
        for r in route_rows:
            v = r["util"][u]
            L.append(f"| {r['route']} | {r['style']} | {r['emitter']} | {label(v['single'])} | "
                     f"{label(v['parallel18'])} | {label(v['serial18'])} |")
    L += ["", "30k designs: share of the route's usable area (60%) needed:", "",
          "| Design | Route | Single | 18 par. | Serial |", "| --- | --- | --- | --- | --- |"]
    for r in w30:
        v = r["fill_at_60pct"]
        L.append(f"| {r['key']} | {r['route']} | {v['single']:.2f} | {v['parallel18']:.2f} | {v['serial18']:.2f} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
