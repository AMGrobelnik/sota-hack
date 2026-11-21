# multi_sensor_fusion_kofn: multi-sensor fusion alarm

Three vital-sign sensors on three ports, mixed model formats -> 2-of-3 vote deterioration alarm.

- Simulated signal and event: a hidden deterioration state (half the windows) shows in each of heart rate (+20-40 bpm), respiration rate (+6-12 /min) and SpO2 (4-8 points down) with probability 0.85; each sensor also shows a spurious abnormality in 8 % of stable windows; 4 samples per sensor.
- Model: multi-head fusion (compose-chip, kofn), heads: intnn ternary 4 -> 6 -> 1 (heart rate, respiration; 5-bit) and XGBoost 6 x depth 3 via TreeLUT (SpO2, 4-bit).
- Chip flow: `compose` (see `chip.json`).
- Vectors: 256 test windows in `vectors.npz`; inputs ['hr_x', 'resp_x', 'spo2_x'], expected outputs ['hr_y', 'resp_y', 'spo2_y', 'spo2_scores', 'alarm'], ground truth ['label_alarm', 'label_hr_y', 'label_resp_y', 'label_spo2_y'].
- Detection (alarm, model on the synthetic test windows): sensitivity 0.935 (139 events), specificity 0.966, accuracy 0.949 on 256 synthetic test windows.
- Detection (hr_y, model on the synthetic test windows): sensitivity 0.827 (139 events), specificity 0.872, accuracy 0.848 on 256 synthetic test windows.
- Detection (resp_y, model on the synthetic test windows): sensitivity 0.849 (139 events), specificity 0.897, accuracy 0.871 on 256 synthetic test windows.
- Detection (spo2_y, model on the synthetic test windows): sensitivity 0.806 (139 events), specificity 0.872, accuracy 0.836 on 256 synthetic test windows.
- Heads: heart rate and respiration rate (intnn ternary 4 -> 6 -> 1, 5-bit signed) and SpO2 (XGBoost 6 x depth 3 via TreeLUT, 4 x 4-bit), each on its own port; every head and the vote are scored against the hidden deterioration state.
- Expected fusion outputs: numpy over the heads' expected decisions (and = all, or = any, kofn = at least k).

Synthetic data from a seeded generator, not patient data; the detection figures are on synthetic test windows and make no clinical claim. Rebuilt by `m3/examples/gen_gallery.py`; chip numbers in `../RESULTS.md`.
