"""Generate AGENT.md (the interface doc for AI scientists) and EVENTS.md (event and artefact formats) from the
live tool registry, so the docs never drift from the code: `chiplab agent-doc --write`."""
from __future__ import annotations

import inspect
import json
import typing

from chiplab import config

EXAMPLES = {
    "ingest_model": {"format": "intnn", "model": "<contents of fixtures/spike_best.json>", "name": "spike"},
    "compile_ir": {"ir": {"ir": "chipir/1", "name": "tiny", "inputs": [{"name": "x", "lanes": 4, "bits": 4, "signed": False}],
                          "nodes": [{"id": "s", "op": "matvec", "src": "x", "W": [[1, -1, 2, 0]], "b": [-3]},
                                    {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}],
                          "outputs": [{"name": "y", "src": "y"}], "meta": {}}},
    "synthesize": {"design_id": "cdaea5efb328"},
    "simulate": {"design_id": "cdaea5efb328", "inputs": "random", "n": 100000},
    "prove_equivalence": {"design_id": "cdaea5efb328"},
    "map_to_process": {"design_id": "cdaea5efb328", "pdk": "sky130"},
    "count_luts": {"design_id": "cdaea5efb328", "family": "ice40"},
    "compose_chip": {"heads": {"a": "<design_id>", "b": "<design_id>"}, "fusion": [{"name": "alarm", "op": "and", "inputs": ["a_y", "b_y"]}],
                     "shared_inputs": False},
    "compile_stream": {"design_id": "cdaea5efb328", "tt": True},
    "rtl_simulate": {"design_id": "cdaea5efb328", "n": 300},
    "submit_job": {"tool": "map_to_process", "args": {"design_id": "cdaea5efb328", "pdk": "sky130"}, "session_id": "agent-A"},
    "job_result": {"job_id": "j-…"},
    "estimate_batch": {"designs": ["<design_id>", "<design_id>"], "keep": 5},
    "chip_report": {"design_id": "cdaea5efb328"},
    "estimate_cost": {"design_id": "cdaea5efb328"},
    "layout": {"design_id": "cdaea5efb328", "pdk": "sky130", "clock_period_ns": 20},
    "timing_power": {"design_id": "cdaea5efb328", "pdk": "sky130"},
    "bitstream": {"design_id": "cdaea5efb328"},
    "tt_package": {"design_id": "cdaea5efb328", "harden": False},
    "prove_sequential": {"design_id": "cdaea5efb328", "timeout": 300},
    "verification_level": {"design_id": "cdaea5efb328"},
    "gate_activity": {"design_id": "cdaea5efb328", "n": 2000, "vcd": True},
    "compare_hw_baseline": {"design_id": "cdaea5efb328", "task": "af_vs_normal", "dataset": "AFDB", "protocol": "record-level, per paper"},
    "submit_verilog": {"verilog": "module m(input [3:0] x, output [4:0] y); assign y = x + x; endmodule", "top": "m",
                       "port_spec": {"inputs": [{"name": "x", "lanes": 1, "bits": 4, "signed": False}],
                                     "outputs": [{"name": "y", "lanes": 1, "bits": 5, "signed": False}]},
                       "reference_ir": "<chipir/1 doc computing x + x>"},
}


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
        if ex:
            out += ["Example:", "```bash", f"chiplab {name.replace('_', '-')} --json '{json.dumps(ex)}'", "```", ""]
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
