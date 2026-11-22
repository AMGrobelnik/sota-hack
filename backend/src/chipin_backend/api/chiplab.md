**Chip lab (compile, verify and the chip part of report).** The chip-lab skill named `chiplab` is available
to you: load it before the compile stage, and whenever you need a gate count or any chip figure (gates, area,
bit-exact simulation, formal equivalence, layout, timing, power, the chip report). It holds the tools for each
stage and how to report their results with `./progress`. Before you mark report done, call
`chiplab chip-report --json '{"design_id": "<the chip you chose>", "decision_rate_hz": <decisions per second>}'`
on the one chip you chose: the chip figures the user sees (area, power, energy, cost, verification) come from
that call.

If the skill does not load: run `chiplab <tool> --json '{...}'` from your working folder; the full reference is
`references/tools.md` in the skill's folder (`.claude/skills/chiplab/` or `.agents/skills/chiplab/`), or `chiplab agent-doc`.
