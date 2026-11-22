## Headline

One real ChipIn run (Claude agent `claude-opus-5-5`, preset `pro`, local runner) on `backend/examples/seizure_eeg_prompt.md` plus section 6 of `chiplab/docs/CHIPIN_INTEGRATION.md` called the chip lab's tools and finished `succeeded` in 17 min 50 s for $1.42.

- **compile** (started, then done): the lab compiled three seizure classifiers and a line-length front-end.
- **verify** (started, then done): every netlist was bit-exact on 256 of the agent's own vectors and 100,000 random vectors, and was formally proved equal to the lab's golden model (verification level 2).
- **report**: sky130 layouts. Power at one decision per second is under 0.05 uW for each classifier.

**The weights are random placeholders.** No model was trained, on any data, and there are no detection figures: the prompt attaches no recordings. These are real circuits of untrained networks, not seizure detectors.

## How it was measured

- Lab `5b15d6c` (tip of `ant/chip-lab` at run time); backend `amg/backend-chiplab` at `cb4eaa0`. Run id `20261122-001507-0ef5bb`.
- The lab came from the existing project-folder install, with nothing in the real home folder. `CHIPIN_CHIPLAB_BIN` pointed at the installer's `chiplab` launcher folder; `CHIPLAB_USER_DIR` and `CHIPLAB_CONFIG` pointed at the install.
- Doctor: `chiplab doctor` inside the backend's real agent environment (`build_agent_env()`) is READY; only the optional `python:mcp` is missing. `chiplab doctor --agent-env` is NOT READY by design: it strips `CHIPLAB_*` and looks for `~/.config/chiplab`, which does not exist here.
- Every number below comes from `m3/e2e/run/events.jsonl`. The lab bridge sent all metrics except one the agent typed (`candidates 3`). Exit codes come from the agent's transcript and the raw lab answers in `run/workspace/lab/`.
- The lab's own `tests/test_chipin_integration.py` passed at `5b15d6c` (1 passed). That test exercises `origin/amg/backend`.
- Backend suite at `cb4eaa0`: 260 passed, 2 skipped. Ruff is clean.

| Design | gates | alkaid gates | LUT4 | GE | placed um2 | slack ns | uW at rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A feature MLP `67301286c5e3` | 2867 | 2367 | 1079 | 5339.7 | 22016.1 | -1.354 | 0.04986 |
| B envelope CNN `28fba9730991` | 3454 | 2607 | 1147 | 5138.7 | 23147.2 | -0.670 | 0.049067 |
| C ternary MLP `94090842ebae` | 1356 | 1279 | 513 | 2424.3 | 11803.8 | -0.850 | 0.026858 |
| F line-length step `e05449cf23de` | 396 | - | 156 | 643.3 | 5113.65 | 6.822 | 0.011049 |

The placed area, slack and power columns are for the alkaid designs (A, B and C) at 1 decision/s, and for F at 256/s. The clock is 20 ns.

- **Lab call exit codes.** `compile-ir`, `synthesize`, `count-luts`, `map-to-process`, `prove-equivalence`, `verification-level` and `timing-power` all exited 0.
- **The one exit 2 was the agent's mistake.** F's first vector check returned 512 mismatches because the agent's expected file held only lane 0 of a 2-lane output. The agent fixed the file and the re-run exited 0. No lab tool failed, so there is no patch under `proposed/`.
- **Chip files.** The run reported 36 artifacts under `workspace/chips/`, and all 36 exist on disk: Verilog, gate netlists, `ir.json`, and four layout PNG plus GDS pairs. Files of 1 MB or less are copied here under `m3/e2e/run/workspace/chips/`. Left out: the four GDS files (1.1 to 4.6 MB) and four `net.json` files over 1 MB.
- **Masking.** The copied events, run record and doctor answers have the home path replaced with `~`. They were checked for key and token patterns.

## What is open

- `m3/e2e/REPORT.md` is not in this PR yet. The agent that ran this could not write it; its content is this description, and it follows in a commit on this branch.
- **A trained model.** Train on a public EEG set (for example CHB-MIT) on a machine whose agent `python3` has numpy or torch; this one had neither. Ingest the weights with `ingest-model` and score the netlist on held-out patients.
- **Untouched lab tools.** The run never called `rtl-simulate`, `chip-report`, `tt-package`, `bitstream`, `estimate-cost` or `layout`, so it reported no `cost_eur`, `fmax_mhz` or `luts_xc7`. The `reference` and `finetune` stages were skipped (no recordings).
- **Timing.** The three classifiers miss the 20 ns clock by 0.67 to 1.35 ns. That does not matter at 1 decision/s, but no slower clock was tried.
- **Doctor with a non-default install.** `chiplab doctor --agent-env` cannot say READY for an install outside the default home paths, even though the backend passes `CHIPLAB_*` through.
- **Speed.** About 18 minutes end to end, about 10 of them for four sequential layouts.
- **The dashboard path.** This run used `chipin-backend run`; `serve` was not exercised.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
