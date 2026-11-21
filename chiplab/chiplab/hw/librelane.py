"""Place-and-route with LibreLane 3.0.14 (Apache-2.0, run dockerized): real cell area, timing, power, a GDS and a
layout image. Wrapped, never reimplemented. Power is vectorless unless an activity VCD is given (OpenSTA read_vcd
on the routed netlist, run inside the same image)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from chiplab import config

PDK_NAMES = {"sky130": "sky130A", "sky130A": "sky130A", "gf180": "gf180mcuD", "gf180mcuD": "gf180mcuD",
             "ihp": "ihp-sg13g2", "ihp-sg13g2": "ihp-sg13g2"}
_GF180_33V = {  # Tiny Tapeout's 3.3 V library selection for gf180mcuD (tt-support-tools tech.py)
    "VDD_PIN_VOLTAGE": 3.3,
    "LIB_SYNTH": "pdk_dir::libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib",
    "LIB_FASTEST": "pdk_dir::libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__ff_n40C_3v60.lib",
    "LIB_SLOWEST": "pdk_dir::libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib",
    "DEFAULT_CORNER": "nom_tt_025C_3v30",
    "STA_CORNERS": ["nom_tt_025C_3v30", "nom_ss_125C_3v00", "nom_ff_n40C_3v60"],
}
METRIC_KEYS = (
    "design__instance__count", "design__instance__area", "design__instance__utilization", "design__die__area",
    "design__core__area", "design__instance__count__stdcell", "timing__setup__ws", "timing__setup__wns",
    "timing__setup__tns", "timing__hold__ws", "timing__setup_vio__count", "timing__hold_vio__count",
    "power__total", "power__internal__total", "power__switching__total", "power__leakage__total",
    "route__wirelength", "route__drc_errors", "antenna__violating__nets", "design__max_slew_violation__count",
    "design__max_cap_violation__count", "clock__skew__worst_setup", "design__instance__area__stdcell",
    "design__instance__count__stdcell", "design__instance__area__class:fill_cell", "design__instance__area__class:tap_cell",
    "design__instance__area__class:multi_input_combinational_cell", "design__instance__area__class:inverter",
    "design__instance__area__class:timing_repair_buffer", "design__instance__area__class:sequential_cell",
)
NAND2_UM2 = {"sky130A": 3.7536, "gf180mcuD": 10.976, "ihp-sg13g2": 7.2576}


class LayoutError(RuntimeError):
    pass


def docker_cmd(workdir: Path, args: list[str], extra_mounts: tuple = ()) -> list[str]:
    """`docker run` the LibreLane image (multi-arch: amd64 and arm64, so the same on Linux and Apple Silicon Macs)
    with the work dir and the PDK root mounted at their own paths. No host LibreLane install needed."""
    wd = str(Path(workdir).resolve())
    pdk = str(Path(config.PDK_ROOT).resolve())
    mounts = dict.fromkeys([wd, pdk, *[str(Path(m).resolve()) for m in extra_mounts]])
    cmd = ["docker", "run", "--rm", "-u", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp", "-e", f"PDK_ROOT={pdk}",
           "-w", wd]
    for m in mounts:
        cmd += ["-v", f"{m}:{m}"]
    return cmd + [config.LIBRELANE_IMAGE, *args]


def run_librelane(workdir: Path, config_file: str, pdk: str, tag: str, timeout: int, force_run_dir: str | None = None) -> subprocess.CompletedProcess:
    args = ["librelane", "--pdk-root", str(Path(config.PDK_ROOT).resolve()), "--pdk", pdk, "--run-tag", tag,
            "--hide-progress-bar"]
    if force_run_dir:
        args += ["--force-run-dir", force_run_dir]
    try:
        return subprocess.run(docker_cmd(workdir, args + [config_file]), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise LayoutError(f"LibreLane timed out after {timeout}s")


def timing_power_layout(rtl_files: list[Path], top: str, workdir: Path, pdk: str = "sky130A",
                        clock_period_ns: float = 10.0, clock_port: str | None = None, die_area: tuple | None = None,
                        activity_vcd: Path | None = None, vcd_scope: str | None = None, core_util: int = 40,
                        timeout: int = 3600, tag: str = "chiplab") -> dict:
    """Run LibreLane's Classic flow (synthesis -> floorplan -> place -> CTS -> route -> STA -> GDS) and read its metrics.

    Combinational designs: leave clock_port None; LibreLane's base.sdc then times every input->output path against a
    virtual clock of clock_period_ns. Returns area/timing/power metrics plus gds/png paths."""
    t0 = time.time()
    pdk = PDK_NAMES[pdk]
    wd = Path(workdir).resolve()
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "src").mkdir(exist_ok=True)
    for f in rtl_files:
        shutil.copy(f, wd / "src" / Path(f).name)
    write_config([Path(f).name for f in rtl_files], top, wd, pdk, clock_period_ns, clock_port, die_area, core_util)
    run_dir = wd / "runs" / tag
    if run_dir.exists():
        shutil.rmtree(run_dir)
    p = run_librelane(wd, "config.json", pdk, tag, timeout)
    (wd / "librelane.log").write_text(p.stdout[-200000:] + p.stderr[-50000:])
    final = run_dir / "final"
    mj = final / "metrics.json"
    if p.returncode != 0 or not mj.exists():
        tail = (p.stdout + p.stderr)[-2500:]
        raise LayoutError(f"LibreLane failed (rc={p.returncode}); see {wd / 'librelane.log'}:\n{tail}")
    m = json.loads(mj.read_text())
    metrics = {k: m[k] for k in METRIC_KEYS if k in m}
    gds = sorted((final / "gds").glob("*.gds"))
    png = sorted(run_dir.glob("*klayout*render*/*.png")) or sorted(run_dir.rglob("*.png"))
    res = {"pdk": pdk, "top": top, "basis": "librelane-layout", "clock_period_ns": clock_period_ns,
           "combinational": clock_port is None, "metrics": metrics,
           "area_um2": metrics.get("design__instance__area__stdcell", metrics.get("design__instance__area")),
           "area_note": "standard cells incl. tap and repair buffers, excluding filler; die_area_um2 is the placed die",
           "core_area_um2_with_fill": metrics.get("design__instance__area"), "die_area_um2": metrics.get("design__die__area"),
           "timing_ws_ns": metrics.get("timing__setup__ws"), "timing_wns_ns": metrics.get("timing__setup__wns"),
           "power_w": metrics.get("power__total"), "leakage_w": metrics.get("power__leakage__total"),
           "power_basis": "vectorless", "gds": str(gds[0]) if gds else None, "png": str(png[0]) if png else None,
           "netlist": _first(final, "pnl/*.pnl.v") or _first(final, "nl/*.nl.v"), "run_dir": str(run_dir),
           "flow_seconds": round(time.time() - t0, 1)}
    if res["png"] is None and res["gds"]:
        res["png"] = render_png(Path(res["gds"]), wd / f"{top}.png")
    if res["area_um2"]:
        res["gate_equivalents_layout"] = round(float(res["area_um2"]) / NAND2_UM2[pdk], 1)
    dyn = (metrics.get("power__internal__total") or 0) + (metrics.get("power__switching__total") or 0)
    if dyn:
        # vectorless: default toggle rates at the clock; one decision per clock period
        res["energy_per_decision_pj_vectorless"] = round(dyn * clock_period_ns * 1e-9 * 1e12, 3)
    if res["timing_ws_ns"] is not None:
        # worst setup slack against the virtual clock -> critical path delay (combinational) or achievable period
        res["critical_path_ns"] = round(clock_period_ns - float(res["timing_ws_ns"]), 4)
    if activity_vcd:
        res.update(activity_power(run_dir, top, pdk, Path(activity_vcd), vcd_scope, clock_period_ns))
    res["seconds"] = round(time.time() - t0, 1)
    return res


def check_pdk(pdk: str) -> dict:
    """Resolve a PDK under config.PDK_ROOT and its standard-cell library without running a flow."""
    name = PDK_NAMES[pdk]
    root = Path(config.PDK_ROOT) / name
    scl = {"sky130A": "sky130_fd_sc_hd", "gf180mcuD": "gf180mcu_fd_sc_mcu7t5v0", "ihp-sg13g2": "sg13g2_stdcell"}[name]
    libs = sorted((root / "libs.ref" / scl / "lib").glob("*.lib")) if root.exists() else []
    tech = sorted((root / "libs.tech" / "librelane").glob("*")) if root.exists() else []
    return {"pdk": name, "root": str(root), "found": root.exists(), "scl": scl, "liberty_files": len(libs),
            "librelane_tech_dir": bool(tech), "ok": root.exists() and bool(libs)}


def write_config(rtl_names: list[str], top: str, workdir: Path, pdk: str, clock_period_ns: float = 10.0,
                 clock_port: str | None = None, die_area: tuple | None = None, core_util: int = 40) -> dict:
    """The LibreLane config the flow would use (also used to check GF180/IHP set-ups without running them)."""
    pdk = PDK_NAMES[pdk]
    cfg = {"DESIGN_NAME": top, "VERILOG_FILES": [f"dir::src/{n}" for n in rtl_names], "CLOCK_PERIOD": clock_period_ns,
           "IO_DELAY_CONSTRAINT": 0, "RUN_MAGIC_DRC": False, "RUN_KLAYOUT_DRC": False, "RUN_KLAYOUT_XOR": False,
           "RUN_LVS": False, "RUN_CTS": clock_port is not None, "GRT_ALLOW_CONGESTION": True,
           "PL_TARGET_DENSITY_PCT": 55, "DESIGN_REPAIR_BUFFER_OUTPUT_PORTS": False, "CLOCK_PORT": clock_port,
           # this run's share of the machine when several layouts run in parallel (docker lane workers)
           "ROUTING_CORES": config.threads_per_docker_job()}
    cfg.update({"FP_SIZING": "absolute", "DIE_AREA": list(die_area)} if die_area else {"FP_SIZING": "relative", "FP_CORE_UTIL": core_util})
    if pdk == "gf180mcuD":
        cfg.update(_GF180_33V)
    Path(workdir).mkdir(parents=True, exist_ok=True)
    (Path(workdir) / "config.json").write_text(json.dumps(cfg, indent=1))
    return cfg


def _first(d: Path, pattern: str) -> str | None:
    hits = sorted(d.glob(pattern))
    return str(hits[0]) if hits else None


def render_png(gds: Path, out: Path, width: int = 1600) -> str | None:
    """Render a GDS to PNG with KLayout inside the LibreLane image (no local KLayout needed)."""
    script = out.with_suffix(".lym.py")
    script.write_text(f"""import pya
lv = pya.LayoutView()
lv.load_layout({str(gds)!r}, 0)
lv.max_hier()
lv.set_config("background-color", "#000000")
lv.set_config("grid-visible", "false")
lv.zoom_fit()
lv.save_image({str(out)!r}, {width}, {width})
""")
    cmd = docker_cmd(out.parent, ["klayout", "-b", "-r", str(script)], extra_mounts=(gds.parent,))
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return None
    return str(out) if p.returncode == 0 and out.exists() else None


def activity_power(run_dir: Path, top: str, pdk: str, vcd: Path, scope: str | None, period_ns: float) -> dict:
    """Power from real switching activity: OpenSTA read_vcd on the routed netlist + SPEF, typical corner."""
    final = run_dir / "final"
    nl = _first(final, "nl/*.nl.v")
    spef = _first(final, "spef/nom*/*.spef") or _first(final, "spef/*/*.spef") or _first(final, "spef/*.spef")
    resolved = json.loads((run_dir / "resolved.json").read_text()) if (run_dir / "resolved.json").exists() else {}
    libs = resolved.get("LIB", {})
    corner = resolved.get("DEFAULT_CORNER", "nom_tt_025C_1v80")
    lib_list = []
    for k, v in libs.items():
        import fnmatch
        if fnmatch.fnmatch(corner, k):
            lib_list = v if isinstance(v, list) else [v]
            break
    if not (nl and lib_list):
        return {"activity_power_error": "routed netlist or liberty not found"}
    tcl = run_dir.parent.parent / "activity_power.tcl"
    sc = f"-scope {scope} " if scope else ""
    tcl.write_text("\n".join([f"read_liberty {l}" for l in lib_list] + [
        f"read_verilog {nl}", f"link_design {top}",
        f"create_clock -name vclk -period {period_ns}" + ("" if True else ""),
        *( [f"read_spef {spef}"] if spef else []),
        f"read_vcd {sc}{vcd}", "report_power", "exit"]))
    cmd = docker_cmd(run_dir.parent.parent, ["sta", "-no_init", "-no_splash", "-exit", str(tcl)], extra_mounts=(vcd.parent,))
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    out = p.stdout + p.stderr
    (tcl.parent / "activity_power.log").write_text(out)
    import re
    m = re.search(r"^Total\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)", out, re.M)
    if not m:
        return {"activity_power_error": out[-800:]}
    internal, switching, leakage, total = (float(v) for v in m.groups())
    return {"power_basis": "activity", "power_w": total, "activity_power": {"internal_w": internal,
            "switching_w": switching, "leakage_w": leakage, "total_w": total, "vcd": str(vcd)}}
