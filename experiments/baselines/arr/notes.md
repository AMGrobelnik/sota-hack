# ARR: heartbeat chips on MIT-BIH vs a weightless-network FlexIC

## Verdict

Not reached. On the baseline's own published split (round 18, test patients
107, 213, 209) the best chip found detects 2063 of 3129 abnormal beats with 1
false alarm in 5320 normal beats. The baseline detects 2147 with 9. Our
specificity is higher (0.9998 against 0.9983) and our chip is much smaller
(304 sky130 gate-equivalents, combinational, against 2549 NAND2-equivalents),
but our sensitivity is lower (0.6593 against 0.6862). Over all 50 of the
baseline's rounds no design beats the baseline's own released per-round runs.
On the standard DS1/DS2 split no design reaches the 1,267-parameter CNN.

## Baselines, read at the primary sources

COIN FlexIC: Miranda et al., Weightless Neural Networks on Flexible
Substrates, IEEE TVLSI 34(2), 2026, doi 10.1109/TVLSI.2025.3630337,
preprint https://utw10244.utweb.utexas.edu/pubs/miranda_ieeevlsi26.pdf .
An earlier version is Pillai et al., arrWNN, https://par.nsf.gov/servlets/purl/10636425 .
Code: https://github.com/lasdi/flexwnn (no licence file; we read it and
reuse none of its code).

- Task: MIT-BIH Arrhythmia, lead 0 (MLII), two classes. Normal is AAMI N
  (N, L, R, e, j) plus the rhythm mark '+'. Abnormal is everything else they
  keep: S (A, a, J, S), V (V, E and the flutter marks [, !, ]), F, and Q,
  which includes the paced beats '/' and 'f'.
- Before the chip (paper: "no preprocessing steps were synthesized into the
  chip"): Pan-Tompkins band-pass (9 to 21.6 Hz at 360 Hz), a 187-sample window
  at each annotated R peak (samples 0 to 185 kept), per-beat min-max
  normalisation to 16 bits, a 2-level thermometer (x >= 128, x >= 32768), a
  fixed random bit mapping. 376 bits (372 plus 4 zero pads) go in serially.
- On the chip: the COIN minterm logic (741 minterms), up/down counters,
  argmax, serial-to-parallel input. 2549 NAND2-eq after synthesis, of which
  36.7 percent of area is sequential; 5706 NAND2-eq after layout; Pragmatic
  0.6 um IGZO FlexIC; 306 test inferences matched simulation. No formal proof
  is reported (Pillai mentions formal verification but gives no detail).
- Split: Monte Carlo rounds of patient-wise train / val / test lists. The
  generator always puts three patients in test: one paced (102, 104, 107,
  217), one of 208 or 213, one S-rich patient (209, 222, 201, 118, 220).
  The paper says 50 rounds.
- Metric: per beat. Sensitivity = abnormal beats flagged / abnormal beats,
  specificity = normal beats passed / normal beats.
- The published point, sensitivity 0.6862 at specificity 0.9983, is one
  model on one round. In the released archive (cv_almost_2023-05-04, 41 of
  50 rounds) round 18 holds exactly that model: 741 minterms, 0.68616 and
  0.99831, test patients 107, 213, 209. As counts: 2147 of 3129 abnormal
  and 9 false alarms in 5320 normals. The authors chose it as the round
  whose test AUC was nearest the mean.
- The same archive, with the authors' own rule (best validation AUC per
  round): mean sensitivity 0.744, mean specificity 0.933, specificity of at
  least 0.998 in 4 of 41 rounds. The paper reports a mean accuracy of 0.8604
  and a mean AUC of 0.8429 over 50 rounds; the archive gives 0.857 and 0.839.

Inter-patient baseline: A Tiny Matched Filter-Based CNN, Sensors 23(3) 1365,
2023, doi 10.3390/s23031365, https://pmc.ncbi.nlm.nih.gov/articles/PMC9919183/ .
Model 6 has 1,267 parameters (882 trainable). Three classes (N, SVEB, VEB),
DS1 for training (records under 200 train, the rest validate), DS2 for
testing. VEB sensitivity 95.00 and PPV 95.63; SVEB sensitivity 81.60 and PPV
82.68; accuracy 98.18. Inputs: three ECG segments (derivative) plus RR
features. It runs in software on a cloud machine and a Raspberry Pi; it is
not a chip.

## What we reproduced, and every difference

Same database, same patient lists (read from the baseline's archive), same
labels, same per-beat metric. Our class counts per round equal the
baseline's archived counts for test and validation in all 49 rounds that
have a count file. Over all 48 records we get 91793, 2779, 7718, 802 and 8035
beats per class, the numbers in the baseline's code comment.

Differences:

1. The baseline's band-pass file (PTA_1) is not in its repository. We run
   the original Pan-Tompkins integer low-pass and high-pass at 360 Hz. We
   tried three variants (with the 21-sample delay removed, without, and a
   zero-phase Butterworth) and picked by mean validation sensitivity on six
   rounds, never on test (filter_check.py). The Butterworth scored highest on
   validation but contradicts the paper's description (integer additions and
   shifts), so we kept the Pan-Tompkins form without delay removal. Our bits
   may still differ from the baseline's.
2. The baseline uses one fixed model chosen from one round. We train a
   model per round on that round's training patients (normal beats subsampled
   to 20000) and fix its threshold on that round's validation patients.
3. Operating point. The baseline uses its argmax rule. Our headline rule,
   set before we saw any test result: the threshold giving specificity of at
   least 0.999 on the validation normals. The 0.998, 0.995 and 0.99 rules are
   reported too.
4. Inputs. Strict track (S*): exactly the baseline's 372 bits. Finer track
   (Q*): the same normalised samples with a 7-level thermometer as well (same
   steps before the chip, finer quantisation; this is the one change to the
   chip input). Extended track (E*): also three RR intervals (previous, next,
   and the mean of the last 8, in samples), measured before the chip from the
   annotated R peaks. The baseline computes no RR intervals. The RR ratio
   tests themselves (64 x RR >= k x mean) run on the chip.
5. Our chips are combinational with parallel inputs. The baseline loads 376
   bits serially and counts. For two designs we also built the lab's streaming
   wrapper and give its flip-flop count (see below).
6. Gate counts. The lab reports generic 2-input gates and, per open PDK,
   area divided by the NAND2 cell area (gate-equivalents). The baseline's
   NAND2-equivalents come from the Pragmatic FlexIC library. Both are
   area / NAND2, but the libraries differ (resistive-load n-type against
   CMOS), so the ratio is indicative only.

## The designs (all integer, every weight a constant in the logic)

Each beat's chip computes an integer score from binary inputs and compares
it with a constant. Trees become the OR of their positive leaf paths (one
small lookup table per leaf). Boosted depth-2 trees sum signed integer leaf
values (q = 7 to 63, the smallest that keeps the training AUC within 0.002).
Linear models: L1 logistic regression, top-k weights rounded to integers on
the same q rule. RR tests: 64 x RR_prev <= round(64 g) x RR_mean on a fixed
grid of g.

Chosen design E2 (tree, depth 4, round 18): it flags a beat when all four
hold: RR_prev / RR_mean > 0.9 (64 x prev > 58 x mean), sample 127 >= 2/8 of
the beat's range, sample 149 < 3/8, sample 114 < 4/8. Inputs: 3 one-bit
inputs plus 3 x 11-bit RR values. It finds 2058 of patient 107's 2135 paced
and ventricular beats and almost nothing else (0 of 384 in 209, 5 of 610 in
213). It is a paced-beat detector, which is what the round's positives are
mostly made of.

## Round 18, the published split (headline rule)

| design | TP/3129 | FP/5320 | sky130 GE |
| --- | --- | --- | --- |
| baseline COIN | 2147 | 9 | 2549 (FlexIC) |
| S2 tree d5 | 53 | 2 | 11.3 |
| S3 lin64 | 1 | 0 | 965.3 |
| S4 gbdt48 | 99 | 2 | 2736.7 |
| Q1 tree d4 | 12 | 0 | 7.7 |
| Q2 lin32 | 34 | 2 | 488.3 |
| Q3 gbdt16 | 929 | 3 | 1036.3 |
| Q4 gbdt48 | 1549 | 1 | 1751.0 |
| E2 tree d4 | 2063 | 1 | 303.7 |
| E3 lin32 | 4 | 2 | 2525.3 |
| E4 gbdt16 | 31 | 0 | 3110.3 |
| E5 gbdt48 | 15 | 0 | 6107.3 |

S1 (popcount width proxy, 2409.7 GE) and E1 (RR-only tree, constant output)
detect nothing. Wilson intervals, per-patient counts, gf180 and IHP numbers
are in results.json. E2: sensitivity 2063/3129 = 0.6593 [0.6425, 0.6757],
specificity 5319/5320 = 0.9998 [0.9989, 1.0].

Non-headline rule, reported because it would change the verdict: with the
validation threshold at specificity 0.99, E2 flags 2213 of 3129 (0.7073) with
10 false alarms (specificity 0.99812). That beats 2147 and 9 on this round,
but the rule was not chosen in advance; at 0.99, Q4 gives 2178 with 8.

## All 50 rounds (headline rule, pooled beats)

Pooled sensitivity stays at or below 0.29 for every chip: E2 22336/165716 =
0.135 at specificity 0.9983; Q4 47292/165716 = 0.285 at 0.988. Patient
bootstrap intervals (resampling within the three groups) are in results.json.
E2 has specificity of at least 0.998 in 42 of 50 rounds (the baseline's runs:
4 of 41). Head-to-head with the baseline's released runs (higher sensitivity
and no lower specificity in the same round): 0 of 41 for E2, 1 of 41 for Q4.
The worst subjects are S-rich patients: 209 (0 of 4992 pooled for most
designs), 118 and 220.

## Float references (not chips, 6 rounds)

Gradient boosting on the 186 float samples plus RR ratios flags 1904 of 3129
on round 18 with 0 false alarms; on the 372 baseline bits alone it flags
921 with 4. Pooled over six rounds: 0.6585 sensitivity at 0.9844 specificity
(samples plus RR) and 0.3516 at 0.9393 (baseline bits). The 2-level code
loses most of what separates the paced beats, and S beats need RR timing.

## Inter-patient DS1 / DS2

Standard AAMI labels, paced records excluded, thresholds fixed on DS1 only
(record-grouped 5-fold CV inside DS1 picks the false-positive rate that
maximises F1). Our extraction drops the first two and the last annotation
of each record, so DS2 has 44218 N, 1836 S, 3219 V (paper: 44259, 1837, 3221).
Best V: boosted trees DS_D, sensitivity 2854/3219 = 0.8866 [0.8752, 0.8971],
PPV 2854/2933 = 0.9731. Best S: DS_B tree, 1370/1836 = 0.7462 at PPV 0.2703;
DS_C linear 868/1836 = 0.4728 at PPV 0.6147. The CNN's 95.00 / 95.63 (V) and
81.60 / 82.68 (S) are not reached. Chip sizes (V plus S heads, sky130 GE):
DS_D 3229.3 + 2777.7, DS_C 2125.7 + 1853.3, DS_B 666.0 + 694.7.

## The chip lab's checks

Every chip in the tables: compile from the chipir/1 document, Yosys/ABC
synthesis (generic gates, logic depth), mapping to sky130_fd_sc_hd, gf180mcu
and IHP SG13G2 (area, gate-equivalents), bit-exact simulation on the held-out
test beats' actual inputs (8449 beats for round 18, 49668 for DS2) against
both the lab's integer model and our own model outputs, 100000 random
vectors, and a formal proof (ABC cec of gates against RTL plus ABC iprove of
RTL against an independent golden model, every input). Verification level 2.
All passed. Streaming wrappers (prove-sequential, level 2 for the clocked
part): E2 needs 45 flip-flops (estimated total about 544 sky130 GE), Q4 needs
115 (about 2364 GE). Estimates use the dfxtp_1 area in NAND2 units; no
layout was run (Docker is off by design).

## Iteration history (honesty)

1. First design set (strict bits only, 0.999 rule) run on round 0: nearly
   zero sensitivity. We then added the finer thermometer and the RR track.
2. That set was run on round 18 and we saw its test result. We then changed
   leaf and weight quantisation to the training-AUC rule above (the
   coarse 4-bit rounding was flattening boosted models).
3. Filter variant picked on validation only (above).
4. The final run (all 50 rounds, this file's numbers) used the frozen code.
   Round 18 E2 gave the same 2063 / 1 in every version.

## Data, licence, credit

MIT-BIH Arrhythmia Database v1.0.0, PhysioNet, Open Data Commons
Attribution License v1.0, https://physionet.org/content/mitdb/1.0.0/ ,
downloaded with the documented wget command, SHA-256 checked. Cite: Moody GB,
Mark RG, The impact of the MIT-BIH Arrhythmia Database, IEEE Eng Med Biol
20(3):45-50, 2001; Goldberger AL et al., PhysioBank, PhysioToolkit, and
PhysioNet, Circulation 101(23):e215-e220, 2000. No recording or derived
waveform is in this repository.

## Reproduce

prep.py (beats), filter_check.py, run_coin.py (rounds), run_ds.py,
make_chip_job.py and chip_eval.py (the lab), summarize.py and
compact_results.py (results.json). models/ holds the chosen designs as
chipir/1 documents.
