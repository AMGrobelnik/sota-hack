"""Run with the chip lab's own Python: maps the lab-generated streaming wrapper (window registers + core) onto
a PDK's standard cells with the lab's own mapping function, so the area includes the flip-flops.
Usage: <lab python> -I lab_seqmap.py <stream.v> <top> <workdir> <pdk>"""
import json
import sys
from pathlib import Path

from chiplab.hw.pdk import map_to_process

rtl, top, wd, pdk = sys.argv[1:5]
Path(wd).mkdir(parents=True, exist_ok=True)
r = map_to_process(Path(rtl), top, Path(wd), pdk)
r["flip_flops"] = sum(v for k, v in r["cells_by_type"].items() if "df" in k.lower() or "dff" in k.lower())
print(json.dumps(r))
