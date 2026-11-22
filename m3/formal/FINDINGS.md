# P4: fast golden proof (gate netlist == golden model, every input)

**Result: done.** The golden equivalence of the spike chip is proved in **3.3 to 3.8 s** wall (3 runs), and of the
3-head fusion chip in **8.4 to 8.9 s** (3 runs), with `scripts/golden_proof.py --engines iprove`. Through the lab's
own `prove(golden=True)` with both proposed patches applied: spike 4.0 to 4.4 s, 3-head chip 10.9 to 12.1 s.
The lab code at 021f68d cannot prove the spike at all (it reports a false failure after 47 s, see "Why").
Target was under 5 minutes.

**On the lab's new commit b77cc76** (which contains both patches, byte for byte): the lab's own
`prove(golden=True)` proves the spike in **3.7 to 3.9 s** and the 3-head chip in **9.1 to 9.6 s** (3 runs each),
the lab's golden-proof tests pass, and all mutated golden models are caught (see "Lab's new commit").

## How it was measured

- Machine: Apple M3 Max, 16 cores, 128 GB, macOS 27.2.1. Yosys 0.71+77 and yosys-abc, sby, eqy, bitwuzla,
  yices and z3 from the lab's OSS CAD Suite in the shared tool folder (`.worktrees/_m3/chiplab-home`).
- The Mac was shared with the four other packages (layouts, benchmark, examples) during every run; the
  1-minute load average was 60 to 160 on 16 cores (logged before each timed run in the `[remeasure]`,
  `[iprove]` and `[check]` lines). Times are wall clock of the whole command, so they are upper bounds for an
  idle machine.
- Every number below is from one command run on this Mac; "3 runs" means three consecutive runs, min to max.
  Raw results of every run: `results/all.jsonl` (collected by `scripts/collect.py` from the run folders).
- Lab code: `origin/ant/chip-lab` at 021f68d, unchanged except where a row says "patch".

## Designs

| Name | Design id | Built from | Gates | Depth |
|---|---|---|---|---|
| spike | 765fa47586bd | fixture `spike_best.json`, intnn ingest | 2,285 | 51 |
| 3-head | 0246527da711 | spike + 2 variants, `compose-chip`, 2-of-3 | 5,588 | 59 |

Gate counts and depth are the lab's `synthesize` metrics. The two variant heads are deterministic edits of
the fixture (input lanes rotated and bias shifted; first layer negated and second-layer weights rotated), made
by `scripts/setup_designs.py`: synthetic, no recordings, no patient data.

## Why the lab's golden proof does not finish today

The lab's golden proof is two proofs chained (`chiplab/verify/formal.py`):

- **B**: gate netlist == production RTL (`design.v`), ABC `cec` on two BLIFs. Fast: 1.0 s on the spike
  (`scripts/repro_lab.py`, 1 run), 1.2 to 4.2 s in all later runs.
- **A**: production RTL == golden model of the IR (`emit/golden.py`), node by node, each node a small miter
  with inputs clamped to derived ranges, proved by Yosys `sat`.

Measured with `scripts/repro_lab.py 765fa47586bd 600` (lab code unchanged, 1 run): proof A spends 45.9 s on
the first 16-lane x 8-input matvec node (`l0_mv`; 64 s in a second run under load), proves the shift node,
then **fails in 0.04 s on the clip node `l0`** with the Yosys error
`No matching port in gate module was found for \o`. Cause: `emit_golden` ends with
`text.replace("[63:0]", f"[{wide - 1}:0]")`, meant for its 64-bit internal lane wires, which also rewrites
the clip node's real 64-bit output port (16 lanes x 4 bits) to `[9:0]`. The miter cannot be built, and the
lab reports `proved: false`. This is a false failure (no counterexample exists), so the golden proof cannot
pass on the spike however long it runs. `proposed/formal.patch` fixes it (only `signed [63:0]` lane wires
are rewritten).

Why gates vs golden in one step is slow: the lab's synthesis (`alumacc`/`maccmap` + ABC) restructures every
adder tree, so the gate netlist and the golden model share almost no internal equal signals. SAT sweeping
then has nothing to merge and faces the full multiplier-adder equivalence: ABC `&cec` on that miter ran out
of its 600 s limit on the spike, and every other solver ran out of its limit (tables below).

## The recipe that works ("chain")

1. **P1: production RTL == golden, whole design, one miter, every input.** Both sides are lowered with
   Yosys `techmap` only (no `alumacc`/`maccmap`), so each `a + b + c` stays a ripple-adder chain in source
   order. The golden model and the production emitter add the same terms in the same order, so their partial
   sums are equal signals and ABC finds and merges them with small SAT calls. Engine: ABC `iprove` on the
   AIGER miter (`&cec -m` and bitwuzla also prove it, slower on the 3-head chip).
2. **P2: gate netlist == production RTL**: the lab's proof B unchanged.
3. P1 and P2 are both proofs over all 2^n input values, so gates == golden for every input (equality is
   transitive). No range assumptions are used anywhere.

Soundness check: three single-point mutations of the golden model (one weight sign flipped, one bias + 1,
the final threshold + 1) must each make P1 fail. All three were caught with a counterexample on both chips,
for every engine used in the final recipe (`--mutants`, 1 run per engine and chip; ABC iprove: 1.9 to 2.5 s
spike, 9.8 to 10.4 s 3-head).

## Results

Seconds are wall clock of the method, including miter building; "limit" is the run's hard time limit.

### Whole-design methods that prove gates == golden for every input

| Method | Design | Time | Result | Runs |
|---|---|---|---|---|
| chain, P1 ABC iprove (final) | spike | 3.3 to 3.8 s | proved | 3 |
| chain, P1 ABC iprove (final) | 3-head | 8.4 to 8.9 s | proved | 3 |
| chain, P1 &cec + bitwuzla race | spike | 4.9 to 5.5 s | proved | 3 |
| chain, P1 &cec only | spike | 7.6 to 9.1 s | proved | 3 |
| chain, P1 bitwuzla only | spike | 5.3 to 9.5 s | proved | 3 |
| chain, P1 &cec only, split | 3-head | 132 to 158 s | proved | 3 |
| chain, P1 bitwuzla only, split | 3-head | 169 to 197 s | proved | 3 |
| chain, P1 &cec + bitwuzla race, split | 3-head | 119 to 131 s | proved | 3 |
| chain, P1 &cec + bitwuzla, split | 3-head | 175 s | proved | 1 |
| chain, P1 &cec, split per output | 3-head | 274 s | proved | 1 |
| chain, P1 &cec, whole | 3-head | 352 s | proved | 1 |
| lab golden + formal.patch | spike | 7.6 s | proved | 1 |
| lab golden + formal.patch | 3-head | 224 s | proved | 1 |
| lab golden + both patches | spike | 4.0 to 4.4 s | proved | 3 |
| lab golden + both patches | 3-head | 10.9 to 12.1 s | proved | 3 |

"lab golden" is the lab's True)` with both proposed patches applied: spike 4.0 to 4.4 s, 3-head chip about 12 s.=own `prove(golden=True)` with both proposed patches applied: spike 4.0 to 4.4 s, 3-head chip 10.9 to 12.1 s.=True)` (`scripts/lab_golden.py`, `scripts/check_iprove.sh`) on a
copy of the lab package with the patch applied. "split" = one P1 miter per output port, all in parallel
(the spike has one output, so split and whole are the same there). The last four 3-head repeat runs
(bitwuzla run 3 and the three race runs, `scripts/remeasure.sh`) ran after b77cc76 was merged into the
worktree; the rebuilt designs kept their ids, so the inputs to the proof were the same.

P1 alone, from the recipe sweep (`scripts/fastgolden.py`, scope `wholertl`, up to 7 jobs in parallel,
limit 300 s, 1 run each; add P2, 1.2 to 9 s, for the full chain):

| P1 engine | spike | 3-head |
|---|---|---|
| ABC iprove, techmap | 6.3 s proved | 14.7 s proved |
| ABC &cec, techmap | 10.8 s proved | 253 s proved |
| sby smtbmc bitwuzla | 8.0 s proved | 259 s proved |
| eqy (sby bitwuzla) | 72.8 s proved | not run |
| ABC &cec after `synth` | timeout | timeout |
| sby smtbmc yices | timeout | not run |
| eqy (sat) | timeout | not run |
| Yosys `sat` | timeout | timeout |
| sby abc pdr | timeout | not run |

### Direct gates == golden, one miter (no chain)

| Method | Design | Limit | Result |
|---|---|---|---|
| ABC &cec, techmap (`--direct`) | spike | 600 s | timeout |
| ABC &cec, techmap | spike, 3-head | 300 s | timeout |
| ABC &cec after `synth` | spike | 120 s | timeout |
| ABC iprove after `synth` | spike | 120 s | timeout |
| ABC pdr after `synth` | spike | 300 s | timeout |
| sby smtbmc bitwuzla | spike, 3-head | 300 s | timeout |
| sby smtbmc yices | spike | 300 s | timeout |
| eqy (sby bitwuzla) | spike | 300 s | timeout |
| Yosys `sat` | spike, 3-head | 300 s | timeout |
| ABC iprove, techmap | spike | 300 s | timeout |
| sby abc pdr | spike | 300 s | timeout |

### Methods that prove less than golden equivalence (not a pass)

| Method | Design | Time | Why it is not a golden proof |
|---|---|---|---|
| lab proof B only (default) | spike | 1.0 s | RTL == model rests on tests |
| nodes, Yosys sat (lab A, fixed) | spike | 67.9 s | relies on `ir/ranges.py` |
| nodes, &cec techmap | spike / 3-head | 7.2 / 29.0 s | relies on `ir/ranges.py` |
| nodes, sby bitwuzla | spike / 3-head | 9.5 / 30.3 s | relies on `ir/ranges.py` |
| nodes, Yosys sat | 3-head | 280.8 s | relies on `ir/ranges.py` |
| ABC `cec` / `dcec` on the miter | spike | 2.0 s | compares the miter with itself |

The node-by-node rows (run with the golden width fix of `scripts/fastgolden.py`) are full proofs only if the
interval ranges are sound; the chain needs no such assumption and is faster on both chips. ABC `cec` and
`dcec` given ONE network compare it with itself ("Networks are equivalent after structural hashing"): they
said "equivalent" in 2 s but did not catch the mutated golden model, so they prove nothing here.

## What the proof shows, in plain words

It shows: for every possible input word, the synthesised gate netlist (`synth/gates.v`) computes exactly
the same output bits as the golden model, an independent, deliberately naive Verilog rendering of the
chip's integer IR (weights, biases, shifts, clips, thresholds, fusion vote), at the IR's own bit widths.
So there is no input on which synthesis, the production Verilog emitter or the fusion logic changes the
model's integer arithmetic.

It does not show:

- that the IR equals the original trained model file (the `ingest-model` translation; that rests on the
  lab's bit-exact simulation and fuzz tests);
- that the model is right about the world: a proved alarm chip is exactly as accurate, or as wrong, as the
  model it was built from, and nothing here says it is clinically correct or safe;
- anything after synthesis: layout, timing, power, the placed-and-routed netlist, the Tiny Tapeout wrapper or
  streaming (sequential) behaviour; this is a combinational check of the synthesised gate netlist;
- that `emit/golden.py` itself is right: it is independent of the production emitter but written by the same
  lab, and both sides are read by the same Yosys front end, so a shared front-end bug would not show.

## Is the lab patch needed? (both are in the lab since b77cc76)

- `proposed/formal.patch`: **yes**. Part 1 (the `[63:0]` port fix in `emit/golden.py`) is needed for any
  golden proof of the spike; without it the lab reports a false failure. Part 2 adds
  `prove_rtl_vs_golden_whole` (P1 above, ABC `&cec`) to `prove(golden=True)`, with the node-by-node proof as
  fallback. Checked: the lab's `tests/test_formal_golden.py` passes on the patched copy (3 passed), and the
  patched `prove(golden=True)` proves both chips (7.6 s and 224 s, 1 run each).
- `proposed/formal-iprove.patch`: **recommended**, applies on top of `formal.patch`. It swaps `&cec -m` for
  ABC `iprove` in that one function: 3-head chip from 224 s to about 12 s. Checked the same way: tests pass
  (3 passed), spike 4.0 to 4.4 s (3 runs), 3-head 10.9 to 12.1 s (3 runs).

## Lab's new commit

Landed as b77cc76 on `origin/ant/chip-lab` (seen 21:35 UTC) and merged into `m3/formal` (normal merge,
`uv sync --locked --extra dev --extra sim --extra ingest`). Its `verify/formal.py` and `emit/golden.py` are
identical to the lab files with `formal.patch` and `formal-iprove.patch` applied (`diff`, no output), so both
patches are now in the lab and nothing more is needed from this package. No `chiplab workers` were running in
this worktree, and the golden proof runs in-process, so there was nothing to restart.

Re-run on b77cc76, same machine, load average 17 to 20:

| Check | Design | Time | Result | Runs |
|---|---|---|---|---|
| lab `tests/test_formal_golden.py` | - | 2.9 s | 3 passed | 1 |
| lab golden (`lab_golden.py`) | spike | 3.7 to 3.9 s | proved | 3 |
| lab golden (`lab_golden.py`) | 3-head | 9.1 to 9.6 s | proved | 3 |
| chain iprove + 3 mutants | spike | 3.2 s | proved, all caught | 1 |
| chain iprove + 3 mutants | 3-head | 8.4 s | proved, all caught | 1 |

Both designs were rebuilt through the merged lab first (`scripts/setup_designs.py`): same design ids, same
gate counts. Commands: `scripts/check_iprove.sh <worktree>/chiplab` (log `results/formal-recheck-b77cc76.log`)
and `golden_proof.py <id> --engines iprove --mutants`.

## Files

- `scripts/golden_proof.py`: the fastest recipe (chain; `--engines iprove` is the fastest, `--mutants` for
  the soundness check, `--split` for one miter per output, `--direct` for the one-step miter). From the repo
  root: `bash m3/formal/scripts/env.sh chiplab/.venv/bin/python m3/formal/scripts/golden_proof.py <design_id>
  --engines iprove --out <dir>`.
- `scripts/fastgolden.py`, `scripts/sweep.sh`, `scripts/jobs*.txt`: the recipe sweep.
- `scripts/repro_lab.py`, `scripts/lab_golden.py`, `scripts/check_patch.sh`, `scripts/check_iprove.sh`: lab
  reproduction and patch checks. `scripts/iprove.sh`, `scripts/remeasure.sh`: the timed repeat runs.
- `results/all.jsonl`: every run's raw result (home path replaced with ~).
- Time used: about 45 minutes of the 2-hour box (first log 20:59 UTC, last run 21:38 UTC).
