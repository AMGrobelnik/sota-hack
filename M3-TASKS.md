# M3 Max work packages (run in parallel, merge later)

Work for the **M3 Max** that speeds up the ChipIn chip lab **without touching the files the build agent is editing**.
Each package below is independent: run them **at the same time**, one agent (or terminal) per package, each on its own
branch and in its own folder. Merge happens after review.

Written Sat 21 Nov 2026, evening. Code freeze is **Sun 22 Nov 14:45**.

## Context (read first)

- The chip lab lives in `chiplab/` on branch `ant/chip-lab`. Scope: **model in → verified, measured, manufacturable chip out.**
  Data, training and clinical scoring belong to the AI scientist; visuals and the dashboard belong to another agent.
- Read `chiplab/README.md` (overview) and `chiplab/AGENT.md` (every tool: Python call, CLI form, JSON, example).
  Tools you will use: `ingest-model`, `compile-verilog`, `synthesize`, `count-luts`, `map-to-process`, `simulate`,
  `prove-equivalence`, `compose-chip`, `compile-stream`, `rtl-simulate`, `estimate-batch`, `synthesize-batch`,
  `estimate-cost`, `compare-hw-baseline`, `gate-activity`, `chip-report`, and the job tools. Layout, timing/power,
  bitstream and Tiny Tapeout tools land on `ant/chip-lab` later tonight; check `AGENT.md` before using them.
- Install once on the M3 (shared by all packages):
  ```bash
  git clone https://github.com/AMGrobelnik/sota-hack && cd sota-hack && git checkout ant/chip-lab && cd chiplab
  scripts/install.sh            # full install incl. Docker image + PDKs; use --skip-docker --skip-pdk for a fast first pass
  .venv/bin/chiplab doctor      # must report READY (or list exactly what is missing)
  ```
  Give Docker Desktop **at least 12 GB RAM** (Settings → Resources) before layout work.

## Rules (no conflicts)

1. **Never edit** anything under `chiplab/chiplab/`, `chiplab/scripts/`, `chiplab/tests/` (existing files),
   `chiplab/pyproject.toml`, `chiplab/uv.lock`, `README.md`, `AGENT.md`, `EVENTS.md` or `.github/`.
   Those belong to the build agent.
2. Each package writes **only in its own folder** (listed below), on **its own branch** created from the latest
   `ant/chip-lab`:
   ```bash
   git fetch origin && git checkout -b m3/<package> origin/ant/chip-lab
   ```
3. Need a change in the lab's code? Put it in your folder as a patch (`proposed/*.patch`) with a short note.
   The build agent applies it. Do not edit the lab's code yourself.
4. Commit and push your branch often: `git push -u origin m3/<package>`.
5. Heavy runs (layout, proofs) go through the lab's job tools or plain CLI, never `sudo`, never outside the repo.
6. Every number you report says how it was measured (estimate / synthesized / layout / activity) and on what machine.

## Packages (run all five in parallel)

### P1. Apple Silicon install and quick-start validation
- **Branch / folder:** `m3/install-check` → `m3/install-check/`
- **Do:** fresh clone; run `scripts/install.sh` with and without the skip flags; `chiplab doctor`; then every
  quick-start command and every example in `AGENT.md` on the M3.
- **Deliver:** `m3/install-check/REPORT.md`: macOS version, chip, RAM, install time per step, doctor JSON, and a
  pass/fail table per command, with the exact error text for each failure. Fixes go in `proposed/*.patch`.
- **Done when:** every AGENT.md example has a pass/fail result on Apple Silicon.

### P2. Layout runs on all three processes (the heavy compute the build agent skipped)
- **Branch / folder:** `m3/layouts` → `m3/layouts/`
- **Do:** once the layout tool is on `ant/chip-lab`, run timing/power/layout for the fixture designs (the spike
  intnn chip, the torchlogix chip, the 3-head fusion chip) on **sky130A, gf180mcuD and ihp-sg13g2**, one Docker run
  at a time per 12 GB of Docker RAM.
- **Deliver:** `m3/layouts/RESULTS.md` + `results.json` (area µm², GE, cell count, setup slack, power total/leakage,
  run time, LibreLane version), plus the KLayout PNGs. Commit PNGs, not GDS (too big; record the paths instead).
- **Done when:** 3 designs × 3 processes have a result or a recorded failure with its log tail.

### P3. Fair speed benchmark (for the judges' "credible baseline" criterion)
- **Branch / folder:** `m3/bench` → `m3/bench/`
- **Do:** measure designs per hour for the same set of candidate designs:
  (a) one at a time, single process; (b) `synthesize-batch` across all CPU cores; (c) cached re-run;
  (d) `estimate-batch` versus real synthesis (accuracy r², time). Use 50–200 small designs generated from the
  fixtures (vary width, bits, inputs) via `compile-ir` / `ingest-model`.
- **Deliver:** `m3/bench/BENCH.md` + raw CSV: designs/hour per mode, speedup with the fair baseline stated, estimate
  accuracy, machine details. No cherry-picking: report median of 3 runs.
- **Done when:** one honest speedup number with its baseline, and the estimate accuracy, are written down.

### P4. Faster formal proof for large designs (research only)
- **Branch / folder:** `m3/formal` → `m3/formal/`
- **Why:** proving the gate netlist equals the original model (golden proof) times out on the 2.2k-gate spike.
  ABC `cec` (gates = RTL) takes about 30 s.
- **Do:** try alternative recipes on the spike and the 3-head chip: ABC `&cec`/`dsec`, Yosys `equiv_*` passes,
  eqy with partitioning, SymbiYosys with different solvers (bitwuzla, yices, kissat via abc pdr), and splitting by
  output. Time each.
- **Deliver:** `m3/formal/FINDINGS.md`: a table of method → time → proved/timeout → what it proves, plus the
  fastest working script in `m3/formal/scripts/`, and a `proposed/formal.patch` if it should go into the lab.
- **Done when:** a recipe proves the golden equivalence on the spike in under 5 minutes, or a documented
  "not possible tonight, here's why".

### P5. Example model gallery and regression fixtures
- **Branch / folder:** `m3/examples` → `m3/examples/`
- **Do:** build 8–12 small example models covering every supported format and feature: intnn (binary, ternary,
  4-bit), torchlogix, TreeLUT/XGBoost (binary and 3-class), several outputs with AND / OR / k-of-n fusion,
  streaming input. Each comes with test vectors (inputs plus expected outputs) and a one-line description of what
  it represents (generic sensor tasks; no patient data).
- **Deliver:** `m3/examples/<name>/{model.json, vectors.npz, README.md}`, plus `m3/examples/RESULTS.md` with gates,
  GE, LUTs, verification level and TT tiles per example, all produced by the lab's CLI.
- **Done when:** every example goes model → chip bit-exact through the CLI, with its numbers recorded.

## Merge plan

1. Each package opens a pull request `m3/<package> → ant/chip-lab` when done (or pushes its branch and reports).
2. The build agent reviews it, applies any `proposed/*.patch` itself, and merges the folders. The folders don't
   overlap, so merges are clean.
3. Report back to Antonio in one line per package: done / blocked, with the branch name and commit hash.

## Priority if the M3 can only run some at once

P1 (unblocks everything on Mac) → P2 (biggest time saver: heavy layouts) → P3 (judging evidence) → P5 → P4.
