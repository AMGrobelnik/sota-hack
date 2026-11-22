# Baseline AF: hard-wired AF detector from RR intervals

## Verdict

Round two (below, and `round2/`) supersedes this verdict where they
differ. Round one, corrected after an independent check:

- Accuracy is a tie, not a win, and size was a loss (round two's
  clocked circuit turns the size result around).
- Chosen design: `and2_n128`, an AND of two integer count thresholds over
  a 128-interval window.
- Held-out subjects, MIT-BIH AF database, leave-one-subject-out:
  sensitivity 3616/3754 = 96.3 %, specificity 4861/5071 = 95.9 %.
- Published chip (Andersson 2015): 94.9 % / 95.8 %, tuned on the same
  data it reports. That it used the same 23 records as Dash is an
  assumption: Andersson's Table I lists 25 AFDB records and names no
  exclusion.
- Sensitivity is not clearly higher. The Wilson interval (95.7 to
  96.9 %) excludes 94.9 %, but the subject-bootstrap interval (92.4 to
  98.6 %) contains it, and the per-subject mean sensitivity is 94.53 %
  over the 18 subjects with at least 10 AF segments (89.93 % over all
  23 subjects with any AF segment; recomputed in
  `round2/results.json`, `round1_recheck`). Specificity is equal
  within noise (+0.06 points; per-subject mean 94.94 %).
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
- The Long-Term AF database result is not an independent test: v1
  results on it were seen before the v2 features and the design were
  chosen.

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
84 subjects. This is a secondary check, not an independent test (v1
results on LTAFDB were seen before the design was chosen). For
`and2_n128`:

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
  tool only buffers frames. Round two builds the running-count design
  (a lab-proved next-state core plus registers) and verifies it.
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

## Size against accuracy (all 20 designs, v2 features)

GE core is the combinational core and GE chip the whole sequential chip,
both sky130 gate-equivalents. FF counts the flip-flops. AFDB columns are
leave-one-subject-out counts; LTAF columns are the train-AFDB,
test-LTAFDB rates. All 20 designs are bit-exact on every held-out window,
formally proved (golden), sequentially proved and pass the RTL test.

| design | gates | depth | GE core | GE chip | FF | AFDB Se | AFDB Sp | LTAF Se | LTAF Sp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| thr1_n16 | 1161 | 39 | 1965.0 | 2955.7 | 138 | 28752/29969 | 36099/40713 | 0.961 | 0.858 |
| and2_n16 | 2201 | 38 | 3226.7 | 4487.3 | 138 | 28786/29969 | 36534/40713 | 0.976 | 0.854 |
| tree3_n16 | 2219 | 44 | 3225.3 | 4466.7 | 138 | 28788/29969 | 36486/40713 | 0.975 | 0.857 |
| thr1_n32 | 2411 | 46 | 3827.7 | 5873.7 | 267 | 14326/14983 | 18418/20351 | 0.970 | 0.883 |
| and2_n32 | 4765 | 47 | 7101.3 | 9447.0 | 267 | 14421/14983 | 18920/20351 | 0.973 | 0.897 |
| tree3_n32 | 4824 | 47 | 7101.3 | 9093.0 | 267 | 14238/14983 | 18893/20351 | 0.965 | 0.907 |
| thr1_n64 | 4919 | 51 | 7750.7 | 12022.0 | 524 | 7198/7492 | 9354/10170 | 0.974 | 0.896 |
| lin_n16 | 6451 | 77 | 9907.3 | 11864.7 | 138 | 28862/29969 | 37003/40713 | 0.952 | 0.922 |
| mlp4_n16 | 8073 | 101 | 13995.0 | 15528.3 | 138 | 28710/29969 | 37157/40713 | 0.950 | 0.931 |
| and2_n64 | 9963 | 53 | 14962.0 | 18920.7 | 524 | 7267/7492 | 9633/10170 | 0.975 | 0.913 |
| thr1_n128 | 9976 | 56 | 15677.7 | 24135.3 | 1037 | 3567/3754 | 4709/5071 | 0.975 | 0.906 |
| lin_n32 | 13240 | 84 | 21086.7 | 23363.7 | 267 | 14240/14983 | 19013/20351 | 0.957 | 0.950 |
| tree3_n64 | 15272 | 57 | 22346.0 | 26031.3 | 524 | 6987/7492 | 9585/10170 | 0.970 | 0.922 |
| mlp4_n32 | 15839 | 117 | 26349.7 | 29177.0 | 267 | 14149/14983 | 19104/20351 | 0.959 | 0.943 |
| lin_n64 | 20192 | 91 | 30467.7 | 35670.3 | 524 | 7308/7492 | 9671/10170 | 0.953 | 0.959 |
| and2_n128 | 20248 | 58 | 30094.0 | 38441.0 | 1037 | 3616/3754 | 4861/5071 | 0.973 | 0.926 |
| mlp4_n64 | 29674 | 121 | 49871.7 | 53834.3 | 524 | 7251/7492 | 9683/10170 | 0.956 | 0.950 |
| tree3_n128 | 31130 | 58 | 45656.3 | 53130.0 | 1037 | 3619/3754 | 4864/5071 | 0.970 | 0.932 |
| lin_n128 | 47234 | 101 | 77026.0 | 83258.7 | 1037 | 3590/3754 | 4835/5071 | 0.959 | 0.958 |
| mlp4_n128 | 59868 | 130 | 97463.7 | 106674.7 | 1037 | 3603/3754 | 4837/5071 | 0.961 | 0.958 |

Intervals for the same 20 designs (AFDB leave-one-subject-out, in
percent; Wilson on segments, subject bootstrap 2000 resamples, seed 0):

| design | Se k/n | Se Wilson | Se boot | Sp k/n | Sp Wilson | Sp boot |
| --- | --- | --- | --- | --- | --- | --- |
| thr1_n16 | 28752/29969 | 95.7-96.2 | 93.3-98.2 | 36099/40713 | 88.4-89.0 | 81.8-94.3 |
| and2_n16 | 28786/29969 | 95.8-96.3 | 92.8-98.7 | 36534/40713 | 89.4-90.0 | 83.0-95.6 |
| tree3_n16 | 28788/29969 | 95.8-96.3 | 93.1-98.4 | 36486/40713 | 89.3-89.9 | 82.7-95.3 |
| thr1_n32 | 14326/14983 | 95.3-95.9 | 91.5-98.8 | 18418/20351 | 90.1-90.9 | 83.8-95.9 |
| and2_n32 | 14421/14983 | 95.9-96.5 | 92.5-99.1 | 18920/20351 | 92.6-93.3 | 88.1-97.0 |
| tree3_n32 | 14238/14983 | 94.7-95.4 | 90.3-98.7 | 18893/20351 | 92.5-93.2 | 87.2-97.2 |
| thr1_n64 | 7198/7492 | 95.6-96.5 | 92.6-98.7 | 9354/10170 | 91.4-92.5 | 85.9-97.0 |
| lin_n16 | 28862/29969 | 96.1-96.5 | 94.6-98.0 | 37003/40713 | 90.6-91.2 | 83.8-96.4 |
| mlp4_n16 | 28710/29969 | 95.6-96.0 | 93.5-97.8 | 37157/40713 | 91.0-91.5 | 84.4-96.7 |
| and2_n64 | 7267/7492 | 96.6-97.4 | 94.7-98.8 | 9633/10170 | 94.3-95.1 | 90.9-98.0 |
| thr1_n128 | 3567/3754 | 94.3-95.7 | 90.5-98.4 | 4709/5071 | 92.1-93.5 | 87.3-97.5 |
| lin_n32 | 14240/14983 | 94.7-95.4 | 90.5-98.0 | 19013/20351 | 93.1-93.8 | 87.6-97.7 |
| tree3_n64 | 6987/7492 | 92.7-93.8 | 87.7-97.9 | 9585/10170 | 93.8-94.7 | 89.4-98.1 |
| mlp4_n32 | 14149/14983 | 94.1-94.8 | 89.1-98.3 | 19104/20351 | 93.5-94.2 | 88.0-97.9 |
| lin_n64 | 7308/7492 | 97.2-97.9 | 95.7-98.7 | 9671/10170 | 94.7-95.5 | 90.0-98.6 |
| and2_n128 | 3616/3754 | 95.7-96.9 | 92.4-98.6 | 4861/5071 | 95.3-96.4 | 92.4-98.7 |
| mlp4_n64 | 7251/7492 | 96.4-97.2 | 94.6-98.2 | 9683/10170 | 94.8-95.6 | 89.8-98.8 |
| tree3_n128 | 3619/3754 | 95.8-97.0 | 92.3-98.7 | 4864/5071 | 95.3-96.4 | 93.0-98.4 |
| lin_n128 | 3590/3754 | 94.9-96.2 | 91.4-98.1 | 4835/5071 | 94.7-95.9 | 89.5-99.0 |
| mlp4_n128 | 3603/3754 | 95.3-96.6 | 91.8-98.5 | 4837/5071 | 94.8-95.9 | 89.8-98.8 |

The smallest designs (N = 16, about 1.2k to 2.2k gates) have
specificity of only 88.7 to 89.7 % on AFDB. No design under about 20k gates
reaches 95.8 % specificity in this parallel form (round two's clocked
form computes `and2_n128` in 771 sky130 GE). iCE40UP5K LUTs: thr1_n16 816,
and2_n16 1336, thr1_n32 1668, thr1_n64 3371. Larger designs do not fit.

# Round two: clocked chip and clean selection

Code, protocol and models are in `round2/`; every number below is in
`round2/results.json` (built by `afr2.collate` from the run outputs).

## Verdict (round two)

- Accuracy, nested selection, primary configuration (N = 128, 23
  records): MATCHES the published chip by the pre-registered rule.
  Sensitivity 3562/3754 = 94.89 % (published 94.9 %), specificity
  4912/5071 = 96.86 % (published 95.8 %). Neither subject-bootstrap
  interval excludes the published value, and the sensitivity point
  estimate is a hair below it, so the rule does not give BEATS.
- All six configurations (N = 128, 64, 32 on 23 and 25 records) give
  MATCHES.
- Size: the clocked circuit computes the chosen design in 830.7 sky130
  gate-equivalents including its 55 flip-flops (925.8 gf180, 864.5
  IHP), against 24,038 NAND2-equivalents for the published chip's
  65 nm synthesis: about 29 times fewer gate-equivalents, with the
  caveats below. Round one's design in the same clocked form is
  771.3 sky130 GE (47 flip-flops), against 38,441 for round one's
  parallel form.
- Untouched test (MIT-BIH Arrhythmia, run once): sensitivity ties the
  published chip, specificity is below it. 200-series: Se 86/87
  (98.9 %, published 98.8 %), Sp 287/384 (74.7 %, published 79.0 %);
  100-series: Sp 343/359 (95.5 %, published 97.0 %). Our detector has
  no ectopic-beat filter. Dash's detector without its filter ("with
  ectopy") got Sp 69.4 % on the 200-series and 96.2 % on the
  100-series in beats (ours in beats: 74.3 % and 95.5 %).
- Honest claim: a tie on accuracy on the AF database, a tie on
  sensitivity and a loss on specificity on the untouched database, and
  a large win on size for the detector logic that is compared.

## Order of commits

- `b60b41e` (pushed 05:03 UTC, 22 Nov 2026): `round2/protocol.md` plus
  the feature, fitting, statistics and nested-selection code. Before
  it, the new code ran only on synthetic random segments.
- After the push: the six nested runs, then `658ef5f` froze the chip
  design (`round2/models/r2_chip_n128.json`) and the untouched-test
  script, then the one untouched run.
- The results commit follows these.

## Protocol in brief (full text in `round2/protocol.md`)

- 26 sequential-friendly integer counts: relative successive
  differences at lags 1 to 4 and shifts 3 to 6, absolute successive
  differences, turning points, runs of two irregular steps, and
  distance from a shift-add running mean.
- Seven families: thr1, and2, or2, tree2, tree3, lin3, lin6 (integer
  weights |w| <= 8).
- Every threshold: highest training specificity with training
  sensitivity >= 0.96.
- Selection inside each outer leave-one-subject-out fold: inner
  leave-one-subject-out on the training subjects; families with inner
  sensitivity >= 0.95; highest inner specificity, ties within 0.2
  points to fewer counters.
- Statistics: counts, Wilson 95 %, subject bootstrap 95 % (2000
  resamples, seed 0), per-subject mean, worst subject.
- Wording rule: BEATS if both nested point estimates >= 94.9 / 95.8
  and one subject-bootstrap interval lies entirely above; MATCHES if
  neither interval lies entirely below; BELOW otherwise.

## Accuracy, nested selection (the primary result)

Segments, held-out subjects, pooled. Se and Sp in percent; W is the
Wilson 95 % interval, B the subject-bootstrap 95 % interval.

| config | Se k/n | Se | Se W | Se B |
| --- | --- | --- | --- | --- |
| 23 rec, N 128 | 3562/3754 | 94.89 | 94.13-95.55 | 90.40-98.27 |
| 25 rec, N 128 | 3888/4067 | 95.60 | 94.92-96.19 | 91.02-98.65 |
| 23 rec, N 64 | 7118/7492 | 95.01 | 94.49-95.48 | 90.12-98.58 |
| 25 rec, N 64 | 7736/8113 | 95.35 | 94.87-95.79 | 91.45-98.59 |
| 23 rec, N 32 | 14335/14983 | 95.68 | 95.34-95.99 | 91.42-98.87 |
| 25 rec, N 32 | 15469/16225 | 95.34 | 95.01-95.65 | 91.45-98.57 |

| config | Sp k/n | Sp | Sp W | Sp B | wording |
| --- | --- | --- | --- | --- | --- |
| 23 rec, N 128 | 4912/5071 | 96.86 | 96.35-97.31 | 93.76-99.23 | MATCHES |
| 25 rec, N 128 | 5218/5464 | 95.50 | 94.92-96.02 | 92.66-98.05 | MATCHES |
| 23 rec, N 64 | 9697/10170 | 95.35 | 94.92-95.74 | 91.55-98.52 | MATCHES |
| 25 rec, N 64 | 10461/10961 | 95.44 | 95.03-95.81 | 92.78-97.91 | MATCHES |
| 23 rec, N 32 | 19228/20351 | 94.48 | 94.16-94.79 | 91.58-97.01 | MATCHES |
| 25 rec, N 32 | 20634/21934 | 94.07 | 93.75-94.38 | 90.64-97.16 | MATCHES |

The published 94.9 / 95.8 is for N = 128; for N = 64 and 32 the
wording uses the same values only as a reference.

Per-subject means and worst subjects (Se mean over subjects with any
AF segment, and over those with at least 10; Sp mean over subjects
with any non-AF segment):

| config | Se mean | Se mean, >= 10 | Sp mean | worst Se (>= 10) | worst Sp |
| --- | --- | --- | --- | --- | --- |
| 23 rec, N 128 | 88.42 | 94.00 (18) | 96.07 | 04043 63/115 | 06426 7/11 |
| 25 rec, N 128 | 92.73 | 94.82 (19) | 94.70 | 04043 67/115 | 06426 7/11 |
| 23 rec, N 64 | 92.41 | 93.27 (20) | 95.34 | 04048 8/13 | 06426 22/29 |
| 25 rec, N 64 | 93.66 | 94.36 (21) | 95.29 | 04048 8/13 | 06426 22/29 |
| 23 rec, N 32 | 95.01 | 95.01 (23) | 93.98 | 06453 8/14 | 06426 49/66 |
| 25 rec, N 32 | 94.80 | 94.58 (24) | 93.58 | 06453 8/14 | 06426 44/66 |

- Primary configuration, interval (beat) level: Se 453839/479390 =
  94.67 %, Sp 627761/650210 = 96.55 %.
- The worst subject overall for Se at N = 128 (23 records) is 06453,
  1 of 4 AF segments.
- Families chosen across the 23 outer folds at N = 128: and2 18, lin6
  3, tree3 2. At N = 32: tree3 21, thr1 1, tree2 1.
- The selection inside the folds made the difference round one could
  not: round one's nested selection gave Sp 4777/5071 = 94.20 %; round
  two's gives 4912/5071 = 96.86 % at a sensitivity 61 segments lower
  (3562 against round one's 3623).

Chip design (the same procedure with all 23 subjects as training data;
not an accuracy result): `and2` with `rel3_4 >= 74` AND `rel4_5 >= 96`,
that is, at least 74 of the 125 lag-3 steps exceed 1/16 of the older
interval and at least 96 of the 124 lag-4 steps exceed 1/32 of it.
On 25 records the same procedure picks the same two counts with
`rel4_5 >= 92`.

## Untouched test: MIT-BIH Arrhythmia database (run once)

What the papers report (opened at source; see round one's notes for
the URLs). Dash 2009 tested its AF-database thresholds on this
database: Table 2, "AF beats" columns, 100-series Sp 96.2 % with
ectopy and 99.5 % without; 200-series Se/Sp 96.5/69.4 % with ectopy
and 90.2/91.2 % without ("before and after removal of all PVCs").
Andersson 2015, Table III, PrecSeg: 100-series Sp 97.0 %, 200-series
Se 98.8 %, Sp 79.0 %. Andersson's Table I lists 25 records in the
100-series and 23 in the 200-series; the database files have 23 and
25 (Dash's text also says 23 in the 100-series).

How we formed segments and labels (fixed in the protocol before the
run): all 48 records; beats from the `.atr` beat labels; contiguous
128-interval segments from each record start; AF if more than half the
intervals are `(AFIB`; no ectopic filter. 830 segments, 87 of them AF
(records 201, 202, 203, 210, 217, 219, 221, 222). Designs frozen in
`658ef5f` before the run.

| design | series | Se k/n | Sp k/n |
| --- | --- | --- | --- |
| round-two chip | 100 | none | 343/359 = 95.54 |
| round-two chip | 200 | 86/87 = 98.85 | 287/384 = 74.74 |
| round-two chip | all | 86/87 = 98.85 | 630/743 = 84.79 |
| round-one and2_n128 | 100 | none | 341/359 = 94.99 |
| round-one and2_n128 | 200 | 87/87 = 100.00 | 286/384 = 74.48 |
| round-one and2_n128 | all | 87/87 = 100.00 | 627/743 = 84.39 |

Intervals for the round-two chip:

- 200-series Se: Wilson 93.77-99.80; subject bootstrap 95.24-100.00
  (only 4 records have at least 10 AF segments).
- 200-series Sp: Wilson 70.16-78.83; bootstrap 58.54-88.71; worst
  record 200, 0/20.
- 100-series Sp: Wilson 92.88-97.24; bootstrap 89.92-100.00; worst
  record 106, 7/15.
- Beat level (Dash's unit): 200-series Se 10740/11013 = 97.52 %, Sp
  36591/49275 = 74.26 %; 100-series Sp 43904/45952 = 95.54 %.

Against the published figures: 200-series sensitivity ties
Andersson's 98.8 %; 200-series specificity 74.7 % is below
Andersson's 79.0 % (79.0 lies just above our Wilson interval and
inside our subject-bootstrap interval; no wording rule was
pre-registered for this test), above Dash's 69.4 % without ectopic
filtering, and far below Dash's 91.2 % after PVC removal. 100-series
specificity 95.5 % is below Andersson's 97.0 % and Dash's 96.2 %
(both inside our Wilson interval 92.88-97.24). Dash's figure is a
held-out database test like ours (thresholds from the AF database
only). Andersson re-ran the grid search for thresholds and validated
on "the same ECG databases" as Dash; which databases the grid search
used is not stated.

## Long-Term AF database (secondary, not independent)

Same frozen designs, all 84 records, 69514 scored segments.

- Round-two chip: Se 39811/40898 = 97.34 % (W 97.18-97.49, B
  95.25-98.92); Sp 26702/28616 = 93.31 % (W 93.02-93.60, B
  88.68-96.74). Worst Sp: record 103, 0/457.
- Round-one and2_n128 (as in round one): Se 39808/40898, Sp
  26499/28616.

## Clocked chip (aim 1)

The detector as the apnoea experiment built its night counter: a
combinational next-state core in chipir/1, compiled and proved by the
lab, plus a Verilog register wrapper (`afr2.seqchip`).

- Core inputs: the new 8-bit interval `x`, the last L intervals `h`
  (L = 4 for the round-two design, 3 for round one's), one 7-bit
  counter per feature `c`, the 7-bit position `p`.
- Core outputs: `af` (1 on the last interval of a segment when the
  rule fires), `done`, `h_next`, `c_next`, `p_next`.
- Per interval: two subtract-absolute-shift-compare units, two
  counter increments gated by the position, a position increment; on
  the 128th interval the two counts are compared with their thresholds
  and the counters restart. No window memory, no multiplier.
- Wrapper: registers for `h`, `c`, `p`, plus registered `af` and
  `done`; synchronous reset at each record start; one clock enable per
  interval.

| quantity | round-two chip | round-one and2_n128 |
| --- | --- | --- |
| core gates (generic) | 241 | 250 |
| core depth | 35 | 34 |
| clocked cells (generic) | 300 | 296 |
| of which flip-flops | 55 | 47 |
| clocked logic depth | 35 | 36 |
| GE sky130 hd, with FFs | 830.7 | 771.3 |
| GE gf180 7t, with FFs | 925.8 | 843.4 |
| GE IHP sg13g2, with FFs | 864.5 | 771.2 |
| area sky130, um2 | 3118 | 2895 |
| area gf180, um2 | 10162 | 9257 |
| area IHP, um2 | 6274 | 5597 |

Generic cells are the lab's yosys two-input gates and its enable
flip-flops. GE is mapped area over the library's NAND2 area, from the
lab's own mapping function on the whole clocked design.

Layout (one run, sky130, round-two chip, lab's LibreLane function with
`clk` as the clock, 20 ns clock): standard-cell area 5405 um2
(including tap and timing-repair buffers, excluding filler), die
13,725 um2, setup slack +6.59 ns (critical path 13.41 ns), hold slack
+0.11 ns, 0 routing DRC errors, 11 max-slew violations reported,
layout GE 1440. No power comparison is made: the published power is a
sub-threshold 65 nm silicon measurement.

### Verification, and which proof is compositional

For both clocked designs:

1. Core, lab `simulate` on its real state trajectory: every interval
   of all 25 AF-database records, 1,221,534 vectors, gate netlist
   against the lab's integer model on every output and against our
   step model on `af`: 0 mismatches. Random inputs: 200,000 vectors,
   0 mismatches.
2. Core, lab `prove-equivalence` with golden=true: proved (ABC cec,
   gates equal RTL, plus iprove of RTL against the lab's independent
   golden model of the IR, for every input). Lab verification level 2.
3. Wrapper, the lab's `prove_sequential` with the core as a black
   box: proved (eqy, depth 8; 4.7 s and 20.2 s). This is the
   compositional proof: (2) covers the core for every input, (3)
   covers the registers and enables with the core uninterpreted;
   together they show that the synthesised clocked netlist equals the
   clocked RTL.
4. Flattened whole design, the same eqy: not proved. All output and
   register partitions proved except 7 partitions on the core's
   internal `p_next` bits ("partitions not equivalent"; 50 of 57 and
   58 of 65 partitions proved). Likely cause: eqy cuts at the matched
   `done` net, so `done` is free in that partition, while the gate
   netlist computes `p_next` from `p` alone (synthesis used
   `done = (p == 127)`). Not established.
5. Icarus (lab's oss-cad-suite), whole records fed one interval per
   clock, on both the clocked RTL and the synthesised generic gate
   netlist of the whole clocked design: every segment decision and
   both counters at every segment end compared with the independent
   step model, and the step model compared with the segment-level
   integer model used for fitting.
   - AF database, 25 records: 1,221,534 intervals, 9531 segments.
   - Long-Term AF database, 84 records: 8,995,889 intervals, 70,240
     segments (69,514 scored plus 726 touching unlabelled intervals).
   - Arrhythmia database, 48 records (after the untouched run):
     109,446 intervals, 830 segments.
   - 0 mismatches everywhere (round-one design on the gate netlist:
     see `round2/results.json`, `icarus_gate_netlist`).
6. Lint: Verilator `--lint-only` on the clocked design is clean with
   default warnings; `-Wall` adds only unused-bit and file-name style
   warnings in the lab-emitted core.

What is not proved: that the clocked design computes the
segment-level model for every possible input sequence. That
equivalence is shown on every real segment of the three databases
(item 5), not formally.

### Size against the published chip

- Ratio: 24,038 / 830.7 = 28.9 (sky130), 26.0 (gf180), 27.8 (IHP).
  For round one's design in clocked form: 31.2, 28.5, 31.2. Round
  one's own parallel chip (38,441 GE) shrinks 49.8-fold.
- Silicon: our layout's cell area 5405 um2 in a 130 nm process
  against their 50,000 um2 synthesis area in 65 nm; die 0.0137 mm2
  against their 0.10 mm2 including the peripheral circuit.
- Caveats:
  - Different libraries and nodes: GE divides by each library's NAND2
    area, theirs is NAND2-eq of a 65 nm low-leakage high-Vt library.
    Only roughly comparable.
  - Their chip contains what ours does not: the ectopic-beat
    preprocessing (percentile limits from the preceding segment, a
    time-multiplexed divider), TPR, RMSSD with a shared multiplier,
    Shannon entropy with a log2 unit, a FIFO, and a 1664-bit
    standard-cell RAM holding 128 intervals of 13 bits.
  - Ours keeps 4 intervals of 8 bits, two 7-bit counters and a 7-bit
    position; the ectopic filter is missing, and the Arrhythmia
    200-series specificity (74.7 % against their 79.0 %) shows its
    cost.
  - Off chip on both sides: R-wave detection and RR-interval timing
    (their Fig. 1). Ours expects the interval already quantised to an
    8-bit count of 8 ms ticks; theirs takes 13-bit words.

## Lab findings (reported; the lab was not edited)

- No registered tool wraps a next-state core with state registers:
  `compile-stream` only buffers frames. The wrapper was synthesised,
  mapped, proved and laid out by calling the lab's own library
  functions (`synth_generic`, `map_to_process`, `prove_sequential`,
  `timing_power_layout`) from the lab's Python.
- The lab's `verification-level` stops at level 2 for the core: its
  level 3 is defined for its own streaming wrapper. Our Icarus runs
  stand in for it.
- The flattened `prove_sequential` fails on internal partitions (see
  item 4 above), as it did for the apnoea night counter.
- From reading the code: the lab's subprocess calls with a timeout
  (eqy in `prove_sequential`, among others) kill only the direct
  child, so solver children can outlive a timeout. Our calls ran each
  lab process in its own process group and killed the group.

## Deviations from the protocol

- Added after the protocol, as an extra check: Icarus on the
  synthesised gate netlist (item 5 above).
- The lab `simulate` of the core used the AF database only (the
  protocol named no database for it); Icarus covered all three.
- None in the accuracy pipeline.

## Weak points a critic would raise

- MATCHES, not BEATS. The nested sensitivity point estimate (94.89 %)
  sits a hair below the published 94.9 %; the subject-bootstrap
  intervals are about 8 points wide. 23 subjects cannot separate the
  two detectors.
- Per-subject sensitivity is uneven: mean 88.42 % over the 23
  subjects with any AF segment, 94.00 % over the 18 with at least 10;
  subjects with only a few AF segments (06453, 1 of 4) are missed.
- The candidate family was written after round one had looked at the
  same database. Round one found the lag-3 relative difference by
  looking at AFDB results, and round two's family contains it (the
  chosen design uses lag-3 and lag-4 counts). Nested selection guards
  the choice inside the family, not the choice of family. The
  operating point (0.96) and the selection floor (0.95) were also set
  knowing round one's operating range. The Arrhythmia database is the
  only clean test, and it has only 87 AF segments in 8 records.
- On that untouched test, specificity is below the published chip on
  both series; sensitivity ties.
- The published figures are in-sample for their thresholds (AF
  database), and their segments are formed after ectopic removal, so
  segment boundaries differ from ours.
- The sequential behaviour is shown by simulation on every real
  segment, not proved for all input sequences; the flattened
  sequential proof did not go through.
- GE across libraries and nodes is a rough measure; the size win
  partly comes from leaving out the ectopic filter and the entropy
  and RMSSD units, not only from the sequential structure.
- The layout reports 11 max-slew violations (timing still met at
  20 ns; the real rate is about one interval per second).
- R-peak detection uses the database annotations on both sides.

## Data (round two)

- MIT-BIH Arrhythmia Database (mitdb 1.0.0), ODC Attribution v1.0,
  <https://doi.org/10.13026/C2F305>. Cite: Moody GB, Mark RG. The
  impact of the MIT-BIH Arrhythmia Database. IEEE Eng Med Biol
  20(3):45-50 (2001); and Goldberger et al. (2000).
- AF and Long-Term AF databases as in round one. Annotation files only
  are read; no recording, annotation or per-beat array is in the
  repository.

## Files (round two)

- `round2/protocol.md`: the pre-registered protocol (commit
  `b60b41e`).
- `round2/src/afr2/seqfeat.py`: the 26 counts, vectorised and as an
  independent step model.
- `fit.py`: families and the operating rule. `nested.py`: nested
  selection. `stats2.py`: statistics and the wording rule.
- `untouched.py`: the one Arrhythmia run and the Long-Term AF check.
- `seqchip.py`: clocked core, wrapper, lab calls, Icarus.
- `r1fix.py`: round-one recheck. `collate.py`: builds
  `round2/results.json`.
- `round2/models/`: the frozen round-two chip design and round one's
  design in round-two form.
- `round2/chip/`: the clocked designs' core IR, wrapper and full
  Verilog.

Reproduce (data in a folder outside the repo, `python -I`, lab
environment as in the task):

```text
python -I -m afr2.nested --afdb D/afdb --recs 23 --n 128 --out W/nested_23_128
python -I -m afr2.untouched --data D --chip round2/models/r2_chip_n128.json --r1 round2/models/r1_and2_n128.json --out W/untouched.json
python -I -m afr2.seqchip --design r2_chip --model-json round2/models/r2_chip_n128.json --out W/chip --data D --dbs afdb ltafdb mitdb --layout
python -I -m afr2.collate --runs W --out round2/results.json --protocol-commit b60b41e
```
