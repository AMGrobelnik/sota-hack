# P2 layouts: spike, torchlogix and fusion chips

Tool: LibreLane v3.0.14 (Docker image ghcr.io/librelane/librelane:3.0.14, arm64, colima vz VM with 12 CPUs and 47 GiB). Machine: Apple M3 Max, 16 cores, 128 GB.
Every number below is from a real LibreLane layout run (basis: layout) unless marked.

## Area and cells

| Chip | Process | Cell µm² | Die µm² | Cells | GE |
| --- | --- | --- | --- | --- | --- |
| spike | gf180 | failed | | | |
| spike | ihp | 21356 | 60892 | 2012 | 2942 |
| torchlogix | sky130 | 2270 | 7442 | 232 | 605 |
| torchlogix | gf180 | 6439 | 15055 | 292 | 587 |
| torchlogix | ihp | 2607 | 8838 | 241 | 359 |
| fusion | sky130 | 24870 | 63319 | 2420 | 6626 |
| fusion | gf180 | failed | | | |
| fusion | ihp | 24716 | 68570 | 2339 | 3406 |

## Timing, power, run time

| Chip | Process | Clk ns | Slack ns | µW | Leak µW | pJ | s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| spike | gf180 | 40 | failed | | | | |
| spike | ihp | 20 | 10.366 | 4981.9 | 1.8974 | 99.6 | 272 |
| torchlogix | sky130 | 20 | 8.527 | 493.3 | 0.0048 | 9.867 | 108 |
| torchlogix | gf180 | 20 | -9.83 | 4587.4 | 0.0304 | 91.747 | 68 |
| torchlogix | ihp | 20 | 12.789 | 181.6 | 0.1817 | 3.628 | 130 |
| fusion | sky130 | 20 | -0.931 | 15725.1 | 0.0544 | 314.501 | 196 |
| fusion | gf180 | 40 | failed | | | | |
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

## Failures

spike on gf180 (2 attempts):

```text
                 running the flow:                                           
                    Synthesis: subprocess (1, ['yosys', '-y',                   
                    '/nix/store/f8bhalkl3s4vjwd7g271xz92bra8yrm5                
                    -python3-3.13.9-env/lib/python3.13/site-pack                
                    ages/librelane/scripts/pyosys/synthesize.py'                
                    , '--', '--config-in',                                      
                    '~/projects/sota-hack/.worktrees                
                    /m3-layouts/chiplab/runs/designs/765fa47586b                
                    d/layout_gf180mcuD/runs/chiplab/06-yosys-syn                
                    thesis/config.json', '--extra-in',                          
                    '~/projects/sota-hack/.worktrees                
                    /m3-layouts/chiplab/runs/designs/765fa47586b                
                    d/layout_gf180mcuD/runs/chiplab/06-yosys-syn                
                    thesis/extra.json', '--output',                             
                    '~/projects/sota-hack/.worktrees                
                    /m3-layouts/chiplab/runs/designs/765fa47586b                
                    d/layout_gf180mcuD/runs/chiplab/06-yosys-syn                
                    thesis/chip_765fa47586bd.nl.v']) failed                     
[21:13:00] ERROR    LibreLane will now quit.                     __main__.py:190
```

fusion on gf180 (2 attempts):

```text
                 running the flow:                                           
                    Synthesis: subprocess (1, ['yosys', '-y',                   
                    '/nix/store/f8bhalkl3s4vjwd7g271xz92bra8yrm5                
                    -python3-3.13.9-env/lib/python3.13/site-pack                
                    ages/librelane/scripts/pyosys/synthesize.py'                
                    , '--', '--config-in',                                      
                    '~/projects/sota-hack/.worktrees                
                    /m3-layouts/chiplab/runs/designs/261bd9ee3b0                
                    4/layout_gf180mcuD/runs/chiplab/06-yosys-syn                
                    thesis/config.json', '--extra-in',                          
                    '~/projects/sota-hack/.worktrees                
                    /m3-layouts/chiplab/runs/designs/261bd9ee3b0                
                    4/layout_gf180mcuD/runs/chiplab/06-yosys-syn                
                    thesis/extra.json', '--output',                             
                    '~/projects/sota-hack/.worktrees                
                    /m3-layouts/chiplab/runs/designs/261bd9ee3b0                
                    4/layout_gf180mcuD/runs/chiplab/06-yosys-syn                
                    thesis/chip_261bd9ee3b04.nl.v']) failed                     
[21:15:37] ERROR    LibreLane will now quit.                     __main__.py:190
```

