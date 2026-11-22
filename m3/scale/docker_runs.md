# Layout and timing-power runs left for a machine with Docker

Not run here: Docker was off on the sweep machine (on purpose), and the lab runs layout
and timing-power only through LibreLane in Docker. These are the commands for the four
runs the task asked for: the 10k and 30k ternary designs on sky130 and gf180. The 30k
4-bit design (1.15 M gates) has no layout run planned; its area is the synthesis estimate.

## What each run needs

| Run | Design id | Cells (synth) | Docker memory |
| --- | --- | --- | --- |
| ternary_10k sky130 | 24fcbc4e7451 | 125k gates | 12 GB |
| ternary_10k gf180 | 24fcbc4e7451 | 125k gates | 12 GB |
| ternary_30k sky130 | 399379742efc | 408k gates | 32 to 64 GB |
| ternary_30k gf180 | 399379742efc | 408k gates | 32 to 64 GB |

Run the two 10k runs together (two Docker workers, Docker memory 24 GB or more). Run the
30k runs one at a time (one Docker worker, Docker memory 64 GB). Design ids are content
hashes of the model, so ingesting the same model JSON gives the same id on any machine.

Clock: synthesis depth is 90 (10k) and 106 (30k) generic-gate levels. At the ns per
level measured on the M3 layouts, that is about 36 and 42 ns on sky130 and 93 and 109 ns
on gf180, against default clocks of 50 ns and 100 ns. So the commands use 100 ns on
sky130 and 200 ns on gf180 to leave room for the long wires of a large die. A sensor
needs a decision per window, so the slower clock costs nothing.

## Commands

From the repository root, with the lab installed (`CHIPLAB_USER_DIR` and `CHIPLAB_CONFIG`
pointing at the install) and a fresh lab home:

```bash
export CHIPLAB_HOME="$PWD/chiplab/runs/scale-layout"
for m in ternary_10k ternary_30k; do
  jq -c '{format: "intnn", name: .meta.name, model: .model}' "m3/scale/models/$m.json" \
    | uv --directory chiplab run chiplab ingest-model
done   # expect design ids 24fcbc4e7451 and 399379742efc

# 10k: two runs at once (Docker memory 24 GB or more)
CHIPLAB_DOCKER_WORKERS=2 uv --directory chiplab run chiplab workers &
uv --directory chiplab run chiplab submit-batch --json '{"tool": "layout", "args_list": [
  {"design_id": "24fcbc4e7451", "pdk": "sky130", "clock_period_ns": 100, "timeout": 14400, "decision_rate_hz": 12},
  {"design_id": "24fcbc4e7451", "pdk": "gf180", "clock_period_ns": 200, "timeout": 14400, "decision_rate_hz": 12}]}'
# poll: chiplab job-status --json '{"job_id": "..."}'; when both are done, stop the workers

# 30k: one run at a time (Docker memory 64 GB)
CHIPLAB_DOCKER_WORKERS=1 uv --directory chiplab run chiplab workers &
uv --directory chiplab run chiplab submit-batch --json '{"tool": "layout", "args_list": [
  {"design_id": "399379742efc", "pdk": "sky130", "clock_period_ns": 100, "timeout": 43200, "decision_rate_hz": 12},
  {"design_id": "399379742efc", "pdk": "gf180", "clock_period_ns": 200, "timeout": 43200, "decision_rate_hz": 12}]}'

# timing and power: the same LibreLane runs, served from the cache (no new run)
for d in 24fcbc4e7451 399379742efc; do
  uv --directory chiplab run chiplab timing-power --json "{\"design_id\": \"$d\", \"pdk\": \"sky130\", \"clock_period_ns\": 100, \"decision_rate_hz\": 12}"
  uv --directory chiplab run chiplab timing-power --json "{\"design_id\": \"$d\", \"pdk\": \"gf180\", \"clock_period_ns\": 200, \"decision_rate_hz\": 12}"
done
```

`decision_rate_hz` 12 is 18 channels with one decision per 1.5 s window each; the lab
recomputes power at any other rate without a new run. The timeouts (4 h for 10k, 12 h for
30k) are guesses scaled from the M3 layouts (2.6k gates in about 200 s); a run that hits
its timeout is a finding to record, not a reason to raise it without measuring.

Optional, same commands with the alkaid designs (ingest with `"optimizer": "alkaid"`
added to the JSON; ids `24fcbc4e7451-alk` and `399379742efc-alk`): 38 % fewer gates on the
10k design, so smaller and faster runs.
