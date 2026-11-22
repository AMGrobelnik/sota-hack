# ChipIn report: two-electrode seizure flag

**All detection figures are on synthetic data** (5 simulated patients, see `data/assumptions.md`). They show the pipeline works; they are not clinical evidence.

## What I built
- Synthetic 2-channel EEG, 256 Hz, 3 h × 5 synthetic patients, 4 seizures each, with EMG, motion and electrode-pop artefacts. Split by patient: train p1,p2 · validation p3 · held-out test p4,p5 (`data/split.json`).
- Reference (no chip limits): float MLP on 14 spectral/line-length/energy features.
- Three chip candidates on 8-bit per-window features (2-s windows, 0.5 decisions/s): line-length threshold, energy (mean |x|) threshold, and a 2-feature integer logistic (weights −4 on line length, +7 on energy). Thresholds and the alarm rule (k consecutive positive windows) were fitted on training patients; the chip was chosen on validation.
- Each compiled with the chip lab, checked bit-exact on all 10,800 held-out windows and formally proved equal (level 2).

## Candidates (synthetic data)
| Design | Lab id | Gates | Depth | k | Val sens | Val FA/h | Test sens | Test FA/h |
|---|---|---|---|---|---|---|---|---|
| line-length threshold | `e00baa02f14a` | 51 | 14 | 2 | 0.00 | 0.00 | 0.00 | 0.00 |
| energy threshold | `c5a5f861d110` | 70 | 19 | 8 | 0.75 | 0.00 | 1.00 | 1.50 |
| 2-feature integer logistic | `1b05ecf2359a` | 237 | 27 | 4 | 1.00 | 0.00 | 1.00 | 0.17 |
| reference MLP (float, not a chip) | – | – | – | 2 | 1.00 | 0.00 | 1.00 | 0.00 |

## Chosen: 2-feature integer logistic (`1b05ecf2359a`) — targets on held-out synthetic patients
| Target | Value (synthetic data) | Result |
|---|---|---|
| sensitivity ≥ 0.8 (primary) | 1.00 (8/8 seizures) | pass |
| false alarms ≤ 1 per hour | 0.17 /h (1 in 6 h) | pass |

Per patient: p4: 4/4 caught, 0 FA in 3 h, p5: 4/4 caught, 1 FA in 3 h — both held-out synthetic patients meet both targets.

## Findings
- The line-length threshold caught nothing: in this synthetic data, EMG bursts have higher line length than seizures, so any threshold that keeps false alarms low misses every seizure.
- The energy threshold catches all test seizures but gives 1.5 FA/h (fails the false-alarm target); motion artefacts trigger it.
- Combining the two (energy up, line length down) separates seizures from both artefact types for 237 gates.

## Chip (from the chip lab's chip report)
| Metric | Value | Basis |
|---|---|---|
| Logic gates | 237 | Yosys yosys 0.71+77, simple gates, ABC effort fast |
| Logic depth | 27 gates | longest path |
| Transistors | 1686 | Yosys CMOS estimate |
| LUTs (xc7) | 67 | Yosys synth_xilinx |
| Area, sky130 | 1640 µm² (437.0 GE, 318 cells) | Liberty synthesis, before layout |

## Verification
- {'level': 1, 'file': 'simulate_vectors.json', 'n': 10800, 'inputs': 'vectors', 'bit_exact': True}
- {'level': 2, 'file': 'formal.json', 'method': 'abc cec', 'against': 'production RTL (synthesis proved; RTL == IR by construction and fuzz tests)', 'proved': True}

## What I could not do
- No real recordings: every detection figure is synthetic data. Real ear-EEG artefacts and seizure types will differ.
- Layout and timing/power were skipped (Docker not available), so there is no measured power or post-layout area.
- The feature front-end (line length, mean |x| over 2 s, 8-bit quantisation) and the k=4 consecutive-window alarm rule run in software; only the decision core is compiled to gates.
- Small test set (8 seizures, 6 h): sensitivity moves in steps of 0.125.

## Next step
Run the same pipeline on a public scalp/ear-EEG seizure dataset restricted to two temporal channels, and compile the feature front-end and alarm counter into the chip.
