# P2 layouts: spike, torchlogix and fusion chips

Tool: LibreLane v3.0.14 (Docker image ghcr.io/librelane/librelane:3.0.14, arm64, colima vz VM with 12 CPUs and 47 GiB). Machine: Apple M3 Max, 16 cores, 128 GB.
Every number below is from a real LibreLane layout run (basis: layout) unless marked.

## Area and cells

| Chip | Process | Cell µm² | Die µm² | Cells | GE |
| --- | --- | --- | --- | --- | --- |
| spike | gf180 | 56768 | 181758 | 2313 | 5172 |
| spike | ihp | 21356 | 60892 | 2012 | 2942 |
| torchlogix | sky130 | 2270 | 7442 | 232 | 605 |
| torchlogix | gf180 | 6439 | 15055 | 292 | 587 |
| torchlogix | ihp | 2607 | 8838 | 241 | 359 |
| fusion | sky130 | 24870 | 63319 | 2420 | 6626 |
| fusion | gf180 | 65735 | 202744 | 2650 | 5989 |
| fusion | ihp | 24716 | 68570 | 2339 | 3406 |

## Timing, power, run time

| Chip | Process | Clk ns | Slack ns | µW | Leak µW | pJ | s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| spike | gf180 | 40 | -13.971 | 49924.6 | 0.3036 | 1996.971 | 104 |
| spike | ihp | 20 | 10.366 | 4981.9 | 1.8974 | 99.6 | 272 |
| torchlogix | sky130 | 20 | 8.527 | 493.3 | 0.0048 | 9.867 | 108 |
| torchlogix | gf180 | 20 | -9.83 | 4587.4 | 0.0304 | 91.747 | 68 |
| torchlogix | ihp | 20 | 12.789 | 181.6 | 0.1817 | 3.628 | 130 |
| fusion | sky130 | 20 | -0.931 | 15725.1 | 0.0544 | 314.501 | 196 |
| fusion | gf180 | 40 | -13.052 | 51500.8 | 0.3564 | 2060.018 | 141 |
| fusion | ihp | 20 | 10.056 | 5500.3 | 2.1575 | 109.963 | 254 |

Columns: Cells = placed standard cells without tap and filler cells; GE = cell area / NAND2 area;
Slack = worst setup slack at the clock; µW and Leak µW = vectorless total and leakage power;
pJ = energy per decision (dynamic power x clock period); s = layout flow time.

## Synthesized (Yosys + ABC generic gates, no layout)

| Chip | Design id | Gates | Depth | Synth s |
| --- | --- | --- | --- | --- |
| spike | 765fa47586bd | 2285 | 51 | 0.68 |
| torchlogix | 174157d29a95 | 243 | 29 | 0.38 |
| fusion | 261bd9ee3b04 | 2622 | 53 | 0.99 |

## Failed attempts before the result above

- spike on gf180: clock 20 ns, util 40%: ERROR: Missing `-liberty liberty_file' option!
- spike on gf180: clock 40 ns, util 25%: ERROR: Missing `-liberty liberty_file' option!
- spike on gf180: clock 20 ns, util 40%: failed (see raw json)
- torchlogix on gf180: clock 20 ns, util 40%: ERROR: Missing `-liberty liberty_file' option!
- torchlogix on gf180: clock 40 ns, util 25%: ERROR: Missing `-liberty liberty_file' option!
- fusion on gf180: clock 20 ns, util 40%: ERROR: Missing `-liberty liberty_file' option!
- fusion on gf180: clock 40 ns, util 25%: ERROR: Missing `-liberty liberty_file' option!
- fusion on gf180: clock 20 ns, util 40%: failed (see raw json)

The gf180 failures were a lab config bug, not the design: LibreLane 3 no longer reads
LIB_SYNTH, so synthesis got no liberty file. The gf180 rows were re-run through
scripts/layout_cli.py, which sets LIB per 3.3 V corner (proposed/gf180-lib.patch).
