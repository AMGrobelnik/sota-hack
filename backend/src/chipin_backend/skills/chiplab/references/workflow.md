# A worked chip-lab sequence

Parameters and result fields for every tool are in `tools.md` beside this
file; this page shows only the order and how the results connect. Run each
call from your working folder.

## compile

```bash
./progress stage compile started
chiplab ingest-model --json '{"format": "intnn", "model": {...}, "name": "seizure-v1"}'
#   -> "design_id": "<id>"; formats: chipir, intnn, xgboost_json, torchlogix
chiplab synthesize --json '{"design_id": "<id>"}'        # gate count
chiplab count-luts --json '{"design_id": "<id>"}'        # FPGA LUTs
chiplab map-to-process --json '{"design_id": "<id>"}'    # area on a process
./progress stage compile done
```

A model written as a chipir/1 document goes through `compile-ir` instead of
`ingest-model`. Several candidates: compile each, compare their gate counts,
and keep the `design_id` of each.

A hand-made rule is a chipir/1 document too. For example, "alarm when at
least 6 of the 11 jumps between 12 heartbeat intervals exceed 40 ms":

```bash
chiplab compile-ir --json '{"ir": {"ir": "chipir/1", "name": "bigjump", "inputs": [{"name": "rr", "lanes": 12, "bits": 11, "signed": false}], "nodes": [{"id": "d", "op": "matvec", "src": "rr", "W": [[-1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, -1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, -1, 1, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, -1, 1, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, -1, 1, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, -1, 1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, -1, 1, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, -1, 1, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, -1, 1, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 1, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 1]]}, {"id": "a", "op": "abs", "src": "d"}, {"id": "big", "op": "cmp", "src": "a", "rel": "gt", "t": 40}, {"id": "n", "op": "matvec", "src": "big", "W": [[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]]}, {"id": "af", "op": "cmp", "src": "n", "rel": "ge", "t": 6}], "outputs": [{"name": "af", "src": "af"}], "meta": {}}}'
```

Each row of the first `matvec` is one difference of neighbouring intervals. Hand-written
Verilog through `submit-verilog` gets no `ir.json` unless you pass the same
chipir/1 model as `reference_ir`, and without it `simulate`,
`prove-equivalence`, `rtl-simulate` and `chip-report` all fail.

## verify

```bash
./progress stage verify started
chiplab simulate --json '{"design_id": "<id>", "inputs": "vectors", "vectors": {...}, "expected": [...]}'
chiplab prove-equivalence --json '{"design_id": "<id>"}'
chiplab verification-level --json '{"design_id": "<id>"}'
./progress stage verify done
```

`simulate` with `"inputs": "random"` exercises the whole input space;
with your own vectors and the outputs your model gave on them it checks the
chip against your model bit for bit. Exit code 2 means the check ran and the
design failed it: report that, do not mark verify done.

Verification levels: 1 bit-exact simulation, 2 formal proof, 3 streaming RTL
simulation and lint, 4 gate-level test after layout, 5 real hardware.

## report (the chip part)

```bash
./progress chosen <id>
chiplab chip-report --json '{"design_id": "<id>", "decision_rate_hz": 2}'
```

`layout`, `timing-power`, `tt-package` and `bitstream` are heavier steps; call
them when the brief needs those figures and the machine can run them, and
never when the brief says no physical layout (they draw the layout and write
GDS files). Then write `report.md` from the `chip-report` answer and your own
results.
