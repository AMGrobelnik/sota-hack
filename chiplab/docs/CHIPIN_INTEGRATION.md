# ChipIn integration: the chip lab inside the AI scientist's run

This page is for Adrian (the AI scientist and backend) and Antonio. It explains how the chip lab shows up on the
ChipIn dashboard when the AI scientist calls it, without anyone editing the backend.

The short version:
- The AI scientist runs in `runs/<run_id>/workspace/`, and the dashboard only sees what goes through the
  `./progress` helper in that folder.
- When a lab tool runs in that folder, the lab calls `./progress` itself: status lines, measured numbers, and
  the chip files it made.
- The dashboard shows one chip's figures at a time: while the agent explores, only the headline `gates` and run
  counters change; `chip-report` on the chosen chip sends that chip's full set (section 2).
- The agent keeps owning the stages.

## 1. How the bridge works

- **Detection.** Every lab tool (CLI `chiplab <tool>` or Python `chiplab.api`) looks in the current working
  folder for an executable `./progress`. If that file is the ChipIn helper (its source says "ChipIn progress
  helper"), the lab reports through it. Anywhere else, the lab behaves exactly as before.
- **How it reports.** The lab runs the helper as a program, exactly as the agent would:
  - `./progress status "ChipIn is synthesising chip 765fa47586bd"` before a heavy tool starts;
  - `./progress metric gates 2285 gates` for every number the tool measured;
  - `./progress artifact chips/765fa47586bd/design.v file` for every file it put in the workspace.

  The lab never writes `progress.jsonl` itself, so the backend's own checks apply to every line: the helper
  rejects bad arguments, and the tailer rejects bad lines.
- **Stages stay with the agent.** By default the lab sends no `stage` lines. The agent marks
  `./progress stage compile started` / `done` around its calls. A tool can do it instead with
  `progress_stages: true` (see section 3).
- **Controls.** Every tool accepts `progress`:
  - `"auto"`: the default, reports when a ChipIn helper is found;
  - `"off"`: never reports;
  - a path to a helper: always reports through that one.

  `"progress": "off"` in `~/.config/chiplab/config.json` turns it off for the whole machine.
- **Never fatal.** If reporting fails (the helper is missing, it rejects a line, or it times out), the lab logs
  it and the tool's own answer and exit code are unchanged.

## 2. Metrics the lab reports

Numbers only, snake_case keys, each with a unit. The table is exported as `chiplab.progress.METRIC_KEYS`.

### One chip on the panel

The dashboard keeps one value per key (the last one wins) and has no chip id. If every tool sent every number, the
panel would mix chips: in the M3 run (20261122-001507-0ef5bb) the final `gates` came from one classifier and the
area, slack and power from the front-end. So the lab sends two kinds of metrics:

- **While exploring (every call):** only the run keys below: `gates` of the chip just synthesised (keeps the
  headline live), `candidates` (distinct chips under `./chips/`) and the run's cumulative `vectors_checked` and
  `mismatches` (the same check repeated counts once). Every other number goes to
  `./chips/<design_id>/metrics.json` and to a status line such as
  `ChipIn measured chip 94090842ebae-alk: 11,804 um2, slack +29.15 ns, fmax 48.0 MHz, ...`.
- **Without a report** the run still ends consistent: fewer numbers on the panel (`gates` of the latest chip and
  the run counters), never two chips mixed. That is what the M3 run gives today, since it never called
  `chip-report`.
- **When reporting a chip:** `chip-report`, or `"report_metrics": true` on any tool call, sends that chip's full
  figure set in one burst, `gates` included. Missing cheap figures are made first (synthesis, sky130 cell mapping,
  cost: seconds). Layout, LUT counts and the bitstream are used only if the agent already ran them. After a
  report, `gates` from other chips stays in status lines until the next report, so the panel always shows one chip.

A report can't remove keys an earlier report sent. If chip B is reported after chip A, and A had a layout but B
doesn't, the timing and power keys still show A until B is laid out. Run `timing-power` on B before reporting it.

| Key | Unit | Sent | Measured by | Basis |
|---|---|---|---|---|
| `gates` | gates | exploring + report | synthesize | synthesized (Yosys, simple 2-input gates) |
| `candidates` | designs | exploring | any tool that puts a chip under `./chips/` | count of distinct chips this run |
| `vectors_checked` | vectors | exploring | simulate, rtl-simulate, submit-verilog | measured, cumulative over the run |
| `mismatches` | vectors | exploring | simulate, rtl-simulate, submit-verilog | measured, cumulative (0 means every check was bit-exact) |
| `depth` | levels | report | synthesize | synthesized (logic levels on the longest path) |
| `transistors` | transistors | report | synthesize | estimate (Yosys CMOS cost model) |
| `luts_ice40` | LUT4 | report | count-luts (ice40), bitstream | synthesized (iCE40UP5K) |
| `luts_xc7` | LUT6 | report | count-luts (xc7) | synthesized (AMD 7-series 6-input LUTs) |
| `area_um2` | um2 | report | map-to-process; layout | sky130 after place and route if laid out, else synthesized onto sky130 cells |
| `ge` | GE | report | map-to-process | synthesized (area divided by one NAND2 cell) |
| `tt_tiles` | tiles | report | map-to-process, estimate-cost, tt-package | the tiles the Tiny Tapeout price is for |
| `cost_eur` | EUR | report | estimate-cost | price list, checked 21 Nov 2026 (Tiny Tapeout route) |
| `verification_level` | level | report | the chip's own checks | 0 to 5, see AGENT.md |
| `timing_slack_ns` | ns | report | layout, timing-power | layout (static timing at the chosen clock; default 50 ns) |
| `fmax_mhz` | MHz | report | layout, timing-power; bitstream | 1000 / critical path after layout; else iCE40 place and route |
| `energy_pj` | pJ | report | layout, timing-power | layout, vectorless (energy per decision) |
| `leakage_uw` | uW | report | layout, timing-power | layout (standby power) |
| `power_uw_at_rate` | uW | report | layout, timing-power, chip-report (with `decision_rate_hz`) | energy_pj × rate × 1e-6 + leakage_uw: the number for battery life |

`./chips/<design_id>/metrics.json` holds every figure measured for that chip:
`{design_id, metrics: {key: {value, unit, from, at}}}`. It is reported once as a `file` artifact when it is created.
The run counters are in `./chips/.chiplab-progress.json`.

A tool that runs another tool inside it (`timing-power` runs `layout`) reports once.

### Chip id on metrics (optional, off until the backend enables it)

Proposed contract for the backend: `./progress metric <key> <number> [unit] --chip <design_id>` becomes an event
with a `chip` field. The lab adds `--chip <design_id>` to every chip figure only when `CHIPIN_PROGRESS_CHIP=1` is
in its environment. The run counters (`candidates`, `vectors_checked`, `mismatches`) never carry a chip. Today's
helper rejects a fourth metric argument and the tailer keeps only key, value and unit, so the lab sends exactly
today's lines without the variable. To turn it on:
1. the helper accepts `--chip`;
2. the tailer keeps `chip`;
3. the backend puts `CHIPIN_PROGRESS_CHIP=1` into the agent's environment. It isn't on the allowlist, so it has to
   be set explicitly, e.g. in `AGENT_ENV_FORCED` or `chiplab_env()`.

`tests/test_progress_one_chip.py` tests both paths.

## 3. Stage mapping

The dashboard's stages are spec, reference, propose, finetune, compile, verify and report. The lab is the
compile and verify stages, and part of report.

| Stage | Lab tools |
|---|---|
| propose | estimate-batch (rank candidates by estimated gates; status line only) |
| compile | ingest-model, compile-ir, synthesize, count-luts, map-to-process |
| verify | simulate, prove-equivalence, prove-sequential, rtl-simulate, verification-level |
| report | chip-report, layout, timing-power, tt-package, bitstream, estimate-cost |

With `progress_stages: true` on a call, the lab marks that tool's stage `started` before it runs and `done`
after a successful run. That is for agents that don't want to manage stages themselves. Normally the agent
marks the stage once around a group of calls.

## 4. Environment: why it works inside the agent's sandbox

The backend starts the agent with an allowlisted environment (`agents/env.py`): `HOME`, `PATH`, `VIRTUAL_ENV`,
`PYTHONPATH`, `TMPDIR`, `LANG` and similar. Of the lab's variables it passes only `CHIPLAB_CONFIG` and
`CHIPLAB_USER_DIR` (for an install outside the default paths), and it puts `CHIPIN_CHIPLAB_BIN` first on `PATH`
(`chipin_backend/chiplab.py`). Everything else is stripped, including `CHIPLAB_HOME`, `DOCKER_HOST` and `PDK_ROOT`.
The lab therefore never depends on those:

- **Config file.** `scripts/install.sh` writes `~/.config/chiplab/config.json`, with absolute paths to the
  OSS CAD Suite tools, the PDKs, the Tiny Tapeout tools, the LibreLane image and the Docker socket. The lab
  reads it from `HOME`, which the agent keeps.
- **Docker.** The lab finds the daemon by itself: the Docker CLI's current context, then the colima, OrbStack,
  Docker Desktop and Rancher sockets.
- **Launcher.** `install.sh` puts a `chiplab` launcher in `~/.local/bin`, so the agent can call `chiplab` by
  name.
- **Check it.** `chiplab doctor --agent-env` re-runs every check under the same rule: the allowlist, plus
  `CHIPLAB_CONFIG` / `CHIPLAB_USER_DIR` when set and `CHIPIN_CHIPLAB_BIN` on `PATH`, with every other variable
  removed. Its `agent_env.chiplab_vars_kept` says which lab variables it kept. It must report READY on the machine
  that runs the agents.

## 5. Where the chip files go

In a ChipIn workspace, each design's files are copied into `./chips/<design_id>/`:
- the Verilog;
- the gate netlist (JSON);
- `report.md`;
- the layout image and GDS;
- the iCE40 bitstream;
- the Tiny Tapeout project, without its `tt/` tool copy or run folders.

Each file is reported as an artifact with a workspace-relative path. The dashboard lists it as
`workspace/chips/<design_id>/...`.

| Artifact kind | Files |
|---|---|
| `report` | the chip report (`report.md` from chip-report) |
| `chip` | layout PNG and GDS, bitstream, Tiny Tapeout package |
| `file` | everything else (Verilog, netlist JSON, ...) |

The lab's own working copy stays in its home folder (`runs/designs/<design_id>/`); the workspace gets copies.

## 6. Paragraph for the AI scientist's instructions (ready to paste)

> **Chip lab (compile, verify and the chip part of report).** The `chiplab` command turns your trained model into
> a verified, measured chip. Its full reference is `chiplab/AGENT.md` in the sota-hack repository, or run
> `chiplab agent-doc`. Every tool takes JSON (`chiplab <tool> --json '{...}'`) and prints one JSON answer.
> If `chiplab` is not found (exit 127), call it by its full path: `~/.local/bin/chiplab`.
> Exit codes: 0 ok, 1 error (read `error`), 2 a check ran and the design failed it (e.g. not bit-exact), 3 timeout.
> - **compile**: `ingest-model` (or `compile-ir`) to bring in your model, then `synthesize`, `count-luts` and
>   `map-to-process`.
> - **verify**: `simulate` (pass your own test vectors and expected outputs), `prove-equivalence`,
>   `rtl-simulate`, and `verification-level`.
> - **report**: `chip-report`, `layout` / `timing-power` (pass `decision_rate_hz` = how often the chip decides,
>   for the battery-relevant power), `tt-package`, `bitstream`, `estimate-cost`.
> Before you mark report done, call `chiplab chip-report --json '{"design_id": "<the chip you chose>", "decision_rate_hz": <decisions per second>}'` on the one chip you chose: the chip figures the user sees (area, power, energy, cost, verification) come from that call.
>
> Run these from your working folder. The lab reports its own metrics, status lines and chip files through
> `./progress`, so do not repeat those numbers. Do mark the stages yourself:
> `./progress stage compile started` before the compile calls and `./progress stage compile done` after them,
> and the same for `verify`. Alternatively, pass `"progress_stages": true` to a tool call. If a lab tool fails,
> report the stage as skipped with the reason instead of done.

## 7. How this is tested

`tests/test_chipin_integration.py` runs against the backend's real code, read-only from `origin/amg/backend`;
it skips if that branch can't be fetched:
1. It writes the real `./progress` helper (`write_helper`) into a workspace.
2. It runs lab tools from that workspace under the real agent environment (`build_agent_env`).
3. It feeds the resulting `progress.jsonl` through the real `ProgressTailer` and `EventLog`.
4. It checks that every line became an event, metrics use the keys above, files landed under
   `workspace/chips/`, and stage events appear only where `progress_stages` was set.

`tests/test_progress_one_chip.py` replays the M3 run's call sequence (A, B, C, each also `-alk`, and the front-end
F; compile, synthesize, count-luts, map-to-process, simulate, prove-equivalence, verification-level, timing-power)
through a stand-in `./progress` with the same command-line contract. It checks that the final panel holds one chip's
figures, before and after a `chip-report`. LibreLane is replaced by the critical paths and power the M3 run
measured, so the test needs no Docker.
