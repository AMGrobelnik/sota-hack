"""Print the "Re-run" table: per example, new result.json against the first run kept in _first_run/."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
KEYS = ["gates", "ge_sky130", "luts_xc7", "tt_package_tiles", "level", "sim_vectors_n"]
print("| Example | Exact | Lv | Gates | TT | cairo | Same as run 1 |")
print("| --- | --- | --- | --- | --- | --- | --- |")
for old in sorted((OUT / "_first_run").glob("*.json")):
    n = old.stem
    a = json.loads(old.read_text())
    b = json.loads((OUT / n / "result.json").read_text())
    same = all(a.get(k) == b.get(k) for k in KEYS) and a.get("chip_outputs") == b.get("chip_outputs")
    exact = b.get("sim_vectors_bit_exact") and b.get("sim_random_bit_exact") and (b.get("prove") or {}).get("equivalent", True)
    print(f"| `{n}` | {b.get('sim_vectors_n')} {'yes' if exact else 'NO'} | {b.get('level')} (was {a.get('level')}) "
          f"| {b.get('gates')} (was {a.get('gates')}) | {b.get('tt_package_tiles')} | "
          f"ok={b.get('tt_user_config_ok')} (was {a.get('tt_user_config_ok')}) | {'yes' if same else 'NO'} |")
    if not same:
        print("   diff:", {k: (a.get(k), b.get(k)) for k in KEYS if a.get(k) != b.get(k)}, "outputs same:", a.get("chip_outputs") == b.get("chip_outputs"))
