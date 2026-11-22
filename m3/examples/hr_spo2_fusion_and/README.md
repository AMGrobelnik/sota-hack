# hr_spo2_fusion_and: heart rate AND SpO2 alarm

Two sensors on two ports: abnormal heart rate AND desaturation -> confirmed alarm, which suppresses single-sensor false alarms.

- Simulated signal and event: windows from the heart-rate and SpO2 generators above, paired by index; the ground truth is both events present (independent draws, so about a quarter of the windows).
- Model: multi-head fusion (compose-chip, and), heads: intnn binary 8 -> 8 -> 1 (heart rate) and intnn 4-bit 6 -> 8 -> 1 (SpO2).
- Chip flow: `compose` (see `chip.json`).
- Vectors: 256 test windows in `vectors.npz`; inputs ['hr_x', 'spo2_x'], expected outputs ['hr_y', 'spo2_y', 'alarm'], ground truth ['label_alarm', 'label_hr_y', 'label_spo2_y'].
- Detection (alarm, model on the synthetic test windows): sensitivity 0.896 (67 events), specificity 1.000, accuracy 0.973 on 256 synthetic test windows.
- Detection (hr_y, model on the synthetic test windows): sensitivity 0.927 (123 events), specificity 1.000, accuracy 0.965 on 256 synthetic test windows.
- Detection (spo2_y, model on the synthetic test windows): sensitivity 0.984 (128 events), specificity 1.000, accuracy 0.992 on 256 synthetic test windows.
- Heads: heart rate (same parameters as hr_alarm_intnn_binary) and SpO2 (intnn 4-bit weights 6 -> 8 -> 1, 4-bit input), each on its own input port.
- Expected fusion outputs: numpy over the heads' expected decisions (and = all, or = any, kofn = at least k).

Synthetic data from a seeded generator, not patient data; the detection figures are on synthetic test windows and make no clinical claim. Rebuilt by `m3/examples/gen_gallery.py`; chip numbers in `../RESULTS.md`.
