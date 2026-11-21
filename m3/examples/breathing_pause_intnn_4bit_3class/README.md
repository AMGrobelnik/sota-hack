# breathing_pause_intnn_4bit_3class: breathing pause

Chest respiration band: breath amplitude over 30 s -> normal / shallow / pause.

- Simulated signal and event: 6 breath-amplitude sub-windows of 5 s (4-bit); shallow breathing scales 2-4 consecutive sub-windows to 35-60 %, a pause holds 2-3 consecutive sub-windows near zero (10-15 s); per-window and per-sample noise.
- Model: intnn 4bit, layers [6, 10, 8, 3], 164 weights (4bit hidden, 5-bit output layer); input 6 lanes x 4-bit unsigned.
- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 test windows in `vectors.npz`; inputs ['x'], expected outputs ['y'], ground truth ['label_y'].
- Detection (y, model on the synthetic test windows): accuracy 0.953, recall per class: normal 0.957, shallow 0.988, pause 0.914, on 256 synthetic test windows.
- Integer model accuracy on the synthetic training windows: 0.944.
- Expected outputs: plain numpy of the intnn integer semantics (h = clip((W h + b) >> shift, 0, amax); score > 0 or argmax).

Synthetic data from a seeded generator, not patient data; the detection figures are on synthetic test windows and make no clinical claim. Rebuilt by `m3/examples/gen_gallery.py`; chip numbers in `../RESULTS.md`.
