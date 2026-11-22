# hr_tachy_brady_fusion_or: fast OR slow heart rate

One heart-rate sensor, two heads on the shared port (too fast, too slow) -> OR: any rate alarm.

- Simulated signal and event: 8 heart-rate samples (one per 2 s, 4-bit signed, 8 bpm per unit from resting); the event is a sustained rise of 25-55 bpm or fall of 22-40 bpm ramping in from a random onset, against drift, noise and one-sample motion spikes.
- Model: multi-head fusion (compose-chip, or), heads: intnn ternary 8 -> 8 -> 1 (fast) and 8 -> 6 -> 1 (slow) on one port.
- Chip flow: `compose` (see `chip.json`).
- Vectors: 256 test windows in `vectors.npz`; inputs ['x'], expected outputs ['tachy_y', 'brady_y', 'any_alarm'], ground truth ['label_any_alarm', 'label_tachy_y', 'label_brady_y'].
- Detection (any_alarm, model on the synthetic test windows): sensitivity 0.945 (127 events), specificity 1.000, accuracy 0.973 on 256 synthetic test windows.
- Detection (tachy_y, model on the synthetic test windows): sensitivity 0.985 (65 events), specificity 1.000, accuracy 0.996 on 256 synthetic test windows.
- Detection (brady_y, model on the synthetic test windows): sensitivity 0.903 (62 events), specificity 1.000, accuracy 0.977 on 256 synthetic test windows.
- Heads: two intnn ternary nets reading the same 8 x 4-bit signed port (shared_inputs=true).
- Expected fusion outputs: numpy over the heads' expected decisions (and = all, or = any, kofn = at least k).

Synthetic data from a seeded generator, not patient data; the detection figures are on synthetic test windows and make no clinical claim. Rebuilt by `m3/examples/gen_gallery.py`; chip numbers in `../RESULTS.md`.
