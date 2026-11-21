# hr_alarm_intnn_binary: heart-rate alarm

Wearable heart-rate sensor: 8 readings over 16 s -> abnormal rate alarm yes/no.

- Simulated signal and event: 8 heart-rate samples (one per 2 s, 4-bit signed, 8 bpm per unit from resting); the event is a sustained rise of 25-55 bpm or fall of 22-40 bpm ramping in from a random onset, against drift, noise and one-sample motion spikes.
- Model: intnn binary (spike single-layer form), layers [8, 8, 1], 72 weights (binary hidden, 5-bit output layer); input 8 lanes x 4-bit signed.
- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 test windows in `vectors.npz`; inputs ['x'], expected outputs ['y'], ground truth ['label_y'].
- Detection (y, model on the synthetic test windows): sensitivity 0.927 (123 events), specificity 1.000, accuracy 0.965 on 256 synthetic test windows.
- Integer model accuracy on the synthetic training windows: 0.968.
- Expected outputs: plain numpy of the intnn integer semantics (h = clip((W h + b) >> shift, 0, amax); score > 0 or argmax).

Synthetic data from a seeded generator, not patient data; the detection figures are on synthetic test windows and make no clinical claim. Rebuilt by `m3/examples/gen_gallery.py`; chip numbers in `../RESULTS.md`.
