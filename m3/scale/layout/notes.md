# Scale evidence: layouts

Work in progress; `results.json` beside this file holds every number.

Machine: colima VM with 8 CPUs and 16 GB, the lab's pinned LibreLane image
`ghcr.io/librelane/librelane:3.0.14` (LibreLane v3.0.14), one layout at a
time, the lab's defaults (core utilisation 40 %, placement density 55 %,
50 ns clock on sky130, 100 ns on gf180, decision rate 1 Hz). Models come
from `m3/scale/models/` of the scale branch (ternary 10k and 30k weights).

## ternary_10k on sky130: stopped at the 3 h cap in detailed routing

- 124,863 generic gates; 173,213 sky130 cells after placement.
- Die 2.94 mm², core 2.88 mm², placed utilisation 49.9 %.
- Global routing used 97 % of the routing resources with a total overflow
  of 593,324 (it took about 45 minutes).
- Detailed routing ran three iterations (40, 28, 27 minutes) and was still
  at 1.09 million violations, mostly shorts on met1 and met2, when the
  3 h cap stopped it. Peak container memory 7.8 GiB, so memory was not the
  limit: congestion was.
- Estimates from the last completed step (global-route parasitics):
  slack 24.5 ns at 50 ns, so about 39 MHz; leakage 0.61 µW; vectorless
  energy per decision about 106 nJ; power at 1 Hz about 0.71 µW.

Finding: at the lab's default 40 % utilisation the XOR-heavy adder trees of
a 125k-gate model do not route. A second run needs a lower utilisation (for
example 20 %) or a bigger die, and more time for detailed routing.

The Docker VM restarted once during the first attempt (04:02 UTC, not
started by this run); that attempt died in global routing and was rerun.
