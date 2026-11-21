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
