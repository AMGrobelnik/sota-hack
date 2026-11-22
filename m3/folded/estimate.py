"""Folded engine estimate for a 30k-weight network from the measurements in results/: area, cycles and energy per
decision at 1 MHz and 32.768 kHz, on sky130 and gf180, against the fully wired cost per weight.

Every number is tagged: M = measured here (results/*.json), S = from a named source, A = assumed.
Writes results/estimate.json and prints the markdown tables used in feasibility.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from power import VDD, cells, totals

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
NAND2 = {"sky130": 3.7536, "gf180": 10.976}          # S: chiplab/chiplab/hw/pdk.py
DFF = {"sky130": "sky130_fd_sc_hd__dfxtp_1", "gf180": "gf180mcu_fd_sc_mcu7t5v0__dffq_1"}

# A: the 30k-weight network: 128 inputs -> 224 hidden -> 4 outputs, 4-bit activations (one decision = one pass).
LAYERS = [(128, 224), (224, 4)]
ABITS = 4
WEIGHTS = sum(i * o for i, o in LAYERS)               # 29,568
NEURONS = sum(o for _, o in LAYERS)
RF_BITS = (LAYERS[0][0] + LAYERS[0][1]) * ABITS       # input and hidden activations held at once
BIAS_BITS = NEURONS * 16                              # A: 16-bit biases, kept in the same kind of ROM
OVERHEAD_CYCLES = 2                                   # A: per neuron (bias load, shift/clip/write back)
UTIL = 0.6                                            # S: chiplab/chiplab/hw/pdk.py tt_tiles_est (60% placement)
ALPHA = 0.10                                          # A: 0->1 transitions per cell input per active cycle
K_WIRE = 2.0                                          # A: wire capacitance equal to pin capacitance
K_INT = 1.5                                           # A: internal (short-circuit) energy adds 50% to switching
ENGINE_FLOPS_CLOCKED = 48                             # A: accumulator, counters, control; RF is clock-gated
DECISION_PERIOD_S = 3.0                               # A: one decision every few seconds
CLOCKS = {"1 MHz": 1e6, "32.768 kHz": 32768.0}
WTYPES = {"ternary": 2, "uniform4": 4}
# S: fully wired ballpark given with the task (scale package results not on origin at the time of writing).
WIRED_BALLPARK_GATES = {"ternary": 6.5, "uniform4": 29.0}
ROUTES_UM2 = {"TT sky130, 16 tiles": ("sky130", 16 * 161 * 111.52),
              "TT GF180, 4x8 tiles": ("gf180", 32 * 346.64 * 160.72),
              "wafer.space GF180 1.73 mm2": ("gf180", 1.73e6),
              "wafer.space GF180 4.46 mm2": ("gf180", 4.46e6),
              "wafer.space GF180 12.92 mm2": ("gf180", 12.92e6),
              "ChipFoundry sky130 ~10 mm2": ("sky130", 10e6)}


def load(name: str):
    return json.loads((RES / name).read_text())


def rom_point(stats: str, size_kbit: int, pdk: str) -> dict:
    """M: per-bit area, GE, leakage and input capacitance of the word-16 ROM at one size."""
    for r in load("rom.json"):
        if (r.get("status") == "ok" and r["stats"] == stats and r["size_kbit"] == size_kbit and r["target"] == pdk
                and r["word_bits"] == 16):
            t = totals(r["cells_by_type"], pdk)
            b = r["stored_bits"]
            return {"um2": r["area_um2"] / b, "ge": r["gate_equivalents"] / b, "leak_nw": t["leak_nw"] / b,
                    "cin_pf": t["cin_pf"] / b, "at_kbit": size_kbit}
    raise KeyError((stats, size_kbit, pdk))


def fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Least-squares line y = a + b x."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return my - b * mx, b


def proto_model(wtype: str, pdk: str) -> dict:
    """M: folded neuron area/leak/cap vs n (P=1, n = 64, 256, 1024): intercept = engine, slope = per (weight +
    activation). The per-activation register-file cost = (slope - ROM cost of one weight at 16 kbit) / ABITS."""
    pts = []
    for n in (64, 256, 1024):
        d = load(f"proto_area_{wtype}_n{n}_p1.json")["folded"][pdk]
        t = totals(d["cells_by_type"], pdk)
        pts.append((n, d["area_um2"], t["leak_nw"], t["cin_pf"]))
    xs = [p[0] for p in pts]
    out = {}
    for i, k in ((1, "um2"), (2, "leak_nw"), (3, "cin_pf")):
        a, b = fit(xs, [p[i] for p in pts])
        out[k] = (a, b)
    rom16 = rom_point(wtype, 16, pdk)
    wb = WTYPES[wtype]
    rf = {k: (out[k][1] - wb * rom16[k]) / ABITS for k in ("um2", "leak_nw", "cin_pf")}
    p1 = load(f"proto_area_{wtype}_n256_p1.json")["folded"][pdk]["area_um2"]
    p4 = load(f"proto_area_{wtype}_n256_p4.json")["folded"][pdk]["area_um2"]
    return {"engine": {k: out[k][0] for k in out}, "rf_per_bit": rf, "slope": {k: out[k][1] for k in out},
            "p4_extra_um2": p4 - p1, "points": pts}


def cycles(p: int) -> int:
    """Cycles per decision: inputs loaded serially, then every neuron takes fan_in/P MAC cycles plus overhead."""
    return LAYERS[0][0] + sum(o * (-(-i // p) + OVERHEAD_CYCLES) for i, o in LAYERS)


def wired(wtype: str, pdk: str) -> dict:
    """M: the lab's fully wired chip of one wide neuron (n = 256 and 1024): GE, generic gates, leakage and input
    capacitance per weight."""
    out = {}
    for n in (256, 1024):
        d = load(f"proto_area_{wtype}_n{n}_p1.json")["wired"]
        if "gate_equivalents" in d.get(pdk, {}):
            t = totals(d[pdk]["cells_by_type"], pdk) if "cells_by_type" in d[pdk] else {}
            out[n] = {"ge_per_w": d[pdk]["gate_equivalents"] / n, "um2_per_w": d[pdk]["area_um2"] / n,
                      "gates_per_w": d["generic"].get("gates", 0) / n if "generic" in d else None,
                      "leak_nw_per_w": t.get("leak_nw", 0) / n, "cin_pf_per_w": t.get("cin_pf", 0) / n}
    return out


ALPHA_WIRED = 0.25   # A: 0->1 transitions per cell input per decision in a wired adder tree (incl. glitches)


def estimate() -> dict:
    rows = []
    for wtype, wb in WTYPES.items():
        rom_kbit = 64 if wtype == "ternary" else 128           # nearest measured size to 30k x wb bits
        for pdk in ("sky130", "gf180"):
            rom = rom_point(wtype, rom_kbit, pdk)
            bias = rom_point(wtype, 16, pdk)
            pm = proto_model(wtype, pdk)
            wr = wired(wtype, pdk)
            for p in (1, 4):
                comp = {"weight ROM": WEIGHTS * wb * rom["um2"], "bias ROM": BIAS_BITS * bias["um2"],
                        "activation RF": RF_BITS * pm["rf_per_bit"]["um2"],
                        "engine (P MACs, acc, control)": pm["engine"]["um2"] + (pm["p4_extra_um2"] if p == 4 else 0),
                        "sequencer (A: +50% of engine)": 0.5 * pm["engine"]["um2"]}
                synth = sum(comp.values())
                leak_nw = (WEIGHTS * wb * rom["leak_nw"] + BIAS_BITS * bias["leak_nw"] + RF_BITS * pm["rf_per_bit"]["leak_nw"]
                           + 1.5 * pm["engine"]["leak_nw"])
                eng_scale = 1.5 * (1 + (pm["p4_extra_um2"] / pm["engine"]["um2"] if p == 4 else 0))  # engine+seq, P
                cin_active = (WEIGHTS * wb * rom["cin_pf"] + BIAS_BITS * bias["cin_pf"]
                              + eng_scale * pm["engine"]["cin_pf"]
                              + RF_BITS * pm["rf_per_bit"]["cin_pf"] * 0.25)   # A: only the RF read mux toggles
                cclk = ENGINE_FLOPS_CLOCKED * cells(pdk)[DFF[pdk]]["cclk_pf"]  # M: liberty CLK pin cap, pF
                v = VDD[pdk]
                e_cycle_pj = K_INT * v * v * (ALPHA * K_WIRE * cin_active + K_WIRE * cclk)   # pF * V^2 = pJ
                cyc = cycles(p)
                per_clock = {}
                for cname, f in CLOCKS.items():
                    t_s = cyc / f
                    e_dyn_nj = cyc * e_cycle_pj / 1000
                    e_leak_nj = leak_nw * DECISION_PERIOD_S     # nW * s = nJ, always on
                    per_clock[cname] = {"seconds_per_decision": t_s, "dynamic_nj": e_dyn_nj,
                                        "leak_nj_per_period": e_leak_nj, "total_nj": e_dyn_nj + e_leak_nj,
                                        "avg_power_nw": (e_dyn_nj + e_leak_nj) / DECISION_PERIOD_S}
                wired_ge = {n: w["ge_per_w"] for n, w in wr.items()}
                w256 = wr.get(256, {})
                wired_e_nj = K_INT * v * v * ALPHA_WIRED * K_WIRE * WEIGHTS * w256.get("cin_pf_per_w", 0) / 1000
                wired_leak_nj = WEIGHTS * w256.get("leak_nw_per_w", 0) * DECISION_PERIOD_S
                wired_meas_um2 = WEIGHTS * (wr[256]["um2_per_w"]) / UTIL if 256 in wr else None
                ge_per_gate = (wr[256]["ge_per_w"] / wr[256]["gates_per_w"]) if 256 in wr and wr[256]["gates_per_w"] else None
                wired_ball_um2 = (WEIGHTS * WIRED_BALLPARK_GATES[wtype] * ge_per_gate * NAND2[pdk] / UTIL
                                  if ge_per_gate else None)
                rows.append({"wtype": wtype, "pdk": pdk, "p": p, "components_um2": comp, "synth_um2": synth,
                             "synth_ge": synth / NAND2[pdk], "layout_um2": synth / UTIL, "leak_nw": leak_nw,
                             "cin_active_pf": cin_active, "e_cycle_pj": e_cycle_pj, "cycles": cyc,
                             "per_clock": per_clock, "rom_basis_kbit": rom_kbit, "rf_per_bit_um2": pm["rf_per_bit"]["um2"],
                             "engine_um2": pm["engine"]["um2"], "wired_ge_per_weight_measured": wired_ge,
                             "wired_layout_um2_measured": wired_meas_um2, "wired_ge_per_generic_gate": ge_per_gate,
                             "wired_layout_um2_ballpark": wired_ball_um2, "wired_dynamic_nj": wired_e_nj,
                             "wired_gates_per_weight": w256.get("gates_per_w"),
                             "wired_leak_nj_per_period": wired_leak_nj,
                             "fits": {k: synth / UTIL <= cap for k, (pp, cap) in ROUTES_UM2.items() if pp == pdk},
                             "wired_fits_measured": {k: (wired_meas_um2 or 1e18) <= cap
                                                     for k, (pp, cap) in ROUTES_UM2.items() if pp == pdk}})
    return {"network": {"layers": LAYERS, "weights": WEIGHTS, "neurons": NEURONS, "rf_bits": RF_BITS,
                        "bias_bits": BIAS_BITS},
            "assumptions": {"util": UTIL, "alpha": ALPHA, "k_wire": K_WIRE, "k_int": K_INT,
                            "engine_flops_clocked": ENGINE_FLOPS_CLOCKED, "decision_period_s": DECISION_PERIOD_S,
                            "overhead_cycles_per_neuron": OVERHEAD_CYCLES, "vdd": VDD},
            "routes_um2": {k: v[1] for k, v in ROUTES_UM2.items()}, "rows": rows}


def markdown(e: dict) -> str:
    L = ["| type | pdk | P | synth mm2 | layout mm2 | cycles | ms @1MHz | s @32k |",
         "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in e["rows"]:
        L.append(f"| {r['wtype']} | {r['pdk']} | {r['p']} | {r['synth_um2'] / 1e6:.3f} | {r['layout_um2'] / 1e6:.3f} | "
                 f"{r['cycles']} | {r['per_clock']['1 MHz']['seconds_per_decision'] * 1e3:.1f} | "
                 f"{r['per_clock']['32.768 kHz']['seconds_per_decision']:.2f} |")
    L += ["", "| type | pdk | P | pJ/cyc | dyn nJ | leak nJ | W mm2 | W dyn | W leak |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in e["rows"]:
        w = r["wired_layout_um2_measured"]
        L.append(f"| {r['wtype']} | {r['pdk']} | {r['p']} | {r['e_cycle_pj']:.1f} | "
                 f"{r['per_clock']['1 MHz']['dynamic_nj']:.0f} | {r['per_clock']['1 MHz']['leak_nj_per_period']:.1f} | "
                 f"{(w or 0) / 1e6:.2f} | {r['wired_dynamic_nj']:.1f} | {r['wired_leak_nj_per_period']:.0f} |")
    L += ["", "| type | pdk | W GE/w | W gates/w | GE/gate | ballpark mm2 |", "|---|---|---:|---:|---:|---:|"]
    for r in e["rows"]:
        if r["p"] != 1:
            continue
        g = r["wired_ge_per_weight_measured"]
        L.append(f"| {r['wtype']} | {r['pdk']} | {g.get(256, 0):.1f} / {g.get(1024, 0):.1f} | "
                 f"{r['wired_gates_per_weight'] or 0:.1f} | {r['wired_ge_per_generic_gate'] or 0:.2f} | "
                 f"{(r['wired_layout_um2_ballpark'] or 0) / 1e6:.2f} |")
    L += ["", "| type | pdk | ROM | bias | RF | engine | seq |", "|---|---|---:|---:|---:|---:|---:|"]
    for r in e["rows"]:
        if r["p"] != 1:
            continue
        c = list(r["components_um2"].values())
        L.append(f"| {r['wtype']} | {r['pdk']} | " + " | ".join(f"{v / 1e6:.4f}" for v in c) + " |")
    return "\n".join(L)


if __name__ == "__main__":
    est = estimate()
    (RES / "estimate.json").write_text(json.dumps(est, indent=1))
    print(markdown(est))
    if "--json" in sys.argv:
        print(json.dumps(est, indent=1)[:6000])
