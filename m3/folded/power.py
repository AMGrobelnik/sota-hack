"""Per-cell data from the lab's Liberty files (the same typical-corner files map-to-process uses): area, leakage,
input-pin capacitance and clock-pin capacitance, summed over a mapped design's cell counts."""
from __future__ import annotations

import re
from functools import lru_cache

from chiplab.hw.pdk import liberty

VDD = {"sky130": 1.8, "gf180": 3.3}      # nominal voltage of the Liberty corner the lab maps to
_NUM = r'"?([-+\d.eE]+)"?'


@lru_cache(maxsize=4)
def cells(pdk: str) -> dict[str, dict]:
    txt = liberty(pdk).read_text()
    unit = re.search(r'leakage_power_unit\s*:\s*"?1?\s*([num]?W)', txt)
    scale_nw = {"nW": 1.0, "uW": 1e3, "mW": 1e6, "W": 1e9}[unit.group(1) if unit else "nW"]
    heads = list(re.finditer(r'\n\s*cell\s*\(\s*"?(\w+)"?\s*\)\s*\{', txt))
    out = {}
    for i, h in enumerate(heads):
        chunk = txt[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(txt)]
        area = re.search(r'\barea\s*:\s*' + _NUM, chunk)
        leak = re.search(r'cell_leakage_power\s*:\s*' + _NUM, chunk)
        if leak:
            leak_nw = float(leak.group(1)) * scale_nw
        else:
            vals = [float(v) for v in re.findall(r'leakage_power\s*\(\s*\)\s*\{[^}]*?value\s*:\s*' + _NUM, chunk)]
            leak_nw = (sum(vals) / len(vals) * scale_nw) if vals else 0.0
        cin = cclk = 0.0
        pins = list(re.finditer(r'\bpin\s*\(\s*"?(\w+)"?\s*\)\s*\{', chunk))
        for j, p in enumerate(pins):
            seg = chunk[p.end(): pins[j + 1].start() if j + 1 < len(pins) else len(chunk)]
            d = re.search(r'direction\s*:\s*"?(\w+)', seg)
            c = re.search(r'\bcapacitance\s*:\s*' + _NUM, seg)
            if not d or d.group(1) != "input" or not c:
                continue
            if re.search(r'\bclock\s*:\s*"?true', seg):
                cclk += float(c.group(1))
            else:
                cin += float(c.group(1))
        out[h.group(1)] = {"area": float(area.group(1)) if area else 0.0, "leak_nw": leak_nw,
                           "cin_pf": cin, "cclk_pf": cclk}
    return out


def totals(cells_by_type: dict[str, int], pdk: str) -> dict:
    lib = cells(pdk)
    t = {"area_um2": 0.0, "leak_nw": 0.0, "cin_pf": 0.0, "cclk_pf": 0.0, "flops": 0, "unknown": []}
    for name, n in cells_by_type.items():
        c = lib.get(name)
        if c is None:
            t["unknown"].append(name)
            continue
        t["area_um2"] += n * c["area"]
        t["leak_nw"] += n * c["leak_nw"]
        t["cin_pf"] += n * c["cin_pf"]
        t["cclk_pf"] += n * c["cclk_pf"]
        t["flops"] += n if c["cclk_pf"] > 0 else 0
    return t
