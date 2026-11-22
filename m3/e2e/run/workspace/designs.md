# Three small seizure-flag networks for a two-channel EEG chip

Setting (from `spec.md`, values chosen where the brief is silent): two bipolar scalp EEG
channels (e.g. F7-T7, F8-T8), 256 Hz, 12-bit samples, one decision per second, alarm after
3 positive decisions in a row. Everything is integer: weights ≤ 4 bits or ternary.

**Sizes below are measured, but with placeholder weights.** No recordings came with the brief and
the machine has no ML libraries, so nothing was trained. Each design was built with seeded random
weights at its intended bit width (`designs/make_ir.py`), compiled by the chip lab, synthesised,
and proved bit-exact. The gate counts are therefore real for the *architecture*. Trained weights
usually have more zeros and repeated values, which tends to make the circuit somewhat smaller.
These circuits do not detect anything yet.

## Second opinion (OpenRouter, `openai/gpt-5-nano`, the "cheap" preset)

Asked for the single most useful extra feature, it proposed **line length**: the sum of
|x[n] − x[n−1]| over the window, per channel. Its reasons were that line length rises with fast,
irregular seizure discharges and needs only a subtract, an abs and an add per sample.

**I agree.** Line length is one of the best single seizure features in the literature, and here I
measured its cost: the two-channel per-sample datapath (subtract, abs, saturating 21-bit
accumulate) synthesises to 396 gates, proved equal to its model. Two caveats shape the designs below.
Line length scales with signal amplitude, which varies between electrodes and patients, so A
also uses it relative to the patient's own slow background. Chewing and movement artefacts
inflate it too, so no design relies on it alone, and the 3-in-a-row alarm rule filters short
bursts.

## Design A: feature MLP (multi-layer perceptron)

- **Inputs (8 × 6-bit unsigned, 4 per channel, computed over the last 2 s):** line length; mean
  |x| (amplitude); zero-crossing count (dominant frequency); line length minus its own slow
  running average (an exponential average with a shift-based update, time constant about 1 min),
  clipped at 0. That last input is "how much busier than this patient's normal" and needs no divider.
- **Layers:** dense 8→8 with 4-bit weights (−7..7) and bias → shift right 6 → clip to 0..15
  (a ReLU with a 4-bit output) → dense 8→1 with 4-bit weights → sign = decision.
- **Parameters:** 8·8 + 8 + 8 + 1 = **81** (about 324 bits of weights).
- **Why it could work:** classic seizure detectors with hand-made features reach high sensitivity
  with a handful of features. The MLP only has to learn a nonlinear boundary across 8 numbers.

## Design B: envelope CNN (temporal)

- **Inputs (32 × 5-bit unsigned):** per channel, line length over each 0.25 s block for the last
  4 s, which gives 16 time steps × 2 channels. The front-end is the line-length datapath above
  plus a 16-deep shift register per channel.
- **Layers:** conv1d over time, 2 in-channels → 4 filters, kernel 4, stride 2, ternary weights
  shared across 7 positions → shift 4 → clip 0..15 (ReLU) → global max over time (4 values) →
  dense 4→1 with 4-bit weights → sign.
- **Parameters:** 4·2·4 + 4 + 4 + 1 = **41**.
- **Why it could work:** seizures show up as a build-up and persistence of rhythmic activity over
  seconds. The convolution sees that shape over time, and the max-pool makes it independent of
  where in the 4 s window the build-up falls. It uses the fewest parameters, but on chip the
  convolution is repeated at all 7 positions.

## Design C: wide ternary MLP (spectral)

- **Inputs (10 × 4-bit unsigned, 5 per channel, over the last 2 s):** energy proxies (sum of |y|,
  no squaring) in four bands, about 0.5–4, 4–8, 8–13 and 13–30 Hz, from integer
  cascaded-integrator/difference filters, plus line length.
- **Layers:** dense 10→16 with **ternary** weights (−1, 0, +1) → shift 2 → clip 0..15 → dense
  16→1 ternary → sign.
- **Parameters:** 10·16 + 16 + 16 + 1 = **193** ternary (about 1.6 bits each).
- **Why it could work:** the shift in band power (rhythmic theta/alpha build-up, loss of
  background) is a standard seizure marker. Ternary weights remove every multiplier, so the layer
  is additions only and can be twice as wide as A for less logic.

## Measured circuit size (placeholder weights, classifier only)

Chip lab, `yosys` generic gates; `-alk` = the lab's shift-add sharing optimiser (`alkaid`).
All designs passed: 256 of my own vectors with expected outputs from an independent
pure-Python evaluator, 100,000 random vectors, and a formal equivalence proof against the lab's
golden model (verification level 2).

| Design | Params | Gates | Gates (-alk) | iCE40 LUTs | sky130 layout area (-alk) | Power at 1 decision/s (-alk) |
|---|---|---|---|---|---|---|
| A feature MLP | 81 | 2,867 | **2,367** | 1,079 | 0.022 mm² | 0.050 µW |
| B envelope CNN | 41 | 3,454 | **2,607** | 1,147 | 0.023 mm² | 0.049 µW |
| C ternary MLP | 193 | 1,356 | **1,279** | 513 | 0.012 mm² | 0.027 µW |
| Front-end: line-length step, 2 ch | — | 396 | — | 156 | 0.005 mm² | 0.011 µW at 256 Hz |

Notes on these numbers:
- Power is LibreLane vectorless power at a 20 ns clock, scaled to the decision rate. At 1 Hz it is
  almost all leakage, so all three are far below the 10 µW budget.
- All three classifiers miss the 20 ns clock by 0.7–1.4 ns. That does not matter for 1 decision per
  second; a 25 ns clock, or anything slower, closes timing.
- Not yet counted: the registers (window buffers, accumulators) and the rest of each front-end
  (A: amplitude, zero-crossing and background average; C: four band filters per channel). My estimate,
  not measured: A's front-end ≈ 1–1.5k gates, B's ≈ 0.5k gates plus 160 flip-flops, C's ≈ 2–3k
  gates, because the band filters are the expensive part.
- B unrolls its convolution 7 times. A streaming version (one position every 0.5 s, keeping a
  running max) would cut the convolution logic several-fold at the cost of a few registers. Not
  measured.

So the classifiers rank **C < A < B** in gates, but adding the front-ends roughly reverses that
(C's features are the costliest). That is why the comparison must count the whole chip, not only the network.

## How to compare them

**Data.**
- Train and develop on **CHB-MIT Scalp EEG** (PhysioNet; 22 paediatric subjects, about 980 h,
  198 seizures, 256 Hz, bipolar montage that includes F7-T7 and F8-T8).
- Test externally on **Siena Scalp EEG** (adults, 512 Hz resampled to 256 Hz) and, for
  artefact-heavy adult data, a slice of **TUH TUSZ**.
- Split **by subject**: leave-one-subject-out on CHB-MIT for the general model, with a sealed
  subject-level test set scored only a few times. Report patient-specific training separately,
  because it is the CHB-MIT habit and inflates results.
- Train each design with quantisation-aware training at its final bit width. Export integer
  weights to the chip lab, which proves that the gate netlist computes exactly the trained integer
  model, so the scores measured in software are the chip's scores.

**Metrics (clinical first).** All measured after the 3-in-a-row alarm rule:
- event sensitivity (share of seizures with an alarm);
- **false alarms per 24 h**;
- **worst-subject sensitivity**;
- median detection latency from electrographic onset.

Window-level AUROC/AUPRC are secondary; seizure windows are well under 1 % of the data, so use
AUPRC rather than accuracy. Put bootstrap confidence intervals over subjects on every number.

**Circuit size.** For the *whole* chip, front-end plus classifier, from the same lab flow:
generic gate count (after `alkaid`), iCE40 LUTs, sky130 area after layout, and energy per decision
at 1 Hz.

**Decision rule.** Plot sensitivity at ≤ 1 false alarm per 24 h against total gates and keep the
Pareto front. Pick the smallest design that meets the floor: ≥ 90 % event sensitivity, ≥ 75 %
worst-subject sensitivity, ≤ 1 false alarm per 24 h. Since A and C share line length, also try a
hybrid (C's ternary layer on A's cheaper features) if C wins on accuracy but loses on front-end size.
