# irregular_beat_logic_3class: irregular beat

Beat-to-beat flags from a heart-rate sensor -> regular / isolated premature beat / irregular rhythm.

- Simulated signal and event: 17 simulated RR intervals give 16 flags (beat-to-beat change above 12 % of the mean RR); regular rhythm has 3 % jitter and a 4 % respiratory swing, a premature beat is one or two short-long pairs, an irregular rhythm has 20 % random RR variation.
- Model: torchlogix logic network, LogicDense(16,48) -> LogicDense(48,48) -> GroupSum(3, tau=4): 96 two-input logic gates; input 16 x 1-bit.
- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 test windows in `vectors.npz`; inputs ['x'], expected outputs ['y', 'scores'], ground truth ['label_y'].
- Detection (y, model on the synthetic test windows): accuracy 0.918, recall per class: regular 0.967, premature beat 0.903, irregular rhythm 0.902, on 256 synthetic test windows.
- 150 Adam steps; discrete network accuracy on the synthetic training windows: 0.952. model.pt is the saved module (pickle written on this machine).
- Expected outputs: torchlogix's own export-mode forward (also checked against eval mode x tau).

Synthetic data from a seeded generator, not patient data; the detection figures are on synthetic test windows and make no clinical claim. Rebuilt by `m3/examples/gen_gallery.py`; chip numbers in `../RESULTS.md`.
