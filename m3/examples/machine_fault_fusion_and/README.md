# machine_fault_fusion_and

Motor monitor, two sensors on two ports: vibration head AND bearing-temperature head -> confirmed fault alarm.

- Chip flow: `compose` (see `chip.json`).
- Vectors: 256 in `vectors.npz`; inputs ['vib_x', 'temp_x'], expected outputs ['vib_y', 'temp_y', 'fault'].
- Heads: vibration (intnn binary, same parameters as vibration_intnn_binary) and temperature (intnn ternary 4 -> 6 -> 1), each on its own input port.
- Expected fusion outputs: numpy over the heads' expected decisions (and = all, or = any, kofn = at least k).

Synthetic data, seeded; rebuilt by `m3/examples/gen_gallery.py`. Chip numbers: `../RESULTS.md`.
