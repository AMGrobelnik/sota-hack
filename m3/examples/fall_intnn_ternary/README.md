# fall_intnn_ternary

Wearable accelerometer: 6 window features (5-bit signed) -> fall yes/no.

- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 in `vectors.npz`; inputs ['x'], expected outputs ['y'].
- intnn, ternary hidden weights, layers [6, 12, 1], input 6 lanes x 5-bit signed, multi-layer form.
- Accuracy of the integer model on synthetic data (numpy, this Mac): train 0.960, held-out vectors 0.953.
- Expected outputs: plain numpy of the intnn integer semantics (h = clip((W h + b) >> shift, 0, amax); score > 0 or argmax).

Synthetic data, seeded; rebuilt by `m3/examples/gen_gallery.py`. Chip numbers: `../RESULTS.md`.
