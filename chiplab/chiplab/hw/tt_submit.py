"""Tiny Tapeout submission readiness: check a lab-made TT project, fill what is missing, export a submission repo.

Nothing here pays, submits or pushes. A human decides; this makes the decision a few minutes of work:

    readiness(project_dir)               -> every check TT's precheck and submission form need (+ local precheck
                                            in the LibreLane image when a hardened GDS exists)
    fix_project(project_dir)             -> fills the pinout and docs from the streaming protocol (idempotent)
    export_submission_repo(project, out) -> a standalone repo shaped like ttsky-verilog-template (git, one commit),
                                            or mode="monorepo" to stage it under chiplab/tt_projects/ for tt-gds.yaml
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import yaml

from chiplab import config

TT_TOP_PORTS = {"ui_in", "uo_out", "uio_in", "uio_out", "uio_oe", "ena", "clk", "rst_n"}
TILES = {"1x1", "1x2", "2x2", "3x2", "4x2", "6x2", "8x2"}
DOC_SECTIONS = ("How it works", "How to test", "External hardware")
PLACEHOLDERS = {"", "tbd", "todo", "unknown", "your name", "example", "my project"}
GENERATED = ("src/config_merged.json", "src/user_config.json", "test/sim_build", "test/results.xml", "test/__pycache__",
             "test/tb.fst", "test/tb.vcd", "test/rtl_test.log", "test/gl_test.log", "test/tb_result.json", "runs", "tt",
             "tt_submission", "test/gate_level_netlist.v", "harden.log", "precheck.log")
SHUTTLE = {"name": "TTSKY26", "pdk": "sky130A", "closes": "2026-11-30", "tile_eur": 70, "devkit_eur": 300,
           "devkit_individual_eur": 100, "submit_url": "https://app.tinytapeout.com/"}


def _ck(name, ok, detail="", fix=None, severity="error"):
    d = {"check": name, "ok": bool(ok), "severity": severity, "detail": detail}
    if not ok and fix:
        d["fix"] = fix
    return d


def _design_dir(project: Path) -> Path | None:
    """runs/designs/<id>/tt/tt_<top> -> runs/designs/<id> (where stream_tt.json lives), if this is a lab project."""
    for p in (project.parent.parent, project.parent):
        if (p / "stream_tt.json").exists():
            return p
    return None


def stream_pinout(stream_info: dict) -> dict:
    """Pin descriptions for the lab's streaming wrapper (emit/stream.py), for info.yaml's pinout section."""
    pins = {f"ui[{i}]": f"data word bit {i} (input value, sent on each strobe)" for i in range(7)}
    pins["ui[7]"] = "strobe: rising edge latches one 15-bit data word {uio_in, ui_in[6:0]}"
    for i in range(8):
        pins[f"uio[{i}]"] = f"data word bit {7 + i} (input; high bits of the 15-bit word)"
    uo_map = stream_info.get("uo_map") or []
    for i in range(7):
        if i < len(uo_map):
            m = uo_map[i]
            pins[f"uo[{i}]"] = f"result: output '{m['output']}' lane {m['lane']} bit {m['bit']}"
        else:
            pins[f"uo[{i}]"] = "unused (driven low)"
    pins["uo[7]"] = "valid: high once a full input frame has been received and the result is ready"
    return pins


def _info_md(stream_info: dict | None, title: str) -> str:
    si = stream_info or {}
    core = si.get("core", {})
    ins = ", ".join(f"{p['name']}: {p['lanes']} x {p['bits']}-bit {'signed' if p['signed'] else 'unsigned'}" for p in core.get("inputs", []))
    outs = ", ".join(f"{o['name']}: {o['lanes']} x {o['bits']}-bit" for o in core.get("outputs", []))
    tpf = si.get("transfers_per_frame", "N")
    return f"""## How it works

{title} is a small fixed-weight integer model wired directly into logic gates (no memory, no processor), designed
and verified in the chipin.space chip lab. The model's inputs ({ins or 'see info.yaml'}) are streamed into the chip
one 15-bit word at a time; when a full frame of {tpf} words has arrived, the combinational core computes the
result ({outs or 'see info.yaml'}) and the chip raises a valid flag.

## How to test

1. Hold `rst_n` low for a few clock cycles, then high. Keep `ena` high.
2. For each input value (inputs in port order, lane 0 first; values wider than 15 bits use several words, least
   significant first): put the low 7 bits on `ui_in[6:0]` and the next 8 bits on `uio_in[7:0]`, then raise
   `ui_in[7]` for at least 3 clock cycles and lower it again.
3. After the {tpf}th word, `uo_out[7]` (valid) goes high and the result is on `uo_out[6:0]` (see the pinout).
4. The project's cocotb test (`test/test.py`) does exactly this with vectors from the integer model.

## External hardware

None. Any microcontroller or the Tiny Tapeout demo board's RP2040 can drive the inputs and read the outputs.
"""


def fix_project(project_dir) -> dict:
    """Fill an empty pinout and thin docs from the streaming protocol; commit the change. Idempotent."""
    proj = Path(project_dir)
    info = yaml.safe_load((proj / "info.yaml").read_text())
    dd = _design_dir(proj)
    si = json.loads((dd / "stream_tt.json").read_text()) if dd else {}
    changed = []
    pins = info.get("pinout") or {}
    if any(not str(pins.get(f"{g}[{i}]", "")).strip() for g in ("ui", "uo", "uio") for i in range(8)):
        new = stream_pinout(si)
        info["pinout"] = {k: (pins.get(k) or new[k]) for k in new}
        changed.append("pinout")
    if info["project"].get("description", "").strip().lower() in PLACEHOLDERS:
        info["project"]["description"] = "A fixed-weight integer model wired into logic gates"
        changed.append("description")
    if changed:
        (proj / "info.yaml").write_text("# Tiny Tapeout project information (chipin.space chip lab)\n"
                                        + yaml.safe_dump(info, sort_keys=False, allow_unicode=True, width=120))
    md = (proj / "docs" / "info.md")
    if not md.exists() or _doc_problems(md.read_text()):
        md.parent.mkdir(exist_ok=True)
        md.write_text(_info_md(si, info["project"].get("title", info["project"]["top_module"])))
        changed.append("docs/info.md")
    if changed and (proj / ".git").exists():
        subprocess.run(["git", "add", "info.yaml", "docs/info.md"], cwd=proj, capture_output=True)
        subprocess.run(["git", "-c", "user.name=chipin.space chip lab", "-c", "user.email=lab@chipin.space", "commit", "-q", "-m",
                        "chip lab: fill pinout and docs for submission"], cwd=proj, capture_output=True)
    return {"project": str(proj), "changed": changed}


def _doc_problems(text: str) -> list[str]:
    probs = []
    for sec in DOC_SECTIONS:
        m = re.search(rf"^##\s*{re.escape(sec)}\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S | re.I)
        if not m:
            probs.append(f"missing section '{sec}'")
        elif len(m.group(1).strip()) < (4 if sec == "External hardware" else 60):
            probs.append(f"section '{sec}' is too thin")
    return probs


def _ports(verilog: str, top: str) -> set[str] | None:
    m = re.search(rf"module\s+{re.escape(top)}\s*(#\s*\(.*?\))?\s*\((.*?)\)\s*;", verilog, re.S)
    if not m:
        return None
    body = re.sub(r"//.*?$|/\*.*?\*/", "", m.group(2), flags=re.M | re.S)
    names = set()
    for part in body.split(","):
        toks = re.findall(r"[A-Za-z_][A-Za-z0-9_$]*", part)
        toks = [t for t in toks if t not in ("input", "output", "inout", "wire", "reg", "signed", "logic")]
        if toks:
            names.add(toks[-1])
    return names


def precheck_env_dir() -> Path:
    """gdstk for the LibreLane image's Python (3.13; the image has klayout and magic but not gdstk), fetched once."""
    import platform
    arch = "aarch64" if platform.machine().lower() in ("arm64", "aarch64") else "x86_64"
    d = config.home("tt_precheck", f"py313-{arch}")
    if not (d / "gdstk").exists():
        subprocess.run(["uv", "pip", "install", "-q", "--target", str(d), "--python-version", "3.13", "--python-platform",
                        f"{arch}-manylinux_2_28", "gdstk"], check=True, capture_output=True, timeout=600)
    shim = config.home("tt_precheck", "shim")
    (shim / "yowasp-yosys").write_text("#!/bin/sh\nexec yosys \"$@\"\n")
    (shim / "yowasp-yosys").chmod(0o755)
    return d


def run_precheck(project_dir, pdk: str = "sky130A", timeout: int = 1800) -> dict:
    """TT's own precheck (tt-support-tools/precheck) on the hardened GDS, inside the LibreLane image."""
    proj = Path(project_dir).resolve()
    info = yaml.safe_load((proj / "info.yaml").read_text())
    top = info["project"]["top_module"]
    sub = proj / "tt_submission" / f"{top}.gds"
    if not sub.exists():
        if not (proj / "runs" / "wokwi" / "final" / "gds" / f"{top}.gds").exists():
            return {"ran": False, "reason": "no hardened GDS (run tt_package with harden=true, or the tt-gds workflow)"}
        from chiplab.hw import tinytapeout as tt
        r = subprocess.run([tt.tt_python(), "tt/tt_tool.py", "--pdk", pdk, "--create-tt-submission"], cwd=proj, env=tt._env(),
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0 or not sub.exists():
            return {"ran": False, "reason": "tt_tool --create-tt-submission failed", "detail": (r.stdout + r.stderr)[-800:]}
    if not (proj / "tt" / "precheck" / "precheck.py").exists():
        return {"ran": False, "reason": "tt/ (tt-support-tools) missing in the project"}
    pp, shim = precheck_env_dir(), config.home("tt_precheck", "shim")
    libs = ("export LD_LIBRARY_PATH=$(for f in libz.so.1 libstdc++.so.6 libgcc_s.so.1; do p=$(ls /nix/store/*/lib/$f 2>/dev/null"
            " | head -1); [ -n \"$p\" ] && dirname $p; done | sort -u | paste -sd:); export PATH=/shim:$PATH; ")
    cmd = ["docker", "run", "--rm", "-u", f"{_uid()}", "-e", "HOME=/tmp", "-e", "PDK_ROOT=/pdk", "-e", f"PDK={pdk}",
           "-v", f"{Path(config.PDK_ROOT).resolve()}:/pdk:ro", "-v", f"{proj}:/proj", "-v", f"{pp}:/pp:ro", "-v", f"{shim}:/shim:ro",
           "-e", "PYTHONPATH=/pp", "-w", "/proj/tt/precheck", config.LIBRELANE_IMAGE, "bash", "-lc",
           libs + f"python3 precheck.py --gds /proj/tt_submission/{top}.gds"]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ran": True, "passed": False, "reason": f"timed out after {timeout}s"}
    log = p.stdout + p.stderr
    (proj / "precheck.log").write_text(log)
    table = {}
    for name, res in re.findall(r"^\|\s*([^|]+?)\s*\|\s*(✅|❌[^|]*)\|", log, re.M):
        if name not in ("Check", "-----------"):
            table[name] = "pass" if res.startswith("✅") else res.replace("❌", "").strip()
    return {"ran": True, "passed": p.returncode == 0 and "Precheck passed" in log, "checks": table,
            "seconds": round(time.time() - t0, 1), "log": str(proj / "precheck.log")}


def _uid() -> str:
    import os
    return f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "1000:1000"


def readiness(project_dir, run_tests: bool = True, run_precheck_if_hardened: bool = True) -> dict:
    proj = Path(project_dir)
    checks = []
    iy = proj / "info.yaml"
    if not iy.exists():
        return {"ready": False, "project": str(proj), "checks": [_ck("info.yaml", False, "missing", "run tt_package first")]}
    try:
        info = yaml.safe_load(iy.read_text())
    except Exception as e:
        return {"ready": False, "project": str(proj), "checks": [_ck("info.yaml parses", False, str(e))]}
    pj = info.get("project", {}) or {}
    checks.append(_ck("yaml_version 6", info.get("yaml_version") == 6, f"yaml_version={info.get('yaml_version')}"))
    for f in ("title", "author", "description", "language"):
        v = str(pj.get(f, "")).strip()
        checks.append(_ck(f"project.{f}", v.lower() not in PLACEHOLDERS, v or "(empty)", "edit info.yaml"))
    checks.append(_ck("project.discord", bool(str(pj.get("discord", "")).strip()), pj.get("discord") or "(empty)",
                      "add the submitter's Discord username (optional for TT, but needed for the Tapeout role)", "warning"))
    checks.append(_ck("project.clock_hz", isinstance(pj.get("clock_hz"), int) and pj["clock_hz"] > 0, str(pj.get("clock_hz"))))
    checks.append(_ck("project.tiles", str(pj.get("tiles")) in TILES, str(pj.get("tiles")), f"one of {sorted(TILES)}"))
    top = str(pj.get("top_module", ""))
    checks.append(_ck("top_module tt_um_*", top.startswith("tt_um_"), top, "rename the top module tt_um_<something>"))
    srcs = [proj / "src" / s for s in pj.get("source_files", [])]
    checks.append(_ck("source files exist", bool(srcs) and all(s.exists() for s in srcs), ", ".join(s.name for s in srcs)))
    pins = info.get("pinout") or {}
    empty = [f"{g}[{i}]" for g in ("ui", "uo", "uio") for i in range(8) if not str(pins.get(f"{g}[{i}]", "")).strip()]
    checks.append(_ck("pinout complete (24 pins)", not empty, f"{24 - len(empty)}/24 described" + (f"; empty: {', '.join(empty[:6])}..." if empty else ""),
                      "readiness fix: chiplab.hw.tt_submit.fix_project(project)"))
    md = proj / "docs" / "info.md"
    probs = _doc_problems(md.read_text()) if md.exists() else ["docs/info.md missing"]
    checks.append(_ck("docs/info.md sections", not probs, "; ".join(probs) or "How it works / How to test / External hardware",
                      "chiplab.hw.tt_submit.fix_project(project)"))
    vtxt = "\n".join(s.read_text() for s in srcs if s.exists())
    ports = _ports(vtxt, top) if vtxt else None
    checks.append(_ck("top module ports", ports == TT_TOP_PORTS, f"{sorted(ports) if ports else 'top module not found'}",
                      f"ports must be exactly {sorted(TT_TOP_PORTS)}"))
    vl = config.find_bin("verilator")
    if vl and srcs:
        p = subprocess.run([vl, "--lint-only", "-Wall", "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL", "--top-module", top, *map(str, srcs)],
                           capture_output=True, text=True, timeout=300)
        msgs = [l for l in p.stderr.splitlines() if l.startswith("%")]
        checks.append(_ck("verilator lint -Wall", p.returncode == 0, f"{len(msgs)} messages" + (f": {msgs[0][:140]}" if msgs else ""),
                          "fix the RTL (all outputs must be assigned)"))
    ys = config.find_bin("yosys")
    if ys and srcs:
        p = subprocess.run([ys, "-q", "-p", f"read_verilog -sv {' '.join(map(str, srcs))}; hierarchy -check -top {top}"],
                           capture_output=True, text=True, timeout=300)
        checks.append(_ck("yosys read (precheck's syntax check)", p.returncode == 0, (p.stderr or "ok")[-200:]))
    lic = proj / "LICENSE"
    checks.append(_ck("LICENSE (Apache-2.0)", lic.exists() and "Apache License" in lic.read_text(errors="ignore"),
                      "present" if lic.exists() else "missing", "copy the template's LICENSE"))
    if (proj / ".git").exists():
        tracked = subprocess.run(["git", "ls-files"], cwd=proj, capture_output=True, text=True).stdout.split()
        bad = [t for t in tracked if t.startswith("tt/") or t.startswith("runs/")]
        checks.append(_ck("tt/ and runs/ not committed", not bad, f"{len(bad)} offending files" if bad else "ok",
                          "git rm -r --cached tt runs; add them to .gitignore"))
        nc = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=proj, capture_output=True, text=True).stdout.strip()
        dirty = [l[3:] for l in subprocess.run(["git", "status", "--porcelain"], cwd=proj, capture_output=True, text=True).stdout.splitlines()
                 if not any(l[3:].startswith(g) for g in GENERATED)]
        checks.append(_ck("git: committed and clean", nc.isdigit() and int(nc) > 0 and not dirty,
                          f"{nc} commits; uncommitted: {dirty[:5]}" if dirty else f"{nc} commits", "git add -A && git commit", "warning"))
    else:
        checks.append(_ck("git repository", False, "not a git repo", "export_submission_repo() creates one", "warning"))
    if run_tests and (proj / "test" / "vectors.json").exists():
        from chiplab.hw.tinytapeout import run_cocotb
        r = run_cocotb(proj, gates=False)
        checks.append(_ck("cocotb RTL test", r["passed"], f"{r.get('seconds')} s, log {r.get('log')}", "see the test log"))
    out = {"project": str(proj), "top_module": top, "tiles": pj.get("tiles"), "clock_hz": pj.get("clock_hz"), "shuttle": SHUTTLE}
    hardened = (proj / "runs" / "wokwi" / "final" / "gds" / f"{top}.gds").exists()
    out["hardened"] = hardened
    if hardened:
        mcsv = proj / "runs" / "wokwi" / "final" / "metrics.csv"
        if mcsv.exists():
            row = dict(l.split(",", 1) for l in mcsv.read_text().splitlines() if "," in l)
            out["utilisation"] = row.get("design__instance__utilization") or row.get("design__instance__utilization__stdcell")
        if run_precheck_if_hardened:
            pc = run_precheck(proj)
            out["precheck"] = pc
            if pc.get("ran"):
                checks.append(_ck("TT precheck (local, LibreLane image)", pc.get("passed"),
                                  ", ".join(f"{k}: {v}" for k, v in pc.get("checks", {}).items() if v != "pass") or "all checks pass",
                                  "see precheck.log"))
    else:
        checks.append(_ck("hardened GDS + TT precheck", False, "not hardened yet",
                          "tt_package(harden=true) locally, or push the exported repo and let the gds workflow build it", "info"))
    errors = [c for c in checks if not c["ok"] and c["severity"] == "error"]
    out.update(ready=not errors, ready_for="cloud harden (gds workflow)" if not hardened else "submission", checks=checks,
               blocking=[c["check"] for c in errors],
               warnings=[c["check"] for c in checks if not c["ok"] and c["severity"] == "warning"])
    return out


README_TMPL = """# {title}

A Tiny Tapeout project generated by the chipin.space chip lab: {description}.

- Top module: `{top}` ({tiles} tile(s), {clock_mhz:g} MHz clock)
- How it works / how to test: [docs/info.md](docs/info.md)
- Verified in the lab: bit-exact against the integer model, streaming RTL test with cocotb (`test/`).

## How to submit (a human does this; nothing is submitted automatically)

1. Create an empty GitHub repo, then: `git remote add origin <url> && git push -u origin main`.
2. Enable GitHub Actions and Pages (Settings > Pages > Source: GitHub Actions). The `gds` workflow builds the layout,
   runs the Tiny Tapeout precheck and the gate-level test, and publishes a 3D viewer.
3. When all jobs are green, go to {submit_url}, create a project from this repository, pay for {tiles} tile(s)
   (EUR {tile_eur} per tile; the devkit is separate), and submit before the shuttle closes ({shuttle} closes {closes}).
4. Designs on Tiny Tapeout are public.
"""


def export_submission_repo(project_dir, out_dir=None, mode: str = "standalone") -> dict:
    """Write a submission-ready repo from a lab TT project. mode=standalone: its own git repo (template layout +
    .github/workflows). mode=monorepo: staged under chiplab/tt_projects/<top>/ for the tt-gds.yaml workflow."""
    from chiplab.hw.tinytapeout import TT_TEMPLATE
    proj = Path(project_dir)
    fix = fix_project(proj)
    info = yaml.safe_load((proj / "info.yaml").read_text())
    pj = info["project"]; top = pj["top_module"]
    out = Path(out_dir) if out_dir else (config.PROJECT_DIR / "tt_projects" / top if mode == "monorepo" else config.home("tt_export") / top)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    skip = set(GENERATED)
    for item in ("info.yaml", "LICENSE", "src", "docs", "test"):
        s = proj / item
        if not s.exists():
            continue
        if s.is_dir():
            shutil.copytree(s, out / item, ignore=lambda d, names: [n for n in names if f"{Path(d).relative_to(proj)}/{n}".lstrip("./") in skip
                                                                        or n in ("__pycache__", "sim_build", "results.xml") or n.endswith((".fst", ".vcd", ".log"))])
        else:
            shutil.copy(s, out / item)
    for f in ("src/config_merged.json", "src/user_config.json", "test/tb_result.json"):
        (out / f).unlink(missing_ok=True)
    (out / ".gitignore").write_text("runs/\ntt/\ntt_submission/\ntest/sim_build/\ntest/results.xml\ntest/__pycache__/\n*.fst\n*.vcd\n")
    files_written = []
    if mode == "standalone":
        wf_src = Path(TT_TEMPLATE) / ".github" / "workflows"
        (out / ".github" / "workflows").mkdir(parents=True)
        for wf in ("gds.yaml", "test.yaml", "docs.yaml"):
            if (wf_src / wf).exists():
                shutil.copy(wf_src / wf, out / ".github" / "workflows" / wf)
                files_written.append(f".github/workflows/{wf}")
        (out / "README.md").write_text(README_TMPL.format(title=pj.get("title", top), description=pj.get("description", ""), top=top,
                                                          tiles=pj.get("tiles"), clock_mhz=pj.get("clock_hz", 0) / 1e6, **SHUTTLE,
                                                          shuttle=SHUTTLE["name"]))
        g = lambda *a: subprocess.run(["git", *a], cwd=out, capture_output=True, text=True)
        g("init", "-q", "-b", "main"); g("add", "-A")
        g("-c", "user.name=chipin.space chip lab", "-c", "user.email=lab@chipin.space", "commit", "-q", "-m", f"Tiny Tapeout project {top}")
        nxt = ["Review README.md and info.yaml (title, author, discord).",
               "gh repo create <you>/<name> --public --source . --push   (or create the repo on github.com and push)",
               "Enable Actions + Pages; wait for gds / precheck / gl_test to pass.",
               f"Submit at {SHUTTLE['submit_url']} before {SHUTTLE['closes']} ({SHUTTLE['name']})."]
    else:
        rel = out.relative_to(config.PROJECT_DIR.parent) if config.PROJECT_DIR.parent in out.parents else out
        nxt = [f"git add {rel} && git commit && git push",
               f"gh workflow run tt-gds.yaml -f project_dir={rel} -f pdk={'sky130A'}",
               "When gds / precheck / gl_test are green, export mode=standalone for the submission repo."]
    files = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file() and ".git/" not in str(p.relative_to(out)) + "/")
    return {"repo": str(out), "mode": mode, "top_module": top, "fixed": fix["changed"], "files": files, "next_steps": nxt}
