"""Manufacturing routes and prices (checked 21 Nov 2026) and a per-design cost estimate. Data, not advice:
prices and deadlines change, so every route carries its source date."""
from __future__ import annotations

import math

CHECKED = "2026-11-21"
ROUTES = [
    {"id": "fpga_ice40", "name": "iCE40UP5K FPGA (UPduino board)", "kind": "fpga", "unit_cost": 36.0, "currency": "USD",
     "capacity": {"lut4": 5280}, "lead_time": "days", "deadline": None, "open_source_flow": True,
     "notes": "reprogrammable; good for a bench demo, not a medical product"},
    {"id": "tt_sky130", "name": "Tiny Tapeout, SkyWater 130 nm (TTSKY26)", "kind": "asic_shuttle", "tile_cost": 70.0,
     "devkit": 300.0, "devkit_individual": 100.0, "currency": "EUR", "tile_um": [161, 111.5], "max_tiles": 16,
     "deadline": "2026-11-30", "ships": "about 2027-06", "open_source_flow": True,
     "notes": "designs are published openly; 8 in / 8 out / 8 bidir pins, so inputs are streamed"},
    {"id": "tt_gf180", "name": "Tiny Tapeout, GlobalFoundries 180 nm", "kind": "asic_shuttle", "tile_cost": 70.0,
     "devkit": 300.0, "currency": "EUR", "deadline": "2026-12-07", "open_source_flow": True, "tile_um": None,
     "notes": "same pricing as sky130 per the organisers; tile size differs"},
    {"id": "waferspace_gf180", "name": "wafer.space, GF180", "kind": "asic_run", "run_cost": 3000.0, "dies": 1000,
     "currency": "USD", "deadline": "2026-12-16", "ships": "2027-Q2", "open_source_flow": True,
     "notes": "GDS with the pin ring; price is for the whole run of about 1,000 dies"},
    {"id": "pragmatic_flexic", "name": "Pragmatic FlexIC (flexible)", "kind": "asic_flexible", "per_mm2": 900.0,
     "min_mm2": 9.0, "units": 50, "currency": "EUR", "deadline": "2027-03-16", "open_source_flow": False,
     "notes": "needs Pragmatic's design kit with commercial tools; our area numbers are sky130 estimates, not FlexIC"},
]


#: sky130 cell area per synthesised gate when no cell mapping is available (no PDK on this machine): measured
#: 5.6-7.3 um2 per gate across the spike, the M3 run's chips and their alkaid versions; 7.0 errs towards more tiles.
SKY130_UM2_PER_GATE = 7.0


def estimate(gates: int | None = None, area_um2: float | None = None, tt_tiles: int | None = None,
             ice40_luts: int | None = None) -> dict:
    out = []
    for r in ROUTES:
        e = {"route": r["id"], "name": r["name"], "currency": r["currency"], "deadline": r.get("deadline"),
             "ships": r.get("ships"), "notes": r["notes"], "checked": CHECKED}
        if r["id"] == "fpga_ice40":
            fits = None if ice40_luts is None else ice40_luts <= r["capacity"]["lut4"]
            e.update(fits=fits, cost=r["unit_cost"], basis=f"{ice40_luts} LUT4 of 5280" if ice40_luts is not None else "LUT count unknown")
        elif r["id"].startswith("tt_"):
            est_area = area_um2 or (gates * SKY130_UM2_PER_GATE if gates else None)
            tiles = tt_tiles or (max(1, math.ceil(est_area / (161 * 111.5 * 0.6))) if est_area else None)
            fits = None if tiles is None else tiles <= r["max_tiles"] if "max_tiles" in r else None
            basis = ("tiles from the Tiny Tapeout package" if tt_tiles else
                     "tiles estimated from sky130 synthesis area at 60% utilisation" if area_um2 else
                     f"tiles estimated from the gate count ({SKY130_UM2_PER_GATE} um2 per gate on sky130, 60% utilisation; "
                     "no sky130 cell mapping on this machine)")
            e.update(tiles=tiles, fits=fits, cost=(tiles * r["tile_cost"] + r["devkit"]) if tiles else None, basis=basis)
        elif r["id"] == "waferspace_gf180":
            e.update(fits=True, cost=r["run_cost"], cost_per_die=round(r["run_cost"] / r["dies"], 2), basis="whole run")
        elif r["id"] == "pragmatic_flexic":
            mm2 = max(r["min_mm2"], (area_um2 or 0) / 1e6 * 4.0)  # flexible process ~4x sky130 area (rough)
            e.update(fits=True, area_mm2_assumed=round(mm2, 2), cost=round(mm2 * r["per_mm2"]), units=r["units"],
                     basis="minimum 3x3 mm; area scaled from sky130 is a rough assumption")
        out.append(e)
    return {"routes": out, "checked": CHECKED, "medical_certification": "none of these routes is medically certified"}
