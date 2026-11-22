# Two-electrode seizure flag: report

**Outcome.** The chosen chip is the linear classifier (design `e51a3da485f2`): 125 logic gates, bit-exact and
proved equal to its model. It **misses the accuracy target** I set. All data is synthetic, so nothing here
says how it would do on patients.

## What was built
Both candidates take 6 unsigned 4-bit features (line length, amplitude, zero crossings for each of 2 channels;
order ll1 ll2 sd1 sd2 zc1 zc2) from a front end that is **not** on the chip, and give one bit per 2 s window.

- A (chosen): `3*ll1 - ll2 + 2*sd1 + sd2 - 2*zc1 - zc2 > 20`.
- B: 6-4-1 network, ternary first layer, 4-bit activations, output weights within -3..3.

## Accuracy (synthetic)
60 simulated subjects, 60 windows each; split by subject 36/12/12. Test = 12 subjects, 720 windows.
Candidate seeds and thresholds were picked on validation; test did not choose the design. I wrote the generator
myself (1/f background, alpha, movement and muscle artefacts, 3-7 Hz rhythmic seizures). Target: both >= 0.90.

| Model | val sens | val spec | test sens | test spec |
|---|---|---|---|---|
| Float reference (6-32-32-1) | 0.836 | 0.909 | 0.869 | 0.930 |
| A linear | 0.808 | 0.813 | 0.800 | 0.776 |
| B 6-4-1 | 0.816 | 0.783 | 0.777 | 0.785 |

The float reference also misses 0.90 sensitivity, using the same 4-bit features. B did not beat A, and I made
one training round only (12 seeds) and did not investigate why.

## Chip lab results
| | A (chosen) | B |
|---|---|---|
| Gates | 125 | 177 |
| Gate depth | 22 | 23 |
| LUTs (xc7) | 39 | 62 |
| sky130 area, before layout (um2) | 973.4 | 1137.3 |
| Bit-exact: 720 test vectors vs my model / 100,000 random vs integer model | yes / yes | yes / yes |
| Formal proof (gates = RTL = golden model, every input) | proved | proved |
| Streaming RTL simulation (300 random frames) + lint | passed | passed |
| Verification level | 3 | 3 |

Verify means the **gate check** ran and passed. The patient-recording check did **not** run (no recordings).

Both passed, so the brief's rule (smaller one that is bit-exact) picks A. The lab's chip report was run for A
(`chipreport.json`); it gives a Tiny Tapeout sky130 price of EUR 370 with the tile count estimated, not laid out.
Nothing was submitted or ordered.

## What I could not do
- No power or energy figure: it needs layout, and layout was not run (Docker is off). The lab gave none.
- No timing after layout; area is synthesis area and layout adds whitespace.
- No patients: no seizure sensitivity, false alarms per day or latency on real EEG.
- The front end (ADC, filters, log quantisers) is not built or counted. It is likely to be much bigger than this core.

## Next step
Fix accuracy first: the float reference also misses the target with these 4-bit features, so better features,
more bits or a longer window come before shrinking further. Then repeat on real two-electrode EEG recordings
with subject-level splits, and run layout for power and timing.
