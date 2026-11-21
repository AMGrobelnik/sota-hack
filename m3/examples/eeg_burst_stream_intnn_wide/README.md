# eeg_burst_stream_intnn_wide: seizure-like EEG burst

One EEG channel: 24 raw samples (1.5 s) streamed in one 15-bit word per strobe -> seizure-like burst yes/no.

- Simulated signal and event: 24 samples at 16 Hz (6-bit signed, about 5 uV per unit) of AR(1) background noise; the event is a 3 Hz spike-and-wave burst of 12-22 units from a random onset; 30 % of normal windows carry a slow blink-like bump.
- Model: intnn ternary, layers [24, 8, 1], 200 weights (ternary hidden, 5-bit output layer); input 24 lanes x 6-bit signed.
- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 test windows in `vectors.npz`; inputs ['x'], expected outputs ['y'], ground truth ['label_y'].
- Detection (y, model on the synthetic test windows): sensitivity 0.968 (125 events), specificity 0.977, accuracy 0.973 on 256 synthetic test windows.
- Integer model accuracy on the synthetic training windows: 0.983.
- Expected outputs: plain numpy of the intnn integer semantics (h = clip((W h + b) >> shift, 0, amax); score > 0 or argmax).

Synthetic data from a seeded generator, not patient data; the detection figures are on synthetic test windows and make no clinical claim. Rebuilt by `m3/examples/gen_gallery.py`; chip numbers in `../RESULTS.md`.
