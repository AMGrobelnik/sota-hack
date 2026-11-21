# P3: fair speed benchmark of the chip lab

## 1. Plan, written before the long runs

### What is measured

Throughput of the lab's generic synthesis (`synthesize`, Yosys + ABC, `effort=fast`) in designs per hour,
on one fixed set of candidate designs, in four modes:

- (a) baseline: one warm Python process calls the lab's `synthesize` tool on each design in turn.
- (b) the lab's `synthesize-batch`: jobs on the lab's Huey CPU lane, with the lab's own lane size for this
  machine (`config.lanes()`: cores - 1 = 15 workers on this 16-core M3 Max).
- (c) cached re-run: the same batch again (and the same serial calls again) after (b) filled the cache.
- (d) the lab's `estimate-batch` gate estimate against the gate counts (b) synthesised: r² and time.

### The designs

`gen_designs.py` builds 163 designs from the lab's only fixture, `chiplab/fixtures/spike_best.json`
(intnn, 8 inputs × 6 bit, 16 hidden, ternary): the fixture itself plus three designs at each point of a grid of
hidden width H ∈ {4, 8, 12, 16, 24, 32}, input bits ∈ {4, 6, 8} and inputs L ∈ {4, 8, 12}. Weights are ternary
with the fixture's own zero rate; biases are drawn from the fixture's own bias values. Random siblings
sometimes collapse to a constant output (0 gates); a first pilot had 6 such designs out of 109, so the generator
synthesises each draw once in a throwaway lab home and replaces a constant one with the next weight seed (the
dropped names are listed in `designs.json`). Every design enters the lab through its own `ingest-model`
(format intnn). The file is generated once and the same `designs.json` is used by every mode and every run.

### Why the baseline is fair

- Same designs, same order, same lab commit, same Yosys binary and flags, same machine, same time window.
- The baseline is not slowed: it keeps one warm process (how a person scripting the lab would run it) and calls
  the tool function directly, with no job queue, no SQLite and no polling overhead.
- Yosys is launched once per design in both modes, so its start-up cost is in both.
- Start-up costs are reported apart from the timed step: Python import of the lab for (a); starting the
  workers until a no-op probe job completes for (b). Ingest (IR, Verilog, Verilator lint) is timed separately
  and not part of either number.
- Cold where it must be: each run of (a) and of (b) uses a brand-new, empty lab home (`CHIPLAB_HOME`), so the
  result cache, job database and design folders start empty. Before the timed step the script asserts that
  the cache holds no `synthesize` result for any design, and every result's `cached` flag is written to
  `results/designs.csv` (all must be false for (a) and (b), all true for (c)). The OS file cache (Yosys binary,
  cell libraries) is warm for both modes alike; Yosys keeps no result cache of its own.
- The order of (a) and (b) alternates between runs (a b, b a, a b) so drift in machine load does not favour
  one mode. Three runs per mode; the median is reported with the min and max.
- Correctness: both modes must give the same gate count and depth for every design.

### What would make it unfair (and is avoided)

- Comparing a cold baseline with a warm cache, or different design sets, tool versions or effort settings.
- Charging the baseline a fresh Python start (or a CLI call) per design while the batch keeps warm workers.
- Hiding the batch's worker start-up, or the baseline's import, inside one number but not the other.
- Reporting the best run instead of the median.
- Quoting the cached re-run (c) as the speedup: it measures the cache, not synthesis.

### Known limits, stated up front

- The machine is shared tonight: other agents' jobs (SMT solvers, a VM, browsers) run at the same time. Load
  average, free memory and the five busiest processes are logged at the start of every timed step.
  (Written before the runs: "contention hurts the parallel mode more". The data says otherwise; see 2.5.)
- The designs are small (sub-second synthesis each), so per-job overheads weigh more than they would on
  large designs.

## 2. Results

All numbers: Apple M3 Max, 16 cores (12 performance + 4 efficiency), 128 GB, macOS 27.2.1, Python 3.12.13,
Yosys 0.71+77 (OSS CAD Suite), lab code at `021f68d` (branch commit `2a7b1be` adds only this folder).
Command: `bash m3/bench/run_all.sh <worktree> <fresh homes dir> m3/bench/results 3`, run 21:10 to 21:25 on
21 Nov 2026; 163 designs, 3 runs per mode, a and b interleaved (a b, b a, a b). Measured kind: synthesized
(Yosys generic gates), wall clock. Raw data: `results/runs.csv` (one row per run and mode),
`results/designs.csv` (one row per design, run and mode, 978 rows), summaries `results/summary.json`
(`summarize.py`) and `results/analysis.json` (`analyze.py`).

### 2.1 Headline

**The lab's `synthesize-batch` (15 workers) synthesises 4.2× more designs per hour than the same tool called one
design at a time in one warm process: median 34,938 against 8,345 designs/hour, 3 cold runs each; per-run
paired ratio 3.4× to 6.0× (median 4.3×).** The only run on a lightly loaded machine (load 22) gave 3.4×; treat
3.4× as the conservative figure.

Held equal: the same 163 designs in the same order, the same lab commit, Yosys binary and flags
(`target=generic`, effort fast), the same machine, the same 15-minute window; cold caches in both (fresh lab
home per run, asserted empty before the timed step; 0 of 978 cold rows came back `cached`). Gate count and
depth agree for every design across all 6 cold runs and both modes (0 mismatches).

Not covered: ingest (IR, Verilog, Verilator lint, timed apart and serial in both modes), layout, simulation,
formal checks, FPGA targets, designs larger than 5,778 gates, other machines.

### 2.2 Designs per hour, all modes

| Mode | Workers | Median/h | Min/h | Max/h |
|---|---|---|---|---|
| (a) one at a time | 1 | 8,345 | 5,788 | 9,778 |
| (b) synthesize-batch, cold | 15 | 34,938 | 33,582 | 35,602 |
| (c) batch re-run, cached | 15 | 135,518 | 86,180 | 195,171 |
| (c) serial re-run, cached | 1 | 30,671 | 21,940 | 69,179 |
| (d) estimate-batch | 1 | 6,821,821 | 5,452,313 | 7,386,075 |

Wall seconds for 163 designs, median (min to max): (a) 70.3 (60.0 to 101.4); (b) 16.8 (16.5 to 17.5);
(c) batch 4.3 (3.0 to 6.8), serial 19.1 (8.5 to 26.7); (d) 0.086 (0.079 to 0.108).
Start-up, outside these numbers: lab import 0.05 s for (a); starting the 15 workers until a probe job finished
0.31 to 0.54 s for (b). Gates per design: 74 to 5,778, median 1,003.

(c) measures the content cache, not synthesis, and is not a speedup claim. A cache hit still costs about
0.05 to 0.16 s per design when called one at a time in a process.

### 2.3 End to end, ingest included

Ingest is serial in both modes (the lab has no batch ingest) and took 22.6 to 80.6 s for the 163 designs
depending on machine load, as long as serial synthesis itself. With ingest and start-up added, the batch path
is 1.4× faster (ratio of medians, 130.9 s against 94.1 s), paired per run 0.88×, 1.86×, 1.78×.
**In run 1 the batch path was slower end to end** (94.1 s against 82.7 s) because its ingest ran under load
80 and took 76.2 s against 22.6 s for the serial run's ingest at load 22. Parallel ingest is the next
bottleneck for the lab; it is not measured here.

### 2.4 Where the batch is slower

Each Yosys job takes longer inside the batch than alone (median of per-design `seconds`, 3 runs):

| Design size (gates) | n | Alone s | In batch s | Ratio |
|---|---|---|---|---|
| 74 to 677 | 54 | 0.21 | 0.47 | 2.1× |
| 687 to 1,498 | 54 | 0.32 | 0.86 | 2.7× |
| 1,504 to 5,778 | 55 | 0.54 | 1.93 | 3.6× |

The sum of job times is 60.3 s alone and 184.4 s in the batch: 15 workers on 12 performance cores plus a
shared machine give about 11 jobs' worth of useful parallelism, and the per-job slowdown grows with design
size (memory bandwidth and efficiency cores). The batch wins on throughput only; one design's latency is worse.

### 2.5 Noise and how much it limits the claim

Load average at the start of the timed steps ranged from 22 to 201 on 16 cores (other packages' SMT solvers
and a layout VM). The batch was stable (16.5 to 17.5 s, a 6 % spread), the serial baseline was not (60 to 101 s,
1.7× spread) and slowed with load: 60 s at load 22, 70 s at load 201, 101 s at load 188. Fifteen
processes take a larger share of a contended CPU than one does, so on this shared machine the load inflates
the speedup rather than hiding it. The 4.2× median carries that bias; the quiet-machine pair (3.4×) is the
better guide, and with one quiet run the true quiet-machine figure is uncertain by at least the spread
between 3.4× and 4.3×.

### 2.6 Estimate accuracy (d)

The lab has no estimate of synthesis time; its estimate is `estimate-batch`'s gate count, which the lab uses
to rank candidates before synthesis. Scored against the synthesized gates of the same 163 designs:

- Default coefficients as shipped (fresh home, no `estimator.json`): r² = -4.94, median estimate 2.74× the
  real count. It ranks designs but its absolute numbers are not usable until refit.
- After the lab's own `refit` on two thirds of the designs, scored on the held-out third (3 folds, 162
  designs; the fixture is excluded): r² = 0.918, median absolute error 17.5 %.
- As a proxy for synthesis time: the held-out estimate explains r² = 0.83 of the variance in serial Yosys time
  (real gate count: 0.90).
- Time: 0.086 s median for all 163 designs (3 runs), about 800× faster than one-at-a-time synthesis.

The estimate numbers are identical in all 3 runs (deterministic); only its time varies.

### 2.7 On the new lab commit

The lab owner's fix commit had not landed on `origin/ant/chip-lab` when these numbers were written (head still
`021f68d`, checked with `git fetch` at the end of this work). All numbers above are from `021f68d`.
