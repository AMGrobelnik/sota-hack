# Submitting a chip-lab design to Tiny Tapeout

The lab prepares everything; **a person decides, pays and submits.** Nothing in the lab submits, pays or pushes to
any repository on its own. This page turns a lab chip into a submission in about 15 minutes of human time, plus
GitHub's build time.

## Before you start

- **Shuttle:** TTSKY26 (SkyWater 130 nm) closes **30 Nov 2026**; chips arrive about June 2027. Tiny Tapeout GF180
  closes 7 Dec 2026. Check https://tinytapeout.com for current dates.
- **Price:** €70 per tile (a tile holds about 1,000 gates). The demo board/devkit is extra: €300, or €100 for
  individuals. Our small test chip needs 1 tile; the feasibility-spike AF chip needs 2 tiles (1x2).
- **Public:** every Tiny Tapeout design is published openly (source, layout, docs).
- **Accounts:** a GitHub account, and a Tiny Tapeout account at https://app.tinytapeout.com/. A Discord username is
  optional but gets the Tapeout role.
- **Not medical:** a Tiny Tapeout chip is a research prototype, not a medical device.

## Steps

1. **Make the project folder** (in the lab):
   ```bash
   chiplab tt-package --json '{"design_id": "<id>"}'            # add "harden": true to also build the GDS locally (Docker)
   ```
2. **Check readiness** (Python, from the `chiplab/` folder):
   ```python
   from chiplab.hw.tt_submit import readiness, fix_project
   r = readiness("<folder from step 1>"); print(r["ready"], r["blocking"], r["warnings"])
   fix_project("<folder>")        # fills the pinout and docs from the streaming protocol, if empty
   ```
   It checks:
   - `info.yaml`: version 6, title, author, description, clock, tiles, a `tt_um_*` top and the source files;
   - all 24 pins described;
   - the docs sections;
   - the exact TT port list;
   - Verilator lint (every output assigned) and the Yosys read that the precheck also does;
   - the Apache-2.0 licence;
   - that `tt/` is not committed;
   - the cocotb RTL test.

   If the project was hardened, it also runs **TT's own precheck locally** in the LibreLane container: DRC, pins,
   boundary, power pins, layers.
3. **Export the submission repo:**
   ```python
   from chiplab.hw.tt_submit import export_submission_repo
   e = export_submission_repo("<folder>", "<empty output folder>"); print(e["next_steps"])
   ```
   This writes a repo shaped like Tiny Tapeout's `ttsky-verilog-template`:
   - `info.yaml`, `src/`, `docs/info.md`, `test/` (cocotb test + vectors), `LICENSE`, `README.md`;
   - `.github/workflows/{gds,test,docs}.yaml` using `TinyTapeout/tt-gds-action@ttsky26d`;
   - git-initialised with one commit, with no `tt/` copy (the action fetches its own tools).
4. **Push it to your own GitHub** (human step):
   ```bash
   cd <output folder> && gh repo create <you>/<name> --public --source . --push
   ```
   Then enable Actions and Pages (Settings → Pages → Source: GitHub Actions).
5. **Wait for the workflows:** `gds` builds the layout, `precheck` runs Tiny Tapeout's checks, `gl_test` runs the
   cocotb test on the laid-out netlist (verification level 4), and `viewer` publishes a 3D view.
6. **Submit** at https://app.tinytapeout.com/: create a project from your repo, choose the shuttle and tile count,
   pay, submit. The form takes its title, description, pinout and docs from `info.yaml` and `docs/info.md`.

**Alternative without a separate repo:** `export_submission_repo(folder, mode="monorepo")` stages the project
under `chiplab/tt_projects/<top>/`. Commit it, then run our workflow:
`gh workflow run tt-gds.yaml -f project_dir=chiplab/tt_projects/<top> -f pdk=sky130A` (GDS, precheck, gate-level
test). The actual submission still needs a standalone repo (steps 3–6).

## Pin map (lab streaming wrapper)

| Pin | Direction | Meaning |
|---|---|---|
| `ui_in[6:0]` | in | data word bits 0–6 |
| `uio_in[7:0]` | in | data word bits 7–14 (`uio_oe` = 0) |
| `ui_in[7]` | in | strobe: a rising edge latches one 15-bit word `{uio_in, ui_in[6:0]}`; hold the data and strobe ≥ 3 clocks |
| `uo_out[6:0]` | out | result bits (which output/lane each bit is: see `info.yaml` pinout or the design's `stream_tt.json`) |
| `uo_out[7]` | out | valid: high once a full frame has been received |
| `clk`, `rst_n`, `ena` | in | clock (default 25 MHz in `info.yaml`), active-low reset, enable |

Inputs are sent in port order, lane 0 first; values wider than 15 bits take several words, least significant first.
A frame has `transfers_per_frame` words (see `stream_tt.json`).

## Testing the real chip later

On the Tiny Tapeout demo board, the RP2040 selects your design and drives `ui_in`/`uio_in` and reads `uo_out`
(MicroPython SDK). Replay the vectors in `test/vectors.json`: send each frame's words with a strobe, wait for
`uo_out[7]`, and compare `uo_out[6:0]` with the expected value. That reaches verification level 5 (real hardware).

## Risks to check before paying

- **Timing at the chosen clock.** The spike chip failed setup at TT's default 50 MHz (−0.57 ns) but passes at
  25 MHz (+19.4 ns), so the lab defaults to 25 MHz. Medical decisions are slow, so a lower clock is fine.
- **Tile utilisation.** Above about 80% routing can fail; `tt-package` picks tiles at 55% target density. The
  spike hardened at 70%.
- **More than 7 output bits** are cut off on `uo_out` (reported as `truncated`); compose fewer outputs or encode them.
- **Public design:** don't submit anything that must stay private.
