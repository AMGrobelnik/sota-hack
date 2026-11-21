# gas_vote_fusion_kofn

Three redundant gas sensors on three ports, mixed model formats -> 2-of-3 vote alarm.

- Chip flow: `compose` (see `chip.json`).
- Vectors: 256 in `vectors.npz`; inputs ['gas_a_x', 'gas_b_x', 'gas_c_x'], expected outputs ['gas_a_y', 'gas_b_y', 'gas_c_y', 'gas_c_scores', 'gas_alarm'].
- Heads: gas_a, gas_b (intnn ternary 4 -> 6 -> 1, 5-bit signed) and gas_c (XGBoost 6 x depth 3 via TreeLUT, 4 x 4-bit), each on its own port.
- Expected fusion outputs: numpy over the heads' expected decisions (and = all, or = any, kofn = at least k).

Synthetic data, seeded; rebuilt by `m3/examples/gen_gallery.py`. Chip numbers: `../RESULTS.md`.
