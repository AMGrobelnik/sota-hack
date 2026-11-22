**Chip lab (compile, verify and the chip part of report).** The chip-lab skill named `chiplab` (listed as
`chipin:chiplab` where skills carry their plugin's name) is available to you: load it before the compile stage, and whenever you need a gate count or any chip figure (gates, area,
bit-exact simulation, formal equivalence, layout, timing, power, the chip report). It holds the tools for each
stage and how to report their results with `./progress`. Before you mark report done, call
`chiplab chip-report --json '{"design_id": "<the chip you chose>", "decision_rate_hz": <decisions per second>}'`
on the one chip you chose: the chip figures the user sees (area, power, energy, cost, verification) come from
that call. When you score one chip's detections with `score-events`, pass that chip's id as `"design_id"` (and
`"progress_metrics": true`) so its event scores are filed under that chip.

**Every design enters the lab as a model, never as hand-written Verilog.** Write each candidate as a
chipir/1 document (a JSON file in your folder) and compile it with `chiplab compile-ir`, or bring a trained
model in with `chiplab ingest-model`. Rules and thresholds are models too: differences of neighbouring
samples are a `matvec` with +1/-1 weights, then `abs`, `cmp` against a threshold, a `matvec` of ones to count,
and a final `cmp` (see the `compile-ir` section of the tool reference for the ops). Only these paths give
the design its `ir.json`, which `simulate`, `prove-equivalence`, `rtl-simulate` and `chip-report` all read:
a design that came in through `submit-verilog` without `reference_ir` has none, and every one of those
calls fails on it. If Verilog really cannot be avoided, pass the design's chipir/1 model as
`reference_ir` to `submit-verilog`, so the lab checks the Verilog against it and keeps it as `ir.json`.

**Physical layout only when the brief wants it.** When the brief or the spec says no physical layout (or
no layout, GDS or tape-out), do not call `layout`, `timing-power`, `tt-package`, `tt-export` or
`bitstream`, not even when another call fails: report the synthesis-based figures that `chip-report` gives
and say that layout was left out because the user asked for that.

If the skill does not load: run `chiplab <tool> --json '{...}'` from your working folder; the full reference is
`references/tools.md` in the skill's folder (`.claude/plugins/chipin/skills/chiplab/` or `.agents/skills/chiplab/`),
or `chiplab agent-doc`.
