# impact_stream_intnn_wide

Structural monitor: 24 consecutive strain-gauge samples (6-bit signed) streamed in one 15-bit word per strobe -> impact yes/no.

- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 in `vectors.npz`; inputs ['x'], expected outputs ['y'].
- intnn, ternary hidden weights, layers [24, 8, 1], input 24 lanes x 6-bit signed, multi-layer form.
- Accuracy of the integer model on synthetic data (numpy, this Mac): train 0.824, held-out vectors 0.812.
- Expected outputs: plain numpy of the intnn integer semantics (h = clip((W h + b) >> shift, 0, amax); score > 0 or argmax).

Synthetic data, seeded; rebuilt by `m3/examples/gen_gallery.py`. Chip numbers: `../RESULTS.md`.
