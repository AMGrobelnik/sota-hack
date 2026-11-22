# Baseline AF: hard-wired AF detector from RR intervals

## Verdict

The baseline is only partly reached.

- Chosen design: `and2_n128`, an AND of two integer count thresholds over
  a 128-interval window.
- Held-out subjects, MIT-BIH AF database, leave-one-subject-out:
  sensitivity 3616/3754 = 96.3 %, specificity 4861/5071 = 95.9 %.
- Published chip (Andersson 2015): 94.9 % / 95.8 %, tuned on the same
  data it reports.
- Sensitivity is higher: the Wilson lower bound is 95.7 %. Specificity
  is equal within noise (+0.06 points).
- This holds only for designs picked after seeing the AFDB results.
- When the design choice is moved inside the folds (nested selection),
  specificity is 4777/5071 = 94.2 %, below the chip's 95.8 %.
- At beat level the chosen design's specificity is 95.6 %, also below.
- The chip is larger than the published one, not smaller:
  38,441 sky130 gate-equivalents for the whole sequential chip (window
  registers included) against 24,038 NAND2-eq for Andersson's 65 nm
  synthesis.
- FDA goals (90 % / 92 %) are met by the point estimates and Wilson
  bounds. The subject-bootstrap lower bound on specificity clears 92 %
  only for the fixed design on AFDB (92.4 %). It falls short for
  nested selection (87.5 %) and on the Long-Term AF database (88.0 %).

## Baselines, confirmed at the primary source

### Andersson et al. 2015, IEEE TBioCAS 9(3)

Title: "A 290 mV Sub-VT ASIC for Real-Time Atrial Fibrillation Detection".
PDF: <https://biosignal.uconn.edu/wp-content/uploads/sites/2503/2018/09/11_Andersson_2015_TBCS.pdf>

- Table III, MIT-BIH AF database, present implementation (PrecSeg):
  sensitivity 94.9 %, specificity 95.8 %. CurrSeg: 90.6 % / 97.6 %.
- Table II: segment N = 128 RR intervals. Thresholds: TPR low 0.46,
  TPR high 0.84, RMSSD 0.15, SE 0.84.
- Thresholds and N come from a grid search on the same databases.
  There is no held-out subject and no subject-wise split.
- Evaluation uses a bit-accurate fixed-point model run on the database RR
  series. The silicon received the same RR test patterns.
- Table IV gives the synthesis area in 65 nm LL-HVT CMOS: 50,000 um2,
  24,038 NAND2-eq (PrecSeg with a shared multiplier). Dedicated
  multipliers: 88,300 um2, 42,452 NAND2-eq.
- Total silicon area including the peripheral circuit: 0.10 mm2 (Fig. 9).
- RAM: 1664 bits of standard-cell memory (128 intervals x 13 bits).
- On their chip: ectopic-beat preprocessing, TPR, RMSSD, Shannon
  entropy (with a log2 unit and a shared multiplier), the thresholds and the
  RAM.
- Not on their chip: the R-wave detector and the RR-interval computation
  (Fig. 1 places "R-wave Classification" and "Delta RR interval" before
  the AF detector).
- Output: one decision per segment of 128 RR intervals (Fig. 10). The
  clock is 1 kHz.

### Dash et al. 2009, Annals of Biomedical Engineering

PDF: <https://biosignal.uconn.edu/wp-content/uploads/sites/2503/2018/09/10_Dash_2009_AnnalsBME.pdf>

- The algorithm that Andersson's chip implements. It works on
  contiguous l-beat segments.
- A segment counts as true AF if more than PercThresh of its beats are
  annotated AF. The optimum is l = 128 and PercThresh = 50 %.
- Published thresholds: 0.54 < TPR < 0.77, RMSSD > 0.1 x meanRR,
  SE > 0.7.
- MIT-BIH AF database: 94.4 % / 95.1 % (Table 2, column "AF beats").
- Records 04936 and 05091 were excluded "because some RR intervals were
  incorrectly annotated". The thresholds were optimised on the same
  database.

### Cinotti et al. 2025, Sensors 25(23):7244

Source: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12694393/>

- An INT8 1D-CNN on 25, 50 or 100 RR intervals, run on a microcontroller.
- Data: 23 AFDB subjects (00735 and 03665 excluded, since they have no ECG
  signal), 5-fold subject-wise CV.
- Other arrhythmias were removed. Sinus-rhythm windows were randomly
  undersampled to balance the classes.
- INT8 accuracy: 0.963, 0.976 and 0.980 for 25, 50 and 100 RR.
- Reported true-positive / true-negative rates (INT8): 25 RR 97.1 / 95.3,
  50 RR 98.0 / 96.9, 100 RR 97.4 / 98.3.
- Flash use is 48.6 to 86.6 KB. No parameter count is reported.
- Not like for like with this work: its classes are balanced and its
  other arrhythmias were removed.

### FDA De Novo DEN180044 (ECG App, 2018)

PDF: <https://www.accessdata.fda.gov/cdrh_docs/reviews/DEN180044.pdf>

- Quote: "The sensitivity and specificity performance goals were set at 90%
  and 92% respectively." Only readable, classifiable recordings counted.
- The task differs: a 30-second single-lead ECG strip against a 12-lead
  reference, in 602 subjects.

## Data

- MIT-BIH Atrial Fibrillation Database (afdb 1.0.0), ODC Attribution
  v1.0, <https://doi.org/10.13026/C2MW2D>.
  Cite: Moody GB, Mark RG. A new method for detecting atrial fibrillation
  using R-R intervals. Computers in Cardiology 10:227-230 (1983).
  Also cite Goldberger et al., PhysioBank, PhysioToolkit and PhysioNet,
  Circulation 101(23):e215-e220 (2000).
- Long-Term AF Database (ltafdb 1.0.0), ODC Attribution v1.0,
  <https://doi.org/10.13026/C2QG6Q>.
  Cite: Petrutiu S, Sahakian AV, Swiryn S. Abrupt changes in fibrillatory
  wave characteristics at the termination of paroxysmal atrial
  fibrillation in humans. Europace 9:466-470 (2007).
  Also cite Goldberger et al. (2000).
- Only the annotation files (.atr, .qrs, .hea) were downloaded with wget
  from physionet.org/files/. No signal was downloaded, and no data is in
  this repository.

## Protocol used here

- Records: the 23 AFDB records Dash 2009 used (all 25 minus 04936 and
  05091). Beats come from the database `.qrs` files, rhythm from `.atr`.
  00735 and 03665 have no ECG signal but do have both annotation files,
  so they are kept.
- LTAFDB: all 84 records. Beats come from the reviewed `.atr` beat
  labels (non-beat symbols dropped).
- RR interval: the time between consecutive beats, in 8 ms units,
  saturated at 255 (2.04 s). It is an 8-bit unsigned value. An interval
  takes the rhythm label active at the beat that ends it.
- Segments: contiguous, non-overlapping blocks of N intervals from the
  start of each record. A segment is AF if more than 50 % of its
  intervals are `(AFIB`. Every other rhythm (N, AFL, J and, in LTAFDB,
  SVTA, AB, B, T, VT and others) counts as non-AF.
- Window lengths: N = 16, 32, 64 and 128.
- Splits:
  - AFDB uses leave-one-subject-out: 23 folds, each record one subject.
  - Cross-database: train on all 23 AFDB records, test on all 84
    LTAFDB records.
- Fitting: everything is fitted on training subjects only, including
  the feature choice, weights, thresholds and tree splits. The operating
  point is the training-set Youden point (largest sens + spec).
- Metrics: segment-level sensitivity and specificity, pooled over
  subjects.
  - Intervals: a Wilson 95 % interval on the pooled count, plus a
    subject-level bootstrap 95 % interval (2000 resamples of subjects,
    seed 0).
  - Worst subject: overall, and among subjects with at least 10 windows
    of the class.
  - Beat level, as in the Dash Table 2 "AF beats" column: every interval
    inherits its segment's decision.
- Nested selection (N = 128): inside each outer fold, an inner
  leave-one-subject-out on the 22 training subjects chooses the feature
  set (v1 or v2) and the family (thr1, and2, tree3 or lin). The winner
  is refitted on those 22 subjects and applied to the held-out one.

## Every difference from the Andersson / Dash protocol

1. Split.
   - Here: subject-wise held-out (leave-one-subject-out).
   - Theirs: thresholds grid-searched on the whole database that they
     report on.
   - Effect: theirs is optimistic, ours is stricter.
2. Ectopic-beat filter.
   - Theirs: drops ectopic beats (percentile rules) before forming
     segments, so their segment boundaries differ.
   - Here: no filter.
3. Beat source.
   - Here: `.qrs`.
   - Theirs: the paper does not name the annotation file.
4. Atrial flutter.
   - Here: counted as non-AF.
   - Theirs: handling not stated.
5. Unit of Se and Sp. Andersson says "AF episodes", while Dash's
   Table 2 column says "AF beats". We report both: segment level is
   the headline, beat level is secondary.
6. Arithmetic.
   - Here: RR quantised to 8 ms, 8 bits.
   - Theirs: 12 fractional bits.
7. Features.
   - Here: integer counts, no multiplier, no division, no log.
   - Theirs: TPR, RMSSD and Shannon entropy.
8. Intervals. Andersson and Dash report no confidence interval.
9. Design choice after the first look.
   - The first feature set (v1) was evaluated on AFDB and LTAFDB first.
   - A second set (v2: lag-2 and lag-3 relative differences and a run
     count, aimed at bigeminy and trigeminy) was added after seeing
     those results.
   - The `and2_n128` design was picked from 20 designs after seeing the
     AFDB leave-one-subject-out results.
   - v1 results are kept in `results.json`. The nested-selection run
     measures what that choice costs.

## Where each step runs

- Off chip: R-peak detection (the database annotations) and RR interval
  timing, quantised to an 8-bit count of 8 ms ticks. Andersson's
  R-wave detector and RR computation are also off chip.
- On chip, through the lab's `compile-stream` wrapper:
  - The RR intervals arrive one word per strobe.
  - The window is held in flip-flops (1024 bits for N = 128, against
    Andersson's 1664-bit RAM).
  - Combinational logic then computes every feature and the classifier
    in parallel over the window.
- `and2_n128` on chip:
  - Successive differences d_i = r_(i+1) - r_i and their absolute values.
  - Comparisons |d_i| > r_i >> 5 (about 3 %), popcounted over 127
    intervals.
  - Lag-3 differences |r_(i+3) - r_i| > r_i >> 4, popcounted over 125.
  - Two thresholds: count1 >= 94 and count2 >= 72, ANDed.
- Unlike Andersson's chip, which computes the statistics sequentially
  with a shared multiplier, this one evaluates the whole window in
  parallel. That is the main reason it is larger.
- The lab's streaming tool only buffers a frame and runs a combinational
  core. It has no way to build an incremental (running-count)
  sequential feature unit.

## Results (N = 128, segment level, held-out subjects)

AFDB leave-one-subject-out: 8825 windows, 3754 of them AF, 23 subjects.

| design | Se k/n | Se % | Sp k/n | Sp % |
| --- | --- | --- | --- | --- |
| and2 (chosen) | 3616/3754 | 96.33 | 4861/5071 | 95.86 |
| tree3 | 3619/3754 | 96.40 | 4864/5071 | 95.92 |
| nested choice | 3623/3754 | 96.51 | 4777/5071 | 94.20 |
| lin | 3590/3754 | 95.63 | 4835/5071 | 95.35 |
| thr1 | 3567/3754 | 95.02 | 4709/5071 | 92.86 |
| Dash fixed | 3402/3754 | 90.62 | 4718/5071 | 93.04 |
| float logreg | 3700/3754 | 98.56 | 4894/5071 | 96.51 |
| float GBDT | 3685/3754 | 98.16 | 4962/5071 | 97.85 |

Intervals for the chosen design, `and2_n128`, on AFDB:

- Se: Wilson 95.67 to 96.88 %; subject bootstrap 92.41 to 98.58 %.
  Worst subject with at least 10 AF windows: 04043, 62/115.
- Sp: Wilson 95.27 to 96.37 %; subject bootstrap 92.43 to 98.67 %.
  Worst subject: 06426, 7/11.
- Beat level: Se 461054/479390 = 96.18 %, Sp 621536/650210 = 95.59 %.

For nested selection on AFDB:

- Se: Wilson 95.87 to 97.05 %; bootstrap 92.62 to 98.75 %.
- Sp: Wilson 93.53 to 94.81 %; bootstrap 87.45 to 98.72 %.
- Worst subject for Sp: 08219, 187/347. That fold chose v1 `lin`.

Train on AFDB, test on LTAFDB: 69514 windows, 40898 of them AF,
84 subjects. For `and2_n128`:

- Se 39808/40898 = 97.33 %. Wilson 97.17 to 97.49 %; bootstrap 95.00 to
  99.07 %. Worst subject: 112, 176/491.
- Sp 26499/28616 = 92.60 %. Wilson 92.29 to 92.90 %; bootstrap 87.99 to
  96.22 %. Worst subject: 103, 3/457. Record 103 has about 22,000
  atrial premature beats and SVTA and AB episodes.

`lin_n128` on LTAFDB:

- Se 39211/40898 = 95.88 %, bootstrap 92.93 to 98.21 %.
- Sp 27417/28616 = 95.81 %, bootstrap 91.94 to 98.61 %.

Dash fixed is our float re-implementation with the published
thresholds and no ectopic filter. It does not reproduce the published
94.4 / 95.1 on our pipeline. The gap is consistent with the missing
ectopic filter, but that is not tested.

The float references on all features show what the features allow:
GBDT reaches 98.2 / 97.9 on AFDB, above the published chip.

## Chip lab results for the chosen design (and2_n128)

- Generic synthesis: 20,248 gates, logic depth 58.
- Core only, mapped by `map-to-process`:

| PDK | area um2 | GE | cells |
| --- | --- | --- | --- |
| sky130 hd | 112,961 | 30,094 | 21,938 |
| gf180 7t | 359,701 | 32,772 | 26,420 |
| IHP sg13g2 | 192,842 | 26,571 | 21,316 |

- Whole sequential chip: the lab's `compile-stream` wrapper, holding
  the window in flip-flops, mapped with the lab's own `map_to_process`
  function. This is called directly from the lab's Python because no
  registered tool maps the wrapper.

| PDK | area um2 | GE | flip-flops |
| --- | --- | --- | --- |
| sky130 hd | 144,292 | 38,441 | 1037 |
| gf180 7t | 468,322 | 42,668 | 1037 |
| IHP sg13g2 | 260,311 | 35,867 | 1037 |

- Lab checks:
  - Bit-exact `simulate` on the actual held-out inputs: all 69514
    LTAFDB windows (0 mismatches) and all 8825 AFDB windows
    (0 mismatches). It covers circuit against integer model and against
    our training-side model.
  - Formal: `prove-equivalence` with golden=true proved (ABC cec, gates
    equal RTL, plus iprove of RTL against the independent golden model,
    for every input). Level 2.
  - `prove-sequential`: the clocked wrapper proved with eqy, the core
    black-boxed.
  - `rtl-simulate`: cocotb plus Icarus on 200 LTAFDB windows, passed,
    lint ok. Level 3.
- Lab-reported verification level: 3. Layout and timing/power were not
  run, because Docker is stopped.
- The iCE40UP5K bitstream does not fit (nextpnr reports 128 %
  utilisation for `thr1_n128`).
- Andersson, for comparison: 24,038 NAND2-eq after 65 nm synthesis
  (Table IV), 0.10 mm2 of silicon. Our whole chip is about 1.6 times
  larger in gate-equivalents, at an older node. It is smaller than
  their dedicated-multiplier variant (42,452).

## Lab finding (reported, the lab was not edited)

- `prove-equivalence` with golden=true failed ("emitter disagrees with
  golden model") on the `mlp4` designs, whose ReLU was written as a
  clip with hi = 2^30.
- Random-input simulation of the same design matched the integer model
  on 100,000 vectors.
- With a tight hi (the largest reachable value of the hidden unit, same
  semantics), the proof passes.
- Likely cause: the golden model renders every lane at one uniform
  width (widest derived width + 2). A clip constant wider than that
  wraps.
- All reported mlp4 designs use the tight bound.

## Weak points a critic would raise

- The specificity match is +0.06 points with a subject-bootstrap interval
  of about 92 to 99 %. That is equality within noise, not a win.
- The chosen design and the v2 features were picked after looking at
  AFDB results, and LTAFDB v1 results were also seen. Selection
  inside the folds gives Sp 94.2 %, below the chip's 95.8 %.
- The Andersson and Dash figures are in-sample, with thresholds tuned on
  the reported data. Our split is stricter, so the comparison is not
  symmetric. A fair rerun of their detector under leave-one-subject-out
  was not possible here: our float re-implementation without the
  ectopic filter gets 90.6 / 93.0.
- Their segments are formed after ectopic removal, and the beat file
  and AFL handling they used are not stated. Segment boundaries
  therefore differ from ours.
- The unit of their Se and Sp (segment against beat) is ambiguous. On
  beats our Sp is 95.6 %, below 95.8 %.
- Gate count is worse, not better: 38.4k sky130 GE for the whole chip
  against their 24.0k NAND2-eq. GE at 130 nm and NAND2-eq at 65 nm are
  only roughly comparable.
- Our chip computes the window in parallel because the lab's streaming
  tool only buffers frames. A running-count design would be far smaller,
  but the lab cannot verify it.
- 23 AFDB subjects is a small sample. Many subjects have few windows of
  one class, so their worst-subject rates rest on as few as 4 to 11
  windows.
- On LTAFDB the subject-bootstrap lower bound for Sp is 88 %, below the
  FDA 92 % goal. Record 103 (atrial ectopy and SVTA) is almost always
  flagged.
- The FDA goals belong to a different task (a 30 s ECG strip against a
  12-lead reference). They are a reference bar, not a regulatory claim.
- R-peak detection is not on our chip, nor on theirs. The database's
  beat annotations replace a real detector, which flatters both.
- No layout, timing or power was run (Docker is stopped), so there is
  no nW or energy comparison with Andersson's 8.1 nW.

## Files

- `src/afchip/afdata.py`: annotations to quantised RR intervals and
  labels.
- `features.py`: the integer features (v1, v2) and the Dash statistics.
- `models.py`: the integer families (thr1, and2, tree3, lin, mlp4).
- `run_eval.py`: AFDB leave-one-subject-out and the LTAFDB cross test.
- `run_nested.py`: nested design selection.
- `chip_ir.py`: chipir/1 for the whole detector.
- `chip_run.py`: lab calls. `lab_seqmap.py` maps the sequential wrapper.
- `make_results.py`: collates the outputs.
- `results.json`: every design's counts, intervals, worst subjects and
  chip numbers, plus the baselines and the v1 results.
- `size_accuracy_table.md`: the size-against-accuracy table.
- `models/final_models_v2.json`: all 20 final designs, as integers.
- `models/and2_n128_chipir.json`: the chosen chip's IR.

Reproduce (data in a folder outside the repo, run with `python -I`):

```text
python -I -m afchip.run_eval --afdb D/afdb --ltafdb D/ltafdb --out W/eval2_n128 --windows 128
python -I -m afchip.run_nested --afdb D/afdb --out W/nested --n 128
python -I -m afchip.chip_run --models W/eval2_n128/final_models.json --afdb D/afdb --ltafdb D/ltafdb --out W/chip_v2 --chiplab LAB/bin
```
