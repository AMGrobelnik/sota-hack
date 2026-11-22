# Report: two-channel EEG seizure-flag chip, design round

## What I built

- `spec.md`: the task, input and budgets. Values the brief did not give are marked as chosen.
- `designs.md`: three candidate networks (A feature MLP, B envelope CNN, C ternary MLP),
  with inputs, layers and parameter counts (81, 41, 193), a measured line-length front-end, an
  OpenRouter second opinion, and the comparison plan.
- `designs/make_ir.py`: builds each design as a chip-lab model (chipir/1) with **placeholder
  weights** (seeded random at the intended bit width), plus test vectors whose expected outputs
  come from an independent pure-Python evaluator.
- `lab/`: the raw JSON answers from every chip-lab call.

## What I measured

- **Compile:** all four models compiled and passed lint. The classifiers were synthesised plain
  and with the `alkaid` shift-add optimiser: A 2,867 → 2,367 gates, B 3,454 → 2,607, C 1,356 → 1,279.
  The front-end (two-channel line-length step) is 396 gates. The lab also recorded iCE40 LUTs,
  sky130 area and power (table in `designs.md`).
- **Verify:** this was a gate-level check only; no patient recordings were scored.
  - Every design was bit-exact against its integer model on 100,000 random vectors and on 256 of my
    own vectors with independently computed expected outputs.
  - Every design was formally proved equal to the lab's golden model (verification level 2).
  - One check failed first: the front-end's vector check, because my script saved only lane 0 of a
    2-lane output. I fixed the script and the re-run matched 256 of 256.
- **Power:** at 1 decision per second (vectorless, sky130) the three classifiers draw 0.03–0.05 µW,
  almost all leakage. All three miss the 20 ns clock by under 1.4 ns, which does not matter at
  this decision rate.

## What I could not do, and why

- **No recordings were attached**, so there is no reference model, no training, and no sensitivity
  or false-alarm numbers. The `reference` and `finetune` stages are marked skipped.
- **No ML libraries** (plain Python only: no numpy, no torch), so even training on simulated data
  was not practical here.
- The gate counts are for architectures with placeholder weights. Trained weights will change them,
  probably downward because trained weights have more zeros.
- Registers and most of the feature front-ends (amplitude, zero crossings, band filters) were not
  compiled; `designs.md` gives an estimate, clearly labelled as one.
- The chip lab has no EEG dataset plugin (only `cinc2017`, an ECG set), so its built-in training
  path does not apply.

## Next step

1. Attach CHB-MIT (and Siena for external testing) and a machine with numpy/torch.
2. Train A, B and C with quantisation-aware training, using a subject-level split.
3. Ingest the trained integer weights into the chip lab and score the gate netlist's own decisions
   on held-out subjects.
4. Write the front-ends as Verilog, submit them through `submit-verilog`, count the whole chip, and
   pick from the sensitivity-vs-gates Pareto front.
