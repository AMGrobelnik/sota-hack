---
name: chiplab
description: >-
  The ChipIn chip lab (the chiplab command). Use it to turn a small integer
  model into a chip: compile it to logic gates and count them (gates, LUTs,
  area), check the gates bit for bit against the model by simulation, prove
  them formally equivalent, measure layout, timing and power, and write the
  chosen chip's report. Use it for the compile and verify stages and the chip
  part of the report stage, and whenever a gate count or any chip figure is
  needed.
---

# Chip lab

The `chiplab` command is on your PATH. Run it from your working folder, where
the `./progress` helper is: the lab reports through that helper by itself.

## The one call shape

```bash
chiplab <tool> --json '{"design_id": "<id>", ...}'
```

Every tool takes one JSON object and prints one JSON answer with `status`.
Exit codes: 0 ok, 1 error (read `error`), 2 a check ran and the design failed
it (e.g. not bit-exact), 3 timeout. The first compile call returns a
`design_id`; every later tool takes it.

## The seven stages and the lab

spec, reference, propose and finetune are your own work. The lab serves the
last three:

- **compile**: `ingest-model` (or `compile-ir`) to bring in your model, then
  `synthesize`, `count-luts` and `map-to-process`.
- **verify** (the chip against your model; against patient recordings too
  when you have them): `simulate` (pass your own test vectors and expected
  outputs), `prove-equivalence`, `rtl-simulate`, and `verification-level`.
- **report**: `layout` / `timing-power` (pass `decision_rate_hz` = how often
  the chip decides, for the battery-relevant power), `tt-package`,
  `bitstream`, `estimate-cost`, and `chip-report`.

Before you mark report done, call `chiplab chip-report --json '{"design_id": "<the chip you chose>", "decision_rate_hz": <decisions per second>}'` on the one chip you chose: the chip figures the user sees (area, power, energy, cost, verification) come from that call.

## Announcing results with ./progress

- The lab sends its own metrics, status lines and chip files through
  `./progress`; do not repeat those numbers.
- Mark the stages yourself: `./progress stage compile started` before the
  compile calls and `./progress stage compile done` after them, and the same
  for `verify`; or pass `"progress_stages": true` to a tool call. If a lab
  tool fails, mark the stage skipped with the reason instead of done:
  `./progress stage verify skipped "<reason>"`.
- A number you measured yourself about one design:
  `./progress metric <key> <number> [unit] --chip <design_id>`.
- The run's chosen chip: `./progress chosen <design_id>` (a later call
  replaces an earlier one).

## Reference

- `references/workflow.md`: a worked compile, verify and report sequence.
- `references/tools.md`: every tool with its parameters and JSON schema,
  copied from the installed lab when this skill was installed; its first
  line names the lab version. Read only the tool sections you need.
- If `references/tools.md` is missing, ask the lab itself: `chiplab agent-doc`
  (the full reference), `chiplab list-tools`, `chiplab describe <tool>`.
