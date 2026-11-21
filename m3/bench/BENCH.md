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
  Contention hurts the parallel mode more than the serial one, so the speedup is if anything understated.
- The designs are small (sub-second synthesis each), so per-job overheads weigh more than they would on
  large designs.
