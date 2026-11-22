# P1 install check on Apple Silicon: install, doctor, every AGENT.md example

Machine: macOS 27.2.1, Apple M3 Max, 16 cores, 128 GB RAM, Python 3.12.13, torch 2.15.0 (device mps).
Lab: `origin/ant/chip-lab` 021f68d (branch `m3/install-check` merged with it). Docker engine: colima
(Docker 29.5.2, arm64 image `ghcr.io/librelane/librelane:3.0.14`). Every number below was measured on this
machine; layout numbers are LibreLane layout results, not estimates.

Update (re-check on b77cc76, merged as f0c296c): all 28 AGENT.md examples return rc 0 (the first pass below
had 24, 23 passed); details in "Re-check on b77cc76" and "End-to-end prep" further down.

Result in five lines (first pass, on 021f68d):

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

## Re-check on b77cc76

What ran: `origin/ant/chip-lab` had moved one commit past the fix when it was pulled (f0c296c, the ChipIn
progress bridge, on top of b77cc76 and a CI commit bde3e80). The branch was merged normally
(`merge: origin/ant/chip-lab f0c296c`), so this re-check ran on b77cc76 plus f0c296c. Then
`uv sync --directory chiplab --extra dev --extra sim --extra ingest` (57 packages checked, no change) and a
restart of this worktree's `chiplab workers` (lanes it picked: cpu 15, gpu 1, docker 3).

How: `m3/install-check/recheck/` holds one log per example (`NN-<tool>.log`: the command as run, rc, wall
time, stdout, stderr) and `results.json`. The runner (`_logs/p1_recheck.py`, outside the repo) takes every
`Example:` block of `chiplab/AGENT.md` verbatim and runs it through bash from `chiplab/`, with
`CHIPLAB_USER_DIR`, `CHIPLAB_CONFIG`, `DOCKER_HOST` (colima) and a fresh, empty `CHIPLAB_HOME`
(so nothing came from the first pass's cache), and no `DYLD_FALLBACK_LIBRARY_PATH`. It ran ingest-model and
compile-ir first, then all others at once on 15 threads (the cpu lane), at most 3 Docker examples at a time
(the docker lane); timing-power after layout, tt-readiness and tt-export after tt-package, job-status and
job-result after submit-job. The only substitution is the one AGENT.md asks for: `@job_id` became the id
printed by submit-job (j-9a6d966f70bd); job-result ran 10 s after job-status. Limit 900 s per example.
Wall times are one run each, on this M3 Max, colima at 12 CPUs and 47 GiB at the time (the engine was
resized to 8 CPUs and 16 GiB after this run; nothing below ran on the smaller engine).

Result: AGENT.md now has 28 examples (it had 24); all 28 returned rc 0 with status ok. No rc 2 (failed
check) and no rc 3 (timeout). The whole set took 51.5 s wall clock (one run).

| # | Example | rc | Seconds | Note |
| --- | --- | --- | --- | --- |
| 1 | synthesize | 0 | 1.4 | design 765fa47586bd (the literal id) |
| 2 | count-luts | 0 | 32.7 |  |
| 3 | simulate | 0 | 5.7 | bit_exact true, 100000 vectors |
| 4 | prove-equivalence | 0 | 3.8 | proved true |
| 5 | map-to-process | 0 | 1.8 | sky130 |
| 6 | ingest-model | 0 | 0.7 | gives 765fa47586bd, as AGENT.md says |
| 7 | compose-chip | 0 | 0.8 | new design 9141eff1cf53 |
| 8 | compile-stream | 0 | 0.3 |  |
| 9 | rtl-simulate | 0 | 4.1 |  |
| 10 | estimate-cost | 0 | 0.3 |  |
| 11 | compare-hw-baseline | 0 | 0.5 |  |
| 12 | gate-activity | 0 | 1.4 |  |
| 13 | chip-report | 0 | 0.5 |  |
| 14 | submit-verilog | 0 | 2.5 | ran in the Docker sandbox; bit_exact true |
| 15 | layout | 0 | 50.6 | LibreLane, sky130, 20 ns, design ed8e52cb7a11 |
| 16 | timing-power | 0 | 0.2 | cached true: reused the layout run |
| 17 | bitstream | 0 | 39.1 | iCE40 |
| 18 | tt-package | 0 | 6.6 | user_config_ok and rtl_test_passed true |
| 19 | prove-sequential | 0 | 16.6 | proved true |
| 20 | verification-level | 0 | 0.2 |  |
| 21 | tt-readiness | 0 | 8.8 | new example; ready true |
| 22 | tt-export | 0 | 0.4 | new example |
| 23 | submit-job | 0 | 0.5 | state queued |
| 24 | job-status | 0 | 0.3 | new example; state queued |
| 25 | job-result | 0 | 1.3 | state done |
| 26 | cache-stats | 0 | 0.2 | new example |
| 27 | estimate-batch | 0 | 0.2 |  |
| 28 | compile-ir | 0 | 0.7 | gives ed8e52cb7a11, as AGENT.md says |

Against the first pass (24 examples on 021f68d, 23 passed):

- Fixed: tt-package. It failed before on the macOS cairo path; now it passes with no extra variable
  (the lab sets `DYLD_FALLBACK_LIBRARY_PATH` itself: `chiplab/chiplab/hw/tinytapeout.py:176`). Patch 05 is
  no longer needed.
- Fixed: the placeholders. Design ids are concrete and match what ingest-model and compile-ir return on a
  fresh lab, so no substitution was needed except the documented `@job_id`.
- Fixed and better than reported: prove-sequential. The first pass counted it as a pass, but its output was
  `status: ok` with `proved: null` after 300.7 s, i.e. a timeout reported as ok. Now `proved: true` in 16.6 s,
  and a timeout would return rc 3.
- Fixed: timing-power reuses the layout (0.2 s, `cached: true`; it was 172.2 s, running its own layout).
- Fixed: submit-verilog now runs in the Docker sandbox and refuses the host without `allow_host: true`
  (HARDENING point 8).
- All five proposed patches are upstream in some form: each now fails `git apply --check` because the lines
  it changes were rewritten by b77cc76 (01 timing-power error, 02 `top` identifier, 03 DNS-rebinding on
  loopback, 04 pinned tag, sha256, `uv sync --locked`, pinned tt-support-tools commit, 05 cairo). They are
  kept in `proposed/` as the record; none is still needed.
- Still open: the default install folders are still `~/.chiplab` and `~/.config/chiplab`, and f0c296c adds
  a launcher at `~/.local/bin/chiplab` (HARDENING point 1). The colima temp-folder note for the Docker tests
  is not addressed in the README (not re-tested here).
- Worse: nothing observed.

## End-to-end prep

Definition used: none of the task list, the new AGENT.md or the lab's docs on b77cc76/f0c296c defines
"end-to-end prep", "backend stub run" or "default-path install". The readings below come from the brief this
package was given, and f0c296c's own integration points (the ChipIn `./progress` bridge,
`chiplab doctor --agent-env`) were used where they apply. Raw outputs are in `e2e/`.

Default-path install, proven under a throwaway home (not the real one: the Mac owner's rule forbids new
folders in the real home directory; installing there awaits the Mac owner's yes):

- Command: `scripts/install.sh` with no flags, from this worktree's `chiplab/`, under `env -i` with exactly
  `HOME=~/projects/sota-hack/.worktrees/_m3/fakehome`, `PATH` (the session's PATH, unchanged),
  `DOCKER_HOST` (colima's socket) and `UV_CACHE_DIR` (the real uv cache, install step only). No `CHIPLAB_*`
  and no `PDK_ROOT`. Through `memgate run --need-gb 16` and a 3600 s limit.
- Result: exit 0, ends with `READY`, 129.9 s wall clock (one run, line stamps in
  `e2e/defaultpath-install-steps.txt`): uv 2.9 s, Python env 1.4 s (cached), OSS CAD Suite 28.0 s (520 MB
  download; the pinned sha256 matched, as no checksum note or mismatch was printed), PDKs 79.3 s (three kits
  downloaded fresh), Docker image 0.6 s (already in colima, which had just been resized to 8 CPUs and
  16 GiB), Tiny Tapeout tools 1.8 s, doctor 15.7 s.
- It wrote `<home>/.chiplab/`, `<home>/.config/chiplab/config.json` (absolute paths, `docker_host`) and the
  launcher `<home>/.local/bin/chiplab`, and printed "add ~/.local/bin to PATH". macOS also created
  `<home>/Library/Caches` and `Library/Logs`.
- `env -i HOME=<fakehome> PATH=$PATH chiplab doctor` as written: exit 127, `chiplab` not found, because the
  launcher folder is not on the session's PATH. With `PATH=<fakehome>/.local/bin:$PATH` (what the install's
  note asks for) and nothing else, not even `DOCKER_HOST`: exit 0, ok true, missing required none, missing
  optional `python:mcp` only; Docker found through the config file; all three kits and the TT tools present
  (`e2e/p1-doctor-fakehome.json`). `chiplab doctor --agent-env` under the same: exit 0, ok true, launcher found
  (`e2e/p1-doctor-fakehome-agentenv.json`).

The owner's literal command against the real home, read-only:

- `env -i HOME=~ PATH=$PATH chiplab doctor`: exit 127, `chiplab` not found (nothing is installed in the real
  home, so there is no launcher). Reading the code first showed doctor creates only a `.doctor` folder in the
  run folder (inside the checkout) and removes it, so it was safe to run.
- Same with the worktree's `.venv/bin/chiplab` called by path: exit 1, ok false; missing required yosys,
  yosys-abc, iverilog, vvp, verilator, pdk:sky130; it points at `~/.chiplab/pdk` and `~/.chiplab/tt`
  (`e2e/p1-doctor-realhome-venv.json`). Note: the JSON says `status: ok` with `ok: false` (exit 1).
- Afterwards `ls -d ~/.chiplab ~/.config/chiplab ~/.local/bin/chiplab`: none exists. Nothing was created.

Backend stub run and the lab from its environment:

- Backend: `~/projects/sota-hack/.worktrees/backend-providers/backend`, used read-only (its git status was
  clean before and after). The command is `--backend stub`, not `--agent stub` (`--agent` belongs to
  `serve`). Run: `chipin-backend run --config <e2e.yaml> --backend stub --mode local --no-summary`, with an
  overlay config that only moves `runs_dir` and `log_dir` to `_m3/e2e/`. Result: run
  20261121-214514-97385c succeeded, the stub's reply, cost $0, 0 model calls (`e2e/stub-run.json`).
- Lab from that run: in the run's `workspace/`, with the environment built by the backend's own
  `build_agent_env` (it kept only HOME, PATH, LANG and its two forced names; the CHIPLAB_* and DOCKER_HOST
  values passed in were stripped), HOME the throwaway home and its `.local/bin` on PATH. The ChipIn
  `./progress` helper was written into the workspace with the backend's `write_helper`, as its API server
  does. Then the quick start on the lab's only fixture: `ingest-model` (spike_best.json), `synthesize`,
  `simulate` (100000 random vectors). All three rc 0, status ok, bit_exact true; 0.5 s, 0.6 s, 1.4 s
  (`e2e/p1-e2e-lab.json`).
- The bridge worked: the lab found the helper and wrote 13 lines into the run's `progress.jsonl` (status
  lines, metrics gates 2285, depth 51, transistors 17380, vectors_checked 100000, mismatches 0, and four
  artifacts copied into `workspace/chips/765fa47586bd/`).
- What is NOT connected: the stub agent did not call the lab; the lab was called by this package's script
  inside the finished run's workspace. The backend's `run` command does not install the helper or read
  `progress.jsonl`, so these lines did not reach the run's `events.jsonl`; only the API server (`serve`)
  tails that file, and `serve` was not started here. So: both pieces work on this Mac and the lab reports
  through the backend's helper format; an agent-driven run that calls the lab has not been run.

## Files

- `doctor.json`, `doctor_full.json`, `doctor_with_docker.json`, `ingest.json`, `synth.json`: raw command output.
- `examples/`: output of every example and the runner's JSON records.
- `proposed/`: `01-timing-power-propagate-error`, `02-verilog-top-identifier`, `03-serve-dns-rebinding-on-loopback`,
  `04-install-pin-and-verify`, `05-tt-cairo-dyld-fallback-macos` (all pass `git apply --check` on the lab branch).
- `HARDENING.md`: read-only findings for the lab's owner.
