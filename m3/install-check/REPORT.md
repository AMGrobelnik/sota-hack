# P1 install check, first half (fast pass), partial

Machine: macOS 27.2.1 (26B131), Apple M3 Max, 16 cores, 128 GB RAM. Lab at origin/ant/chip-lab c8de5fb.

## Install (`scripts/install.sh --skip-docker --skip-pdk`, user folder variables set)

Run unchanged; the script honoured CHIPLAB_USER_DIR and CHIPLAB_CONFIG, so no patch was needed.
Nothing was written to ~/.chiplab or ~/.config/chiplab (both absent after the run).

| Step | Result | Time |
| --- | --- | --- |
| 1 uv | uv 0.13.5 present | under 1 s |
| 2 uv sync (dev, sim, ingest) | 57 packages, torch 2.15.0, device mps | about 9 s (cached) |
| 3 OSS CAD Suite | release 2026-11-21, Yosys 0.71+77 | about 30 s |
| 4 PDKs | skipped (--skip-pdk) | - |
| 5 Docker image | skipped (--skip-docker) | - |
| 6 Tiny Tapeout tools | tt-support-tools 0922544e6c7f | about 5 s |

Times come from log stamps of the earlier interrupted run (buffered log), so they are rough.
Release tarball sha256 f1afeda6cbbc0df119ee1339a5a42a43c0636688d2978d28a63ad3e805bf9a88 (not verified upstream).
Homebrew libomp 23.1.4 was already installed. Tool folder size 2.2 GB.

## Doctor (doctor.json)

ok false, as expected for the fast pass. Missing required: pdk:sky130.
Missing optional: python:mcp, docker, pdk:gf180, pdk:ihp.
OK: yosys, yosys-abc, iverilog, vvp, verilator, nextpnr-ice40, icepack, icetime, eqy, sby,
Tiny Tapeout tools, torch, xgboost, cocotb, torchlogix, alkaid.

## Quick start so far

| Command | Result |
| --- | --- |
| chiplab doctor | runs, JSON saved (not READY: PDK and Docker skipped) |
| ingest-model intnn fixtures/spike_best.json | pass, design_id 765fa47586bd |
| synthesize that design | pass: 2285 gates, depth 51, 0.35 s (Yosys, this Mac) |

Not yet run: remaining quick-start commands, AGENT.md examples, PDK and Docker steps.
Files: doctor.json, ingest.json, synth.json here (home path replaced by ~).
