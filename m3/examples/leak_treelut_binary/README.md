# leak_treelut_binary

Water pipe: 6 pressure/flow/acoustic features (4-bit) -> leak yes/no.

- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 in `vectors.npz`; inputs ['x'], expected outputs ['y', 'scores'].
- XGBoost 3.4.1, 8 rounds x depth 3, binary; TreeLUT w_feature=4, w_tree=3.
- Accuracy of TreeLUT's quantised model on synthetic data (this Mac): train 0.852, held-out vectors 0.836.
- Expected outputs: TreeLUT's own predict (vendored copy) and its per-class integer sums.
- `chipir.json`: the same model after the lab's TreeLUT converter, ingested as format chipir when the CLI's xgboost_json path fails (see ../RESULTS.md).

Synthetic data, seeded; rebuilt by `m3/examples/gen_gallery.py`. Chip numbers: `../RESULTS.md`.
