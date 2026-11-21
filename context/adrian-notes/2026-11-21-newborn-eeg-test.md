# Newborn seizure detection from EEG: quick feasibility test (Sat 21 Nov)

Verdict: with cheap features the test AUC is only 0.63 to 0.73, so this is not a working demo yet. The data and the pipeline are ready, and better features are the missing work.

This is a quick test run on Sat 21 Nov 2026 on the open Helsinki newborn EEG dataset. It is one seed and one split.

## Dataset structure

- 79 EDF recordings, one per baby, plus annotation files and a clinical information file.
- Each recording has 21 signals at 256 Hz: 19 EEG channels, plus ECG and respiration.
- Channel order differs between files (3 orderings), so channels are picked by name.
- One file has a bad header and needed a minimal custom reader.
- Total 111.90 h of data. Per baby: min 0.87 h, median 1.24 h, max 4.28 h.
- 3 experts (A, B, C) labelled each baby, one 0 or 1 value per second.
- Seizure share of seconds (402,825 s in total):

| Agreement rule | Share of seconds | Babies |
| --- | --- | --- |
| Any expert | 18.33% | 57 |
| 2 of 3 experts | 12.56% | 46 |
| All 3 experts | 9.75% | 39 |

- The test uses "all 3 experts agree" as the label. This is our reading of "consensus".

## Features and split by baby

- Windows of 8 s, step 4 s: 100,599 windows, 9,723 of them seizure windows (9.67%).
- Three cheap features per channel, 57 in total: line length, energy and zero crossings.
- A window is a seizure if more than 4 of its 8 seconds are all-3-expert seizure.
- Split by baby (seed 0), 60/20/20, so no baby is in two parts:

| Part | Babies | With seizure | Windows | Seizure windows |
| --- | --- | --- | --- | --- |
| train | 47 | 23 | 58,139 | 7,126 |
| val | 16 | 8 | 21,323 | 1,506 |
| test | 16 | 8 | 21,137 | 1,091 |

## Test metrics

Per window. The threshold was chosen on val. FA/h is false-positive windows per hour of test data, with no smoothing.

Main run:

| Model | AUC | Sens | Spec | FA/h |
| --- | --- | --- | --- | --- |
| Float MLP 57-32-1, 30 epochs | 0.6905 | 0.6994 | 0.5756 | 362.2 |
| Integer model (4-bit inputs, ternary weights) | 0.6288 | 0.3712 | 0.7814 | 186.6 |

Variant with each baby's median feature value removed (uses the whole recording, so not causal):

| Model | AUC | Sens | Spec | FA/h |
| --- | --- | --- | --- | --- |
| Float MLP | 0.6325 | 0.2869 | 0.8550 | 123.8 |
| Integer ternary | 0.7268 | 0.5573 | 0.8337 | 142.0 |

- The integer model beating the float one in the variant is split noise (16 test babies, one seed), not a real effect.
- Sanity check: within a baby, the AUC of mean line length has median 0.658 over 30 seizure babies. Pooled across babies it is 0.497. So the labels line up and the features carry some signal. But the features are far too weak across babies, and the signal level differs per baby.

## Batched candidates speed

64 random small candidate designs were trained together as one batch (3 epochs, 30,000 train windows). Training time only.

| Device | Seconds | Candidates per minute |
| --- | --- | --- |
| MPS | 0.56 | 6830 |
| CPU | 0.94 | 4103 |

- One timing each, no warm-up run, so treat it as an order of magnitude.
- Candidate quality is not good: val AUC over the 64 candidates was min 0.363, median 0.474, max 0.647 (3 epochs only, undertrained).

## Limits

- One seed, one split, no tuning, no search over epochs.
- 16 test babies (8 with seizures), so the metrics are noisy.
- Window-level only. No event-level metrics and no smoothing, so FA/h counts raw overlapping windows.
- No frequency-band features, no bipolar montage conversion, no artefact handling. Only the 3 cheap features.
- The threshold maximises sensitivity plus specificity on val. It is not set for a target sensitivity or false-alarm rate.
- The integer model was scored by simulating the integer arithmetic in torch. It was not exported or checked in Verilog.

## Not done

- No threshold re-selection for a target false-alarm rate.
- No event-level scoring and no tuning.
- No repeated seeds or cross-validation.
- No hardware export.
- No rerun of the batch after normalisation.

Source: the results file in the eeg-spike scratch folder on Adrian's Mac (not committed).
