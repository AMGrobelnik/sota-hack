"""Map a design onto a real process's standard cells: area (µm²), gate-equivalents, cell counts."""
from __future__ import annotations

import re
from pathlib import Path

from chiplab import config
from chiplab.hw.yosys import abc_cmd, run

# Liberty file (typical corner) and the NAND2 cell that defines one gate-equivalent, per PDK.
PDKS = {
    "sky130": {"glob": "sky130/versions/*/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib",
               "nand2": "sky130_fd_sc_hd__nand2_1", "nand2_um2": 3.7536, "dont_use": "*__probe_* *__lpflow_* *__clkdly* *__dlygate*",
               "label": "SkyWater 130 nm, sky130_fd_sc_hd, tt 25C 1.8V"},
    "gf180": {"glob": "gf180mcu/versions/*/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib",
              "nand2": "gf180mcu_fd_sc_mcu7t5v0__nand2_1", "nand2_um2": 10.976, "dont_use": "",
              "label": "GlobalFoundries 180 nm MCU, 7-track 5V0 cells, tt 25C 3.3V"},
    "ihp": {"glob": "ihp-sg13g2/versions/*/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/sg13g2_stdcell_typ_1p20V_25C.lib",
            "nand2": "sg13g2_nand2_1", "nand2_um2": 7.2576, "dont_use": "",
            "label": "IHP SG13G2 130 nm BiCMOS, sg13g2_stdcell, typ 25C 1.2V"},
}
# sky130A and sky130B share the hd cell library; accept either.
_FALLBACK = {"sky130": "sky130/versions/*/sky130B/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"}


def liberty(pdk: str) -> Path:
    if pdk not in PDKS:
        raise ValueError(f"pdk must be one of {list(PDKS)}")
    root = Path(config.PDK_ROOT) / "ciel"
    hits = sorted(root.glob(PDKS[pdk]["glob"])) or sorted(root.glob(_FALLBACK.get(pdk, "__none__")))
    if not hits:  # ciel's enabled layout: PDK_ROOT/<variant>/libs.ref/...
        tail = PDKS[pdk]["glob"].split("/versions/*/", 1)[1]
        hits = sorted(Path(config.PDK_ROOT).glob(tail)) or sorted(Path(config.PDK_ROOT).glob(tail.replace("sky130A", "sky130B")))
    if not hits:
        raise FileNotFoundError(f"Liberty for {pdk} not found under {root}; run scripts/setup_toolchain.sh")
    return hits[0]


def map_to_process(rtl: Path, top: str, workdir: Path, pdk: str = "sky130", timeout: int = 900, effort: str = "fast") -> dict:
    lib = liberty(pdk)
    p = PDKS[pdk]
    du = " ".join(f"-dont_use {g}" for g in p["dont_use"].split()) if p["dont_use"] else ""
    script = f"""read_verilog {rtl}
hierarchy -check -top {top}
synth -top {top} -flatten -noabc
dfflibmap -liberty {lib}
{abc_cmd(effort, f"-liberty {lib} {du}")}
opt_clean -purge
tee -q -o stat_{pdk}.txt stat -liberty {lib}
write_verilog -noattr mapped_{pdk}.v
"""
    r = run(script, workdir, timeout, f"map_{pdk}")
    txt = (workdir / f"stat_{pdk}.txt").read_text()
    m = re.search(r"Chip area for (?:top )?module\s+'?\\?\S*'?:\s*([\d.]+)", txt) or re.search(r"Chip area[^:]*:\s*([\d.]+)", txt)
    area = float(m.group(1)) if m else None
    cells = {}
    for name, cnt in re.findall(r"^\s+(\S+__\S+|sg13g2_\S+)\s+(\d+)", txt, re.M):
        cells[name] = int(cnt)
    if not cells:  # newer yosys prints "count  area  name" columns
        for cnt, name in re.findall(r"^\s+(\d+)\s+[\d.E+-]+\s+(\S+__\S+|sg13g2_\S+)\s*$", txt, re.M):
            cells[name] = int(cnt)
    ncells = sum(cells.values()) or None
    ge = round(area / p["nand2_um2"], 1) if area else None
    tt_tiles = None
    if pdk == "sky130" and area:
        # one Tiny Tapeout sky130 tile is about 161 x 111.5 µm; placement typically reaches ~60% utilisation
        tt_tiles = max(1, int(-(-area // (161 * 111.5 * 0.6))))
    return {"pdk": pdk, "library": p["label"], "area_um2": area, "gate_equivalents": ge, "std_cells": ncells,
            "cells_by_type": cells, "tt_tiles_est": tt_tiles, "nand2_um2": p["nand2_um2"],
            "mapped_netlist": str(workdir / f"mapped_{pdk}.v"), "seconds": r["seconds"],
            "note": "synthesis area before placement and routing (layout adds whitespace)"}
