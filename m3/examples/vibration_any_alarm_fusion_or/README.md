# vibration_any_alarm_fusion_or

One vibration sensor, two fault heads on the shared port (bearing wear, imbalance) -> OR: any-fault alarm.

- Chip flow: `compose` (see `chip.json`).
- Vectors: 256 in `vectors.npz`; inputs ['x'], expected outputs ['bearing_y', 'imbalance_y', 'any_fault'].
- Heads: two intnn ternary nets reading the same 8 x 4-bit signed input port (shared_inputs=true).
- Expected fusion outputs: numpy over the heads' expected decisions (and = all, or = any, kofn = at least k).

Synthetic data, seeded; rebuilt by `m3/examples/gen_gallery.py`. Chip numbers: `../RESULTS.md`.
