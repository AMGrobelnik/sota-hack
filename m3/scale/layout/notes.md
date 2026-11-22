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

## ternary_10k on gf180: detailed placement failed after 8.5 minutes

- 144,818 gf180 cells; die 5.77 mm², core 5.66 mm².
- Post-placement repair inserted 33,334 buffers and resized 26,093 cells;
  the following detailed placement could not legalise two cells
  (DPL-0036), so LibreLane quit. Peak container memory 1.8 GiB.
- Estimates before repair: leakage 7.2 µW, vectorless energy per
  decision about 200 nJ; the timing at that point (-31.6 ns slack) is
  before buffering and not meaningful.

## 16 kbit constant ROM (folded package) on sky130: stopped at the 1 h cap

- Plain Verilog through the lab's `timing_power_layout` (the `layout` tool
  only takes design ids). 3,221 cells, die 0.053 mm², utilisation 53 %.
- Global routing at 99.6 % usage, overflow 3,156; detailed routing ran
  four iterations and the violations did not fall (24,797 to 26,373).
- Estimates: 124 MHz, leakage 0.009 µW, 14 pJ per word read at 1 MHz.

## ternary_10k on sky130 at 20 % utilisation: lost to a VM stop

Same design (`24fcbc4e7451`), run through the lab's `chiplab layout`
command at 10:00 UTC with a 2 h 15 min hard cap. It did not finish.

| Setting | Earlier run | This run |
|---|---|---|
| Core utilisation target | 40 % | 20 % |
| Die (from utilisation) | 2.94 mm² | 5.84 mm² |
| Placement density | 55 % | 55 % |
| Clock | 50 ns | 50 ns |
| Routing cores | 8 | 16 |
| Layout time limit | 3 h | 2 h 15 min |

The lab's layout tool exposes only the utilisation and the clock. The
placement density (55 %), the routing layers (met1 to met5) and the
global-routing adjustment are fixed inside the lab and stayed as they
were; the die follows from the utilisation. Routing cores come from the
lab's own default on the command line (host cores; the earlier driver
pinned 8).

- Die 2,412 x 2,423 µm (5.84 mm²), core 5.76 mm². Of the sky130 routes in
  the cost table, only ChipFoundry (about 10 mm²) holds it; a Tiny
  Tapeout sky130 slot (0.287 mm²) does not.
- 224,707 cells after repair; placed utilisation 28.2 %. Because the
  placement density stays at 55 %, global placement packed the cells
  into clusters rather than spreading them over the larger die.
- Global routing took 1 h 9 min (50 extra iterations) and finished with
  congestion: 83 % of routing resources used, total overflow 407,192.
  The earlier run used 97 % with an overflow of 593,324. So the lower
  utilisation helped, but met1 and met2 were still 93 % used.
- At 11:38 UTC the colima Docker VM went down. This run did not start or
  stop it. LibreLane lost its container during step 41 (antenna repair),
  before detailed routing, after 1 h 39 min. Peak container memory was
  2.6 GiB.
- Placement-stage estimates (taken at step 37, before global routing;
  the values are identical in steps 37 to 40): slack 25.6 ns at 50 ns,
  so about 41 MHz, a single-clock-period estimate (1 / (50 ns minus
  slack)); leakage 0.68 µW; vectorless energy per decision about 113 nJ,
  which is (internal plus switching power) times the clock period, with
  default toggle rates and one decision per clock period (2.2587 W times
  50 ns = 112.9 nJ); power at 1 Hz about 0.79 µW, which is leakage plus
  113 nJ times 1 Hz.
- Global-routing figures: 3,543 nets over the antenna limit before
  repair, 29.8 m of wire length, routing usage 83.03 % with overflow
  407,192 (met1 93.03 %, met2 93.33 %).
- No GDS, no detailed routing, no timing-power result. There was no
  second attempt at 12 %: the VM was down, and less than an hour was left
  before the 12:40 deadline.

## ternary_30k on sky130: stopped by decision in global routing

Design `399379742efc`, the lab's defaults (core utilisation 40 %, 50 ns
clock). The owner chose to stop this run and spend the remaining time on
a lower-density 10k layout instead, to get one finished layout before the
code freeze. This was a scheduling decision, not a failure of the design.

- The LibreLane container started at 08:15 UTC and was stopped at
  09:57 UTC: 1 h 43 min of layout (job wall time 6,175 s; ingest and
  synthesis were cached).
- It had reached step 38, global routing (started 09:42 UTC), with no
  global routing result written yet. Peak container memory 7.6 GiB.
- At step 37 (placement-stage estimates, no routed wires): 602,096
  cells, die 9.56 mm², core 9.45 mm², utilisation 55.1 %, slack 23.2 ns
  at 50 ns (about 37 MHz), leakage 2.2 µW, about 580 nJ per decision.
- The queue that would have followed it and its driver were stopped with
  it; nothing from that run is still running.

The Docker VM restarted once during the first attempt (04:02 UTC, not
started by this run); that attempt died in global routing and was rerun.
