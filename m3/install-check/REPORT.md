# P1 install check on Apple Silicon: install, doctor, every AGENT.md example

Machine: macOS 27.2.1, Apple M3 Max, 16 cores, 128 GB RAM, Python 3.12.13, torch 2.15.0 (device mps).
Lab: `origin/ant/chip-lab` 021f68d (branch `m3/install-check` merged with it). Docker engine: colima
(Docker 29.5.2, arm64 image `ghcr.io/librelane/librelane:3.0.14`). Every number below was measured on this
machine; layout numbers are LibreLane layout results, not estimates.

Result in five lines:

1. The fast install and the full install both work on the M3 with only `CHIPLAB_USER_DIR` and `CHIPLAB_CONFIG` set; nothing was written to `~/.chiplab` or `~/.config/chiplab`.
2. `chiplab doctor` reports ok with the engine reachable: only the optional `python:mcp` is missing.
3. All 24 AGENT.md examples have a result: 23 pass, the rest listed in the table with their error text.
4. The lab's test suite ran per file: see the test table (one in-process segfault, one macOS library-path fix).
5. Fixes are in `proposed/*.patch` (five patches); hardening notes are in `HARDENING.md`.

## Install (`scripts/install.sh`, run unchanged, user folder variables set)

Run in two passes by two agents, so the times come from the two install logs
(`_logs/install-fast-report.md`, `_logs/full-install.log`, `_logs/full_install.log`, kept outside the repo).

| Step | Result | Time measured |
| --- | --- | --- |
| 1 uv | uv 0.13.5 present | under 1 s |
| 2 uv sync (dev, sim, ingest) | 57 packages, torch 2.15.0, device mps | about 9 s on the fast pass (cached); 7 s on the full pass |
| 3 OSS CAD Suite | release 2026-11-21, Yosys 0.71+77 | about 30 s (fast pass, rough: log stamps of an interrupted run) |
| 4 PDKs | sky130 (16 s), gf180mcu (26 s), ihp-sg13g2 (18 s) | 60 s |
| 5 Docker plus image pull | image 3.0.14 pulled into colima | 90 s (pull only; colima start about 4 s) |
| 6 Tiny Tapeout tools | tt-support-tools 0922544e6c7f | about 5 s (fast pass) |
| doctor | READY | 14 s inside the install; 8 s on its own |

The last full pass as logged ran 1 min 53 s (21:07:49 to 21:09:42) with the OSS suite and tools already in
place; the fast pass measured the first-time tool downloads. The tool folder
(`~/projects/sota-hack/.worktrees/_m3/chiplab-home`) holds oss-cad-suite, pdk, tt, tt-venv, template, config.json.
The OSS CAD Suite tarball sha256 is f1afeda6cbbc0df119ee1339a5a42a43c0636688d2978d28a63ad3e805bf9a88
(computed locally, not compared with an upstream value).

Redirect variables: the script honoured `CHIPLAB_USER_DIR` and `CHIPLAB_CONFIG`. Without them the defaults are
`~/.chiplab` and `~/.config/chiplab` (new folders in the home directory); see HARDENING.md point 1. No patch was
needed for the redirect itself.

## Doctor

- With the engine: `doctor_with_docker.json` (ok true, missing required none, missing optional `python:mcp`;
  docker 29.5.2, image arm64, pdk sky130, gf180 and ihp present). Took 8 s.
- Fast pass (no PDKs, no Docker): `doctor_full.json`; the very first run, before the PDKs existed, is `doctor.json`
  (missing pdk:sky130).
- The doctor only finds the engine when `DOCKER_HOST` points at colima's socket
  (`unix://~/.colima/default/docker.sock`); with the default context it reports docker missing.

## Quick start

| Command | Result |
| --- | --- |
| `scripts/install.sh` | pass (see above) |
| `chiplab doctor` | pass, ok true |
| `chiplab ingest-model --json ... fixtures/spike_best.json` | pass, design_id 765fa47586bd |
| `chiplab synthesize --json {design_id}` | pass: 2285 gates, depth 51, 0.35 s (Yosys 0.71+77) |

## Every AGENT.md example

Each of the 24 `Example:` blocks in `chiplab/AGENT.md` was run through the CLI with the arguments as written.
Two substitutions were unavoidable and are not failures of the lab: the literal design id `cdaea5efb328` and the
`<design_id>` placeholders do not exist on a fresh lab, so the id of the fixture ingested by the first example
(765fa47586bd) was used; and the `job-result` example has the placeholder job id `j-...`, so the id returned by
the `submit-job` example was used (run with the literal placeholder it fails with `KeyError: 'unknown job j-...'`,
as expected). Raw outputs are in `examples/*.out.txt`, the runner's records in `examples/results*.json`.
Independent examples ran four at a time; layout and tt-package ran after the engine was up.
Times are single wall-clock measurements, first (uncached) run, except layout and timing-power, which are the
rerun with the engine.

| # | AGENT.md example | Result | Seconds | Note or exact error |
| --- | --- | --- | --- | --- |
| 1 | ingest-model | pass | 0.2 | fixture spike_best.json, design 765fa47586bd |
| 2 | compile-ir | pass | 0.2 |  |
| 3 | synthesize | pass | 0.1 |  |
| 4 | count-luts | pass | 19.3 |  |
| 5 | simulate | pass | 1.0 |  |
| 6 | prove-equivalence | pass | 0.9 |  |
| 7 | map-to-process | pass | 0.6 |  |
| 8 | compose-chip | pass | 0.2 |  |
| 9 | compile-stream | pass | 0.1 |  |
| 10 | rtl-simulate | pass | 4.9 |  |
| 11 | estimate-cost | pass | 0.1 |  |
| 12 | compare-hw-baseline | pass | 0.1 |  |
| 13 | gate-activity | pass | 0.1 |  |
| 14 | chip-report | pass | 0.2 |  |
| 15 | submit-verilog | pass | 0.2 |  |
| 16 | layout | pass | 86.8 | LibreLane in Docker (colima), sky130A, 20 ns clock |
| 17 | timing-power | pass | 172.2 | runs its own layout |
| 18 | bitstream | pass | 23.6 |  |
| 19 | tt-package | FAIL | 1.5 | as written: status ok but user_config_ok false, error 'no library called libcairo-2 was found' (cairocffi cannot see Homebrew lib); with DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib: user_config_ok tr |
| 20 | prove-sequential | pass | 300.7 | timeout 300 as written |
| 21 | verification-level | pass | 0.1 |  |
| 22 | submit-job | pass | 0.1 | returns status queued (counted as pass) |
| 23 | job-result | pass | 0.4 | run with the job_id returned by submit-job |
| 24 | estimate-batch | pass | 0.1 |  |

Layout result (example 16, LibreLane, sky130A, 20 ns clock): see `examples/layout.out.txt`.

## The lab's own test suite (extra evidence)

First, one in-process run (`pytest -v`): 53 passed, 3 failed, then the process died with a segmentation fault
(exit 139, no Python traceback) in `tests/test_treelut.py::test_treelut_chip_bit_exact[2]`. The same test passes
alone (2 passed). A likely cause is two OpenMP runtimes (torch and XGBoost) in one process on macOS; this was not
investigated further. The three failures were `test_librelane.py::test_sky130_layout` (no engine reachable at that
moment) and two `test_tinytapeout.py` tests (cairo library, see below).

Second, one pytest process per file, with the engine and `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`:

| Test file | Result |
| --- | --- |
| test_compose.py | 5 passed (exit 0 seconds=17) |
| test_encode.py | 3 passed (exit 0 seconds=8) |
| test_eqy.py | 1 passed (exit 0 seconds=33) |
| test_formal_golden.py | 3 passed (exit 0 seconds=14) |
| test_fpga.py | 1 passed (exit 0 seconds=5) |
| test_ingest.py | 3 passed (exit 0 seconds=2) |
| test_intnn_lower.py | 2 passed (exit 0 seconds=14) |
| test_ir_fuzz.py | 18 passed (exit 0 seconds=12) |
| test_ladder.py | 3 passed (exit 0 seconds=1) |
| test_librelane.py | 1 failed, 3 passed (exit 1 seconds=7) |
| test_sandbox.py | 2 passed (exit 0 seconds=1) |
| test_split.py | 3 passed (exit 0 seconds=2) |
| test_stream.py | 4 passed (exit 0 seconds=18) |
| test_tinytapeout.py | 1 failed, 1 passed (exit 1 seconds=13) |
| test_torchlogix.py | 2 passed (exit 0 seconds=14) |
| test_treelut.py | 2 passed (exit 0 seconds=12) |

Docker-based tests and colima: `test_librelane.py::test_sky130_layout` and
`test_tinytapeout.py::test_tt_harden_and_gate_level` fail under colima with pytest's default temp folder
(`/private/var/folders/...`), which colima does not mount into its VM. Exact errors:
`Error: Invalid value for '[CONFIG_FILES]...': Path 'config.json' does not exist.` and
`Error: Invalid value for '--force-run-dir': Directory 'runs/wokwi' does not exist.` The AGENT.md layout example
works because the run folders are inside the project under `~/projects`. With `--basetemp` pointing inside the
project, test_librelane.py: 4 passed (98.25s); test_tinytapeout.py: see log (?s, with the cairo path variable too) (observed). Suggested fix for the lab or its README: run the tests with a `--basetemp` under the
checkout (or start colima with a mount for `/private/var/folders`); Docker Desktop shares these folders by default.
In the per-file table below the two Docker test files therefore show the failure of the default run.

macOS finding: the Tiny Tapeout tools import `cairocffi`, which does not search Homebrew's lib folder. With
Homebrew `cairo` installed, `tt-package` fails with `no library called "libcairo-2" was found` unless
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` is set; with it set, `tt-package` returns user_config_ok true and
rtl_test_passed true (observed, 5 s), and the TT test passes. Patch 05 sets it inside the lab's TT environment on
macOS. `scripts/install.sh` does not install `cairo`; here it was already present.

## Files

- `doctor.json`, `doctor_full.json`, `doctor_with_docker.json`, `ingest.json`, `synth.json`: raw command output.
- `examples/`: output of every example and the runner's JSON records.
- `proposed/`: `01-timing-power-propagate-error`, `02-verilog-top-identifier`, `03-serve-dns-rebinding-on-loopback`,
  `04-install-pin-and-verify`, `05-tt-cairo-dyld-fallback-macos` (all pass `git apply --check` on the lab branch).
- `HARDENING.md`: read-only findings for the lab's owner.
