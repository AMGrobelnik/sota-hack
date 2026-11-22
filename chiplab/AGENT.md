# chipin.space chip lab: interface for AI scientists

The lab turns a trained model into a verified, measured, manufacturable chip. You (the AI scientist) bring the data, the training and the clinical judgement; the lab compiles, synthesises, verifies, measures and packages, and reports every number with its basis. Generated from the tool registry; do not edit by hand (`chiplab agent-doc --write`).

## Quick start (any machine: Apple Silicon Mac or Linux)

```bash
git clone https://github.com/AMGrobelnik/sota-hack && cd sota-hack/chiplab
scripts/install.sh                      # add --skip-docker / --skip-pdk to defer the big downloads
.venv/bin/chiplab doctor                # every check green = ready; otherwise it prints the fix
.venv/bin/chiplab ingest-model --json "{\"format\": \"intnn\", \"model\": $(cat fixtures/spike_best.json)}"
.venv/bin/chiplab synthesize --json '{"design_id": "<design_id from the line above>"}'
```
Then `simulate` (bit-exact), `prove-equivalence` (formal), `map-to-process` (area), `timing-power` / `layout`,
`bitstream`, `tt-package`, `chip-report`. Python: `import chiplab.api as lab; lab.synthesize(design_id=...)`.

Support: Apple Silicon (M1–M4) and Linux x86_64/arm64 are supported; Intel Macs use the darwin-x64 tool build and
should work but are untested. Heavy hardware steps (LibreLane layout, Tiny Tapeout harden) need Docker; GF180 and
IHP layouts are supported by the same flow but validated on sky130 only. The Tiny Tapeout harden can also run in
GitHub's cloud: commit the folder from `tt-package` and run the `tt-gds` workflow.

## How to call a tool

- CLI: `chiplab <tool-name> --json '{...}'` (or `--json-file f.json`, or JSON on stdin) prints one JSON object; exit code 0 when `status` is `ok`.
- Python: `import chiplab.api as lab; lab.<tool_name>(**args)` returns the same dict.
- Async (several agents at once): `submit-job {tool, args, session_id}` returns a `job_id`; poll `job-status` / `job-result`. Lanes are sized to the machine: cpu = cores - 1, gpu = 1, docker = Docker memory / 12 GB (1-4); override with CHIPLAB_CPU_WORKERS / CHIPLAB_GPU_WORKERS / CHIPLAB_DOCKER_WORKERS (or "lanes" in the config file); `chiplab doctor` shows what it picked. Start workers with `chiplab workers`. Results are cached by content, so duplicate designs return instantly (`cached: true`).
- Every tool also accepts `run_id`, `session_id`, `round` (events, see EVENTS.md: `chiplab agent-doc --events` prints it) and `force` (skip the cache).
- In a ChipIn run (a `./progress` helper in the working folder) every tool reports to the dashboard by itself; see EVENTS.md (`chiplab agent-doc --events`), "ChipIn dashboard". While you explore, the dashboard shows only `gates` of the latest chip and the run's counters, never a mix of chips. Before you mark report done, call `chiplab chip-report --json '{"design_id": "<the chip you chose>", "decision_rate_hz": <decisions per second>}'` on the one chip you chose: the chip figures the user sees (area, power, energy, cost, verification) come from that call. `report_metrics: true` on any call does the same for that call's design.
- Timing: `layout` / `timing-power` default to a 50 ns clock (20 MHz; 100 ns on gf180), which closes for chips of a few thousand gates; every answer also gives `fmax_mhz`, the fastest clock the chip meets.
- Status and exit code are honest: `ok` = 0 (the tool did its job and every check it ran passed), `error` = 1 (it could not do its job; see `error`), `fail` = 2 (it ran, and the design failed a check, e.g. `bit_exact: false`), `timeout` = 3. A queued job is `ok` with `state: queued`.
- Proof sizes: `prove-equivalence` (gates = RTL) takes about a second at a few thousand gates; with `golden: true` it also proves the RTL against an independent golden model of the IR in one miter (spike, 2.3k gates: about 7 s). `prove-sequential` is compositional (the core is a black box, proven by prove-equivalence), so it proves the clocked wrapper in seconds at any model size; `whole: true` proves the flattened design and is only practical for a few hundred gates.
- Safety: `submit-verilog` runs lint/synthesis only inside the sandbox container unless you pass `allow_host: true`; `ingest-model` with `format: torchlogix` loads a pickle and needs `trusted: true` (and `CHIPLAB_ALLOW_PICKLE=1` when called through the optional network server). XGBoost models are converted in a separate process.
- Verification levels: 1 bit-exact simulation, 2 formal proof, 3 streaming RTL simulation (cocotb + Icarus) + lint, 4 Tiny Tapeout gate-level test after layout, 5 real hardware (never set automatically).

## Tools

### `compile-verilog`

Compile one trained candidate (or a raw chipir/1 document) to Verilog-2005 with its weights wired in. Returns a design_id used by every hardware and verification tool.

- Python: `lab.compile_verilog(batch_id: str | None = None, k: int | None = None, ir: dict | None = None, optimizer: str | None = None) -> dict`
- Lane: cpu; cached: True
  - `batch_id`: str
  - `k`: int — candidate index in the batch
  - `ir`: dict — a chipir/1 document instead
  - `optimizer`: str — none (default) | alkaid: constant multiplies via alkaid's shared shift-adds (smaller; design id gets -alk)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "batch_id": {
   "type": "string",
   "default": null
  },
  "k": {
   "type": "integer",
   "default": null
  },
  "ir": {
   "type": "object",
   "default": null
  },
  "optimizer": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": []
}
```
</details>

### `synthesize`

Synthesise a design. target=generic: gate count by type, logic depth, transistor estimate, gate netlist. target=xc7|ice40: lookup-table counts (same as count_luts).

- Python: `lab.synthesize(design_id: str, target: str = generic, effort: str = fast, timeout: int = 900) -> dict`
- Lane: cpu; cached: True
  - `design_id`: str
  - `target`: str — generic|xc7|ice40
  - `abc`: str — extra ABC flags, e.g. '-fast'
  - `timeout`: int seconds (900)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "target": {
   "type": "string",
   "default": "generic"
  },
  "effort": {
   "type": "string",
   "default": "fast"
  },
  "timeout": {
   "type": "integer",
   "default": 900
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab synthesize --json '{"design_id": "765fa47586bd"}'
```

### `count-luts`

Lookup-table count for an FPGA family: xc7 (6-input, Spartan-7 class, for comparison with published FPGA designs) or ice40 (4-input, iCE40UP5K).

- Python: `lab.count_luts(design_id: str, family: str = xc7) -> dict`
- Lane: cpu; cached: True
  - `design_id`: str
  - `family`: str — xc7|ice40

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "family": {
   "type": "string",
   "default": "xc7"
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab count-luts --json '{"design_id": "765fa47586bd", "family": "ice40"}'
```

### `simulate`

Verification level 1: run inputs through the gate netlist and compare with the integer model, and with the scientist's expected outputs when given (inputs=vectors). inputs=random exercises the whole input space.

- Python: `lab.simulate(design_id: str, inputs: str = random, n: int = 100000, device: str = auto, seed: int = 0, vectors: dict | None = None, expected: list | None = None) -> dict`
- Lane: gpu; cached: True
  - `design_id`: str
  - `inputs`: str — random|vectors|val|test (random)
  - `n`: int — random vectors (100000)
  - `vectors`: dict — port -> [[lane ints]], the scientist's test inputs (inputs=vectors)
  - `expected`: list — expected first-output values per vector, from the scientist's own model (optional)
  - `device`: str — auto|cuda|mps|numpy (auto: CUDA, else Apple MPS, else CPU)
  - `seed`: int

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "inputs": {
   "type": "string",
   "default": "random"
  },
  "n": {
   "type": "integer",
   "default": 100000
  },
  "device": {
   "type": "string",
   "default": "auto"
  },
  "seed": {
   "type": "integer",
   "default": 0
  },
  "vectors": {
   "type": "object",
   "default": null
  },
  "expected": {
   "type": "array",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab simulate --json '{"design_id": "765fa47586bd", "inputs": "random", "n": 100000}'
```

### `score-events`

Fair event-level referee (timescoring 0.0.7): your detections vs reference labels per recording. Returns per-recording tp/fp/refTrue/numSamples, per-patient sums, SzCORE per-patient averages and pooled figures, false alarms per hour and per 24 h, sensitivity at fixed FA/h (0.1, 0.36, 1) from a threshold sweep over scores, worst case, 1 s ROC AUC, patient bootstrap 95% CIs and provenance. profile=szcore (tolerance 30/60 s, merge <90 s, split >300 s; SzCORE-comparable) or neonatal (any overlap, no merge, no split).

- Python: `lab.score_events(recordings: list | None = None, path: str | None = None, profile: str = szcore, params: dict | None = None, nan_policy: str = omit, score_threshold: float = 0.5, fa_targets: list | None = None, thresholds: dict | None = None, n_thresholds: int = 200, n_bootstrap: int = 2000, seed: int = 0, progress_metrics: bool = False, design_id: str | None = None) -> dict`
- Lane: cpu; cached: False
  - `recordings`: list — [{patient_id, recording_id, fs, labels (0/1 per sample), decisions (0/1) and/or scores (float), timestamps (s, optional: gaps split the recording)}] (or give path)
  - `path`: str — JSON file with that list (or {recordings: [...]})
  - `profile`: str — szcore|neonatal (szcore)
  - `params`: dict — overrides: tolerance_start_s, tolerance_end_s, min_overlap, merge_s (null: never), split_s (null: never), collar_s
  - `nan_policy`: str — omit|zero: undefined per-patient values left out (SzCORE) or counted as 0 (omit)
  - `score_threshold`: float — decisions = scores >= this where decisions are missing (0.5)
  - `fa_targets`: list[float] — FA/h targets for the sweep (0.1, 0.36, 1.0)
  - `thresholds`: dict — {target: threshold} chosen on other data; skips the same-data sweep
  - `n_thresholds`: int — score quantiles in the sweep, at most 200; each one rescores every recording, so lower it for many long recordings with noisy scores (200)
  - `n_bootstrap`: int — patient-level bootstrap resamples (2000)
  - `seed`: int — bootstrap seed (0)
  - `progress_metrics`: bool — send event_sensitivity, fa_per_hour, worst_patient_sensitivity, auc to ./progress (false)
  - `design_id`: str (optional) — the chip these recordings came from; its ./progress metrics then carry that chip, as chip-report's do (output unchanged)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "recordings": {
   "type": "array",
   "default": null
  },
  "path": {
   "type": "string",
   "default": null
  },
  "profile": {
   "type": "string",
   "default": "szcore"
  },
  "params": {
   "type": "object",
   "default": null
  },
  "nan_policy": {
   "type": "string",
   "default": "omit"
  },
  "score_threshold": {
   "type": "number",
   "default": 0.5
  },
  "fa_targets": {
   "type": "array",
   "default": null
  },
  "thresholds": {
   "type": "object",
   "default": null
  },
  "n_thresholds": {
   "type": "integer",
   "default": 200
  },
  "n_bootstrap": {
   "type": "integer",
   "default": 2000
  },
  "seed": {
   "type": "integer",
   "default": 0
  },
  "progress_metrics": {
   "type": "boolean",
   "default": false
  },
  "design_id": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": []
}
```
</details>

### `prove-equivalence`

Verification level 2: prove the gate netlist equals the model for every possible input (ABC equivalence check against an independent golden model of the IR; falls back to proving synthesis if inconclusive).

- Python: `lab.prove_equivalence(design_id: str, timeout: int = 600, golden: bool = False) -> dict`
- Lane: cpu; cached: True
  - `design_id`: str
  - `timeout`: int seconds per proof attempt (600)
  - `golden`: bool — also try the proof against the independent golden model (small chips; slow on large ones)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "timeout": {
   "type": "integer",
   "default": 600
  },
  "golden": {
   "type": "boolean",
   "default": false
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab prove-equivalence --json '{"design_id": "765fa47586bd"}'
```

### `map-to-process`

Map a design onto a real process's standard cells: area in µm², gate-equivalents (area / NAND2), cell counts and an estimate of Tiny Tapeout tiles.

- Python: `lab.map_to_process(design_id: str, pdk: str = sky130) -> dict`
- Lane: cpu; cached: True
  - `design_id`: str
  - `pdk`: str — sky130|gf180|ihp

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "pdk": {
   "type": "string",
   "default": "sky130"
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab map-to-process --json '{"design_id": "765fa47586bd", "pdk": "sky130"}'
```

### `ingest-model`

Bring a trained model into the lab and compile it to a chip design. Formats: chipir (chipir/1 JSON), intnn (integer-network params: cfg/W1/b1/shift/W2/b2/amax or the multi-layer form), xgboost_json (an XGBoost model saved as JSON + w_feature/w_tree quantisation, converted via TreeLUT), torchlogix (a saved torchlogix module, local path only, trusted=true required because it is a pickle). Returns design_id, ports and lint.

- Python: `lab.ingest_model(format: str, model: dict | None = None, path: str | None = None, b64: str | None = None, in_spec: dict | None = None, w_feature: int = 4, w_tree: int = 4, trusted: bool = False, name: str = model, optimizer: str | None = None) -> dict`
- Lane: cpu; cached: True
  - `format`: str — chipir|intnn|xgboost_json|torchlogix
  - `model`: dict — the model JSON (chipir/intnn/xgboost_json)
  - `path`: str — file on this machine
  - `b64`: str — base64 file content (xgboost_json)
  - `in_spec`: dict — intnn input port {lanes, bits, signed} if not in the params
  - `w_feature`: int — TreeLUT input bits (xgboost_json)
  - `w_tree`: int — TreeLUT leaf bits (xgboost_json)
  - `trusted`: bool — allow unpickling (torchlogix)
  - `name`: str
  - `optimizer`: str — none (default) | alkaid (smaller constant multiplies; design id gets -alk)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "format": {
   "type": "string"
  },
  "model": {
   "type": "object",
   "default": null
  },
  "path": {
   "type": "string",
   "default": null
  },
  "b64": {
   "type": "string",
   "default": null
  },
  "in_spec": {
   "type": "object",
   "default": null
  },
  "w_feature": {
   "type": "integer",
   "default": 4
  },
  "w_tree": {
   "type": "integer",
   "default": 4
  },
  "trusted": {
   "type": "boolean",
   "default": false
  },
  "name": {
   "type": "string",
   "default": "model"
  },
  "optimizer": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "format"
 ]
}
```
</details>

Example:
```bash
chiplab ingest-model --json "{\"format\": \"intnn\", \"model\": $(cat fixtures/spike_best.json), \"name\": \"spike\"}"
```

### `compose-chip`

Build ONE chip from several model heads (multi-output, multi-input) with fusion logic between their decision outputs: and | or | kofn (k-of-n vote), or score-level fusion of multi-bit head scores: max | sum then a threshold compare (1-bit decision; e.g. one per-channel model on several channel ports, shared_inputs=false). Heads are design_ids or chipir/1 documents.

- Python: `lab.compose_chip(heads: dict, fusion: list | None = None, shared_inputs: bool = True, name: str = composed) -> dict`
- Lane: cpu; cached: True
  - `heads`: dict — head name -> design_id or chipir/1
  - `fusion`: list — [{name, op: and|or|kofn, k?, inputs: [<head>_<output>]}] or [{name, op: max|sum, t, rel? (ge), score? (false: also output <name>_score), inputs}]
  - `shared_inputs`: bool — heads read the same input port (true) or each keeps its own port (false)
  - `name`: str

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "heads": {
   "type": "object"
  },
  "fusion": {
   "type": "array",
   "default": null
  },
  "shared_inputs": {
   "type": "boolean",
   "default": true
  },
  "name": {
   "type": "string",
   "default": "composed"
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "heads"
 ]
}
```
</details>

Example:
```bash
chiplab compose-chip --json '{"heads": {"a": "765fa47586bd", "b": "ed8e52cb7a11"}, "fusion": [{"name": "alarm", "op": "and", "inputs": ["a_y", "b_y"]}], "shared_inputs": false}'
```

### `compile-stream`

Wrap a design for streaming hardware: inputs arrive one 15-bit word per strobe (ui_in[7]); outputs on uo_out[6:0] with valid on uo_out[7]. tt=true gives the Tiny Tapeout top (tt_um_chipin_<id>), else a generic top for FPGA boards. Optional postproc (smoothing, k-of-N, duration timer, alarm hold) and channel_serial (max or sum over C channels with one model copy) blocks; area=true also reports flip-flops and gates (and, with channel_serial, the parallel version with C copies of the core).

- Python: `lab.compile_stream(design_id: str, tt: bool = True, postproc: dict | None = None, channel_serial: dict | None = None, area: bool = False) -> dict`
- Lane: cpu; cached: True
  - `design_id`: str
  - `tt`: bool (true)
  - `postproc`: dict — optional on-chip post-processing of the per-frame decision: {output?, lane?, threshold? (frame bit = value >= threshold), smooth?: {mode: majority|kofn|average, n, k?, threshold?}, min_duration? (frames the condition must last), hold? (frames the alarm stays on)}; alarm on bit 0
  - `channel_serial`: dict — optional {channels: C, reduce: max|sum, threshold: T, output?, lane?}: each frame is ONE channel's input to ONE per-channel model; decision = reduce(score over C frames) >= T, valid every C frames; outputs decision then acc (one model copy instead of C)
  - `area`: bool — synthesise and report flip-flops and gates (false)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "tt": {
   "type": "boolean",
   "default": true
  },
  "postproc": {
   "type": "object",
   "default": null
  },
  "channel_serial": {
   "type": "object",
   "default": null
  },
  "area": {
   "type": "boolean",
   "default": false
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab compile-stream --json '{"design_id": "765fa47586bd", "tt": true}'
```

### `rtl-simulate`

Verification level 3: cocotb + Icarus simulation of the streaming wrapper (frames streamed in, outputs compared with the integer model or with the scientist's expected outputs) plus a Verilator lint.

- Python: `lab.rtl_simulate(design_id: str, n: int = 1000, vectors: dict | None = None, expected: dict | None = None, tt: bool = True, postproc: dict | None = None, channel_serial: dict | None = None) -> dict`
- Lane: cpu; cached: True
  - `design_id`: str
  - `n`: int — random frames if no vectors (1000)
  - `vectors`: dict — port -> [[lane ints]] (optional)
  - `expected`: dict — output -> [[lane ints]] (optional)
  - `tt`: bool (true)
  - `postproc`: dict — optional on-chip post-processing of the per-frame decision: {output?, lane?, threshold? (frame bit = value >= threshold), smooth?: {mode: majority|kofn|average, n, k?, threshold?}, min_duration? (frames the condition must last), hold? (frames the alarm stays on)}; alarm on bit 0
  - `channel_serial`: dict — optional {channels: C, reduce: max|sum, threshold: T, output?, lane?}: each frame is ONE channel's input to ONE per-channel model; decision = reduce(score over C frames) >= T, valid every C frames; outputs decision then acc (one model copy instead of C)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "n": {
   "type": "integer",
   "default": 1000
  },
  "vectors": {
   "type": "object",
   "default": null
  },
  "expected": {
   "type": "object",
   "default": null
  },
  "tt": {
   "type": "boolean",
   "default": true
  },
  "postproc": {
   "type": "object",
   "default": null
  },
  "channel_serial": {
   "type": "object",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab rtl-simulate --json '{"design_id": "765fa47586bd", "n": 300}'
```

### `estimate-cost`

Manufacturing routes for a design (iCE40 FPGA, Tiny Tapeout sky130/GF180/IHP, wafer.space GF180 slots, ChipFoundry chipIgnite, EUROPRACTICE GF180/IHP, Pragmatic FlexIC): fits or not, cost, deadline, the basis of each number, and per figure whether it was read on the vendor's page or is unverified.

- Python: `lab.estimate_cost(design_id: str) -> dict`
- Lane: inline; cached: False
  - `design_id`: str

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab estimate-cost --json '{"design_id": "765fa47586bd"}'
```

### `compare-hw-baseline`

Compare a design with published hardware from the lab's registry. Only entries with the same task, dataset and protocol (as you declare them) count as comparable; others are shown for context only.

- Python: `lab.compare_hw_baseline(design_id: str, task: str | None = None, dataset: str | None = None, protocol: str | None = None) -> dict`
- Lane: inline; cached: False
  - `design_id`: str
  - `task`: str — e.g. af_vs_normal (optional)
  - `dataset`: str — what the model was tested on (optional)
  - `protocol`: str — e.g. 'record-level, split by patient' (optional)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "task": {
   "type": "string",
   "default": null
  },
  "dataset": {
   "type": "string",
   "default": null
  },
  "protocol": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab compare-hw-baseline --json '{"design_id": "765fa47586bd", "task": "af_vs_normal", "dataset": "AFDB", "protocol": "record-level, per paper"}'
```

### `gate-activity`

Gate activity as raw numbers: run the scientist's input sequence (or random vectors) through the gate netlist and return, per net, how often it switches (toggle rate) and how often it is 1. Optionally writes a VCD of the ports. Data for power estimates and for whoever draws the 'chip lighting up' view.

- Python: `lab.gate_activity(design_id: str, vectors: dict | None = None, n: int = 2000, vcd: bool = False, top: int = 50, seed: int = 0) -> dict`
- Lane: cpu; cached: True
  - `design_id`: str
  - `vectors`: dict — port -> [[lane ints]] in time order (optional)
  - `n`: int — random vectors if none (2000)
  - `vcd`: bool — also write ports.vcd (false)
  - `top`: int — how many most active nets to return inline (50)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "vectors": {
   "type": "object",
   "default": null
  },
  "n": {
   "type": "integer",
   "default": 2000
  },
  "vcd": {
   "type": "boolean",
   "default": false
  },
  "top": {
   "type": "integer",
   "default": 50
  },
  "seed": {
   "type": "integer",
   "default": 0
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab gate-activity --json '{"design_id": "765fa47586bd", "n": 2000, "vcd": true}'
```

### `chip-report`

One-page chip report (markdown text): ports, hardware numbers with their basis, verification level and evidence, manufacturing routes and cost, published hardware for context, artefact paths. With decision_rate_hz (or a rate given to layout earlier) it shows power at that decision rate. Also returns `figures`: the chip's full figure set, which a ChipIn run's dashboard shows. Before you mark report done, call `chiplab chip-report --json '{"design_id": "<the chip you chose>", "decision_rate_hz": <decisions per second>}'` on the one chip you chose: the chip figures the user sees (area, power, energy, cost, verification) come from that call.

- Python: `lab.chip_report(design_id: str, name: str | None = None, decision_rate_hz: float | None = None) -> dict`
- Lane: inline; cached: False
  - `design_id`: str
  - `name`: str — a readable name (optional)
  - `decision_rate_hz`: float — decisions per second the device needs (optional)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "name": {
   "type": "string",
   "default": null
  },
  "decision_rate_hz": {
   "type": "number",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab chip-report --json '{"design_id": "765fa47586bd"}'
```

### `submit-verilog`

Submit hand- or agent-written Verilog safely. It is screened (no system tasks or includes), linted and synthesised inside a locked-down container, then checked bit for bit against a reference: a chipir/1 model (reference_ir) or the scientist's vectors + expected outputs. Ports must follow the lab convention (port_spec: inputs/outputs with lanes, bits, signed). Accepted designs get a design_id like any other.

- Python: `lab.submit_verilog(verilog: str, top: str, port_spec: dict, reference_ir: dict | None = None, vectors: dict | None = None, expected: dict | None = None, n: int = 20000, allow_host: bool = False) -> dict`
- Lane: cpu; cached: False
  - `verilog`: str — the source
  - `top`: str — top module name
  - `port_spec`: dict — {inputs:[{name,lanes,bits,signed}], outputs:[...]}
  - `reference_ir`: dict — chipir/1 model the circuit must equal (optional)
  - `vectors`: dict — port -> [[ints]] (optional)
  - `expected`: dict — output -> [[ints]] (optional)
  - `n`: int — random vectors when checking against reference_ir (20000)
  - `allow_host`: bool — run lint/synthesis on this machine if the sandbox container is missing (default false: refuse)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "verilog": {
   "type": "string"
  },
  "top": {
   "type": "string"
  },
  "port_spec": {
   "type": "object"
  },
  "reference_ir": {
   "type": "object",
   "default": null
  },
  "vectors": {
   "type": "object",
   "default": null
  },
  "expected": {
   "type": "object",
   "default": null
  },
  "n": {
   "type": "integer",
   "default": 20000
  },
  "allow_host": {
   "type": "boolean",
   "default": false
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "verilog",
  "top",
  "port_spec"
 ]
}
```
</details>

Example:
```bash
chiplab submit-verilog --json '{"verilog": "module xx(input [3:0] x, output [4:0] y); assign y = x + x; endmodule", "top": "xx", "port_spec": {"inputs": [{"name": "x", "lanes": 1, "bits": 4, "signed": false}], "outputs": [{"name": "y", "lanes": 1, "bits": 5, "signed": false}]}, "reference_ir": {"ir": "chipir/1", "name": "xx", "inputs": [{"name": "x", "lanes": 1, "bits": 4, "signed": false}], "nodes": [{"id": "s", "op": "add", "a": "x", "b": "x"}], "outputs": [{"name": "y", "src": "s"}], "meta": {}}}'
```

### `layout`

Place and route the chip with LibreLane (Docker): real cell area, die area, timing slack against a clock, power (vectorless, or from an activity VCD), GDS and the KLayout image. Power is given at the clock (power_uw_at_clock) and, with decision_rate_hz, at the rate the sensor actually needs decisions (power_uw_at_rate = energy per decision x rate + leakage). Changing the rate never re-runs LibreLane.

- Python: `lab.layout(design_id: str, pdk: str = sky130, clock_period_ns: float | None = None, core_util: int = 40, activity_vcd: str | None = None, timeout: int = 3600, decision_rate_hz: float | None = None) -> dict`
- Lane: docker; cached: True
  - `design_id`: str
  - `pdk`: str — sky130|gf180|ihp (sky130)
  - `clock_period_ns`: float — clock for timing (default 50 ns = 20 MHz; 100 ns on gf180)
  - `core_util`: int — target utilisation % (40)
  - `activity_vcd`: str — VCD of real activity for power (optional)
  - `timeout`: int seconds (3600)
  - `decision_rate_hz`: float — decisions per second the device needs (optional)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "pdk": {
   "type": "string",
   "default": "sky130"
  },
  "clock_period_ns": {
   "type": "number",
   "default": null
  },
  "core_util": {
   "type": "integer",
   "default": 40
  },
  "activity_vcd": {
   "type": "string",
   "default": null
  },
  "timeout": {
   "type": "integer",
   "default": 3600
  },
  "decision_rate_hz": {
   "type": "number",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab layout --json '{"design_id": "ed8e52cb7a11", "pdk": "sky130"}'
```

### `timing-power`

Timing and power of the laid-out chip (same LibreLane run as layout; cached, so calling both costs one run). With decision_rate_hz it adds power_uw_at_rate: energy per decision x decisions per second + leakage.

- Python: `lab.timing_power(design_id: str, pdk: str = sky130, clock_period_ns: float | None = None, activity_vcd: str | None = None, decision_rate_hz: float | None = None) -> dict`
- Lane: docker; cached: True
  - `design_id`: str
  - `pdk`: str — sky130|gf180|ihp (sky130)
  - `clock_period_ns`: float (default 50 ns = 20 MHz; 100 ns on gf180)
  - `activity_vcd`: str — optional VCD for activity-based power
  - `decision_rate_hz`: float — decisions per second the device needs (optional)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "pdk": {
   "type": "string",
   "default": "sky130"
  },
  "clock_period_ns": {
   "type": "number",
   "default": null
  },
  "activity_vcd": {
   "type": "string",
   "default": null
  },
  "decision_rate_hz": {
   "type": "number",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab timing-power --json '{"design_id": "ed8e52cb7a11", "pdk": "sky130", "decision_rate_hz": 1}'
```

### `bitstream`

iCE40UP5K bitstream (UPduino class board): the streaming wrapper plus a board top (clk, rst_n, ui_in, uo_out on pins), synthesised, placed and routed; LUTs, pins, maximum clock. Pass a .pcf for a specific board's pins.

- Python: `lab.bitstream(design_id: str, pcf: str | None = None, freq_mhz: float = 12.0) -> dict`
- Lane: cpu; cached: True
  - `design_id`: str
  - `pcf`: str — pin constraints file (optional; unconstrained otherwise)
  - `freq_mhz`: float (12)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "pcf": {
   "type": "string",
   "default": null
  },
  "freq_mhz": {
   "type": "number",
   "default": 12.0
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab bitstream --json '{"design_id": "765fa47586bd"}'
```

### `tt-package`

Tiny Tapeout project for the chip: streaming top tt_um_chipin_<id>, info.yaml, docs, a cocotb test with vectors from the integer model, Tiny Tapeout user config. harden=true also builds the GDS locally (Docker) and runs the gate-level test (verification level 4); otherwise commit the folder and run the tt-gds workflow.

- Python: `lab.tt_package(design_id: str, harden: bool = False, tiles: str = auto, pdk: str = sky130A, vectors: int = 64, clock_hz: int = 25000000, title: str | None = None) -> dict`
- Lane: docker; cached: True
  - `design_id`: str
  - `harden`: bool (false)
  - `tiles`: str — auto|1x1|1x2|2x2|... (auto)
  - `pdk`: str — sky130A|gf180mcuD|ihp-sg13g2
  - `vectors`: int — test vectors from the integer model (64)
  - `clock_hz`: int (25000000)
  - `title`: str (optional)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "harden": {
   "type": "boolean",
   "default": false
  },
  "tiles": {
   "type": "string",
   "default": "auto"
  },
  "pdk": {
   "type": "string",
   "default": "sky130A"
  },
  "vectors": {
   "type": "integer",
   "default": 64
  },
  "clock_hz": {
   "type": "integer",
   "default": 25000000
  },
  "title": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab tt-package --json '{"design_id": "ed8e52cb7a11", "harden": false}'
```

### `prove-sequential`

Sequential equivalence (eqy) of the streaming wrapper against its synthesised netlist: verification level 2 for clocked designs. Compositional by default: the combinational core is a black box here (prove it with prove_equivalence), so the proof covers only the clocked wrapper and takes seconds at any model size (spike: 3 s). whole=true proves the flattened design instead (small chips only, a few hundred gates).

- Python: `lab.prove_sequential(design_id: str, timeout: int = 600, whole: bool = False, postproc: dict | None = None, channel_serial: dict | None = None) -> dict`
- Lane: cpu; cached: True
  - `design_id`: str
  - `timeout`: int seconds (600)
  - `whole`: bool — prove the whole flattened design (false)
  - `postproc`: dict — optional on-chip post-processing of the per-frame decision: {output?, lane?, threshold? (frame bit = value >= threshold), smooth?: {mode: majority|kofn|average, n, k?, threshold?}, min_duration? (frames the condition must last), hold? (frames the alarm stays on)}; alarm on bit 0
  - `channel_serial`: dict — optional {channels: C, reduce: max|sum, threshold: T, output?, lane?}: each frame is ONE channel's input to ONE per-channel model; decision = reduce(score over C frames) >= T, valid every C frames; outputs decision then acc (one model copy instead of C)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "timeout": {
   "type": "integer",
   "default": 600
  },
  "whole": {
   "type": "boolean",
   "default": false
  },
  "postproc": {
   "type": "object",
   "default": null
  },
  "channel_serial": {
   "type": "object",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab prove-sequential --json '{"design_id": "765fa47586bd", "timeout": 300}'
```

### `verification-level`

The chip's verification level (1 bit-exact, 2 formal, 3 streaming RTL sim + lint, 4 TT gate-level test, 5 hardware) with the evidence behind it and what to run next.

- Python: `lab.verification_level(design_id: str) -> dict`
- Lane: inline; cached: False
  - `design_id`: str

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab verification-level --json '{"design_id": "765fa47586bd"}'
```

### `tt-readiness`

Tiny Tapeout submission readiness of a design's TT project (made by tt_package): info.yaml, pinout, docs, top ports, lint, licence, RTL test, and TT's official precheck if the project was hardened. Never submits or pays.

- Python: `lab.tt_readiness(design_id: str, run_tests: bool = True, precheck: bool = True) -> dict`
- Lane: docker; cached: False
  - `design_id`: str
  - `run_tests`: bool (true)
  - `precheck`: bool — run TT precheck if hardened (true)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "run_tests": {
   "type": "boolean",
   "default": true
  },
  "precheck": {
   "type": "boolean",
   "default": true
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab tt-readiness --json '{"design_id": "ed8e52cb7a11", "run_tests": true}'
```

### `tt-export`

Export a design's TT project as a standalone repo shaped like Tiny Tapeout's template (or staged under chiplab/tt_projects/ for the tt-gds workflow), ready for a human to push and submit. Creates no remote repo.

- Python: `lab.tt_export(design_id: str, out_dir: str | None = None, mode: str = standalone) -> dict`
- Lane: cpu; cached: False
  - `design_id`: str
  - `out_dir`: str — where to write (optional)
  - `mode`: str — standalone|monorepo (standalone)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "out_dir": {
   "type": "string",
   "default": null
  },
  "mode": {
   "type": "string",
   "default": "standalone"
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

Example:
```bash
chiplab tt-export --json '{"design_id": "ed8e52cb7a11", "mode": "standalone"}'
```

### `submit-job`

Run any tool asynchronously on its resource lane (cpu, gpu, docker). Returns a job_id immediately; poll job_status / job_result. Identical work from any agent is served from the cache.

- Python: `lab.submit_job(tool: str, args: dict | None = None, lane: str | None = None, session_id: str | None = None) -> dict`
- Lane: inline; cached: False
  - `tool`: str — tool name, e.g. synthesize
  - `args`: dict — the tool's arguments
  - `lane`: str — override lane (optional)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "tool": {
   "type": "string"
  },
  "args": {
   "type": "object",
   "default": null
  },
  "lane": {
   "type": "string",
   "default": null
  },
  "session_id": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "tool"
 ]
}
```
</details>

Example:
```bash
chiplab submit-job --json '{"tool": "map_to_process", "args": {"design_id": "765fa47586bd", "pdk": "sky130"}, "session_id": "agent-A"}'
```

### `submit-batch`

Submit many jobs of one tool at once (e.g. synthesize 50 candidates). Returns the job ids in order.

- Python: `lab.submit_batch(tool: str, args_list: list, session_id: str | None = None) -> dict`
- Lane: inline; cached: False
  - `tool`: str
  - `args_list`: list[dict] — one argument dict per job

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "tool": {
   "type": "string"
  },
  "args_list": {
   "type": "array"
  },
  "session_id": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "tool",
  "args_list"
 ]
}
```
</details>

### `job-status`

State of a job: queued | running | done | failed | cancelled, with timings.

- Python: `lab.job_status(job_id: str) -> dict`
- Lane: inline; cached: False
  - `job_id`: str

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "job_id": {
   "type": "string"
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "job_id"
 ]
}
```
</details>

Example (`@job_id` = the job id printed by the submit-job example):
```bash
chiplab job-status --json '{"job_id": "@job_id"}'
```

### `job-result`

Result of a finished job (the tool's own JSON answer).

- Python: `lab.job_result(job_id: str) -> dict`
- Lane: inline; cached: False
  - `job_id`: str

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "job_id": {
   "type": "string"
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "job_id"
 ]
}
```
</details>

Example (`@job_id` = the job id printed by the submit-job example):
```bash
chiplab job-result --json '{"job_id": "@job_id"}'
```

### `cancel-job`

Cancel a queued job (running jobs finish).

- Python: `lab.cancel_job(job_id: str) -> dict`
- Lane: inline; cached: False
  - `job_id`: str

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "job_id": {
   "type": "string"
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "job_id"
 ]
}
```
</details>

### `list-jobs`

List recent jobs (optionally one session's) and the load on each lane.

- Python: `lab.list_jobs(limit: int = 100, session_id: str | None = None) -> dict`
- Lane: inline; cached: False
  - `limit`: int (100)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "limit": {
   "type": "integer",
   "default": 100
  },
  "session_id": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": []
}
```
</details>

### `cache-stats`

Cache statistics: entries, hits, misses, bytes.

- Python: `lab.cache_stats() -> dict`
- Lane: inline; cached: False

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": []
}
```
</details>

Example:
```bash
chiplab cache-stats --json '{}'
```

### `estimate-batch`

Fast pre-synthesis gate estimates for many designs (chipir/1 documents or design ids), labelled as estimates. Use it to rank candidates; only finalists need real synthesis. Optionally keep the best N. est_error_notes gives the fit's held-out error for each design family present (intnn, composed, torchlogix, treelut, alkaid); the stream wrapper's flip-flops and area are separate fields, not in gates_est.

- Python: `lab.estimate_batch(designs: list, keep: int | None = None) -> dict`
- Lane: inline; cached: False
  - `designs`: list — chipir/1 dicts or design_id strings
  - `keep`: int — how many smallest to mark kept (optional)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "designs": {
   "type": "array"
  },
  "keep": {
   "type": "integer",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "designs"
 ]
}
```
</details>

Example:
```bash
chiplab estimate-batch --json '{"designs": ["765fa47586bd", "ed8e52cb7a11"], "keep": 1}'
```

### `synthesize-batch`

Synthesize many designs at once (fans out over the CPU lane). Returns job ids.

- Python: `lab.synthesize_batch(design_ids: list, target: str = generic, session_id: str | None = None, run_id: str | None = None) -> dict`
- Lane: inline; cached: False
  - `design_ids`: list[str]
  - `target`: str — generic|xc7|ice40

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_ids": {
   "type": "array"
  },
  "target": {
   "type": "string",
   "default": "generic"
  },
  "session_id": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string",
   "default": null
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_ids"
 ]
}
```
</details>

### `ingest-batch`

Ingest many models at once: each item is an ingest_model argument dict ({format, model|path|b64, name, ...}). They run in parallel on the CPU lane (start workers with `chiplab workers`). Returns job ids; with wait=true it waits and returns the design ids in the same order (null where an ingest failed).

- Python: `lab.ingest_batch(models: list, wait: bool = False, wait_timeout: int = 900, session_id: str | None = None, run_id: str | None = None) -> dict`
- Lane: inline; cached: False
  - `models`: list[dict] — ingest_model arguments, one per model
  - `wait`: bool — wait for all and return design ids (false)
  - `wait_timeout`: int seconds to wait (900)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "models": {
   "type": "array"
  },
  "wait": {
   "type": "boolean",
   "default": false
  },
  "wait_timeout": {
   "type": "integer",
   "default": 900
  },
  "session_id": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string",
   "default": null
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "models"
 ]
}
```
</details>

### `simulate-batch`

Bit-exact check many designs at once on the GPU lane. Returns job ids.

- Python: `lab.simulate_batch(design_ids: list, inputs: str = random, n: int = 100000, session_id: str | None = None, run_id: str | None = None) -> dict`
- Lane: inline; cached: False
  - `design_ids`: list[str]
  - `inputs`: str — random|val|vectors
  - `n`: int

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_ids": {
   "type": "array"
  },
  "inputs": {
   "type": "string",
   "default": "random"
  },
  "n": {
   "type": "integer",
   "default": 100000
  },
  "session_id": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string",
   "default": null
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_ids"
 ]
}
```
</details>

### `compile-ir`

Compile a chipir/1 document directly (no training batch): validates, emits Verilog, lints. Same as compile_verilog(ir=...).

- Python: `lab.compile_ir(ir: dict, optimizer: str | None = None) -> dict`
- Lane: cpu; cached: True
  - `ir`: dict — chipir/1
  - `optimizer`: str — none (default) | alkaid (smaller constant multiplies; design id gets -alk)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "ir": {
   "type": "object"
  },
  "optimizer": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "ir"
 ]
}
```
</details>

Example:
```bash
chiplab compile-ir --json '{"ir": {"ir": "chipir/1", "name": "tiny", "inputs": [{"name": "x", "lanes": 4, "bits": 4, "signed": false}], "nodes": [{"id": "s", "op": "matvec", "src": "x", "W": [[1, -1, 2, 0]], "b": [-3]}, {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}], "outputs": [{"name": "y", "src": "y"}], "meta": {}}}'
```

## Optional extras: data and training

Not needed for model -> chip. The AI scientist normally brings its own data, training and clinical scoring; these exist for regression tests and quick experiments (install with `--extra data`).

### `define-task`

Define a chip-design task: dataset or simulator, classes, clinical floor, budgets. Locks a subject-level split (train/val/test) that nobody can change afterwards.

- Python: `lab.define_task(name: str, classes: dict, dataset: str | None = None, simulator: dict | None = None, split: dict | None = None, clinical_floor: dict | None = None, budgets: dict | None = None, test_budget: int = 5, notes: str = ) -> dict`
- Lane: inline; cached: False
  - `name`: str — short task name
  - `dataset`: str — dataset plugin (see `chiplab plugins`), or omit with simulator
  - `simulator`: dict — {name, n_subjects, params, seed} for simulated data
  - `classes`: dict — class name -> list of dataset labels, negative class first, e.g. {"neg":["N"],"pos":["A"]}
  - `split`: dict — {fractions:[.7,.15,.15], seed:0, algo:'stratified-v1'}
  - `clinical_floor`: dict — e.g. {worst_subject_sensitivity: .9, specificity: .9}
  - `budgets`: dict — {max_gates, max_luts, max_area_um2, ...}
  - `test_budget`: int — how many times the sealed test set may be scored (default 5)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "name": {
   "type": "string"
  },
  "classes": {
   "type": "object"
  },
  "dataset": {
   "type": "string",
   "default": null
  },
  "simulator": {
   "type": "object",
   "default": null
  },
  "split": {
   "type": "object",
   "default": null
  },
  "clinical_floor": {
   "type": "object",
   "default": null
  },
  "budgets": {
   "type": "object",
   "default": null
  },
  "test_budget": {
   "type": "integer",
   "default": 5
  },
  "notes": {
   "type": "string",
   "default": ""
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "name",
  "classes"
 ]
}
```
</details>

### `load-data`

Turn a task's recordings into windows of frames with an off-chip front-end; returns a view_id. Window labels and the locked split come with it.

- Python: `lab.load_data(task_id: str, frontend: dict, window: dict) -> dict`
- Lane: cpu; cached: False
  - `task_id`: str
  - `frontend`: dict — {name, params} front-end plugin, e.g. {name:'rr_intervals'}
  - `window`: dict — {L: frames per window, stride, max_per_rec}

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "task_id": {
   "type": "string"
  },
  "frontend": {
   "type": "object"
  },
  "window": {
   "type": "object"
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "task_id",
  "frontend",
  "window"
 ]
}
```
</details>

### `propose-designs`

Propose a batch of candidate designs (family settings + input encoding) by explicit list, random or grid sampling of a design space. Returns a proposal_id to train.

- Python: `lab.propose_designs(view_id: str, family: str, sampler: str = random, n: int = 64, seed: int = 0, space: dict | None = None, candidates: list | None = None) -> dict`
- Lane: inline; cached: False
  - `view_id`: str
  - `family`: str — model family plugin, e.g. 'intnn'
  - `sampler`: str — explicit|random|grid
  - `n`: int — number of candidates (random)
  - `seed`: int
  - `space`: dict — setting -> list of values (family settings and encoding: L, encoder, bits, lo, hi, features)
  - `candidates`: list — explicit designs

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "view_id": {
   "type": "string"
  },
  "family": {
   "type": "string"
  },
  "sampler": {
   "type": "string",
   "default": "random"
  },
  "n": {
   "type": "integer",
   "default": 64
  },
  "seed": {
   "type": "integer",
   "default": 0
  },
  "space": {
   "type": "object",
   "default": null
  },
  "candidates": {
   "type": "array",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "view_id",
  "family"
 ]
}
```
</details>

### `train-batch`

Train every candidate of a proposal at once on the GPU (population training). Scores on train/val only; the sealed test set is never touched. Returns per-candidate validation metrics and timing.

- Python: `lab.train_batch(proposal_id: str, epochs: int | None = None, seed: int = 0, device: str | None = None, teacher: str | None = None, force: bool = False) -> dict`
- Lane: gpu; cached: False
  - `proposal_id`: str
  - `epochs`: int (family default)
  - `seed`: int
  - `device`: str — cuda|cpu|mps (auto)
  - `teacher`: str — design or reference to distil from (optional)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "proposal_id": {
   "type": "string"
  },
  "epochs": {
   "type": "integer",
   "default": null
  },
  "seed": {
   "type": "integer",
   "default": 0
  },
  "device": {
   "type": "string",
   "default": null
  },
  "teacher": {
   "type": "string",
   "default": null
  },
  "force": {
   "type": "boolean",
   "default": false
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  }
 },
 "required": [
  "proposal_id"
 ]
}
```
</details>

### `evaluate-clinical`

Clinical referee: the chip's own decisions (gate netlist outputs) scored per window, per recording and per subject, with the worst subject. split=val is free; split=test spends the task's test budget.

- Python: `lab.evaluate_clinical(design_id: str, split: str = val) -> dict`
- Lane: cpu; cached: False
  - `design_id`: str
  - `split`: str — val|test

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "design_id": {
   "type": "string"
  },
  "split": {
   "type": "string",
   "default": "val"
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": [
  "design_id"
 ]
}
```
</details>

### `leaderboard`

Leaderboard of compiled designs: gates, depth, bit-exact status and validation metrics.

- Python: `lab.leaderboard(task_id: str | None = None) -> dict`
- Lane: inline; cached: False
  - `task_id`: str (optional)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "task_id": {
   "type": "string",
   "default": null
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": []
}
```
</details>

### `events`

Events for the front end since a time (stage changes, candidate dots, check results).

- Python: `lab.events(since: float = 0.0) -> dict`
- Lane: inline; cached: False
  - `since`: float — unix time (0)

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "since": {
   "type": "number",
   "default": 0.0
  },
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": []
}
```
</details>

### `plugins`

List available plugins of every kind (datasets, frontends, families, simulators, targets).

- Python: `lab.plugins() -> dict`
- Lane: inline; cached: False

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "run_id": {
   "type": "string"
  },
  "session_id": {
   "type": "string"
  },
  "round": {
   "type": "integer"
  },
  "force": {
   "type": "boolean",
   "default": false
  }
 },
 "required": []
}
```
</details>
