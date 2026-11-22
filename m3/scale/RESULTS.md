# Scale evidence: per-channel EEG models from 1k to 30k weights

Sixteen designs through the chip lab on one machine (Apple M3 Max, 16 cores, 128 GB),
with the lab's batch tools (`ingest-batch`, `submit-batch`, `simulate-batch`) and
6 CPU workers. Every number below is measured by the lab except where marked
"estimate" or "fit". Machine-readable: [results.json](results.json).

## Short answer

- **Gates per weight, today (default emitter).** Ternary: 8.2 at 1k rising to
  13.6 at 30k (408k gates), so about twice the 6 to 7 expected. 4-bit: 35 to 38
  (1.15 M gates at 30k), about 30 % above the 29 expected. Accumulators widen with
  fan-in, so cost per weight grows with size (area fit: weights^1.16 for ternary).
  So the ballpark (ternary about 6 to 7 gates per weight, 30k about 200k gates;
  4-bit about 29, 30k about 870k) does not hold for today's default emitter: 30k
  ternary is about 2x and 30k 4-bit about 1.3x the expected gate count. With alkaid
  it roughly holds for ternary (8.0, 241k) and beats it for 4-bit (21, 631k).
- **With alkaid** (`optimizer=alkaid`, shared shift-adds): ternary 6.5 to 8.0
  gates per weight (241k gates at 30k), 4-bit 21 to 22 (631k at 30k): 41 % and
  45 % fewer gates than the default at 30k. alkaid solved the 30k 4-bit model in
  120 s and the 30k ternary in 24 s.
- **Weights that fit, one model, fully wired today** (60 % utilisation; ternary /
  4-bit): Tiny Tapeout sky130 16 tiles 2.4k / 0.65k; TT GF180 4x8 4.1k / 1.2k;
  wafer.space quarter 4.0k / 1.2k, half 9.2k / 3.0k, full 23k / 8.4k; ChipFoundry
  10 mm2 about 54k / 21k. alkaid raises each by 40 to 90 %.
- **A 30k-weight per-channel model** fits only ChipFoundry (sky130, about 10 mm2):
  ternary uses 48 % of its usable area (29 % with alkaid). With alkaid, ternary 30k
  also fits a wafer.space full GF180 die (70 %), and 4-bit 30k fits ChipFoundry
  (77 %). Nothing smaller holds 30k weights, and no route holds 30k 4-bit as wired
  today.
- **Channel-serial** (one model copy for 18 EEG channels instead of 18 copies): the
  whole die goes to one model, so the weights per channel model rise 12-fold or more
  (from 4.4k to 54k ternary on ChipFoundry, from 52 to 2.4k on TT sky130); serial
  costs only an 18-bit result register, so it matches the single-model column. With 18
  copies, no route holds more than 2k 4-bit weights per channel (1.3k as wired today).
- **Verification:** all 16 designs bit-exact on 100,000 random inputs (gate netlist
  against the integer model). Formal proof within the 20-minute cap: full golden
  proof for 8 designs (all 1k and 5k except 4-bit 5k default, plus ternary 10k with
  alkaid), gates == RTL only for 3 more (including ternary 30k with alkaid), and a
  timeout for the 5 largest default and 4-bit designs (finding 9).
- **Not run:** layout and timing-power (Docker off on this machine, on purpose); the
  commands and Docker memory for the owner's machine are in
  [docker_runs.md](docker_runs.md).

## Models

[gen_models.py](gen_models.py), fixed seeds, models in [models/](models/). One EEG
channel window of L raw samples, 6-bit signed (as in the lab's eeg_burst example),
hidden layers `clip((W h + b) >> shift, 0, amax)`, one output `score > 0`.

| Size | Inputs | Hidden | Weights | Ternary non-zero | 4-bit non-zero |
| --- | --- | --- | --- | --- | --- |
| 1k | 24 | 40 | 1,000 | 518 | 879 |
| 5k | 32 | 96, 20 | 5,012 | 2,457 | 4,344 |
| 10k | 48 | 160, 14 | 9,934 | 4,936 | 8,636 |
| 30k | 64 | 384, 14 | 29,966 | 15,085 | 25,943 |

Ternary: weights in {-1, 0, +1}, half zeros, 3-bit activations. 4-bit: signed 4-bit
weights from a rounded normal (sigma 3, clipped to -8..7), 4-bit activations.
Weights count every matrix entry, zeros included.

## Per design

| Design | Gates | G/w | Depth | LUTs | sky130 um2 | gf180 um2 | ihp um2 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| q4_30k/default | 1,145,201 | 38.22 | 130 | ~376,283 est. | 8,220,092 | 27,318,957 | 13,493,750 |
| q4_30k/alkaid | 630,518 | 21.04 | 162 | ~163,857 est. | 4,614,492 | 14,486,371 | 7,181,863 |
| ternary_30k/default | 408,000 | 13.62 | 106 | ~134,058 est. | 2,859,525 | 10,109,023 | 4,766,277 |
| ternary_30k/alkaid | 240,751 | 8.03 | 125 | ~62,566 est. | 1,730,049 | 5,403,537 | 2,667,181 |
| q4_10k/default | 379,467 | 38.2 | 120 | ~124,683 est. | 2,882,124 | 9,916,076 | 5,192,407 |
| q4_10k/alkaid | 217,987 | 21.94 | 140 | ~56,650 est. | 1,621,714 | 5,066,552 | 2,489,739 |
| ternary_10k/default | 124,863 | 12.57 | 90 | ~41,027 est. | 933,712 | 3,224,459 | 1,662,680 |
| ternary_10k/alkaid | 77,361 | 7.79 | 116 | 20,298 | 503,279 | 1,624,920 | 817,595 |
| q4_5k/default | 178,076 | 35.53 | 119 | ~58,511 est. | 1,329,478 | 4,412,651 | 2,180,677 |
| q4_5k/alkaid | 108,445 | 21.64 | 135 | ~28,182 est. | 826,617 | 2,592,722 | 1,317,401 |
| ternary_5k/default | 52,791 | 10.53 | 89 | 17,275 | 370,286 | 1,262,980 | 604,162 |
| ternary_5k/alkaid | 35,855 | 7.15 | 97 | 9,023 | 266,965 | 825,720 | 423,788 |
| q4_1k/default | 34,894 | 34.89 | 75 | 11,600 | 251,553 | 857,537 | 435,161 |
| q4_1k/alkaid | 22,396 | 22.4 | 80 | 5,614 | 165,701 | 515,501 | 259,306 |
| ternary_1k/default | 8,164 | 8.16 | 55 | 2,564 | 57,289 | 194,743 | 102,752 |
| ternary_1k/alkaid | 6,494 | 6.49 | 70 | 1,720 | 43,557 | 139,503 | 70,036 |

| Design | Synth s | Peak MB | Sim | Proof | Proof s | fmax sky/gf est |
| --- | --- | --- | --- | --- | --- | --- |
| q4_30k/default | 443.268 | 17397 | bit-exact | timeout | 1777.708 | 19.5 / 7.5 |
| q4_30k/alkaid | 318.044 | 13551 | bit-exact | timeout | 1521.292 | 15.6 / 6.0 |
| ternary_30k/default | 196.857 | 6678 | bit-exact | timeout | 1278.163 | 23.9 / 9.2 |
| ternary_30k/alkaid | 52.669 | 5567 | bit-exact | proved | 1229.144 | 20.3 / 7.8 |
| q4_10k/default | 63.279 | 6441 | bit-exact | timeout | 1275.498 | 21.1 / 8.1 |
| q4_10k/alkaid | 58.031 | 5208 | bit-exact | timeout | 1294.95 | 18.1 / 6.9 |
| ternary_10k/default | 22.947 | 970 | bit-exact | proved | 1606.454 | 28.1 / 10.8 |
| ternary_10k/alkaid | 15.173 | 881 | bit-exact | proved | 93.899 | 21.8 / 8.4 |
| q4_5k/default | 34.582 | 1454 | bit-exact | proved | 1215.047 | 21.3 / 8.2 |
| q4_5k/alkaid | 38.9 | 1214 | bit-exact | proved | 130.326 | 18.8 / 7.2 |
| ternary_5k/default | 15.612 | - | bit-exact | proved | 507.334 | 28.4 / 10.9 |
| ternary_5k/alkaid | 14.859 | 513 | bit-exact | proved | 78.541 | 26.1 / 10.0 |
| q4_1k/default | 5.303 | 172 | bit-exact | proved | 146.518 | 33.8 / 12.9 |
| q4_1k/alkaid | 6.703 | 72 | bit-exact | proved | 57.637 | 31.6 / 12.1 |
| ternary_1k/default | 1.375 | 75 | bit-exact | proved | 37.401 | 46.0 / 17.7 |
| ternary_1k/alkaid | 2.702 | 132 | bit-exact | proved | 20.216 | 36.2 / 13.9 |

Columns: G/w = gates per weight; LUTs = Xilinx 7-series 6-input LUTs from
`count-luts` ("~N est.": it hit its fixed 900 s cap, so the count is an estimate
from gates, finding 2); area = cell area
after mapping to each process's standard cells, before placement; Synth s =
`synthesize` wall time; Peak MB = largest resident memory of the synthesis (Yosys
plus its ABC child, sampled every 2 s; "-": finished between samples); Proof s = `prove-equivalence` wall time
(golden=true, 1200 s cap per proof attempt); fmax = estimate, 1000 / (logic depth x
ns per level), with the ns per level measured on the M3 layouts of the same lab
(sky130 0.395, gf180 1.03); it ignores the longer wires of a large die, so it is
optimistic. No slack is available without layout.

alkaid solve time (the alkaid ingest's wall time; the default ingest of the same
model takes 0.2 to 4 s): 0.9 s (ternary 1k), 4.2 s (5k), 7.4 s (10k), 23.9 s (30k);
4-bit 1.7 s, 8.8 s, 15.7 s, 119.6 s. alkaid implemented every matvec node of every
model (no fallback to the standard code).

## Fit per route

Usable area = route area x utilisation; window registers added at the process's
flip-flop area (64 inputs x 6 bits per held window). Weights from a power-law fit of
cell area against weights through the four measured sizes (exponent 1.16 ternary
default, 1.07 ternary alkaid, 1.03 4-bit default, 0.98 4-bit alkaid); "extrap."
marks a result outside the measured 1k to 30k range.

- single: one model and one window (a one-channel chip).
- 18 par.: 18 copies and 18 windows (18-channel EEG wired one copy per channel,
  which is what the lab builds today).
- serial: one copy evaluated per channel in turn (channel-serial), one window and an
  18-bit result register; the host streams one channel's window at a time, as the
  lab's streaming wrapper already does. Control logic is not counted (well under
  1 %).

Route areas: TT sky130 16 x (161 x 111.52 um) = 0.287 mm2; TT GF180 32 x (346.64 x
160.72 um) = 1.78 mm2; wafer.space GF180 quarter 1.73, half 4.46 (lower bound of 4.46
to 5.02), full 12.92 mm2 core; ChipFoundry about 10 mm2 sky130. Utilisation assumed:
60 % (the lab's own Tiny Tapeout tile estimate), and 40 % as the conservative case
(the M3 layouts were placed at 25 to 40 %).

Weights that fit, utilisation 60% (single / 18 parallel / channel-serial):

| Route | Style | Emitter | Single | 18 par. | Serial |
| --- | --- | --- | --- | --- | --- |
| tt_sky130 | ternary | default | 2.4k | 52 (extrap.) | 2.4k |
| tt_sky130 | ternary | alkaid | 3.4k | 53 (extrap.) | 3.4k |
| tt_sky130 | q4 | default | 655 (extrap.) | 9 (extrap.) | 654 (extrap.) |
| tt_sky130 | q4 | alkaid | 980 (extrap.) | 10 (extrap.) | 978 (extrap.) |
| tt_gf180 | ternary | default | 4.1k | 228 (extrap.) | 4.1k |
| tt_gf180 | ternary | alkaid | 6.5k | 272 (extrap.) | 6.5k |
| tt_gf180 | q4 | default | 1.2k | 44 (extrap.) | 1.2k |
| tt_gf180 | q4 | alkaid | 2.0k | 64 (extrap.) | 2.0k |
| ws_quarter | ternary | default | 4.0k | 219 (extrap.) | 4.0k |
| ws_quarter | ternary | alkaid | 6.3k | 259 (extrap.) | 6.3k |
| ws_quarter | q4 | default | 1.2k | 42 (extrap.) | 1.2k |
| ws_quarter | q4 | alkaid | 2.0k | 60 (extrap.) | 2.0k |
| ws_half | ternary | default | 9.2k | 673 (extrap.) | 9.2k |
| ws_half | ternary | alkaid | 15k | 887 (extrap.) | 15k |
| ws_half | q4 | default | 3.0k | 151 (extrap.) | 3.0k |
| ws_half | q4 | alkaid | 5.2k | 232 (extrap.) | 5.2k |
| ws_full | ternary | default | 23k | 1.8k | 23k |
| ws_full | ternary | alkaid | 42k (extrap.) | 2.7k | 42k (extrap.) |
| ws_full | q4 | default | 8.4k | 478 (extrap.) | 8.4k |
| ws_full | q4 | alkaid | 16k | 773 (extrap.) | 16k |
| chipfoundry | ternary | default | 54k (extrap.) | 4.4k | 54k (extrap.) |
| chipfoundry | ternary | alkaid | 95k (extrap.) | 6.4k | 95k (extrap.) |
| chipfoundry | q4 | default | 21k | 1.3k | 21k |
| chipfoundry | q4 | alkaid | 38k (extrap.) | 2.0k | 38k (extrap.) |

Weights that fit, utilisation 40% (single / 18 parallel / channel-serial):

| Route | Style | Emitter | Single | 18 par. | Serial |
| --- | --- | --- | --- | --- | --- |
| tt_sky130 | ternary | default | 1.7k | none | 1.7k |
| tt_sky130 | ternary | alkaid | 2.3k | none | 2.3k |
| tt_sky130 | q4 | default | 432 (extrap.) | none | 431 (extrap.) |
| tt_sky130 | q4 | alkaid | 633 (extrap.) | none | 631 (extrap.) |
| tt_gf180 | ternary | default | 2.9k | 112 (extrap.) | 2.9k |
| tt_gf180 | ternary | alkaid | 4.4k | 125 (extrap.) | 4.4k |
| tt_gf180 | q4 | default | 799 (extrap.) | 19 (extrap.) | 798 (extrap.) |
| tt_gf180 | q4 | alkaid | 1.3k | 27 (extrap.) | 1.3k |
| ws_quarter | ternary | default | 2.8k | 105 (extrap.) | 2.8k |
| ws_quarter | ternary | alkaid | 4.3k | 116 (extrap.) | 4.2k |
| ws_quarter | q4 | default | 775 (extrap.) | 18 (extrap.) | 774 (extrap.) |
| ws_quarter | q4 | alkaid | 1.3k | 25 (extrap.) | 1.3k |
| ws_half | ternary | default | 6.5k | 436 (extrap.) | 6.5k |
| ws_half | ternary | alkaid | 10k | 552 (extrap.) | 10k |
| ws_half | q4 | default | 2.0k | 92 (extrap.) | 2.0k |
| ws_half | q4 | alkaid | 3.4k | 138 (extrap.) | 3.4k |
| ws_full | ternary | default | 16k | 1.3k | 16k |
| ws_full | ternary | alkaid | 29k | 1.8k | 29k |
| ws_full | q4 | default | 5.7k | 312 (extrap.) | 5.7k |
| ws_full | q4 | alkaid | 10k | 496 (extrap.) | 10k |
| chipfoundry | ternary | default | 38k (extrap.) | 3.1k | 38k (extrap.) |
| chipfoundry | ternary | alkaid | 65k (extrap.) | 4.3k | 65k (extrap.) |
| chipfoundry | q4 | default | 14k | 846 (extrap.) | 14k |
| chipfoundry | q4 | alkaid | 25k | 1.3k | 25k |

30k designs: share of the route's usable area (60%) needed:

| Design | Route | Single | 18 par. | Serial |
| --- | --- | --- | --- | --- |
| q4_30k/default | tt_sky130 | 47.73 | 859.22 | 47.74 |
| q4_30k/default | tt_gf180 | 25.56 | 460.12 | 25.56 |
| q4_30k/default | ws_quarter | 26.34 | 474.16 | 26.34 |
| q4_30k/default | ws_half | 10.22 | 183.92 | 10.22 |
| q4_30k/default | ws_full | 3.53 | 63.49 | 3.53 |
| q4_30k/default | chipfoundry | 1.37 | 24.68 | 1.37 |
| q4_30k/alkaid | tt_sky130 | 26.82 | 482.69 | 26.82 |
| q4_30k/alkaid | tt_gf180 | 13.57 | 244.18 | 13.57 |
| q4_30k/alkaid | ws_quarter | 13.98 | 251.63 | 13.98 |
| q4_30k/alkaid | ws_half | 5.42 | 97.61 | 5.42 |
| q4_30k/alkaid | ws_full | 1.87 | 33.69 | 1.87 |
| q4_30k/alkaid | chipfoundry | 0.77 | 13.87 | 0.77 |
| ternary_30k/default | tt_sky130 | 16.64 | 299.42 | 16.64 |
| ternary_30k/default | tt_gf180 | 9.47 | 170.52 | 9.47 |
| ternary_30k/default | ws_quarter | 9.76 | 175.72 | 9.76 |
| ternary_30k/default | ws_half | 3.79 | 68.16 | 3.79 |
| ternary_30k/default | ws_full | 1.31 | 23.53 | 1.31 |
| ternary_30k/default | chipfoundry | 0.48 | 8.60 | 0.48 |
| ternary_30k/alkaid | tt_sky130 | 10.08 | 181.47 | 10.08 |
| ternary_30k/alkaid | tt_gf180 | 5.07 | 91.34 | 5.08 |
| ternary_30k/alkaid | ws_quarter | 5.23 | 94.13 | 5.23 |
| ternary_30k/alkaid | ws_half | 2.03 | 36.51 | 2.03 |
| ternary_30k/alkaid | ws_full | 0.70 | 12.60 | 0.70 |
| ternary_30k/alkaid | chipfoundry | 0.29 | 5.21 | 0.29 |

## Findings

1. **A timed-out Yosys step leaves its ABC process running.** The lab's
   `hw.yosys.run` uses `subprocess.run(timeout=...)`, which kills Yosys only. Yosys
   starts ABC as `sh -c yosys-abc ...`; when Yosys dies, the shell and ABC are
   re-parented to launchd and keep computing. Seen in the sweep after every
   `count-luts` timeout: 10 orphaned `sh` + `yosys-abc` pairs, 6 after the 900 s cap
   (14 to 15 minutes old, 8.5 to 9.6 CPU minutes each) and 4 after the 3600 s LUT
   retries (59 minutes old, 49 to 50 CPU minutes each); `orphans_reaped` in
   results.json lists them (it also lists 2 pairs left by stale duplicate jobs I
   killed by hand, and the 2 false positives of finding 8). The 30k 4-bit one was still running 10
   minutes later at 25 to 37 % CPU and 600 MB, its CPU time still climbing, until it
   was killed by hand. The same `run()` builds both netlists of every formal proof
   (`prove-equivalence` steps blif_rtl and blif_gate) and every synthesis and mapping,
   so a timed-out proof leaves ABC behind the same way. Reproduced on its own with
   [orphan_check.py](orphan_check.py) (lab `count_luts` on the 1k 4-bit design, cap
   set to the middle of its ABC window, 190 s): stock lab, one orphaned
   `sh` + `yosys-abc` pair; with the fix, none. Fix:
   [proposed/yosys-timeout-kill-group.patch](proposed/yosys-timeout-kill-group.patch)
   (Yosys in its own session, the whole process group killed on timeout or
   interrupt; adds `tests/test_yosys_timeout.py`, which fails on the stock lab with a
   leftover child and passes with the patch). Until it lands,
   [reap_orphans.py](reap_orphans.py) cleans up after a run. The Verilator lint call
   has the same shape (a Perl wrapper starting `verilator_bin`); not observed here.
2. **`count-luts` (xc7) hits its fixed 900 s cap from about 100k gates** (ternary
   10k and 30k, 4-bit 5k and up, default and alkaid). Yosys `synth_xilinx` with ABC9
   is about 50 to 100 times slower than the lab's generic synthesis of the same design
   (4-bit 1k: 278 s against 5 s), and `count-luts` takes no timeout argument.
   `synthesize` with `target=xc7` and its own `timeout` runs the same flow;
   [lut_retry.py](lut_retry.py) used it with a 3600 s cap on four of them (ternary 30k and 10k, 4-bit 10k and 5k,
   default emitter), and all four timed out again at 3600 s. The largest design whose
   LUT count finished is ternary 10k with alkaid (77k gates, 20,298 LUTs in under
   900 s). The LUT column therefore marks the rest as estimates: gates x 0.329 LUTs
   per gate (default) or 0.260 (alkaid), a least-squares slope through the designs
   whose count finished (3 default, 4 alkaid). The alkaid retries were not run.
3. **Cost per weight grows with size on the default emitter, much less with alkaid.**
   Ternary gates per weight 8.2, 10.5, 12.6, 13.6 from 1k to 30k: wider accumulators
   for larger fan-in (64 inputs and 384 hidden units at 30k). alkaid shares partial
   sums across rows and gets relatively better as layers grow (ternary 6.5 to 8.0;
   4-bit 22.4 at 1k to 21.0 at 30k, area exponent below 1).
4. **alkaid trades depth for area.** Logic depth rises 15 to 30 % (ternary 30k 106 to
   125 levels, 4-bit 30k 130 to 162), so the fmax estimate drops by the same share;
   still about 15 MHz on sky130 for the 30k 4-bit design, far above what a sensor
   needs.
5. **Memory.** Synthesis of the 1.15 M-gate design peaks at 17.4 GB (Yosys plus
   ABC), each process mapping at about 10.8 GB, the xc7 LUT run at 10.5 GB. Six
   workers on 30k 4-bit designs therefore need about 60 GB. The GPU-lane worker kept
   about 18 GB after simulating the 1.15 M-gate netlist (PyTorch MPS cache), until it
   exited.
6. **Batch order.** The lab's queues are first in, first out, with no priority: the
   largest-first order holds only as far as the submission order does. The alkaid
   designs finished ingesting smallest first, so their hardware jobs queued smallest
   first.
7. **Process mapping of the 1.15 M-gate design takes 7.7 to 9.2 minutes per process
   against a fixed, unexposed 900 s cap** in `hw.pdk.map_to_process`; a design about
   twice that size would time out there too.
8. **My own sweep failure, fixed.** The first two sweep runs died at the formal
   proofs: the first version of the orphan reaper walked up from every `yosys-abc`
   past any non-Yosys parent, so the formal check's `cec` (ABC started directly by the
   lab's Python worker) looked orphaned and the reaper killed the worker and the sweep
   driver. Fixed (only `sh` wrappers are walked), and the sweep was resumed in the
   same lab home: every finished step came from the lab's result cache with its
   original timings, so only the proofs and the LUT retries ran again.

9. **Formal proofs stop at about 100k to 180k gates within the 20-minute cap.** The
   lab's golden proof has two stages: ABC `cec` of the gate netlist against the RTL,
   then the RTL against the golden integer model (one miter, `iprove`).
   - Full proof, both stages: all 1k and 5k designs except 4-bit 5k default, plus
     ternary 10k with alkaid (8 designs, 20 to 507 s).
   - Gates == RTL only, the golden stage inconclusive in its budget: ternary 30k
     with alkaid (241k gates; `cec` itself took 105 s, the whole call 1229 s),
     ternary 10k default (1606 s) and 4-bit 5k default (1215 s). The lab reports
     these as proved at level 2 ("RTL == IR by construction and fuzz tests").
   - Timeout at the `cec` stage (1200 s cap on the ABC call): ternary 30k default,
     4-bit 30k (both emitters) and 4-bit 10k (both emitters). Log tail of each:
     `abc cec ... timed out after 1200s`. Wall time 1275 to 1778 s, because
     building the two BLIF netlists before `cec` is not under the cap.
   - Wider default accumulators are harder for `cec` than alkaid's shared sums at
     the same size (ternary 30k: alkaid proved, default timed out).
   - The proof timeouts left no solver process behind: `cec` is a direct child of
     the lab worker and is killed by `subprocess.run`; the process list after each
     timeout and the reaper showed no orphan from a proof. The orphans of finding 1
     come only from Yosys steps (which also build the proof's BLIF netlists, so a
     timeout there would leave one; none happened).

## What was not run

- Layout and timing-power for ternary 10k and 30k on sky130 and gf180: Docker is off
  on this machine tonight, and the lab runs both only through LibreLane in Docker.
  Exact commands and the Docker memory each needs (12 GB per 10k run, 32 to 64 GB per
  30k run): [docker_runs.md](docker_runs.md).
- 30k 4-bit layout: not planned (1.15 M gates default, 631k with alkaid); estimate only.
- Slack and fmax from layout: none without layout; the fmax column is an estimate.

## Reproduce

```bash
python m3/scale/gen_models.py m3/scale/models
python m3/scale/sweep.py --models m3/scale/models --out raw.json      # lab env set
python m3/scale/make_results.py --raw raw.json --out m3/scale/results.json
python -m pytest m3/scale/test_scale.py   # generator and results builder, 12 tests
```

The lab environment: `CHIPLAB_USER_DIR` and `CHIPLAB_CONFIG` pointing at the lab
install, `CHIPLAB_HOME` at a fresh lab home (its result cache lives there),
`CHIPLAB_CPU_WORKERS=6`, run under `memgate`.
