# vibration_intnn_binary

Machine vibration: 8 band-energy deviations (4-bit signed) -> bearing fault yes/no.

- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 in `vectors.npz`; inputs ['x'], expected outputs ['y'].
- intnn, binary hidden weights, layers [8, 8, 1], input 8 lanes x 4-bit signed, spike single-layer form.
- Accuracy of the integer model on synthetic data (numpy, this Mac): train 0.915, held-out vectors 0.926.
- Expected outputs: plain numpy of the intnn integer semantics (h = clip((W h + b) >> shift, 0, amax); score > 0 or argmax).

Synthetic data, seeded; rebuilt by `m3/examples/gen_gallery.py`. Chip numbers: `../RESULTS.md`.
