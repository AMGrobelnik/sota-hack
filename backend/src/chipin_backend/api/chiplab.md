**Chip lab (compile, verify and the chip part of report).** The `chiplab` command turns your trained model into
a verified, measured chip. Its full reference is `chiplab/AGENT.md` in the sota-hack repository, or run
`chiplab agent-doc`. Every tool takes JSON (`chiplab <tool> --json '{...}'`) and prints one JSON answer.
Exit codes: 0 ok, 1 error (read `error`), 2 a check ran and the design failed it (e.g. not bit-exact), 3 timeout.

- **compile**: `ingest-model` (or `compile-ir`) to bring in your model, then `synthesize`, `count-luts` and
  `map-to-process`.
- **verify** (the chip against your model; against patient recordings too when you have them): `simulate`
  (pass your own test vectors and expected outputs), `prove-equivalence`, `rtl-simulate`, and
  `verification-level`.
- **report**: `layout` / `timing-power` (pass `decision_rate_hz` = how often the chip decides, for the
  battery-relevant power), `tt-package`, `bitstream`, `estimate-cost`. Before you mark report done, call
  `chiplab chip-report --json '{"design_id": "<the chip you chose>", "decision_rate_hz": <decisions per second>}'`
  on the one chip you chose: the chip figures the user sees (area, power, energy, cost, verification) come from
  that call.

Run these from your working folder. The lab reports its own metrics, status lines and chip files through
`./progress`, so do not repeat those numbers. Do mark the stages yourself:
`./progress stage compile started` before the compile calls and `./progress stage compile done` after them,
and the same for `verify`. Alternatively, pass `"progress_stages": true` to a tool call. If a lab tool fails,
report the stage as skipped with the reason instead of done.
