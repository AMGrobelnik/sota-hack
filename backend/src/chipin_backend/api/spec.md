**The user's spec.** This run comes with the user's own spec: the block "The user's spec" at the top of your
first message, and `spec.json` in your working folder. It is the user's decision, not a draft to improve:

- spec stage: `spec.md` restates THIS spec (device, signal, what is detected, patients, place, every target,
  the primary metric, the false-alarm unit, the channel budget, the data) and checks it: can each target be
  measured with the data this run has? Do not invent a different device, signal or targets. Where the spec is
  silent, choose a value and say you chose it; where a target cannot be met or measured, say so and keep it.
- Every target is a bar the chosen design is judged against. `report.md` has a table: each target, the chosen
  design's value on the test set, pass or fail.
- The primary metric and the false-alarm unit are the user's: use them in `report.md` and status lines. A night
  is 12 hours and a day 24 hours, as the block says; a false-alarm target in that unit is the hourly rate times
  those hours.
- Channels: a number in the spec is a fixed budget (every candidate uses at most that many). "Find the best
  budget" means compare budgets: propose candidates at two or more channel counts and choose on the trade-off.
- Data: follow the "Data" line of the block. Synthetic data is labelled "synthetic data" in every result,
  record and status line; never call it patient data or a measurement on patients.

**Design records (the user's chart is drawn from these).** For EVERY candidate design you score, not only
the winner, report one record with `./progress design <file.json>` (a file in your working folder holding one
JSON object) or `./progress design '<json object>'`. The helper checks it and answers `ok`, or exit status 2
with the reason: fix the record and send it again. Fields:

- `id` (your name for the design; once the lab has compiled it, the lab's `design_id`, with `previous_id` set
  to your earlier name so the record moves over), `label` (a few words), `budget`
  (`{"channels": 2, "name": "2 electrodes"}`, or `sensors` instead of `channels`);
- `gates`: the lab's measured gate count, ONLY when the lab returned it, else `null`; `gates_est`: your own
  estimate, or `null`; `depth`: logic depth if known, else `null`;
- `metrics`: `sensitivity`, `specificity`, `fa_per_hour` (false alarms per hour; the dashboard converts it to
  the user's unit), `agreement` when the task has it, and every metric the targets name; fractions from 0 to 1
  (0.92, not 92), rates per hour;
- `basis`: `validation` or `test` (which split the metrics are on); `counts`: `events_caught`, `events_total`,
  `negatives_correct`, `negatives_total`, `hours`, `patients`, consistent with the metrics;
- `per_patient`: `[{"id": "p01", "caught": 3, "total": 4, "false_alarms": 1, "hours": 24}]` with anonymous
  ids, one row per patient of that split (their sums must equal `counts`);
- `verified`: `{"vectors": 512, "mismatches": 0, "level": "<the lab's level>", "proved": true}` from the lab's
  verify tools, else `null`; `data`: `synthetic` or `public:<dataset>`; `note`: one short sentence.

Send a design's record when it is first scored, again as soon as the lab has compiled it (with the lab's measured
`gates` and its `design_id`, before you verify anything), and again when it is verified (with `verified`); the user
watches the chart fill in as you go, so do not hold the records back to the end. A later record for the same `id`
replaces the earlier one, so send the whole record every time. Then mark the chosen design with `./progress chosen <id>` (the same id).

Example:
`./progress design '{"id": "lr-2ch", "label": "logistic, 2 features", "budget": {"channels": 2, "name": "2 electrodes"}, "gates": null, "gates_est": 900, "depth": null, "metrics": {"sensitivity": 0.9, "specificity": 0.95, "fa_per_hour": 0.2}, "basis": "test", "counts": {"events_caught": 9, "events_total": 10, "negatives_correct": 380, "negatives_total": 400, "hours": 10, "patients": 2}, "per_patient": [{"id": "p1", "caught": 5, "total": 5, "false_alarms": 1, "hours": 5}, {"id": "p2", "caught": 4, "total": 5, "false_alarms": 1, "hours": 5}], "verified": null, "data": "synthetic", "note": "synthetic data"}'`
