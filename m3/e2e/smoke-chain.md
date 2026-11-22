# Smoke chain on the merged chip-lab branch

Run on 22 Nov 2026 on `ant/chip-lab` at `4200b54` (merge of pull request 23), Apple M3 Max. Every step
passed. No lab code was changed.

## Setup

- **Model:** design A, the 8-input feature MLP of the earlier end-to-end run
  (`m3/e2e/run/workspace/designs/A.ir.json`, chipir/1: 8 lanes of 6-bit unsigned input, one hidden
  layer of 8, one 1-bit output). Its weights are random placeholders, as `m3/e2e/REPORT.md` says.
- **Lab code:** the branch tip's `chiplab/` package, run with the Python environment of an earlier
  development checkout whose `chiplab/` tree is identical to `4200b54`. `chiplab doctor` with the
  settings below: ready, only the optional `python:mcp` missing.
- **Settings:** `CHIPLAB_USER_DIR` and `CHIPLAB_CONFIG` pointed at the existing project-folder lab
  install (Yosys 0.71+77, OSS CAD Suite); `CHIPLAB_HOME` at a fresh folder under the checkout's
  ignored `chiplab/runs/`, so the result cache started empty and no answer came from it;
  `CHIPLAB_CPU_WORKERS=4`, `CHIPLAB_DOCKER_WORKERS=0`.
- **How each step ran:** `python -m chiplab.cli <tool> --json-file <args>` (the `chiplab` command's
  own entry point), one process per step in its own session, from a driver started in the
  background under `memgate`. The driver's timeout killed every descendant and its process group; no
  step came near it. The answers and the log stayed in the ignored `chiplab/runs/smoke-chain/`.

## Result per step

The arguments below are the exact JSON each step received; `<id>` is `67301286c5e3`.

| # | tool | arguments | result | wall s |
|---:|---|---|---|---:|
| 1 | compile-ir | `{"ir": <A.ir.json>}` | pass | 0.3 |
| 2 | synthesize | `{"design_id": <id>}` | pass | 0.7 |
| 3 | simulate | `{"design_id": <id>, "inputs": "random", "n": 100000}` | pass | 1.4 |
| 4 | prove-equivalence | `{"design_id": <id>, "golden": true, "timeout": 300}` | pass | 7.2 |
| 5 | compile-stream | see below, with `"area": true` | pass | 2.3 |
| 6 | rtl-simulate | see below, with `"n": 200` | pass | 2.9 |
| 7 | chip-report | `{"design_id": <id>, "decision_rate_hz": 1.0}` | pass | 0.9 |
| 8 | score-events | `{"path": <recordings.json>, "profile": "szcore"}` | pass | 5.5 |

Steps 5 and 6 used the same wrapper options, both blocks at once:

```json
{"tt": true,
 "postproc": {"smooth": {"mode": "majority", "n": 3}, "hold": 4},
 "channel_serial": {"channels": 4, "reduce": "sum", "threshold": 2}}
```

Every step exited 0 with `status: ok`.

### What the tools returned

- **compile-ir:** design `67301286c5e3`, top `chip_67301286c5e3`, 41 lines of Verilog, lint clean.
  The same design id as design A in the earlier run.
- **synthesize:** 2,867 gates, logic depth 60, about 21,868 transistors (Yosys estimate).
- **simulate:** 100,000 random vectors on Apple MPS, 0 mismatches against the integer model,
  bit-exact; verification level 1.
- **prove-equivalence:** proved against the independent golden model of the IR (ABC `cec` gates ==
  RTL, then ABC `iprove` RTL == golden for every input), 7.0 s in total, 5.67 s for the whole-design
  node; verification level 2.
- **compile-stream:** top `tt_um_chipin_67301286c5e3`, 8 transfers per frame, 4 frames per decision.
  The smoothing became majority 2 of 3 with a 4-frame hold. The outputs are the alarm, the decision
  and a 3-bit accumulator. Area, from the lab's own synthesis:

  | version | flip-flops | gates |
  |---|---:|---:|
  | channel-serial, one model copy | 70 | 3,079 |
  | parallel, 4 copies, no post-processing | 206 | 12,127 |

  Parallel over serial: 3.94 times the gates, 2.94 times the flip-flops.
- **rtl-simulate:** cocotb with Icarus on the Tiny Tapeout top: 800 frames, 200 decisions, 0 mismatches
  against the lab's sequence model (`emit.postproc.reference`), Verilator lint clean; verification
  level 3. The alarm was on for 99.5 % of decisions, because random frames from an untrained model
  trip the 2-of-4 vote almost every time.
- **chip-report:** 2,867 gates, depth 60, 20,043 µm² on sky130 before layout (5,339.7 GE), 2 Tiny
  Tapeout tiles, 440 EUR on the Tiny Tapeout sky130 price list, verification level 3. No layout,
  power or slack, since layout needs Docker.
- **score-events** (SzCORE profile) on synthetic recordings: 3 patients, 2 recordings each, 2 h at
  1 Hz, 2 labelled events of 40 to 90 s per recording. The scores are 0.15 plus 0.6 inside an
  event plus Gaussian noise (σ 0.12), clipped to 0 to 1, from a fixed seed (7). They test the
  referee, not this chip: design A is untrained.

  | figure | value |
  |---|---:|
  | events (reference) | 12 |
  | true positives | 12 |
  | false positives at threshold 0.5 | 56 |
  | sensitivity, pooled and per-patient mean | 1.0 |
  | precision, pooled | 0.176 |
  | false alarms per hour, pooled | 4.67 |
  | pooled 1 s ROC AUC | 0.9998 |
  | sensitivity at 0.1, 0.36 and 1 FA/h | 1.0 at threshold 0.714 |

  The lab flags the last row as optimistic: the threshold was chosen on the scored data itself.

## Not run: steps that need Docker

Docker was not used. These steps of the full chain (`chiplab/scripts/smoke.sh --full`,
`chiplab/scripts/smoke_small.py`) run in the lab's Docker lane or container and were not run:

- `layout` and `timing-power` (LibreLane): placed area, slack, fmax and power;
- `tt-package` and `tt-readiness`: the Tiny Tapeout project, its local harden and the gate-level
  test (verification level 4);
- `submit-verilog`, whose lint and synthesis run in a sandbox container by default.

Also outside this chain: `map-to-process`, `count-luts`, `bitstream`, `prove-sequential` and
`estimate-cost`. They need no Docker but were not in the requested chain.

## Process check

After the chain, `pgrep` found no `yosys`, `yosys-abc`, `sby`, `eqy`, `yices` or `smtbmc` process
left over.
