# spo2_drop_treelut_binary: SpO2 drop

Pulse oximeter: 6 SpO2 readings over 30 s -> desaturation yes/no.

- Simulated signal and event: 6 SpO2 readings (one per 5 s, 4-bit as 100 minus SpO2 %); the event is a dip of 4-10 points with partial recovery from a random onset; 20 % of normal windows carry a one-sample motion-artefact drop.
- Model: XGBoost via TreeLUT, 8 rounds x depth 3 (8 trees), binary, TreeLUT w_feature=4, w_tree=3; input 6 x 4-bit.
- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 test windows in `vectors.npz`; inputs ['x'], expected outputs ['y', 'scores'], ground truth ['label_y'].
- Detection (y, model on the synthetic test windows): sensitivity 1.000 (126 events), specificity 1.000, accuracy 1.000 on 256 synthetic test windows.
- XGBoost 3.4.1; TreeLUT quantised model accuracy on the synthetic training windows: 0.997.
- Expected outputs: TreeLUT's own predict (vendored copy) and its per-class integer sums.
- `chipir.json`: the same model after the lab's TreeLUT converter, ingested as format chipir when the CLI's xgboost_json path fails (see ../RESULTS.md).

Synthetic data from a seeded generator, not patient data; the detection figures are on synthetic test windows and make no clinical claim. Rebuilt by `m3/examples/gen_gallery.py`; chip numbers in `../RESULTS.md`.
