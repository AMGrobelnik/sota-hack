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
  `synthesize`, `count-luts` and `map-to-process`. Every design comes in this
  way, rules and thresholds included (write them as chipir/1: `matvec`,
  `sub`, `abs`, `cmp`): it gives the design the `ir.json` that `simulate`,
  `prove-equivalence`, `rtl-simulate` and `chip-report` read. Never
  hand-write Verilog for `submit-verilog` without `reference_ir`: such a
  design has no `ir.json`, so all four fail on it. `compose-chip` joins
  several heads into one chip (decision votes, or `max` / `sum` of their
  scores against a threshold). `compile-stream` wraps a design for streaming
  hardware; its `postproc` option smooths the alarm on the chip (majority or
  k-of-N over frames, a minimum duration, a hold), and `channel_serial`
  runs one per-channel model over several channels in turn.
- **verify** (the chip against your model; against patient recordings too
  when you have them): `simulate` (pass your own test vectors and expected
  outputs), `prove-equivalence`, `rtl-simulate` (pass the same `postproc` or
  `channel_serial` you gave `compile-stream`), and `verification-level`.
- **scoring detections** (whenever you have per-recording decisions or
  scores and labels, from your model or the chip): `score-events` gives
  event-level sensitivity, false alarms per hour, per-patient figures and
  confidence intervals. Whenever the detections are one chip's (its model's
  or its gates' decisions), pass that chip's id as `"design_id"` in the same
  call, with `"progress_metrics": true`, so its event scores are filed under
  that chip; leave `design_id` out only for detections of no one chip. The
  lab marks these figures as its own, so they never replace a figure you
  report yourself.
- **report**: `layout` / `timing-power` (pass `decision_rate_hz` = how often
  the chip decides, for the battery-relevant power), `tt-package`,
  `bitstream`, `estimate-cost`, and `chip-report`. When the brief says no
  physical layout, skip `layout`, `timing-power`, `tt-package`, `tt-export`
  and `bitstream` (they draw the layout and write GDS files) and report the
  synthesis-based figures `chip-report` gives.

Before you mark report done, call `chiplab chip-report --json '{"design_id": "<the chip you chose>", "decision_rate_hz": <decisions per second>}'` on the one chip you chose: the chip figures the user sees (area, power, energy, cost, verification) come from that call.

## Announcing results with ./progress

- The lab sends its own metrics, status lines and chip files through
  `./progress`; do not repeat those numbers. While you explore it sends only
  `gates` and the run's counters; every figure it measured for a chip is in
  `chips/<design_id>/metrics.json`, and `chip-report` sends the full set.
- Mark the stages yourself: `./progress stage compile started` before the
  compile calls and `./progress stage compile done` after them, and the same
  for `verify`; or pass `"progress_stages": true` to a tool call. If a lab
  tool fails, mark the stage skipped with the reason instead of done:
  `./progress stage verify skipped "<reason>"`.
- A number you measured yourself about one design:
  `./progress metric <key> <number> [unit] --chip <design_id>`. Give your
  own false-alarm rate in the spec's unit (`/h`), not the lab's `FA/h`.
- The run's chosen chip: `./progress chosen <design_id>` (a later call
  replaces an earlier one).

## Reference

- `references/workflow.md`: a worked compile, verify and report sequence.
- `references/tools.md`: every tool with its parameters and JSON schema,
  copied from the installed lab when this skill was installed; its first
  line names the lab version. Read only the tool sections you need.
- If `references/tools.md` is missing, ask the lab itself: `chiplab agent-doc`
  (the full reference), `chiplab list-tools`, `chiplab describe <tool>`.
- What each tool sends to the dashboard (events, metric keys and units,
  chip ids): `chiplab agent-doc --events`.
