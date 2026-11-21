# hvac_intnn_4bit_3class

Room climate: 6 sensor readings (4-bit) -> idle / heat / cool.

- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 in `vectors.npz`; inputs ['x'], expected outputs ['y'].
- intnn, 4bit hidden weights, layers [6, 10, 8, 3], input 6 lanes x 4-bit unsigned, multi-layer form.
- Accuracy of the integer model on synthetic data (numpy, this Mac): train 0.781, held-out vectors 0.773.
- Expected outputs: plain numpy of the intnn integer semantics (h = clip((W h + b) >> shift, 0, amax); score > 0 or argmax).

Synthetic data, seeded; rebuilt by `m3/examples/gen_gallery.py`. Chip numbers: `../RESULTS.md`.
