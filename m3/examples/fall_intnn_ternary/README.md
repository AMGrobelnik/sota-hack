# fall_intnn_ternary: fall detection

Wrist accelerometer: 6 features of a 4 s window -> fall yes/no.

- Simulated signal and event: 6 accelerometer window features (5-bit signed: peak, jerk, tilt change, free-fall, stillness, step regularity); a fall shifts all six together, 25 % of non-falls are hard sit-downs with a high peak and jerk only; unit-variance noise x 3.
- Model: intnn ternary, layers [6, 12, 1], 84 weights (ternary hidden, 5-bit output layer); input 6 lanes x 5-bit signed.
- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 test windows in `vectors.npz`; inputs ['x'], expected outputs ['y'], ground truth ['label_y'].
- Detection (y, model on the synthetic test windows): sensitivity 0.897 (146 events), specificity 0.973, accuracy 0.930 on 256 synthetic test windows.
- Integer model accuracy on the synthetic training windows: 0.951.
- Expected outputs: plain numpy of the intnn integer semantics (h = clip((W h + b) >> shift, 0, amax); score > 0 or argmax).

Synthetic data from a seeded generator, not patient data; the detection figures are on synthetic test windows and make no clinical claim. Rebuilt by `m3/examples/gen_gallery.py`; chip numbers in `../RESULTS.md`.
