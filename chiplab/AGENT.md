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
- Async (several agents at once): `submit-job {tool, args, session_id}` returns a `job_id`; poll `job-status` / `job-result`. Lanes: cpu (6 workers), gpu (1), docker (1); start workers with `chiplab workers`. Results are cached by content, so duplicate designs return instantly (`cached: true`).
- Every tool also accepts `run_id`, `session_id`, `round` (events, see EVENTS.md) and `force` (skip the cache).
- Verification levels: 1 bit-exact simulation, 2 formal proof, 3 streaming RTL simulation (cocotb + Icarus) + lint, 4 Tiny Tapeout gate-level test after layout, 5 real hardware (never set automatically).

## Tools

### `compile-verilog`

Compile one trained candidate (or a raw chipir/1 document) to Verilog-2005 with its weights wired in. Returns a design_id used by every hardware and verification tool.

- Python: `lab.compile_verilog(batch_id: str | None = None, k: int | None = None, ir: dict | None = None) -> dict`
- Lane: cpu; cached: True
  - `batch_id`: str
  - `k`: int — candidate index in the batch
  - `ir`: dict — a chipir/1 document instead

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
chiplab synthesize --json '{"design_id": "cdaea5efb328"}'
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
chiplab count-luts --json '{"design_id": "cdaea5efb328", "family": "ice40"}'
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
chiplab simulate --json '{"design_id": "cdaea5efb328", "inputs": "random", "n": 100000}'
```

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
chiplab prove-equivalence --json '{"design_id": "cdaea5efb328"}'
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
chiplab map-to-process --json '{"design_id": "cdaea5efb328", "pdk": "sky130"}'
```

### `ingest-model`

Bring a trained model into the lab and compile it to a chip design. Formats: chipir (chipir/1 JSON), intnn (integer-network params: cfg/W1/b1/shift/W2/b2/amax or the multi-layer form), xgboost_json (an XGBoost model saved as JSON + w_feature/w_tree quantisation, converted via TreeLUT), torchlogix (a saved torchlogix module, local path only, trusted=true required because it is a pickle). Returns design_id, ports and lint.

- Python: `lab.ingest_model(format: str, model: dict | None = None, path: str | None = None, b64: str | None = None, in_spec: dict | None = None, w_feature: int = 4, w_tree: int = 4, trusted: bool = False, name: str = model) -> dict`
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
chiplab ingest-model --json '{"format": "intnn", "model": "<contents of fixtures/spike_best.json>", "name": "spike"}'
```

### `compose-chip`

Build ONE chip from several model heads (multi-output, multi-input) with fusion logic between their decision outputs: and | or | kofn (k-of-n vote). Heads are design_ids or chipir/1 documents.

- Python: `lab.compose_chip(heads: dict, fusion: list | None = None, shared_inputs: bool = True, name: str = composed) -> dict`
- Lane: cpu; cached: True
  - `heads`: dict — head name -> design_id or chipir/1
  - `fusion`: list — [{name, op: and|or|kofn, k?, inputs: [<head>_<output>]}]
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
chiplab compose-chip --json '{"heads": {"a": "<design_id>", "b": "<design_id>"}, "fusion": [{"name": "alarm", "op": "and", "inputs": ["a_y", "b_y"]}], "shared_inputs": false}'
```

### `compile-stream`

Wrap a design for streaming hardware: inputs arrive one 15-bit word per strobe (ui_in[7]); outputs on uo_out[6:0] with valid on uo_out[7]. tt=true gives the Tiny Tapeout top (tt_um_chipin_<id>), else a generic top for FPGA boards.

- Python: `lab.compile_stream(design_id: str, tt: bool = True) -> dict`
- Lane: cpu; cached: True
  - `design_id`: str
  - `tt`: bool (true)

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
chiplab compile-stream --json '{"design_id": "cdaea5efb328", "tt": true}'
```

### `rtl-simulate`

Verification level 3: cocotb + Icarus simulation of the streaming wrapper (frames streamed in, outputs compared with the integer model or with the scientist's expected outputs) plus a Verilator lint.

- Python: `lab.rtl_simulate(design_id: str, n: int = 1000, vectors: dict | None = None, expected: dict | None = None, tt: bool = True) -> dict`
- Lane: cpu; cached: True
  - `design_id`: str
  - `n`: int — random frames if no vectors (1000)
  - `vectors`: dict — port -> [[lane ints]] (optional)
  - `expected`: dict — output -> [[lane ints]] (optional)
  - `tt`: bool (true)

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
chiplab rtl-simulate --json '{"design_id": "cdaea5efb328", "n": 300}'
```

### `estimate-cost`

Manufacturing routes for a design (iCE40 FPGA, Tiny Tapeout sky130/GF180, wafer.space GF180, Pragmatic FlexIC): fits or not, cost, deadline, and the basis of each number.

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
chiplab estimate-cost --json '{"design_id": "cdaea5efb328"}'
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
chiplab compare-hw-baseline --json '{"design_id": "cdaea5efb328", "task": "af_vs_normal", "dataset": "AFDB", "protocol": "record-level, per paper"}'
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
chiplab gate-activity --json '{"design_id": "cdaea5efb328", "n": 2000, "vcd": true}'
```

### `chip-report`

One-page chip report (markdown text): ports, hardware numbers with their basis, verification level and evidence, manufacturing routes and cost, published hardware for context, artefact paths.

- Python: `lab.chip_report(design_id: str, name: str | None = None) -> dict`
- Lane: inline; cached: False
  - `design_id`: str
  - `name`: str — a readable name (optional)

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
chiplab chip-report --json '{"design_id": "cdaea5efb328"}'
```

### `submit-verilog`

Submit hand- or agent-written Verilog safely. It is screened (no system tasks or includes), linted and synthesised inside a locked-down container, then checked bit for bit against a reference: a chipir/1 model (reference_ir) or the scientist's vectors + expected outputs. Ports must follow the lab convention (port_spec: inputs/outputs with lanes, bits, signed). Accepted designs get a design_id like any other.

- Python: `lab.submit_verilog(verilog: str, top: str, port_spec: dict, reference_ir: dict | None = None, vectors: dict | None = None, expected: dict | None = None, n: int = 20000) -> dict`
- Lane: cpu; cached: False
  - `verilog`: str — the source
  - `top`: str — top module name
  - `port_spec`: dict — {inputs:[{name,lanes,bits,signed}], outputs:[...]}
  - `reference_ir`: dict — chipir/1 model the circuit must equal (optional)
  - `vectors`: dict — port -> [[ints]] (optional)
  - `expected`: dict — output -> [[ints]] (optional)
  - `n`: int — random vectors when checking against reference_ir (20000)

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
chiplab submit-verilog --json '{"verilog": "module m(input [3:0] x, output [4:0] y); assign y = x + x; endmodule", "top": "m", "port_spec": {"inputs": [{"name": "x", "lanes": 1, "bits": 4, "signed": false}], "outputs": [{"name": "y", "lanes": 1, "bits": 5, "signed": false}]}, "reference_ir": "<chipir/1 doc computing x + x>"}'
```

### `layout`

Place and route the chip with LibreLane (Docker): real cell area, die area, timing slack against a clock, power (vectorless, or from an activity VCD), GDS and the KLayout image. Validated on sky130; gf180 and ihp use the same flow (validated up to configuration).

- Python: `lab.layout(design_id: str, pdk: str = sky130, clock_period_ns: float = 20.0, core_util: int = 40, activity_vcd: str | None = None, timeout: int = 3600) -> dict`
- Lane: docker; cached: True
  - `design_id`: str
  - `pdk`: str — sky130|gf180|ihp (sky130)
  - `clock_period_ns`: float — decision clock for timing (20)
  - `core_util`: int — target utilisation % (40)
  - `activity_vcd`: str — VCD of real activity for power (optional)
  - `timeout`: int seconds (3600)

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
   "default": 20.0
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
chiplab layout --json '{"design_id": "cdaea5efb328", "pdk": "sky130", "clock_period_ns": 20}'
```

### `timing-power`

Timing and power of the laid-out chip (same LibreLane run as layout; cached, so calling both costs one run).

- Python: `lab.timing_power(design_id: str, pdk: str = sky130, clock_period_ns: float = 20.0, activity_vcd: str | None = None) -> dict`
- Lane: docker; cached: True
  - `design_id`: str
  - `pdk`: str — sky130|gf180|ihp (sky130)
  - `clock_period_ns`: float (20)
  - `activity_vcd`: str — optional VCD for activity-based power

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
   "default": 20.0
  },
  "activity_vcd": {
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
chiplab timing-power --json '{"design_id": "cdaea5efb328", "pdk": "sky130"}'
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
chiplab bitstream --json '{"design_id": "cdaea5efb328"}'
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
chiplab tt-package --json '{"design_id": "cdaea5efb328", "harden": false}'
```

### `prove-sequential`

Sequential equivalence (eqy) of the streaming wrapper against its synthesised netlist: verification level 2 for clocked designs. Works on small chips; may time out on large ones (reported honestly).

- Python: `lab.prove_sequential(design_id: str, timeout: int = 600) -> dict`
- Lane: cpu; cached: True
  - `design_id`: str
  - `timeout`: int seconds (600)

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
chiplab prove-sequential --json '{"design_id": "cdaea5efb328", "timeout": 300}'
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
chiplab verification-level --json '{"design_id": "cdaea5efb328"}'
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
chiplab submit-job --json '{"tool": "map_to_process", "args": {"design_id": "cdaea5efb328", "pdk": "sky130"}, "session_id": "agent-A"}'
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

Example:
```bash
chiplab job-result --json '{"job_id": "j-\u2026"}'
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

### `estimate-batch`

Fast pre-synthesis gate estimates for many designs (chipir/1 documents or design ids), labelled as estimates. Use it to rank candidates; only finalists need real synthesis. Optionally keep the best N.

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
chiplab estimate-batch --json '{"designs": ["<design_id>", "<design_id>"], "keep": 5}'
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

- Python: `lab.compile_ir(ir: dict) -> dict`
- Lane: cpu; cached: True
  - `ir`: dict — chipir/1

<details><summary>JSON schema</summary>

```json
{
 "type": "object",
 "properties": {
  "ir": {
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
