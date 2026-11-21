## gf180 with the official fix (lab 0174b1d)

Lab merged into this branch at 0174b1d (contains the lab's own gf180 liberty fix and the 40 ns default clock);
no local patch applied (`git status` clean of lab files). Three chips submitted as one
`chiplab submit-batch` of tool `layout` (pdk gf180, no clock given so the lab default applies,
core utilisation 25%), docker lane with 2 workers, one run each, M3 Max,
LibreLane 3.0.14. Batch wall time 298 s for all three (two at a time).

| Chip | Done | Clk ns | Cell µm² | Die µm² | GE |
| --- | --- | --- | --- | --- | --- |
| spike | yes | 40 | 56768 | 181758 | 5172 |
| fusion | yes | 40 | 65735 | 202744 | 5989 |
| torchlogix | yes | 40 | 6173 | 22324 | 562 |

| Chip | tt ns | ss ns | ff ns | Setup vio | Hold vio | DRC |
| --- | --- | --- | --- | --- | --- | --- |
| spike | 13.298 | -13.971 | 24.676 | 1 | 0 | 0 |
| fusion | 13.56 | -13.052 | 24.739 | 4 | 0 | 0 |
| torchlogix | 20.72 | 1.082 | 28.993 | 0 | 0 | 0 |

| Chip | Power µW | Leak µW | pJ/decision | Run s |
| --- | --- | --- | --- | --- |
| spike | 49925 | 0.304 | 1997 | 254 |
| fusion | 51501 | 0.356 | 2060 | 274 |
| torchlogix | 1904 | 0.034 | 76 | 58 |

Slack = worst setup slack per STA corner (tt 25C 3.3V, ss 125C 3.0V, ff -40C 3.6V); the lab reports the
worst of the three as the chip's slack. Power is OpenSTA vectorless at the nominal corner;
pJ per decision = dynamic power x clock period. Run s = job run time in the lab queue (two jobs shared
the docker engine with each other and with other agents' runs, so it is longer than a lone run).

Findings:

- The official fix reproduces the patched run exactly for spike and fusion (identical cell area, die,
  slack, power and energy), so the lab's fix is equivalent to proposed/gf180-lib.patch.
- proposed/gf180-lib.patch is no longer needed: it reverse-applies cleanly onto the merged lab (the lab
  already contains the same change, commit b77cc76), and the file now carries a SUPERSEDED note.
- At the default 40 ns clock only torchlogix meets timing at all three corners (worst +1.08 ns at ss).
  Spike and fusion meet it at tt and ff but miss at the slow corner (-13.97 and -13.05 ns), so their
  worst slack is negative; a clock near 55 ns would close them at ss.
- Spike and fusion in the earlier table were run at 40 ns and 25% utilisation; torchlogix gf180 here is
  a new row at 40 ns (the earlier 20 ns torchlogix row missed timing at -9.83 ns).
- Pictures: spike, fusion and torchlogix `_gf180mcuD_official.png` in this folder.
