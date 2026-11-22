"""Manufacturing routes and prices (checked 22 Nov 2026) and a per-design cost estimate. Data, not advice:
prices and deadlines change, so every route carries its source date, its source page and, per figure, whether
that figure was read on the vendor's public page on the check date ("vendor page") or not ("unverified")."""
from __future__ import annotations

import math

from chiplab.hw.tinytapeout import TILE_SIZES

CHECKED = "2026-11-22"
VENDOR, UNVERIFIED = "vendor page", "unverified"

#: wafer.space GF180MCU Run 3 slots (https://wafer.space/, read 2026-11-22): standard price for 1,000 dies, die
#: area, core area inside the default pad ring (needed for chip-on-board) and usable silicon without a pad ring.
WAFERSPACE_SLOTS = [
    {"slot": "0.5x0.5", "price": 3000.0, "die_mm2": 4.90, "core_mm2": 1.73, "usable_mm2": 4.67},
    {"slot": "1x0.5", "price": 5000.0, "die_mm2": 9.94, "core_mm2": 5.02, "usable_mm2": 9.61},
    {"slot": "0.5x1", "price": 5000.0, "die_mm2": 9.93, "core_mm2": 4.46, "usable_mm2": 9.57},
    {"slot": "1x1", "price": 8000.0, "die_mm2": 20.12, "core_mm2": 12.92, "usable_mm2": 19.65},
]

ROUTES = [
    {"id": "fpga_ice40", "name": "iCE40UP5K FPGA (UPduino board)", "kind": "fpga", "unit_cost": 36.0, "currency": "USD",
     "capacity": {"lut4": 5280}, "lead_time": "days", "deadline": None, "open_source_flow": True,
     "notes": "reprogrammable; good for a bench demo, not a medical product",
     "source": None, "provenance": {"unit_cost": UNVERIFIED}},
    {"id": "tt_sky130", "name": "Tiny Tapeout, SkyWater 130 nm (TTSKY26)", "kind": "asic_shuttle", "pdk": "sky130A",
     "tile_cost": 70.0, "devkit": 300.0, "devkit_individual": 100.0, "currency": "EUR", "tile_um": [161.0, 111.52],
     "max_tiles": 16, "deadline": "2026-11-30", "ships": "about 2027-06-25", "open_source_flow": True,
     "notes": "designs are published openly; 8 in / 8 out / 8 bidir pins, so inputs are streamed",
     "source": "https://tinytapeout.com/",
     "provenance": {"deadline": VENDOR, "tile_um": "tt-support-tools tech/sky130A/tile_sizes.yaml",
                    "tile_cost": UNVERIFIED, "devkit": UNVERIFIED, "ships": UNVERIFIED}},
    {"id": "tt_gf180", "name": "Tiny Tapeout, GlobalFoundries 180 nm (TTGF26c)", "kind": "asic_shuttle",
     "pdk": "gf180mcuD", "tile_cost": 70.0, "devkit": 300.0, "currency": "EUR", "tile_um": [346.64, 160.72],
     "max_tiles": 32, "max_shape": "4x8", "deadline": "2026-12-07", "ships": "about 2027-06-09",
     "open_source_flow": True,
     "notes": "design must be public and Apache-2.0 compatible; dies come bonded on a board (chip-on-board); "
              "the tile price for GF180 is not confirmed",
     "source": "https://tinytapeout.com/",
     "provenance": {"deadline": VENDOR, "tile_um": "tt-support-tools tech/gf180mcuD/tile_sizes.yaml",
                    "max_tiles": "tt-support-tools tech/gf180mcuD/tile_sizes.yaml", "tile_cost": UNVERIFIED,
                    "devkit": UNVERIFIED, "ships": UNVERIFIED}},
    {"id": "tt_ihp", "name": "Tiny Tapeout, IHP SG13G2 130 nm", "kind": "asic_shuttle", "pdk": "ihp-sg13g2",
     "tile_cost": None, "devkit": None, "currency": "EUR", "tile_um": [202.08, 154.98], "max_tiles": 32,
     "max_shape": "8x4", "deadline": None, "ships": None, "open_source_flow": True,
     "notes": "no IHP shuttle was open on tinytapeout.com on the check date; price and dates not known",
     "source": "https://tinytapeout.com/",
     "provenance": {"tile_um": "tt-support-tools tech/ihp-sg13g2/tile_sizes.yaml",
                    "max_tiles": "tt-support-tools tech/ihp-sg13g2/tile_sizes.yaml", "deadline": VENDOR}},
    {"id": "waferspace_gf180", "name": "wafer.space, GF180 (Run 3)", "kind": "asic_run", "slots": WAFERSPACE_SLOTS,
     "dies": 1000, "cob_addon": 1500.0, "currency": "USD", "purchase_by": "2026-12-09", "deadline": "2026-12-16",
     "ships": "2027-Q2", "open_source_flow": True, "open_source_required": False, "dies_tested": False,
     "notes": "1,000 dies per slot; GDS by 16 Dec 2026, slot purchase by 9 Dec; chip-on-board packaging +$1,500 "
              "(needs the default pad ring); the design may stay closed; early-bird prices ended 30 Sep 2026",
     "source": "https://wafer.space/",
     "provenance": {"slots": VENDOR, "dies": VENDOR, "cob_addon": VENDOR, "purchase_by": VENDOR, "deadline": VENDOR,
                    "ships": VENDOR, "open_source_required": VENDOR + " (https://wafer.space/faq)",
                    "dies_tested": UNVERIFIED}},
    {"id": "chipfoundry_chipignite", "name": "ChipFoundry chipIgnite, sky130", "kind": "asic_run", "pdk": "sky130A",
     "run_cost": 14950.0, "user_area_mm2": 15.0, "units": 100, "currency": "USD", "deadline": "2027-03-20",
     "ships": "about 2027-11", "open_source_flow": True,
     "notes": "100 QFN-packaged parts (or bare dies) and an evaluation board; harness with a RISC-V SoC",
     "source": "https://chipfoundry.io/chipignite",
     "provenance": {"run_cost": VENDOR, "user_area_mm2": VENDOR + " (up to 15 mm2)", "units": VENDOR,
                    "deadline": UNVERIFIED, "ships": UNVERIFIED}},
    {"id": "europractice_gf180", "name": "EUROPRACTICE MPW, GF180MCU", "kind": "asic_mpw", "pdk": "gf180",
     "per_mm2": 913.0, "min_mm2": 6.0, "currency": "EUR", "deadline": None, "open_source_flow": True,
     "notes": "standard price per mm2 of die (pad ring included), minimum 6 mm2; discounted academic price exists",
     "source": "https://europractice-ic.com/schedules-prices-2026/",
     "provenance": {"per_mm2": VENDOR, "min_mm2": VENDOR}},
    {"id": "europractice_ihp_sg13g2", "name": "EUROPRACTICE MPW, IHP SG13G2", "kind": "asic_mpw", "pdk": "ihp",
     "per_mm2": 7300.0, "min_mm2": 0.8, "currency": "EUR", "deadline": None, "open_source_flow": True,
     "notes": "standard price per mm2 of die (pad ring included), minimum 0.8 mm2",
     "source": "https://europractice-ic.com/schedules-prices-2026/",
     "provenance": {"per_mm2": VENDOR, "min_mm2": VENDOR}},
    {"id": "europractice_ihp_sg13cmos", "name": "EUROPRACTICE MPW, IHP SG13CMOS", "kind": "asic_mpw", "pdk": "ihp",
     "per_mm2": 4500.0, "min_mm2": 0.8, "units": 40, "currency": "EUR", "deadline": None, "open_source_flow": True,
     "notes": "SG13G2 without the HBT; standard price per mm2 of die (pad ring included), minimum 0.8 mm2",
     "source": "https://europractice-ic.com/schedules-prices-2026/",
     "provenance": {"per_mm2": VENDOR, "min_mm2": VENDOR, "units": UNVERIFIED}},
    {"id": "pragmatic_flexic", "name": "Pragmatic FlexIC (flexible)", "kind": "asic_flexible", "per_mm2": 900.0,
     "min_mm2": 9.0, "units": 50, "currency": "EUR", "deadline": "2027-03-16", "open_source_flow": False,
     "notes": "needs Pragmatic's design kit with commercial tools; our area numbers are sky130 estimates, not FlexIC",
     "source": None, "provenance": {"per_mm2": UNVERIFIED, "min_mm2": UNVERIFIED, "deadline": UNVERIFIED}},
]


#: sky130 cell area per synthesised gate when no cell mapping is available (no PDK on this machine): measured
#: 5.6-7.3 um2 per gate across the spike, the M3 run's chips and their alkaid versions; 7.0 errs towards more tiles.
SKY130_UM2_PER_GATE = 7.0
#: NAND2_X1 cell area per PDK (chiplab.hw.pdk), used to scale a sky130 area to another process when that process
#: has not been mapped: same gate count, bigger or smaller cells.
NAND2_UM2 = {"sky130": 3.7536, "gf180": 10.976, "ihp": 7.2576}
#: placement utilisation assumed when turning cell area into tiles or core area
UTILISATION = 0.6
_PDK_KEY = {"sky130A": "sky130", "gf180mcuD": "gf180", "ihp-sg13g2": "ihp", "sky130": "sky130", "gf180": "gf180",
            "ihp": "ihp"}


def _area(pdk: str, area_um2: float | None, gates: int | None, area_by_pdk: dict | None) -> tuple[float | None, str]:
    """Cell area on `pdk` (um2) and where it came from: that PDK's own mapping, the sky130 one scaled by NAND2 size,
    or the gate count."""
    k = _PDK_KEY[pdk]
    if area_by_pdk and area_by_pdk.get(k):
        return float(area_by_pdk[k]), f"{k} cell mapping"
    sky = area_um2 or (gates * SKY130_UM2_PER_GATE if gates else None)
    if not sky:
        return None, "area unknown"
    src = "sky130 synthesis area" if area_um2 else (f"the gate count ({SKY130_UM2_PER_GATE} um2 per gate on sky130; "
                                                   "no sky130 cell mapping on this machine)")
    if k == "sky130":
        return sky, src
    return sky * NAND2_UM2[k] / NAND2_UM2["sky130"], f"{src} scaled to {k} by NAND2 cell size"


def tt_tiles_for(area_um2: float, pdk: str = "sky130A", utilisation: float = UTILISATION) -> int:
    """Tiles (count) a cell area needs on one PDK's Tiny Tapeout tile."""
    w, h = TILE_SIZES[pdk]["1x1"]
    return max(1, math.ceil(area_um2 / (w * h * utilisation)))


def waferspace_slot(area_mm2: float | None, pad_ring: bool = True, utilisation: float = UTILISATION) -> dict:
    """Cheapest wafer.space slot whose core (default pad ring) or usable silicon (no pad ring) holds the cell area
    at the utilisation. fits False when even the full 1x1 slot is too small; None when the area is unknown."""
    if area_mm2 is None:
        return {"fits": None, "slot": None}
    need = area_mm2 / utilisation
    room = "core_mm2" if pad_ring else "usable_mm2"
    for s in sorted(WAFERSPACE_SLOTS, key=lambda s: (s["price"], -s[room])):
        if need <= s[room]:
            return {"fits": True, "slot": s["slot"], "price": s["price"], "need_mm2": round(need, 4),
                    "room_mm2": s[room], "room": room}
    return {"fits": False, "slot": None, "need_mm2": round(need, 4), "room_mm2": WAFERSPACE_SLOTS[-1][room], "room": room}


def estimate(gates: int | None = None, area_um2: float | None = None, tt_tiles: int | None = None,
             ice40_luts: int | None = None, *, area_by_pdk: dict | None = None, tt_pdk: str = "sky130A") -> dict:
    """Every route: fits, cost and the basis. area_um2 is the sky130 cell area; area_by_pdk adds other PDKs' own
    mapped areas ({"gf180": um2, "ihp": um2}); tt_tiles is the tile count of the Tiny Tapeout package, made for
    tt_pdk."""
    out = []
    tt_pdk = {"sky130": "sky130A", "gf180": "gf180mcuD", "ihp": "ihp-sg13g2"}.get(tt_pdk, tt_pdk)
    for r in ROUTES:
        e = {"route": r["id"], "name": r["name"], "currency": r["currency"], "deadline": r.get("deadline"),
             "ships": r.get("ships"), "notes": r["notes"], "checked": CHECKED, "source": r.get("source"),
             "provenance": r.get("provenance", {})}
        if r["id"] == "fpga_ice40":
            fits = None if ice40_luts is None else ice40_luts <= r["capacity"]["lut4"]
            e.update(fits=fits, cost=r["unit_cost"], basis=f"{ice40_luts} LUT4 of 5280" if ice40_luts is not None else "LUT count unknown")
        elif r["id"].startswith("tt_"):
            pdk = r["pdk"]
            area, src = _area(pdk, area_um2, gates, area_by_pdk)
            if tt_tiles and pdk == tt_pdk:
                tiles, basis = tt_tiles, "tiles from the Tiny Tapeout package"
            else:
                tiles = tt_tiles_for(area, pdk) if area else None
                if pdk == "sky130A":   # unchanged wording: the dashboard and reports show it
                    mapped = area_um2 or (area_by_pdk or {}).get("sky130")
                    basis = ("tiles estimated from sky130 synthesis area at 60% utilisation" if mapped else
                             f"tiles estimated from the gate count ({SKY130_UM2_PER_GATE} um2 per gate on sky130, "
                             "60% utilisation; no sky130 cell mapping on this machine)")
                else:
                    basis = (f"tiles estimated from {src} at {round(UTILISATION * 100)}% utilisation on the "
                             f"{r['tile_um'][0]} x {r['tile_um'][1]} um tile" if area else "area unknown")
            fits = None if tiles is None else tiles <= r["max_tiles"]
            cost = (tiles * r["tile_cost"] + r["devkit"]) if tiles and r.get("tile_cost") is not None else None
            if r.get("tile_cost") is None:
                basis += "; price not known"
            e.update(tiles=tiles, fits=fits, cost=cost, basis=basis)
        elif r["id"] == "waferspace_gf180":
            area, src = _area("gf180", area_um2, gates, area_by_pdk)
            s = waferspace_slot(area / 1e6 if area else None)
            price = s.get("price") if s["fits"] else (None if s["fits"] is False else WAFERSPACE_SLOTS[0]["price"])
            basis = (f"slot {s['slot']}: {s['need_mm2']} mm2 needed ({src} at {round(UTILISATION * 100)}% "
                     f"utilisation) in {s['room_mm2']} mm2 of core" if s["fits"] else
                     f"{s['need_mm2']} mm2 needed, more than the {s['room_mm2']} mm2 core of a 1x1 slot"
                     if s["fits"] is False else "area unknown; price of the smallest slot")
            e.update(fits=s["fits"], slot=s["slot"], cost=price,
                     cost_per_die=round(price / r["dies"], 2) if price else None, dies=r["dies"],
                     cob_addon=r["cob_addon"], purchase_by=r["purchase_by"], basis=basis)
        elif r["id"] == "chipfoundry_chipignite":
            area, src = _area("sky130", area_um2, gates, area_by_pdk)
            need = area / 1e6 / UTILISATION if area else None
            fits = None if need is None else need <= r["user_area_mm2"]
            e.update(fits=fits, cost=r["run_cost"], units=r["units"],
                     basis=(f"{round(need, 4)} mm2 needed ({src}) of {r['user_area_mm2']} mm2 user area; "
                            f"price for {r['units']} packaged parts") if need is not None else "area unknown")
        elif r["id"].startswith("europractice_"):
            area, src = _area(r["pdk"], area_um2, gates, area_by_pdk)
            need = area / 1e6 / UTILISATION if area else None
            mm2 = max(r["min_mm2"], need or 0)
            e.update(fits=None if need is None else need <= 121.0, area_mm2_assumed=round(mm2, 3),
                     cost=round(mm2 * r["per_mm2"]), units=r.get("units"),
                     basis=(f"core {round(need, 4)} mm2 ({src}), minimum {r['min_mm2']} mm2; the pad ring adds area"
                            if need is not None else f"area unknown; minimum {r['min_mm2']} mm2"))
        elif r["id"] == "pragmatic_flexic":
            mm2 = max(r["min_mm2"], (area_um2 or 0) / 1e6 * 4.0)  # flexible process ~4x sky130 area (rough)
            e.update(fits=True, area_mm2_assumed=round(mm2, 2), cost=round(mm2 * r["per_mm2"]), units=r["units"],
                     basis="minimum 3x3 mm; area scaled from sky130 is a rough assumption")
        out.append(e)
    return {"routes": out, "checked": CHECKED, "medical_certification": "none of these routes is medically certified"}
