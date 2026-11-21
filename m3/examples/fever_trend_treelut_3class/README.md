# fever_trend_treelut_3class: fever trend

Skin-temperature patch: 6 readings over 3 h -> normal / rising trend / fever.

- Simulated signal and event: 6 samples one per 30 min (4-bit, 0.25 C per unit above 36.0 C); normal is flat at 36.4-37.2 C, a rising trend climbs 0.24-0.44 C per hour from 36.5-37.0 C, fever sits at 38.0-39.5 C; 0.12 C noise.
- Model: XGBoost via TreeLUT, 6 rounds x depth 3 (18 trees), 3 classes, TreeLUT w_feature=4, w_tree=3; input 6 x 4-bit.
- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 test windows in `vectors.npz`; inputs ['x'], expected outputs ['y', 'scores'], ground truth ['label_y'].
- Detection (y, model on the synthetic test windows): accuracy 0.973, recall per class: normal 0.937, rising 0.977, fever 1.000, on 256 synthetic test windows.
- XGBoost 3.4.1; TreeLUT quantised model accuracy on the synthetic training windows: 0.978.
- Expected outputs: TreeLUT's own predict (vendored copy) and its per-class integer sums.
- `chipir.json`: the same model after the lab's TreeLUT converter, ingested as format chipir when the CLI's xgboost_json path fails (see ../RESULTS.md).

Synthetic data from a seeded generator, not patient data; the detection figures are on synthetic test windows and make no clinical claim. Rebuilt by `m3/examples/gen_gallery.py`; chip numbers in `../RESULTS.md`.
