# chipin.space chip lab: events and artefacts

Data only. The lab emits events and files; whoever draws the dashboard or the visuals reads them.

## Event stream
- One JSON object per line in `CHIPLAB_HOME/events/<run_id>.jsonl` (replayable; `seq` increases by 1 per event).
- Pass `run_id` (and optionally `session_id`, `round`) to any tool to have its result appear as events.
- With the optional MCP extra, the same stream is served at `GET /events/<run_id>` (SSE) and `?format=jsonl`.

Envelope on every event: `{type, run_id, session_id, seq, t, round?}`. `t` is seconds since the run's first event.

| type | emitted by | fields |
|---|---|---|
| `candidates_scored` | estimate_batch | `ids[]`, `gates_est[]` (estimates, label in `est_basis`), `kept_ids[]` |
| `chip_compiled` | synthesize, count_luts | `designs: [{id, gates, by_type, depth, transistors_est}]` or `[{id, luts: {xc7 or ice40: n}}]` |
| `check_bitexact` | simulate, prove_equivalence | `design_id, method (simulation or formal:...), vectors_compared, mismatches, passed, verification_level, against?` |
| `hw_metrics` | map_to_process, timing_power, layout | `design_id, pdk, area_um2, ge?, core_mm2?, die_mm2?, timing_ws_ns?, power_uw?, power_basis?, energy_per_decision_pj?, basis (liberty-synth or librelane-layout)` |
| `gate_activity` | gate_activity | `design_id, wire_toggle {net id: toggle rate}` (top nets; the full map is in gate_activity.json) |
| `layout_ready` | layout, timing_power | `design_id, pdk, png_url, gds_url, metrics` |
| `bitstream_ready` | bitstream | `design_id, path, luts` |
| `tt_package_ready` | tt_package | `design_id, path, tiles` |
| `report_ready` | chip_report | `design_id, report_md, verilog_url, netlist_json_url, schematic_svg_url (null), layout_png_url, digest` |
| `cost` | every tool | `design_id, tool, wall_s, cpu_s_host` (compute only) |

The AI scientist's own events (run_started, check_heldout, ...) can share the same file and envelope; the lab never
writes clinical numbers into events.

## ChipIn dashboard (`./progress`)
When the working folder holds ChipIn's `./progress` helper, every tool also reports through it (metric, status and
artifact lines; the lab runs the helper, so the backend validates every line). The dashboard keeps one value per
metric key and has no chip id, so the lab never lets two chips share the panel:

- **Exploring (every call):** only `gates` (the chip just synthesised), `candidates` (distinct chips under
  `./chips/`), the run's cumulative `vectors_checked` (each distinct check counted once) and `mismatches`: the sum
  over chips of each chip's latest result per check kind (simulate with your vectors, simulate random, rtl-simulate,
  submit-verilog), so a corrected re-run replaces a failed one and 0 means every chip's latest checks passed. Every
  other figure of a chip goes to `./chips/<design_id>/metrics.json` and to a status line
  (`ChipIn measured chip <id>: ...`).
- **Reporting (`chip-report`, or `report_metrics: true` on any call):** the full figure set of that one chip in one
  burst: `gates, depth, transistors, luts_ice40, luts_xc7, area_um2, ge, tt_tiles, cost_eur, verification_level,
  timing_slack_ns, fmax_mhz, energy_pj, leakage_uw, power_uw_at_rate` (whichever exist; synthesis, sky130 mapping and
  cost are filled in first when missing, layout and LUT counts only if they were already run). After a report,
  `gates` of other chips stays in status lines until the next report, so the panel shows one chip.
- Run counters live in `./chips/.chiplab-progress.json`. A tool called from inside another tool (timing-power runs
  layout) reports once.

`./chips/<design_id>/metrics.json`: `{design_id, metrics: {key: {value, unit, from (tool), at}}}`; units are
`chiplab.progress.METRIC_KEYS` (depth in `levels`). Full contract: docs/CHIPIN_INTEGRATION.md.

**Chip id on metrics (optional, off until the backend enables it).** With `CHIPIN_PROGRESS_CHIP=1` in the
environment, every chip figure is sent as `./progress metric <key> <number> <unit> --chip <design_id>` (run counters
`candidates`, `vectors_checked`, `mismatches` never carry a chip). Today's helper rejects a fourth argument, so
without the variable the lines are exactly `./progress metric <key> <number> <unit>`.

## Artefacts per design: `CHIPLAB_HOME/designs/<design_id>/`
| file | format |
|---|---|
| `ir.json` | chipir/1 (the integer model; see chiplab/ir/schema.py) |
| `design.v` | Verilog-2005, combinational core, weights as constants |
| `port.json` | `{top, inputs: [{name, lanes, bits, signed}], outputs: [...]}`; lane i of a port sits at bits `[i*bits, (i+1)*bits)` |
| `synth/net.json`, `synth/gates.v` | Yosys JSON netlist and gate-level Verilog (simple gates) |
| `synth.json`, `luts_xc7.json`, `luts_ice40.json`, `pdk_<pdk>.json` | metrics as returned by the tools |
| `simulate_<inputs>.json`, `formal.json`, `rtlsim.json` | verification evidence (read by the ladder) |
| `stream_tt.v`, `stream.v` | streaming wrappers (Tiny Tapeout top `tt_um_chipin_<id>`, generic top) |
| `gate_activity.json` | `{toggle_rate: {net: r}, ones: {net: f}, cells: [{type, inputs, output}], steps}` |
| `ports.vcd` | port waveforms over the given vectors (optional) |
| `layout_<pdk>/...` | LibreLane run: `final/metrics.json`, GDS, KLayout PNG (flow outputs) |
| `report.md`, `cost.json` | chip report and manufacturing routes |

Job table: `CHIPLAB_HOME/jobs/jobs.db` (SQLite). Run log of every tool call: `CHIPLAB_HOME/log.jsonl`.
