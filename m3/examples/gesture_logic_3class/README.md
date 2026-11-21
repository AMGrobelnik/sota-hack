# gesture_logic_3class

Gesture pad: 16 thresholded capacitive touch pads -> swipe-left / swipe-right / tap.

- Chip flow: `ingest` (see `chip.json`).
- Vectors: 256 in `vectors.npz`; inputs ['x'], expected outputs ['y', 'scores'].
- torchlogix LogicDense(16,48) -> LogicDense(48,48) -> GroupSum(3, tau=4), 150 Adam steps; model.pt is the saved module (pickle written on this machine).
- Accuracy of the discrete network on synthetic data (this Mac): train 0.972, held-out vectors 0.961.
- Expected outputs: torchlogix's own export-mode forward (also checked against eval mode x tau).

Synthetic data, seeded; rebuilt by `m3/examples/gen_gallery.py`. Chip numbers: `../RESULTS.md`.
