# A8: folded (time-shared) engine for 30k+ weights: feasibility

The task asked for this file as `FINDINGS.md`. A local file-name hook refused that name, so it is
`feasibility.md`.

This package adds results and a design sketch only. Nothing in `chiplab/` changed. Branch `lab/folded`,
based on `ant/chip-lab` at `3a49ed5`.

Everything was measured on 22 Nov 2026 on an Apple M3 Max, with the lab's own tool install: Yosys
0.71+77, Icarus Verilog, and SymbiYosys with Yosys-SMTBMC and Yices, all from OSS CAD Suite. Liberty
files are the typical corners the lab maps to:

- sky130_fd_sc_hd, tt, 25 °C, 1.8 V;
- gf180mcu 7-track, tt, 25 °C, 3.3 V.

Tags: **M** = measured here (file in `results/`), **S** = from a named source, **A** = assumed.

## 1. Headline

- **ROM cost per bit.** A synthesised constant ROM costs 0.15 to 0.21 gate-equivalents (GE) per stored
  bit (M). That is 0.58 to 0.78 µm² per bit on sky130 and 1.9 to 2.6 µm² per bit on gf180. The cost per
  bit falls as the ROM grows and hardly depends on word width or weight statistics.
- **Stored weights cost 15 to 43 times less than wired weights.**
  - Stored: 0.42 generic gates per ternary weight, 0.82 per 4-bit weight (M).
  - Wired, ballpark given with the task (S): 6 to 7 per ternary weight, 29 per 4-bit weight.
  - Wired, the lab's own chip of one wide neuron (M): 11.8 per ternary weight, 35 per 4-bit weight.
- **Area at 30k weights (M + A).** The folded engine needs 0.17 to 0.23 mm² on sky130 and 0.53 to 0.74
  mm² on gf180, after layout. Fully wired needs 4.9 to 14 mm² on sky130 and 16 to 47 mm² on gf180. That is
  29 to 66 times more.
- **Routes.** The folded engine fits Tiny Tapeout:
  - TT sky130, 16 tiles: 58 to 60% for ternary weights, 78 to 81% for 4-bit weights (tight).
  - TT GF180, 32 tiles: 30 to 42%.

  Fully wired fits no Tiny Tapeout route.
- **Latency** (P = number of multiply-accumulate units):

  | P | cycles per decision | at 1 MHz | at 32.768 kHz |
  |---:|---:|---:|---:|
  | 1 | 30,152 | 30 ms | 0.92 s |
  | 4 | 7,976 | 8 ms | 0.24 s |

  Even one MAC at 32 kHz meets one decision every few seconds.
- **Energy.** At one decision every 3 s, the folded engine uses less energy per decision than an
  always-on wired chip. Capacitance and leakage are M; activity is A. With P = 4 it uses about 0.6 µJ
  against 3.5 µJ on sky130 (ternary), and 6 µJ against 93 µJ on gf180. Folding spends more switching
  energy, because it reads the ROM every cycle. It wins because leakage dominates a wired chip that sits
  idle between decisions.
- **Recommendation: go** (section 8). The first gate is one layout run of the ROM. That needs Docker,
  so it was not run tonight (section 9).

## 2. ROM gates and area per stored bit (M)

### What was built

- The ROM is a Verilog `case` statement of constants, read by a free-running address counter, with a
  registered output word.
- `rom_bench.py` runs each ROM through the lab's own flows:
  - `chiplab.hw.yosys.synth_generic` for generic gates;
  - `chiplab.hw.pdk.map_to_process` for sky130 and gf180 cells. This is the same script as the lab's
    `map-to-process` tool, with ABC effort `fast`.
- Weight statistics:
  - ternary: 50% zeros, 25% +1, 25% -1, as 2-bit sign-magnitude;
  - 4-bit: uniform from -8 to 7.
- Word width is 16 bits. Raw data: `results/rom.json`.

### Results

| kbit | stats | gates/bit | sky GE/bit | sky µm²/bit | gf GE/bit | gf µm²/bit |
|---:|---|---:|---:|---:|---:|---:|
| 16 | ternary | 0.244 | 0.207 | 0.78 | 0.232 | 2.55 |
| 16 | 4-bit | 0.257 | 0.218 | 0.82 | 0.245 | 2.69 |
| 64 | ternary | 0.211 | 0.168 | 0.63 | 0.188 | 2.07 |
| 64 | 4-bit | 0.219 | 0.173 | 0.65 | 0.195 | 2.14 |
| 128 | ternary | 0.194 | 0.154 | 0.58 | 0.171 | 1.88 |
| 128 | 4-bit | 0.205 | 0.159 | 0.60 | 0.177 | 1.94 |

How to read the columns:

- **gates** is the lab's generic count: 2-input gates, MUX and flip-flops, excluding buffers.
- **GE** is the mapped area divided by the NAND2_1 area (S: `chiplab/chiplab/hw/pdk.py`).
- All areas are synthesis areas, before placement.
- The counter and the 16 output flip-flops are included. At 64 kbit and above they are under 1% of the
  total.

### What the results show

- **Cost per bit falls with depth.** It goes from 0.21 GE at 16 kbit to 0.15 GE at 128 kbit. That fits
  the classic result that random Boolean functions cost about 2^n / n gates, where n is the number of
  address bits.
- **Word width hardly matters.** Words of 4, 8, 16, 32 and 64 bits, at 16 and 128 kbit, land within ±4%
  of each other (`results/rom_words.json`, 48 runs). A folded engine can use whatever ROM word width its
  MACs need.
- **Zeros save little per bit, but ternary halves the bits.** Ternary with 50% zeros is only 3% cheaper
  per bit than uniform 4-bit. Per weight, at 30k weights:

  | weights | ROM size | sky130 GE | gf180 GE | generic gates |
  |---|---:|---:|---:|---:|
  | ternary | 60 kbit | 0.34 | 0.38 | 0.42 |
  | 4-bit | 120 kbit | 0.64 | 0.71 | 0.82 |

- **The netlists keep every word.** All 18 word-16 netlists (generic, sky130 and gf180, every size and
  statistic) were simulated against their RTL over the full address range, with the PDK cell models.
  The result was 0 mismatches (`results/rom_verify.json`, `verify_rom.py`). A test shows that one flipped
  constant is caught.
- **Runtime and timeouts.** The largest synthesis, 128 kbit mapped to gf180, took 6 s. Every job ran in
  its own process group under `memgate`, with a 2,400 s cap. No synthesis timed out.

## 3. Fully wired cost per weight

The scale package's results (`lab/scale`, `m3/scale/results.json`) were not on origin when this was
written. Two references are used instead:

- **Ballpark from the task (S):** 6 to 7 gates per ternary weight (6.5 used here), and 29 per 4-bit
  weight.
- **Measured here (M):** the lab's own wired chip of the same single wide neuron the prototype computes.
  - The neuron is `clip((w·x + b) >> s, 0, 15)` with unsigned 4-bit activations.
  - It was built with `compile_verilog(ir=...)`, then run through `synthesize` and `map-to-process`.
  - Data: `results/proto_area_*.json`, key `wired`.

| weights | n | gates/w | sky GE/w | gf GE/w |
|---|---:|---:|---:|---:|
| ternary | 256 | 11.8 | 26.3 | 30.1 |
| ternary | 1024 | 12.4 | 27.7 | 32.0 |
| 4-bit | 256 | 35.3 | 76.9 | 87.3 |
| 4-bit | 1024 | 34.4 | 73.3 | 83.1 |

- **Ternary is about twice the ballpark; 4-bit is close.** This was not checked. The likely reason is
  that this neuron's inputs are 4-bit, wider than in the designs behind the ballpark. Section 5 shows
  both.
- **ROM against wired, per weight, in generic gates:**
  - ternary: 0.42 against 6.5 (ballpark), 15 times less; against 11.8 (measured), 28 times less;
  - 4-bit: 0.82 against 29 (ballpark), 35 times less; against 35 (measured), 43 times less.

## 4. Design sketch: folded per-channel engine

### How it works

The engine is output-stationary: it computes one output channel (one neuron) at a time. For each neuron
it streams that neuron's weights out of the ROM and accumulates. Then it writes the activation back and
moves to the next neuron.

```text
 sensor/serial in --> [activation RF: input bank | hidden bank] --P x 4 bit--> [P MAC: +/-x or w*x]
                                    ^                                               |
                         write back |                                        [adder tree, 24-bit acc]
                                    +---- [>>> shift, clip 0..amax] <---------------+
 [controller FSM] --address--> [weight ROM: case statement, word = P weights]  [bias ROM]
   IDLE -> LOAD inputs -> per layer, per neuron: ACC (fan_in/P cycles) -> WB (2 cycles) -> DONE
```

### Blocks

- **Weight ROM.** A case-statement ROM with one word of P weights per cycle, addressed by a 15-bit weight
  counter. It is pure standard cells, so the lab's synthesis, mapping, simulation and layout flows apply
  unchanged.
- **Bias ROM.** The same kind of ROM, with 16-bit biases (A).
- **Activation register file.**
  - Two flip-flop banks: inputs (128 × 4 bits) and hidden activations (224 × 4 bits).
  - Written serially. Read as words of P activations, so the read mux does not grow with P.
  - Clock-gated: clocked only when written.
- **MAC units.** P units, from 1 to 4.
  - A ternary unit adds, subtracts or skips; it needs no multiplier.
  - A 4-bit unit is a signed 4 × 4 multiplier.
  - The units feed an adder tree into a 24-bit accumulator. A post stage does the arithmetic shift and
    the clip, then writes back.
- **Controller.** Layer, neuron and weight counters, and a start, done and valid handshake. It produces
  one decision every few seconds.

### Network assumed for the estimate (A)

- An MLP of 128 → 224 → 4, with 4-bit activations.
- 29,568 weights and 228 neurons.
- The register file holds the inputs and the hidden activations at once: 1,408 bits.

### Prototype (M)

`proto/folded_proto.py` builds this engine for one neuron of up to 1,024 weights: ROM, P MACs, register
file and controller.

**Simulation against the integer model.** Icarus checked it bit for bit against `chiplab.ir.interp`,
the lab's integer model:

- 200 vectors per configuration: 4 edge cases plus random activations, with outputs spread over 16
  values.
- 8 configurations: n = 64, 256 and 1024 at P = 1, and n = 256 at P = 4, each with ternary and 4-bit
  weights.
- 0 mismatches in all 8, at exactly n / P cycles per output (`results/proto_sim_*.json`).

**Area model.** The prototype was mapped at n = 64, 256 and 1024. Area grows in a straight line with n:
42.9 GE, then 42.7 GE per extra n (sky130, ternary).

- The intercept is the engine: MAC, accumulator and control.
- The slope is one weight plus one activation.
- Subtracting the ROM cost per weight leaves the register-file cost:

| block (P = 1) | sky130 | gf180 |
|---|---:|---:|
| activation RF, per bit | 39.7 µm² (10.6 GE) | 123 µm² (11.2 GE) |
| engine, ternary | 2,694 µm² (718 GE) | 8,248 µm² (751 GE) |
| engine, 4-bit | 3,444 µm² (918 GE) | 12,407 µm² (1,130 GE) |
| P = 1 to P = 4, extra | 2,650 to 4,600 µm² | 9,600 to 13,600 µm² |

## 5. 30k-weight estimate

`estimate.py` reproduces every number in this section from `results/`, and writes
`results/estimate.json`.

### Area

**How it is computed:**

- Area = weight ROM + bias ROM + register file + engine + sequencer.
- The sequencer (layer and neuron counters, write-back) is assumed to cost 50% of the engine (A).
- Layout area = synthesis area / 0.6. This is the 60% utilisation that `chiplab/chiplab/hw/pdk.py` uses
  for its Tiny Tapeout tile estimate (S).
- Wired layout area = measured GE per weight (n = 256) × 29,568 / 0.6.
- The wired ballpark converts the task's gates per weight into GE with the GE-per-gate ratio measured on
  the wired neuron: 2.2 on sky130, 2.5 on gf180.

| weights | pdk | P | synth mm² | layout mm² | wired mm², M / ballpark |
|---|---|---:|---:|---:|---:|
| ternary | sky130 | 1 | 0.100 | 0.167 | 4.86 / 2.68 |
| ternary | sky130 | 4 | 0.103 | 0.172 | 4.86 / 2.68 |
| ternary | gf180 | 1 | 0.317 | 0.529 | 16.3 / 8.97 |
| ternary | gf180 | 4 | 0.327 | 0.545 | 16.3 / 8.97 |
| 4-bit | sky130 | 1 | 0.135 | 0.224 | 14.2 / 11.7 |
| 4-bit | sky130 | 4 | 0.140 | 0.233 | 14.2 / 11.7 |
| 4-bit | gf180 | 1 | 0.431 | 0.718 | 47.2 / 38.8 |
| 4-bit | gf180 | 4 | 0.444 | 0.741 | 47.2 / 38.8 |

Where the area goes (synthesis, mm², P = 1):

| weights | pdk | weight ROM | bias ROM | act. RF | engine | seq. |
|---|---|---:|---:|---:|---:|---:|
| ternary | sky130 | 0.0373 | 0.0028 | 0.0559 | 0.0027 | 0.0013 |
| 4-bit | sky130 | 0.0705 | 0.0030 | 0.0560 | 0.0034 | 0.0017 |
| ternary | gf180 | 0.1223 | 0.0093 | 0.1733 | 0.0082 | 0.0041 |
| 4-bit | gf180 | 0.2298 | 0.0098 | 0.1728 | 0.0124 | 0.0062 |

**For ternary weights the activation register file, not the ROM, is the largest block.** Its 1,408
flip-flop bits cost about as much as 60 kbit of ROM. Two ways to shrink it matter more than the ROM: a
latch-based register file, or fewer or narrower stored activations.

### Cycles and latency

Cycles = 128 serial input loads + Σ over layers of neurons × (fan-in / P + 2). The 2 overhead cycles per
neuron are assumed (A).

| P | cycles | at 1 MHz | at 32.768 kHz |
|---:|---:|---:|---:|
| 1 | 30,152 | 30.2 ms | 0.92 s |
| 4 | 7,976 | 8.0 ms | 0.24 s |

### Energy per decision

**Model:**

```text
E_cycle = K_int · V² · (α · K_wire · C_active + K_wire · C_clk)
```

| term | value | source |
|---|---|---|
| C_active | input-pin capacitance of what switches each cycle | M, Liberty |
| C_clk | clock-pin capacitance of 48 engine flip-flops | M, Liberty |
| α | 0.1 transitions per input per cycle | A |
| K_wire | 2 (wire capacitance equal to pin capacitance) | A |
| K_int | 1.5 (internal energy adds 50%) | A |
| V | 1.8 V (sky130), 3.3 V (gf180) | S, Liberty corners |

**Assumptions behind the terms:**

- C_active covers the ROM, engine and sequencer, plus a quarter of the register file for its read mux
  (A). The capacitances are summed over the mapped cell counts (`power.py`).
- C_clk counts only engine flip-flops because the register file is assumed clock-gated (A).
- Leakage (M) is the Liberty cell leakage summed over the mapped cells, at tt 25 °C, always on, with one
  decision every 3 s (A).
- Wired switching uses the same model, with α = 0.25 per decision (A): one adder-tree evaluation,
  glitches included.

| weights | pdk | P | pJ/cycle | dyn. nJ | leak nJ/3 s | wired dyn. nJ | wired leak nJ/3 s |
|---|---|---:|---:|---:|---:|---:|---:|
| ternary | sky130 | 1 | 58 | 1,757 | 93 | 7 | 3,542 |
| ternary | sky130 | 4 | 61 | 489 | 93 | 7 | 3,542 |
| ternary | gf180 | 1 | 395 | 11,900 | 2,921 | 56 | 92,629 |
| ternary | gf180 | 4 | 416 | 3,317 | 2,921 | 56 | 92,629 |
| 4-bit | sky130 | 1 | 102 | 3,070 | 121 | 21 | 10,517 |
| 4-bit | sky130 | 4 | 108 | 860 | 121 | 21 | 10,517 |
| 4-bit | gf180 | 1 | 684 | 20,617 | 3,944 | 162 | 270,708 |
| 4-bit | gf180 | 4 | 717 | 5,721 | 3,944 | 162 | 270,708 |

**What it means:**

- **Clock speed does not change energy per decision, to first order.** The same cycles switch the same
  capacitance, and leakage is paid over the decision period. 1 MHz against 32.768 kHz changes only
  latency and the clock source. The clock source's own power is not modelled.
- **P = 4 cuts dynamic energy 3.6 times for 3% more area.** Each cycle reads one ROM word whatever its
  width, so fewer, wider reads cost less, at the same α.
- **Totals with P = 4, one decision every 3 s** (energy per decision, then average power):

  | weights | pdk | folded | wired, always on |
  |---|---|---|---|
  | ternary | sky130 | 0.58 µJ, 0.19 µW | 3.5 µJ, 1.2 µW |
  | 4-bit | sky130 | 0.98 µJ, 0.33 µW | 10.5 µJ, 3.5 µW |
  | ternary | gf180 | 6.2 µJ, 2.1 µW | 93 µJ, 31 µW |
  | 4-bit | gf180 | 9.7 µJ, 3.2 µW | 271 µJ, 90 µW |

- **Sensitivity:**
  - Folded dynamic energy scales with α: α from 0.05 to 0.3 gives 0.5 to 3 times the figures above.
  - tt 25 °C is the lowest-leakage case. Leakage rises steeply with temperature (A, not measured here).
    That favours the folded engine, which has 25 to 66 times fewer cells.
  - A wired chip that is power-gated between decisions would win on energy. That needs power switches
    and a wake-up sequence, which this estimate does not include.

## 6. Which route it fits

| route | capacity | folded 30k | wired 30k, M / ballpark |
|---|---|---|---|
| TT sky130, 16 tiles of 161 × 111.52 µm | 0.287 mm² | yes: ternary 58-60%, 4-bit 78-81% | no / no |
| TT GF180, 4 × 8 tiles of 346.64 × 160.72 µm | 1.78 mm² | yes: 30-42% | no / no |
| wafer.space GF180, 1.73 mm² core | 1.73 mm² | yes | no / no |
| wafer.space GF180, 4.46 to 5.02 mm² | 4.46 mm² | yes | no / no |
| wafer.space GF180, 12.92 mm² | 12.92 mm² | yes | no / ternary only |
| ChipFoundry, about 10 mm² (sky130) | 10 mm² | yes | ternary only / ternary only |

- **Tightest case: TT sky130 with 4-bit weights,** at 78 to 81% of 16 tiles under 60% utilisation. It
  needs the layout in section 9 before anyone relies on it.
- **TT GF180 and wafer.space have wide margins.** Ternary weights fit every route.

## 7. What a proof would need

Simulation against the integer model is done (section 4).

### Whole-decision BMC

`proto/prove_proto.py` builds a SymbiYosys miter:

- It loads n symbolic activations into the folded neuron. They are `anyconst`, so they cover every input
  vector at once.
- It starts the neuron and asserts at `done` that the output equals the lab's wired chip of the same
  integer model.
- It also asserts that `done` arrives on the right cycle.
- From reset, one decision is a fixed-length run, so BMC to that depth fully proves one decision for
  every input.

A changed ROM weight is caught as FAIL (`results/prove/*_mutated.json`).

How far it reaches, with Yices and a 300 s cap per run (`results/prove/`):

| weights | n = 8 | n = 16 | n = 32 | n = 64 | n = 128 |
|---|---|---|---|---|---|
| ternary | PASS 0.7 s | PASS 1.4 s | PASS 2.0 s | TIMEOUT 300 s | not run |
| 4-bit | PASS 10.6 s | PASS 13.6 s | PASS 44 s | PASS 260 s | TIMEOUT 300 s |

Whole-run BMC stops between n = 32 and 128. It cannot reach 30k weights.

**Timeout finding: killing sby's process group is not enough.** sby starts each engine (`yosys-smtbmc`
and its `yices-smt2`) in a process group of its own. The first version of the script killed only sby's
group when the 300 s cap fired.

- After the n = 128 timeout, a `ps` check found the solver still running as an orphan. It was killed by
  hand after about 5 minutes.
- The script now collects every descendant before killing anything, then kills each one and its group.
- A repeat timeout test (n = 64, 20 s cap) left no `yices` or `smtbmc` process behind.

Anyone running SymbiYosys from a script should do the same.

### A proof that scales

Split it into three small parts:

1. **ROM table equivalence (combinational).** The ROM logic equals its constant table.
   - Shown by exhaustive simulation over every address, as `verify_rom.py` does now, or by ABC `cec`
     against the table.
2. **One MAC step (combinational, small).** acc' = acc + Σ_p w_p · x_p, for every acc, w and x.
3. **A controller invariant, by k-induction in SymbiYosys.**
   - At weight step k, acc = b + Σ_{i<k} w_i · x_i.
   - When a neuron finishes, its result goes to the right register-file address, and the controller
     returns to idle.
   - With the ROM as an uninterpreted table, this does not depend on the number of weights.

`eqy` alone does not fit. It pairs state between two designs, and the folded and wired designs share
none. It can help with part 1, and with checking that synthesis kept the folded RTL intact.

## 8. Recommendation: go, after one layout

Build a folded mode after the hackathon:

- **It is the only route to 30k weights on Tiny Tapeout or wafer.space.** It is 29 to 66 times smaller
  than wired: 0.17 to 0.74 mm² after layout, against 5 to 47 mm².
- **Latency is not a constraint.** P = 1 at 32 kHz decides in under 1 s. Use P = 4: it costs 3% more
  area and cuts cycles 4 times and dynamic energy 3.6 times.
- **Energy is lower.** At one decision every few seconds it uses less energy per decision than an
  always-on wired chip.
- **It reuses the lab.** The ROM is pure standard cells, and the same Yosys, mapping, simulation and
  layout flows apply. The integer model stays the reference.

Conditions, in order:

1. **Lay out one 128 kbit ROM.** Confirm that a random-logic ROM this size routes at about 60%
   utilisation (section 9). If it routes only at 40%, sky130 with 4-bit weights no longer fits 16 tiles.
   Ternary and gf180 still fit.
2. **Decide how to store activations.** For ternary weights the register file is the largest block.
3. **Build the decomposed proof of section 7** before calling a folded chip verified. Today the only
   evidence is simulation and small BMC.

## 9. Not run, and findings for the lab's owner

### Layout: needs Docker, not run

The Docker engine was stopped on purpose on this machine tonight. To run it, with Docker up, from a
checkout of this branch:

```text
LAB_HOME=<lab install folder> bash m3/folded/run.sh layout_rom.py --size-kbit 128 --stats uniform4 --pdk sky130
```

- **What it does:** places and routes the 128 kbit 4-bit ROM (seed 1, the same netlist as
  `results/rom.json`) through `chiplab.hw.librelane.timing_power_layout`. The clock is `clk` at 1 MHz,
  with 40% core utilisation.
- **Output:** `m3/folded/results/layout_128k_uniform4_w16_sky130.json`.
- **What to check:** compare `area_um2` and `die_area_um2` with the synthesis area of 78,134 µm².
- **Other cases:** use `--pdk gf180`, or `--stats ternary --size-kbit 64`.

### Lab finding: Yosys crashes on wide wired neurons

- **Symptom:** for a 1,024-input, 4-bit matvec row, the lab's Verilog puts the whole sum on one line of
  40k characters. Yosys 0.71 crashes parsing it with SIGSEGV (exit 139) under the default 8 MB stack.
  `synthesize` and `map-to-process` then fail with only "yosys failed".
- **Confirmed cause:** the stack. The same file parses with a 64 MB stack (`ulimit -s 65520`). `run.sh`
  here sets that.
- **Impact:** any fully wired chip with a fan-in near 1,000 hits this.
- **Possible fixes** (in `chiplab/`, so left to the lab's owner): emit a balanced tree of partial sums,
  or raise `RLIMIT_STACK` for the Yosys child in `chiplab/hw/yosys.py`.

### Lab finding: ABC children may outlive a Yosys timeout

This comes from reading the code; it was not observed.

- `run()` in `chiplab/hw/yosys.py` uses `subprocess.run(timeout=...)`. On timeout that kills only
  `yosys`, not the `yosys-abc` children it started.
- This package's scripts avoid the problem: they start each job in its own process group and kill the
  whole group on timeout.

## 10. Reproduce

`LAB_HOME` is the lab tool install: the folder holding `config.json`, `oss-cad-suite` and `pdk`.
Lab state and the result cache go to the ignored `m3/folded/work/`.

```text
bash m3/folded/run.sh rom_bench.py run --sizes 128,64,16 --cap 2400          # results/rom.json
bash m3/folded/run.sh rom_bench.py run --sizes 128,16 --words 4,8,32,64 --out m3/folded/results/rom_words.json
bash m3/folded/run.sh summarize.py                                            # per-bit tables
bash m3/folded/proto/run_proto.sh                                             # proto sim + area
bash m3/folded/proto/run_prove.sh 300                                         # BMC reach
bash m3/folded/run.sh estimate.py                                             # section 5 tables
bash m3/folded/run.sh pytest m3/folded -q                                     # tests
```

### Test results on 22 Nov 2026

These runs started from an empty lab cache.

- **`m3/folded` tests: 15 passed.** They cover the weight statistics, ROM packing, the cycle count and the
  line fit. They also synthesise a 1 kbit ROM, check it exhaustively and catch a flipped constant. Other
  tests confirm that Liberty sums match the mapped area, and that the folded neuron matches the integer
  model for both weight types at P = 1 and 4. Finally, a BMC proof passes at n = 8 and a mutated ROM
  weight fails.
- **The lab's fast selection** (`pytest -m "not docker and not slow and not data"` in `chiplab/`, run on
  this branch's base `3a49ed5`): 101 passed, 5 failed, 3 skipped, 8 deselected. This branch changes
  nothing in `chiplab/`, so all 5 failures are in the base or its environment:
  - `test_agent_examples[layout]`, `[timing_power]` and `[submit_verilog]` call Docker, which was
    stopped tonight. They carry no `docker` marker.
  - `test_chipin_integration::test_lab_reports_through_the_real_progress_helper` expects no `CHIPLAB_*`
    variables, but this run set them on purpose to use the existing lab install.
  - `test_regressions::test_failed_check_is_rc2` returned exit code 1 where the test expects 2; the
    cause was not investigated.
