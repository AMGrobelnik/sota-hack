# ChipIn integration: the chip lab inside the AI scientist's run

This page is for Adrian (the AI scientist and backend) and Antonio. It explains how the chip lab shows up on the
ChipIn dashboard when the AI scientist calls it, without anyone editing the backend.

The short version:
- The AI scientist runs in `runs/<run_id>/workspace/`, and the dashboard only sees what goes through the
  `./progress` helper in that folder.
- When a lab tool runs in that folder, the lab calls `./progress` itself: status lines, measured numbers, and
  the chip files it made.
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

| Key | Unit | Reported by | Basis |
|---|---|---|---|
| `gates` | gates | synthesize | synthesized (Yosys, simple 2-input gates) |
| `depth` | gates | synthesize | synthesized (longest path) |
| `transistors` | transistors | synthesize | estimate (Yosys CMOS cost model) |
| `luts_ice40` | LUT4 | count-luts (ice40), bitstream | synthesized (iCE40UP5K) |
| `luts_xc7` | LUT6 | count-luts (xc7) | synthesized (AMD 7-series 6-input LUTs) |
| `area_um2` | um2 | map-to-process; layout | synthesized onto the process's cells (map-to-process), or after place and route (layout) |
| `ge` | GE | map-to-process | synthesized (area divided by one NAND2 cell) |
| `tt_tiles` | tiles | map-to-process, tt-package | estimate (sky130 area at 60% utilisation), or the tiles tt-package picked |
| `cost_eur` | EUR | estimate-cost | price list, checked 21 Nov 2026 (Tiny Tapeout route) |
| `vectors_checked` | vectors | simulate, rtl-simulate | measured (bit-exact comparison) |
| `mismatches` | vectors | simulate, rtl-simulate | measured (0 means bit-exact) |
| `verification_level` | level | prove-equivalence, rtl-simulate, verification-level | 0 to 4, see AGENT.md |
| `timing_slack_ns` | ns | layout, timing-power | layout (static timing at the chosen clock) |
| `fmax_mhz` | MHz | bitstream | FPGA place and route (nextpnr) |
| `energy_pj` | pJ | layout, timing-power | layout, vectorless power (energy per decision at the clock rate) |
| `leakage_uw` | uW | layout, timing-power | layout (standby power) |
| `power_uw_at_rate` | uW | layout, timing-power, chip-report (with `decision_rate_hz`) | energy_pj × rate × 1e-6 + leakage_uw: the number for battery life |
| `candidates` | designs | estimate-batch and the batch tools | count |
| `best_gates` | gates | estimate-batch | estimate (fast pre-synthesis estimate); real synthesis reports `gates` |

Batch tools report only `candidates` and `best_gates`, not one metric per design.

## 3. Stage mapping

The dashboard's stages are spec, reference, propose, finetune, compile, verify and report. The lab is the
compile and verify stages, and part of report.

| Stage | Lab tools |
|---|---|
| propose | estimate-batch (rank candidates by estimated gates) |
| compile | ingest-model, compile-ir, synthesize, count-luts, map-to-process |
| verify | simulate, prove-equivalence, prove-sequential, rtl-simulate, verification-level |
| report | chip-report, layout, timing-power, tt-package, bitstream, estimate-cost |

With `progress_stages: true` on a call, the lab marks that tool's stage `started` before it runs and `done`
after a successful run. That is for agents that don't want to manage stages themselves. Normally the agent
marks the stage once around a group of calls.

## 4. Environment: why it works inside the agent's sandbox

The backend starts the agent with an allowlisted environment (`agents/env.py`): `HOME`, `PATH`, `VIRTUAL_ENV`,
`PYTHONPATH`, `TMPDIR`, `LANG` and similar. It strips everything else, including `CHIPLAB_*`, `DOCKER_HOST` and
`PDK_ROOT`. The lab therefore never depends on those variables:

- **Config file.** `scripts/install.sh` writes `~/.config/chiplab/config.json`, with absolute paths to the
  OSS CAD Suite tools, the PDKs, the Tiny Tapeout tools, the LibreLane image and the Docker socket. The lab
  reads it from `HOME`, which the agent keeps.
- **Docker.** The lab finds the daemon by itself: the Docker CLI's current context, then the colima, OrbStack,
  Docker Desktop and Rancher sockets.
- **Launcher.** `install.sh` puts a `chiplab` launcher in `~/.local/bin`, so the agent can call `chiplab` by
  name.
- **Check it.** `chiplab doctor --agent-env` re-runs every check under the same allowlist, with every other
  variable removed. It must report READY on the machine that runs the agents.

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
