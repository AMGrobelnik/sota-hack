# chipin.space chip lab

**A trained model goes in; a verified, measured, manufacturable chip comes out.** The lab is a Python package and
command-line tool that an AI scientist installs and calls on its own machine. It compiles the model into logic
gates with the weights wired in, proves the circuit equals the model, measures it on real chip processes, and
packages it for an FPGA or a Tiny Tapeout chip.

**Not part of the lab:** collecting data, labelling, training and clinical scoring belong to the AI scientist
(older data and training helpers survive only as optional extras). Visuals and the dashboard belong to another
agent; the lab only emits data for them.

Per-tool reference: [AGENT.md](AGENT.md). Event and file formats: [EVENTS.md](EVENTS.md). Original foundation
text: [SPEC.md](SPEC.md).

---

## 1. What you can do with it

- **Bring a model in one of these formats**
  - `chipir`: the lab's own integer IR (13 ops). Anything that lowers to it works.
  - `intnn`: small integer neural networks (binary, ternary or k-bit weights, one or more layers).
  - `torchlogix`: logic-gate networks (each neuron is a 2-input logic gate).
  - TreeLUT / XGBoost: boosted decision trees, quantised by TreeLUT.
  - Optional: alkaid, to compare a constant matrix multiply against its shift-add optimiser.
- **Several outputs and several sensors on one chip.** `compose-chip` puts several model heads on one chip, each
  reading the same input port or its own port (sensor 1, sensor 2, ...). Simple fusion logic between their
  decisions: AND, OR, k-of-n vote.
- **Streaming hardware.** `compile-stream` wraps the chip so inputs arrive one value per clock with a strobe. That's
  what an 8-pin Tiny Tapeout slot or a small FPGA needs.
- **Many candidates at once, by several agents.** Async jobs on resource lanes, a cache keyed by design content, a
  fast gate estimator for ranking, and batch tools.
- **Every output a chip maker or a judge asks for:**
  - Verilog and a gate netlist;
  - gate, transistor and LUT counts;
  - area on three real processes;
  - timing, power and layout (LibreLane);
  - iCE40 bitstream and Tiny Tapeout project;
  - verification level with evidence;
  - cost per manufacturing route and comparison with published chips;
  - a one-page report.

## 2. Quick start on a fresh Mac or Linux machine

Supported: Apple Silicon Macs (M1–M4) and Linux x86_64/arm64. Intel Macs use the darwin-x64 tool build and should
work, but are untested. Docker is needed only for layout, timing/power and the local Tiny Tapeout build.

```bash
git clone https://github.com/AMGrobelnik/sota-hack && cd sota-hack && git checkout ant/chip-lab && cd chiplab
scripts/install.sh                 # flags: --skip-docker, --skip-pdk, --skip-tt, --pdks "sky130", --mcp
.venv/bin/chiplab doctor           # JSON; every required check green = ready, otherwise it prints the fix
.venv/bin/chiplab ingest-model --json "{\"format\": \"intnn\", \"model\": $(cat fixtures/spike_best.json)}"
.venv/bin/chiplab synthesize --json '{"design_id": "<design_id printed above>"}'
```

`install.sh` is safe to re-run: it skips whatever is already installed, so you can start with `--skip-docker
--skip-pdk` and fetch the big downloads later. It writes the tool and PDK locations to
`~/.config/chiplab/config.json`. `scripts/smoke.sh` runs the whole flow below on the example model
(`--full` adds layout, bitstream and Tiny Tapeout).

## 3. How a chip flows through the lab

```
 model ──ingest-model / compile-ir──▶ chipir/1 IR ──▶ Verilog-2005 (weights as constants)
   │                                      │
   │                     estimate-batch (rank many, labelled estimates)
   ▼                                      ▼
 compose-chip (multi-head, fusion)   synthesize ─ count-luts ─ map-to-process      (gates, LUTs, µm², GE)
                                          │
                     verification ladder: simulate ▸ prove-equivalence ▸ rtl-simulate ▸ TT gate-level test
                                          │
                     timing-power / layout (LibreLane) ▸ bitstream (iCE40) ▸ tt-package (Tiny Tapeout)
                                          │
                     chip-report ▸ estimate-cost ▸ compare-hw-baseline ▸ gate-activity
```

| Step | Tool (see [AGENT.md](AGENT.md)) | What it gives |
|---|---|---|
| Bring the model in | `ingest-model`, `compile-ir` | design id, Verilog, Verilator lint |
| Combine heads | `compose-chip` | one chip, several outputs, fusion outputs |
| Rank candidates fast | `estimate-batch` | gate estimates (always labelled as estimates) |
| Synthesise | `synthesize` | gates by type, logic depth, transistor estimate, gate netlist |
| FPGA size | `count-luts` | 6-input LUTs (Spartan-7 class) or 4-input LUTs (iCE40) |
| Real process | `map-to-process` | area in µm², gate-equivalents, standard cells (sky130, gf180, ihp) |
| Level 1 | `simulate` | circuit = integer model (= your expected outputs) on every vector given |
| Level 2 | `prove-equivalence` | circuit = model for every possible input |
| Level 3 | `compile-stream`, `rtl-simulate` | streaming wrapper simulated in Icarus via cocotb, plus lint |
| Layout, timing, power | `layout`, `timing-power` | LibreLane: area, slack, power, GDS, KLayout image |
| FPGA | `bitstream` | iCE40UP5K bitstream, LUTs, maximum clock |
| Tiny Tapeout | `tt-package` | ready project folder (local or cloud build, gate-level test = level 4) |
| Paperwork | `chip-report`, `estimate-cost`, `compare-hw-baseline`, `gate-activity` | report, routes and prices, published chips, switching data |

## 4. Verification levels: what each one proves

Each chip carries the highest level it reached with nothing skipped below it.

| Level | Check | Proves | Doesn't prove |
|---|---|---|---|
| 1 | Bit-exact simulation (`simulate`) | On every vector run, the gate netlist gives exactly the integer model's answer (and your model's, if you pass expected outputs) | Inputs never tried |
| 2 | Formal equivalence (`prove-equivalence`) | For every possible input, the gates equal the generated RTL (ABC equivalence check). A stronger proof against an independent golden model is tried first when time allows; the result says which proof was obtained | That the IR equals your training framework, which is level 1 with your vectors |
| 3 | Streaming RTL simulation + lint (`rtl-simulate`) | The clocked wrapper (strobe, word assembly, valid flag) delivers the right answers frame by frame | Behaviour after placement and routing |
| 4 | Tiny Tapeout gate-level test after layout | The laid-out netlist behaves like the RTL | Real silicon |
| 5 | Running on a real board | Never set automatically | |

A negative control is part of the tests: flip one gate and both the simulation and the proof must fail.

## 5. Outputs per chip and where they land

Everything for a design is in `runs/designs/<design_id>/` (or `$CHIPLAB_HOME/designs/...`):

| Number or file | Basis |
|---|---|
| `design.v`, `ir.json`, `port.json` | generated |
| gates by type, depth (`synth.json`) | synthesized (Yosys, simple gates) |
| transistors | estimate (Yosys CMOS cost model) |
| LUTs (`luts_xc7.json`, `luts_ice40.json`) | synthesized |
| area µm², gate-equivalents (`pdk_<pdk>.json`) | synthesized onto the process's standard cells, before layout |
| Tiny Tapeout tiles before layout | estimate (area at 60% utilisation) |
| area, slack, power, GDS, PNG (`layout_<pdk>/`) | layout (LibreLane); power is vectorless unless an activity trace is given |
| gate activity (`gate_activity.json`), `ports.vcd` | activity from your vectors |
| verification evidence (`simulate_*.json`, `formal.json`, `rtlsim.json`) | measured |
| `report.md`, `cost.json` | report; prices as checked on 21 Nov 2026 |
| `estimate-batch` gate counts | estimate (least-squares fit to the lab's own syntheses) |

## 6. Manufacturing: what you can really buy today

| Route | What the lab gives | Cost and time | Caveats |
|---|---|---|---|
| iCE40UP5K FPGA | bitstream (`bitstream`) | $36 UPduino board, days | A real board needs its pin map (pass a `.pcf`); reprogrammable, not a product |
| Tiny Tapeout, sky130 | complete project folder (`tt-package`) | €70 per tile (about 1,000 gates) + €300 devkit (€100 for individuals); TTSKY26 closes 30 Nov 2026, chips about June 2027 | 8 in / 8 out / 8 bidirectional pins (hence streaming); designs are published openly. Cloud build: commit the folder, run the `tt-gds` GitHub workflow |
| Tiny Tapeout, GF180 / IHP | same flow | same pricing; GF180 closes 7 Dec 2026 | validated on sky130; GF180/IHP checked up to config and PDK resolution |
| wafer.space GF180, ChipFoundry, EUROPRACTICE, Pragmatic FlexIC | area, timing and power estimates only | wafer.space $3,000 per ~1,000 dies; Pragmatic €900/mm² (minimum 3×3 mm) | Need full-chip steps the lab does **not** do yet: pad ring, harness, full DRC/LVS signoff, commercial design kits |

No route is medically certified; the device maker remains responsible for clinical validation and approval.

## 7. Several agents at once, on any machine

- **Where it runs.** The lab runs where the AI scientist runs (a Mac, a Linux box, a GPU server). It needs nothing
  from the machine it was built on.
- **Async jobs.** `submit-job` / `submit-batch` return job ids; `job-status`, `job-result`, `cancel-job`,
  `list-jobs`. Jobs run on lanes sized to the machine:
  - cpu: cores − 1 workers (Yosys, ABC, Icarus and Verilator are single-threaded, so batches fan out one job per
    core);
  - gpu: 1 (batched bit-exact checks; CUDA, else Apple MPS, else CPU);
  - docker: Docker memory ÷ 12 GB, 1–4 workers (LibreLane and the Tiny Tapeout build; each layout gets
    cores ÷ docker-workers routing threads).

  Override with `CHIPLAB_CPU_WORKERS`, `CHIPLAB_GPU_WORKERS`, `CHIPLAB_DOCKER_WORKERS`, or `"lanes"` in the config
  file. `chiplab doctor` shows the sizes it picked. Start the workers with `chiplab workers`.
- **Cache.** Results are keyed by design content, tool, arguments and lab version, so two agents submitting the
  same design share one result (`cached: true`).
- **Sessions.** Pass `session_id` for per-agent quotas and history. The job table is SQLite and the cache is
  diskcache, so both work locally on a Mac or Linux with no server.
- **Optional MCP.** `--extra mcp` adds an MCP server (stdio or HTTP) for agents that prefer MCP. The lab never
  needs it.

## 8. Events and files for other systems

Pass `run_id` to any tool and its result becomes JSON-lines events in `runs/events/<run_id>.jsonl`, each with
`{type, run_id, session_id, seq, t, round?}`. Event types:

- `chip_compiled`, `check_bitexact`, `hw_metrics` (always with its basis);
- `gate_activity` (raw toggle rates);
- `layout_ready`, `bitstream_ready`, `tt_package_ready`, `report_ready`;
- `candidates_scored`, `cost`.

Field-by-field formats and the file list: [EVENTS.md](EVENTS.md).

## 9. Measured so far (Sat 21 Nov 2026)

All measured on one Linux machine: RTX 3090, Yosys 0.71, OSS CAD Suite 2026-11-21, ABC effort `fast`.

| Chip | Result | How measured |
|---|---|---|
| Feasibility-spike AF detector (intnn: 8 inputs × 6-bit, 16 hidden, ternary) | 2,285 gates, depth 51, ~17,400 transistors (estimate); sky130 16,638 µm² = 4,433 GE, 2,940 cells, ~2 Tiny Tapeout tiles (€440 incl. devkit); 862 iCE40 LUTs | `synthesize`, `map-to-process`, `count-luts`; Yosys's slower default ABC script gives 2,206 gates |
| Same chip, verification | bit-exact on 200,000 random vectors (GPU) and on all 3,688 validation windows three ways (circuit = integer model = PyTorch); formal proof gates = RTL; streaming wrapper 200/200 frames | `simulate`, `prove-equivalence` (ABC cec, ~30 s), `rtl-simulate` |
| torchlogix logic-gate network 16-48-48, 3 classes | 242 gates, depth 29, bit-exact 2,000/2,000 against torchlogix itself | `ingest-model` + tests |
| TreeLUT boosted trees | 661 gates (binary, 8 trees, depth 3); 1,537 gates (3 classes), bit-exact against TreeLUT's predict | tests |
| 3 heads on separate input ports + AND / 2-of-3 / OR fusion | 2,622 gates, depth 53; level 1 4,000/4,000; level 3 300/300 frames (Tiny Tapeout and generic wrappers) | tests |
| Larger AF candidate (16 inputs × 8-bit, 8 hidden) | 5,075 gates, depth 60, synthesised in 1 s (Yosys's default ABC script timed out after 15 min) | `synthesize` |
| Gate estimator | r² = 0.75 on 32 synthesised designs | `estimate-batch` refit |
| Population training (optional extra) | 256 candidates as one GPU program, ~2,100–2,500 candidates/min | `train-batch`; one-at-a-time GPU baseline is launch-bound, so no speedup is claimed |

Layout, timing and power (LibreLane, sky130) and the Tiny Tapeout build are validated with one smoke run on a
small design; their numbers go in the chip report when run.

## 10. Limits and honesty notes

- **Digital core only.** Real sensors need an analog front-end (amplifier, ADC) that the lab doesn't design.
- **Not medically certified**, and no route here is.
- **Formal proof:** gates = RTL is fast. The proof against the independent golden model can time out on designs of
  a few thousand gates; the tool reports which proof it got and the level stays honest.
- **Published chips are context, not a scoreboard,** unless task, dataset, protocol and unit all match. The
  registry carries these fields and the report says "context only" otherwise.
- **GF180 and IHP** are supported by the same flow but validated only up to configuration and PDK resolution.
  Full layouts were validated on sky130.
- **Optimisation headroom:** alkaid's shift-add sharing makes constant matrix multiplies 29–45% smaller than the
  lab's current emitter, which is not yet adopted.
- Transistor counts, pre-layout tile counts and `estimate-batch` gate counts are estimates and are labelled as such.

## 11. Architecture, repo layout and licences

```
chiplab/
  chiplab/ir/        chipir/1 schema, interval-derived widths, reference interpreter, gate estimator
  chiplab/emit/      Verilog emitter, independent golden model (for proofs), streaming wrapper
  chiplab/ingest/    converters: chipir, intnn, torchlogix, TreeLUT/XGBoost (vendored, MIT), compose (fusion)
  chiplab/hw/        Yosys (gates, LUTs), Liberty mapping, LibreLane, iCE40, Tiny Tapeout, cost table, baselines.yaml
  chiplab/verify/    bit-parallel netlist evaluator (numpy/CUDA/MPS), bit-exact, ABC proof, eqy, cocotb sim, ladder
  chiplab/jobs/      Huey job lanes; cache.py (diskcache); events.py; tools*.py (the registry); cli.py; api.py
  chiplab/data|train|referee|plugins/   optional extras (datasets, population training, clinical metrics)
  scripts/           install.sh, smoke.sh;  tests/  (IR fuzz, ingest, compose, stream, formal, ...)
```

Wrapped or reused, not reimplemented. Licences as published by each project:

| Project | Licence | Use |
|---|---|---|
| Yosys, ABC, eqy/sby, nextpnr, icestorm (OSS CAD Suite) | ISC / BSD-style | synthesis, proofs, FPGA |
| Icarus Verilog | GPL-2.0 | RTL simulation (run as a tool) |
| Verilator | LGPL-3.0 / Artistic-2.0 | lint |
| LibreLane 3.0.14 (OpenROAD BSD-3, OpenSTA GPL-3.0, Magic, KLayout GPL) | Apache-2.0 | layout, timing, power (run in its container) |
| SkyWater 130, GF180MCU, IHP SG13G2 PDKs; ciel | Apache-2.0 | standard cells |
| tt-support-tools, tt-gds-action | Apache-2.0 | Tiny Tapeout projects and cloud build |
| cocotb | BSD-3-Clause | testbenches |
| torchlogix | MIT | logic-gate network models (dependency) |
| TreeLUT | MIT | vendored in `chiplab/ingest/vendor/treelut` with its licence |
| alkaid | LGPL-3.0 | optional dependency only, not vendored |
| Huey | MIT | job queue |
| diskcache | Apache-2.0 | result cache |
| PyTorch | BSD-3-Clause | training and GPU bit-exact checks |
| XGBoost | Apache-2.0 | tree models |
| Jinja2, pyvcd, NumPy, SciPy | BSD / MIT | report, VCD, numerics |
| MCP Python SDK (optional) | MIT | optional MCP server |

Ours: the IR and range analysis, the Verilog and golden emitters, the converters, the fusion and streaming
wrapper, the netlist evaluator, the verification stamping, the tool registry and docs, the cost table and the
baseline registry.

## 12. Built before vs built at the event

- **Before the event (Fri 20 Nov and earlier):** none of this code. Open-source tools listed above are used as
  published.
- **At the event (Sat 21 – Sun 22 Nov 2026):** everything in `chiplab/`. It generalises the feasibility spike
  written on Sat 21 Nov (`origin/amg/context:spike/`), whose fixture `fixtures/spike_best.json` is the regression
  design. Git history on branch `ant/chip-lab` shows each step.
