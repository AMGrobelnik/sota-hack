# Feasibility test: ECG to gates on a Mac

Written by an AI agent during the event (Sat 21 Nov 2026). One seed, no tuning. The data (PhysioNet / CinC Challenge 2017 training set) is not in the repo; `src/prep.py` expects the downloaded zip.

# Chip spike: AF vs normal rhythm, ECG to gates

Folder: `./`. Python: `P=.venv/bin/python -I`.
All numbers below are copied from the logs in `logs/` and files in `work/`.

## Data and assumptions

- Data: PhysioNet / CinC Challenge 2017 training set (`data/training2017.zip`,
  99 MB, open access, downloaded in about a minute, no login). Fallback not needed.
- Labels in zip: N 5050, A 738, O 2456, ~ 284. Spike keeps only N (normal) and
  A (AF): 5788 recordings. Other rhythm and noisy classes are left out.
- Outside the circuit: R-peak detection (`wfdb.processing.xqrs_detect`, 300 Hz),
  RR intervals in ms, windows of 25 consecutive RR (stride 4, max 40 per recording),
  input quantisation (`common.py: quantise`): rr = floor(rr_ms / (2048/2^bits)) clipped,
  or drr = signed difference of successive quantised RR, clipped.
- Inside the circuit: everything after the quantised integers: ternary or binary
  weighted sums, integer bias, arithmetic shift, clip to 0..15, second weighted sum,
  bias, sign test. Output = 1 bit (AF if score > 0).
- Split by recording, stratified by class, seed 0: 70/15/15 train/val/test.
  Recordings with fewer than 25 RR intervals (480) are dropped (no window).
  Train/val/test recordings 4051/868/869 (AF 516/111/111); windows 16878/3688/3880
  (AF 3341/736/864). Test recordings with a window: 800 (96 AF).
- AF is the positive class. Record-level = majority vote of that recording's window
  decisions. Window-level is also reported, and is the level the circuit is checked at.

## Step 0, data prep
`P src/prep.py data/training2017.zip work/rr.npz` (log `logs/prep.log`; 0 failures, median 36 RR per recording).

## Step 1, full-precision baseline
`P src/baseline.py work/rr.npz` (log `logs/baseline.log`). MLP 48-64-64-1 (7361 params), float, MPS, 30 epochs.

| test | sens | spec | F1 |
|---|---|---|---|
| window-level | 0.9745 | 0.9334 | 0.8831 |
| record-level | 0.9688 | 0.9531 | 0.8378 |

(F1 is low next to sens/spec because AF is a minority class and false positives
are ~5% of 700 normals.) Record-level: 93/96 AF caught, 33 false positives.

## Step 2, K candidates as one batched program
`P src/batched.py work/rr.npz work timing` (logs `logs/timing.log`, `work/timing.json`);
selection run: `P src/batched.py work/rr.npz work select [max_HxL]`.
Formulation: stacked, zero-padded weights and `torch.bmm` (not `vmap`), straight-through
estimator for ternary/binary weights, integer biases, floor-shift, clip(0..15).
Candidates differ in window L in {8,16,24}, input bits in {4,5,6,8}, hidden width in
{4,8,16,32}, feature rr/drr, ternary/binary. 60 epochs, batch 512, 16878 training windows,
same epochs in every row. Time is training only (no data prep). No missing MPS operator.

| device | K | batched s | batched cand/min | one at a time cand/min |
|---|---|---|---|---|
| MPS | 1 | 2.37 | 25.3 | 27.6 (16 runs, 34.8 s) |
| MPS | 16 | 2.19 | 437.8 | |
| MPS | 64 | 2.86 | 1344.6 | |
| MPS | 256 | 9.45 | 1625.5 | |
| CPU | 1 | 1.06 | 56.7 | 56.0 (16 runs, 17.2 s) |
| CPU | 16 | 5.19 | 185.0 | |
| CPU | 64 | 20.85 | 184.1 | |
| CPU | 256 | 44.97 | 341.6 | |

One-at-a-time was measured on the first 16 candidates (K=1 per run) and is a per-candidate
rate; 64 and 256 one-at-a-time were not run separately (would be ~linear: ~2.3 min and ~9.3 min on MPS).
The yosys run overlapped part of the timing run on the CPU, so CPU numbers are noisy.
Batched MPS at K=256 is ~59x the one-at-a-time MPS rate, ~29x the one-at-a-time CPU rate.
Per-candidate validation scores (window F1, sens, spec, record F1) for all 256 are in
`work/val_scores.json` (small-model run) and the printed rows in `logs/select_unconstrained.log`
and `logs/select_small.log`. Validation window F1 spans up to 0.75 (unconstrained).

Selection, unconstrained (`logs/select_unconstrained.log`): best val window F1 0.7504 =
L24, 4 bit, H32, rr, ternary; torch test window F1 0.7812 (sens 0.7975, spec 0.93).
This circuit did NOT synthesise in time (see step 3), so it was replaced.
Selection with size cap H*L <= 128 (`logs/select_small.log`): best val window F1 0.7039 =
L8, 6 bit, H16, drr, ternary (sens 0.788, spec 0.8875 on val). This is the model used below.

## Step 3, gates (the shrunk model)
Export: `P src/export_verilog.py work/best.json work/af.v` (integer arithmetic, weights as constants).
Synthesis: `.venv/bin/yowasp-yosys -q -l logs/yosys_small.log -s src/synth.ys`
(`synth -top af -flatten`, then `abc -g AND,NAND,OR,NOR,XOR,XNOR,ANDNOT,ORNOT,MUX`, `stat`, `ltp -noff`).
Took under 1 min for the shrunk model (first yosys start includes a one-time wasm compile).

- Cells after `synth`: 2340. After `abc -g` to simple gates: 2330 (`work/stat_gates.txt`):
  XOR 428, XNOR 325, NAND 894, AND 229, OR 222, ORNOT 95, ANDNOT 69, NOR 36, MUX 25, NOT 7.
- Longest path (`ltp`): 52 cells (`work/ltp.txt`).
- Failed first attempt: the unconstrained best (L24, H32, 8503 cells before abc,
  `work/af_large.v`) was still inside `abc` after 11 minutes (over the 10 minute limit),
  killed. Shrunk by capping H*L at 128. Not retried with a different abc script.

## Step 4, same answers
`P src/verify.py work/rr.npz work/best.json work/net.json work/torch_test_pred.npy` (log `logs/verify.log`).
The gate netlist (`write_json`) is evaluated bit-parallel in numpy on all 3880 test
windows (not just 500), against an independent numpy int64 integer model and the torch forward.

- circuit vs integer model: 3880/3880 identical, 0 mismatches
- integer model vs torch forward: 3880/3880 identical
- circuit vs torch: 3880/3880 identical

Not done: Yosys `sim` or a second simulator; the netlist evaluator is my own code (a
bug would show as mismatches, none seen, but it is not an independent tool).

## Step 5, circuit accuracy next to the baseline (test set)

| model | level | sens | spec | F1 |
|---|---|---|---|---|
| float MLP baseline | window | 0.9745 | 0.9334 | 0.8831 |
| float MLP baseline | record | 0.9688 | 0.9531 | 0.8378 |
| gate circuit (L8, 6 bit drr, H16, ternary) | window | 0.7315 | 0.8790 | 0.6792 |
| gate circuit | record | 0.8333 | 0.8764 | 0.6084 |

The circuit is exact to the integer model but clearly less accurate than the float
baseline. The gap is a model gap, not a hardware gap.

## What was left out / caveats
- Only 60 epochs, one seed, no hyperparameter search beyond the 256 random candidates;
  the low-precision candidates top out near 0.75 val F1, which is not tuned. The window
  of 8 RR gives little context. More epochs/bits/richer features were not tried.
- The accuracy gap vs the float baseline was not investigated further (time-box).
- Large-model synthesis is slow in wasm Yosys; native Yosys or a different abc script
  may handle it.
- No per-gate timing or area in a real library; cell count and topological depth only.
- Test windows are overlapping (stride 4) within a recording; all windows of a recording
  share a split, so there is no leakage across splits.
