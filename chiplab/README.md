# chipin.space chip lab

The toolbox an AI scientist calls to design, train, compile, verify, measure and package tiny chips for medical
sensing devices. The AI scientist decides what to try; the lab makes it and returns honest numbers. Foundation
spec: [SPEC.md](SPEC.md). Tool reference for agents: `chiplab agent-doc` (also written to AGENT.md).

## Setup (this machine: RTX 3090, Ubuntu)

```bash
cd chiplab && uv sync --extra dev --extra sim        # torch cu130, numpy, wfdb, cocotb, pytest
scripts/setup_toolchain.sh                           # OSS CAD Suite, LibreLane image, PDKs (sky130, gf180, ihp)
.venv/bin/python -m pytest -q                        # IR fuzz (netlist + Icarus), split, encoders, family
```
Data is downloaded by dataset plugins into `~/chiplab-data`; results go to `chiplab/runs/` (git-ignored).

## Use

```bash
C=.venv/bin/chiplab
$C list-tools
$C define-task     --json '{"name":"af_rr","dataset":"cinc2017","classes":{"neg":["N"],"pos":["A"]}}'
$C load-data       --json '{"task_id":"…","frontend":{"name":"rr_intervals"},"window":{"L":25,"stride":4,"max_per_rec":40}}'
$C propose-designs --json '{"view_id":"…","family":"intnn","sampler":"random","n":256,"space":{"L":[8,16,24],"bits":[4,6,8],"hidden":[[4],[8],[16]],"encoder":["uniform","delta"],"lo":[0],"hi":[2048],"wtype":["ternary","binary"]}}'
$C train-batch     --json '{"proposal_id":"…","epochs":60}'
$C compile-verilog --json '{"batch_id":"…","k":39}'
$C synthesize      --json '{"design_id":"…"}'                    # gates by type, depth, transistors
$C simulate        --json '{"design_id":"…","inputs":"val"}'     # bit-exact: circuit = integer model = torch
$C prove-equivalence --json '{"design_id":"…"}'                  # every possible input
$C map-to-process  --json '{"design_id":"…","pdk":"sky130"}'     # µm², gate-equivalents, TT tiles
$C evaluate-clinical --json '{"design_id":"…","split":"val"}'    # per window / recording / subject
$C leaderboard
```
Full chain: `scripts/e2e_phase0.sh`.

## How it is built

| Layer | Where | Notes |
|---|---|---|
| IR `chipir/1` | `chiplab/ir/` | 13 integer ops; widths derived by interval arithmetic, so no overflow by construction |
| Verilog-2005 | `chiplab/emit/verilog.py` | weights wired in, canonical-signed-digit shift-adds, explicit sign handling |
| Golden reference | `chiplab/emit/golden.py` | independent naive rendering of the IR, used by the formal proof |
| Synthesis | `chiplab/hw/yosys.py`, `hw/pdk.py` | Yosys 0.71 (OSS CAD Suite); sky130 / gf180 / ihp Liberty |
| Verification | `chiplab/verify/` | 64-way bit-parallel netlist evaluator (numpy or CUDA), ABC equivalence proof |
| Data | `chiplab/data/` | generic recordings → frames → windows; locked subject-level split; encoders = chip boundary |
| Training | `chiplab/train/`, `plugins/families/` | population training: K candidates as one GPU program |
| Referee | `chiplab/referee/` | metrics per window / recording / subject; sealed test set with a budget and an audit log |
| Plugins | `chiplab/plugins/` | datasets, front-ends, model families, simulators: everything task-specific lives here |

The core never names a sensor or disease (a test enforces it). New sensors, datasets, model families and
simulators are plugins; a family is accepted only if its trained model equals its IR bit for bit.

## What is measured (Sat 21 Nov 2026, RTX 3090, CinC 2017 AF vs normal, split by recording)

- Split and windows reproduce the feasibility spike exactly: 16,878 / 3,688 / 3,880 windows.
- 256 candidates trained as one GPU program: about 2,100–2,500 candidates/min (training only).
  One at a time on the GPU is far slower, but that baseline is dominated by kernel launches, so a fair
  CPU-batched baseline is still to be run before quoting a speedup.
- Spike's chip through the new pipeline: 2,206 gates, depth 49 (Yosys 0.71), bit-exact on 200,000 random inputs.
- Formal: gate netlist proved equal to the RTL for every input (ABC cec); a one-gate mutant is caught.

Built before the event: nothing in this folder (the spike it generalises was written on Sat 21 Nov).
