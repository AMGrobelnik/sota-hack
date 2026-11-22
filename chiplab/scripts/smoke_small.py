"""Smoke run of every hardware tool on a small chip (a few hundred gates): the lab's validation of the heavy flows."""
import json, sys, time
import chiplab.api as lab

ir = {"ir": "chipir/1", "name": "small", "inputs": [{"name": "x", "lanes": 4, "bits": 4, "signed": False}],
      "nodes": [{"id": "h0", "op": "matvec", "src": "x", "W": [[1, -1, 0, 1], [0, 1, 1, -1], [1, 1, -1, 0], [-1, 0, 1, 1]], "b": [1, 0, -2, 3]},
                {"id": "h1", "op": "shift", "src": "h0", "k": 1}, {"id": "h2", "op": "clip", "src": "h1", "lo": 0, "hi": 7},
                {"id": "s", "op": "matvec", "src": "h2", "W": [[1, -1, 1, -1]], "b": [-1]}, {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}],
      "outputs": [{"name": "y", "src": "y"}], "meta": {}}
full = "--full" in sys.argv
run = f"smoke-small-{int(time.time())}"
d = lab.compile_ir(ir=ir)["design_id"]
print("design", d)
steps = [("synthesize", {}), ("simulate", {"inputs": "random", "n": 65536}), ("prove_equivalence", {"golden": True}),
         ("map_to_process", {"pdk": "sky130"}), ("count_luts", {"family": "ice40"}), ("rtl_simulate", {"n": 100}),
         ("prove_sequential", {"timeout": 300}), ("bitstream", {}), ("tt_package", {"harden": full}),
         ("layout", {"pdk": "sky130"}), ("timing_power", {"pdk": "sky130"}), ("verification_level", {}),
         ("estimate_cost", {}), ("chip_report", {})]
for tool, args in steps:
    t = time.time(); r = getattr(lab, tool)(design_id=d, run_id=run, **args)
    keep = {k: r.get(k) for k in ("status", "error", "metrics", "bit_exact", "proved", "against", "passed", "area_um2", "die_mm2",
            "timing_ws_ns", "power_uw", "energy_per_decision_pj", "png", "bin", "tiles", "user_config_ok", "rtl_test_passed",
            "harden_ok", "gl_test_passed", "verification_level", "cached") if r.get(k) is not None}
    print(f"{tool:20s} {time.time() - t:6.1f}s {json.dumps(keep, default=str)[:420]}", flush=True)
