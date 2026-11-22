"""Generate AGENT.md (the interface doc for AI scientists) and EVENTS.md (event and artefact formats) from the
live tool registry, so the docs never drift from the code: `chiplab agent-doc --write`."""
from __future__ import annotations

import inspect
import json
import typing

from chiplab import config

SPIKE = "765fa47586bd"     # design id of fixtures/spike_best.json after `ingest-model` (deterministic on every machine)
TINY = "ed8e52cb7a11"      # design id of the `compile-ir` example below
ADD_IR = {"ir": "chipir/1", "name": "xx", "inputs": [{"name": "x", "lanes": 1, "bits": 4, "signed": False}],
          "nodes": [{"id": "s", "op": "add", "a": "x", "b": "x"}], "outputs": [{"name": "y", "src": "s"}], "meta": {}}
# Every example runs as written (tests/test_agent_examples.py), in this order, after the two that create designs.
EXAMPLES = {
    "ingest_model": {"format": "intnn", "model": "@fixtures/spike_best.json", "name": "spike"},
    "compile_ir": {"ir": {"ir": "chipir/1", "name": "tiny", "inputs": [{"name": "x", "lanes": 4, "bits": 4, "signed": False}],
                          "nodes": [{"id": "s", "op": "matvec", "src": "x", "W": [[1, -1, 2, 0]], "b": [-3]},
                                    {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}],
                          "outputs": [{"name": "y", "src": "y"}], "meta": {}}},
    "synthesize": {"design_id": SPIKE},
    "simulate": {"design_id": SPIKE, "inputs": "random", "n": 100000},
    "prove_equivalence": {"design_id": SPIKE},
    "map_to_process": {"design_id": SPIKE, "pdk": "sky130"},
    "count_luts": {"design_id": SPIKE, "family": "ice40"},
    "compose_chip": {"heads": {"a": SPIKE, "b": TINY}, "fusion": [{"name": "alarm", "op": "and", "inputs": ["a_y", "b_y"]}],
                     "shared_inputs": False},
    "compile_stream": {"design_id": SPIKE, "tt": True},
    "rtl_simulate": {"design_id": SPIKE, "n": 300},
    "prove_sequential": {"design_id": SPIKE, "timeout": 300},
    "estimate_batch": {"designs": [SPIKE, TINY], "keep": 1},
    "gate_activity": {"design_id": SPIKE, "n": 2000, "vcd": True},
    "estimate_cost": {"design_id": SPIKE},
    "compare_hw_baseline": {"design_id": SPIKE, "task": "af_vs_normal", "dataset": "AFDB", "protocol": "record-level, per paper"},
    "verification_level": {"design_id": SPIKE},
    "chip_report": {"design_id": SPIKE},
    "bitstream": {"design_id": SPIKE},
    "layout": {"design_id": TINY, "pdk": "sky130"},
    "timing_power": {"design_id": TINY, "pdk": "sky130", "decision_rate_hz": 1},
    "tt_package": {"design_id": TINY, "harden": False},
    "tt_readiness": {"design_id": TINY, "run_tests": True},
    "tt_export": {"design_id": TINY, "mode": "standalone"},
    "submit_verilog": {"verilog": "module xx(input [3:0] x, output [4:0] y); assign y = x + x; endmodule", "top": "xx",
                       "port_spec": {"inputs": [{"name": "x", "lanes": 1, "bits": 4, "signed": False}],
                                     "outputs": [{"name": "y", "lanes": 1, "bits": 5, "signed": False}]},
                       "reference_ir": ADD_IR},
    "submit_job": {"tool": "map_to_process", "args": {"design_id": SPIKE, "pdk": "sky130"}, "session_id": "agent-A"},
    "job_status": {"job_id": "@job_id"},
    "job_result": {"job_id": "@job_id"},
    "cache_stats": {},
}
# What each example needs beyond yosys/iverilog/verilator (tests skip when it is missing).
REQUIRES = {"map_to_process": ["pdk"], "layout": ["docker", "pdk"], "timing_power": ["docker", "pdk"],
            "tt_package": ["tt"], "tt_readiness": ["tt"], "tt_export": ["tt"], "submit_verilog": ["docker"],
            "submit_job": ["pdk"], "chip_report": [], "bitstream": ["ice40"]}


def example_cli(name: str, ex: dict) -> str:
    """The example as a shell command. '@file' values are inlined with $(cat ...); '@job_id' is the job id that
    submit-job printed."""
    if name == "ingest_model":
        return ("chiplab ingest-model --json \"{\\\"format\\\": \\\"intnn\\\", \\\"model\\\": "
                "$(cat fixtures/spike_best.json), \\\"name\\\": \\\"spike\\\"}\"")
    return f"chiplab {name.replace('_', '-')} --json '{json.dumps(ex)}'"


def _schema(t) -> dict:
    o = typing.get_origin(t)
    if t is typing.Any or t is inspect.Parameter.empty:
        return {}
    if o is typing.Union or str(o) == "<class 'types.UnionType'>":
        args = [a for a in typing.get_args(t) if a is not type(None)]
        return _schema(args[0]) if len(args) == 1 else {"anyOf": [_schema(a) for a in args]}
    base = o or t
    return {str: {"type": "string"}, int: {"type": "integer"}, float: {"type": "number"}, bool: {"type": "boolean"},
            dict: {"type": "object"}, list: {"type": "array"}}.get(base, {})


def tool_schema(fn) -> dict:
    hints = typing.get_type_hints(fn)
    props, req = {}, []
    for p in inspect.signature(fn).parameters.values():
        s = _schema(hints.get(p.name, typing.Any))
        if p.default is not inspect.Parameter.empty:
            s = {**s, "default": p.default}
        else:
            req.append(p.name)
        props[p.name] = s
    for c in ("run_id", "session_id"):
        props.setdefault(c, {"type": "string"})
    props.setdefault("round", {"type": "integer"})
    props.setdefault("force", {"type": "boolean", "default": False})
    return {"type": "object", "properties": props, "required": req}


QUICKSTART = """## Quick start (any machine: Apple Silicon Mac or Linux)

```bash
git clone https://github.com/AMGrobelnik/sota-hack && cd sota-hack/chiplab
scripts/install.sh                      # add --skip-docker / --skip-pdk to defer the big downloads
.venv/bin/chiplab doctor                # every check green = ready; otherwise it prints the fix
.venv/bin/chiplab ingest-model --json "{\\"format\\": \\"intnn\\", \\"model\\": $(cat fixtures/spike_best.json)}"
.venv/bin/chiplab synthesize --json '{"design_id": "<design_id from the line above>"}'
```
Then `simulate` (bit-exact), `prove-equivalence` (formal), `map-to-process` (area), `timing-power` / `layout`,
`bitstream`, `tt-package`, `chip-report`. Python: `import chiplab.api as lab; lab.synthesize(design_id=...)`.

Support: Apple Silicon (M1–M4) and Linux x86_64/arm64 are supported; Intel Macs use the darwin-x64 tool build and
should work but are untested. Heavy hardware steps (LibreLane layout, Tiny Tapeout harden) need Docker; GF180 and
IHP layouts are supported by the same flow but validated on sky130 only. The Tiny Tapeout harden can also run in
GitHub's cloud: commit the folder from `tt-package` and run the `tt-gds` workflow.
"""


def agent_md() -> str:
    from chiplab.api import TOOLS
    from chiplab.tools_hw import CHIP_REPORT_SENTENCE
    out = ["# chipin.space chip lab: interface for AI scientists", "",
           "The lab turns a trained model into a verified, measured, manufacturable chip. You (the AI scientist) bring the "
           "data, the training and the clinical judgement; the lab compiles, synthesises, verifies, measures and "
           "packages, and reports every number with its basis. Generated from the tool registry; do not edit by hand "
           "(`chiplab agent-doc --write`).", "", QUICKSTART,
           "## How to call a tool", "",
           "- CLI: `chiplab <tool-name> --json '{...}'` (or `--json-file f.json`, or JSON on stdin) prints one JSON object; "
           "exit code 0 when `status` is `ok`.",
           "- Python: `import chiplab.api as lab; lab.<tool_name>(**args)` returns the same dict.",
           "- Async (several agents at once): `submit-job {tool, args, session_id}` returns a `job_id`; poll `job-status` / "
           "`job-result`. Lanes are sized to the machine: cpu = cores - 1, gpu = 1, docker = Docker memory / 12 GB (1-4); "
           "override with CHIPLAB_CPU_WORKERS / CHIPLAB_GPU_WORKERS / CHIPLAB_DOCKER_WORKERS (or \"lanes\" in the config "
           "file); `chiplab doctor` shows what it picked. Start workers with `chiplab workers`. Results are "
           "cached by content, so duplicate designs return instantly (`cached: true`).",
           "- Every tool also accepts `run_id`, `session_id`, `round` (events, see EVENTS.md) and `force` (skip the cache).",
           "- In a ChipIn run (a `./progress` helper in the working folder) every tool reports to the dashboard by "
           "itself; see EVENTS.md, \"ChipIn dashboard\". While you explore, the dashboard shows only `gates` of the "
           "latest chip and the run's counters, never a mix of chips. " + CHIP_REPORT_SENTENCE + " `report_metrics: true` "
           "on any call does the same for that call's design.",
           "- Timing: `layout` / `timing-power` default to a 50 ns clock (20 MHz; 100 ns on gf180), which closes for "
           "chips of a few thousand gates; every answer also gives `fmax_mhz`, the fastest clock the chip meets.",
           "- Status and exit code are honest: `ok` = 0 (the tool did its job and every check it ran passed), `error` = 1 "
           "(it could not do its job; see `error`), `fail` = 2 (it ran, and the design failed a check, e.g. "
           "`bit_exact: false`), `timeout` = 3. A queued job is `ok` with `state: queued`.",
           "- Proof sizes: `prove-equivalence` (gates = RTL) takes about a second at a few thousand gates; with "
           "`golden: true` it also proves the RTL against an independent golden model of the IR in one miter (spike, "
           "2.3k gates: about 7 s). `prove-sequential` is compositional (the core is a black box, proven by "
           "prove-equivalence), so it proves the clocked wrapper in seconds at any model size; `whole: true` proves "
           "the flattened design and is only practical for a few hundred gates.",
           "- Safety: `submit-verilog` runs lint/synthesis only inside the sandbox container unless you pass "
           "`allow_host: true`; `ingest-model` with `format: torchlogix` loads a pickle and needs `trusted: true` (and "
           "`CHIPLAB_ALLOW_PICKLE=1` when called through the optional network server). XGBoost models are converted in a "
           "separate process.",
           "- Verification levels: 1 bit-exact simulation, 2 formal proof, 3 streaming RTL simulation (cocotb + Icarus) + "
           "lint, 4 Tiny Tapeout gate-level test after layout, 5 real hardware (never set automatically).", "",
           "## Tools", ""]
    extras = ["define_task", "load_data", "propose_designs", "train_batch", "evaluate_clinical", "leaderboard", "events", "plugins"]
    core = [n for n in TOOLS if n not in extras]
    order = core + ["__extras__"] + [n for n in extras if n in TOOLS]
    for name in order:
        if name == "__extras__":
            out += ["## Optional extras: data and training", "",
                    "Not needed for model -> chip. The AI scientist normally brings its own data, training and clinical "
                    "scoring; these exist for regression tests and quick experiments (install with `--extra data`).", ""]
            continue
        t = TOOLS[name]
        fn = t["fn"].__wrapped__
        sig = str(inspect.signature(fn)).replace("'", "")
        out += [f"### `{name.replace('_', '-')}`", "", t["summary"], "",
                f"- Python: `lab.{name}{sig}`", f"- Lane: {t.get('lane')}; cached: {bool(t.get('cacheable'))}"]
        for p, d in t["params"].items():
            out.append(f"  - `{p}`: {d}")
        ex = EXAMPLES.get(name)
        out += ["", "<details><summary>JSON schema</summary>", "", "```json", json.dumps(tool_schema(fn), indent=1, default=str), "```", "</details>", ""]
        if ex is not None:
            note = " (`@job_id` = the job id printed by the submit-job example)" if "@job_id" in json.dumps(ex) else ""
            out += [f"Example{note}:", "```bash", example_cli(name, ex), "```", ""]
    return "\n".join(out)


def events_md() -> str:
    return """# chipin.space chip lab: events and artefacts

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
"""


def write() -> list[str]:
    a, e = config.PROJECT_DIR / "AGENT.md", config.PROJECT_DIR / "EVENTS.md"
    a.write_text(agent_md()); e.write_text(events_md())
    return [str(a), str(e)]
