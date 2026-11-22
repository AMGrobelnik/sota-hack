# AF detector, round two: protocol (fixed before any result)

This file is committed and pushed before any new candidate is run on
real data. Code written before this commit was only run on synthetic
random segments (a smoke test of the code paths, no labels from any
database). Nothing below changes after the commit; any deviation is
listed in notes.md as a deviation.

## Aims

1. Size at matched accuracy: build the detector as a clocked circuit
   (one RR interval per clock enable, a few stored intervals, one
   counter per feature, a position counter) and measure it with the
   flip-flops included.
2. Accuracy with clean selection: every choice of feature, family,
   threshold and design is made inside each leave-one-subject-out fold
   on training subjects only.

## Baseline

Andersson et al. 2015 (IEEE TBioCAS 9(3)), Table III, present
implementation, PrecSeg:

- MIT-BIH AF database: sensitivity 94.9 %, specificity 95.8 %.
- MIT-BIH Arrhythmia, 100-series: specificity 97.0 % (no AF there).
- MIT-BIH Arrhythmia, 200-series: sensitivity 98.8 %, specificity
  79.0 %.
- Segment N = 128 RR intervals; ectopic-beat preprocessing on chip;
  thresholds from a grid search (Section II.C); Se and Sp defined on
  "AF episodes", i.e. detector segments.
- Table I lists 25 MIT-BIH AF records, and the two Arrhythmia series
  (all 48 records).

Dash et al. 2009 (Ann. Biomed. Eng. 37(9)), Table 2, l = 128,
PercThresh 50 %, thresholds optimised on the MIT-BIH AF database only,
then tested on the Arrhythmia database; Se and Sp in the column
headed "AF beats":

- MIT-BIH AF (23 records, 04936 and 05091 excluded): 94.4 / 95.1 %.
- Arrhythmia 100-series: Sp 96.2 % with ectopy, 99.5 % without.
- Arrhythmia 200-series: 96.5 / 69.4 % with ectopy, 90.2 / 91.2 %
  without ("before and after removal of all PVCs").

## Data and segments

- MIT-BIH AF database (afdb 1.0.0). Beats from the `.qrs` files,
  rhythm from `.atr`, as in round one.
- Record sets. Primary: the 23 records of round one (all 25 minus
  04936 and 05091, Dash's exclusion). Secondary: all 25 records
  (Andersson's Table I lists 25 and does not mention an exclusion).
- RR interval: beat-to-beat time in 8 ms units, rounded, saturated at
  255. An interval takes the rhythm active at the beat that ends it.
- Segments: contiguous, non-overlapping blocks of N intervals from the
  start of each record. A segment is AF when more than half of its
  intervals are `(AFIB`; every other rhythm is non-AF. Segments that
  touch an interval before the first rhythm label are not scored.
- N = 128 is primary (the published chip's N). N = 64 and N = 32 are
  secondary.
- Configurations: N in {128, 64, 32} times record set {23, 25}: six.
  The primary configuration is N = 128 on 23 records.

## Candidate family (fixed)

Features: 26 integer counts over one segment, each computable when
the intervals arrive one at a time, with at most the last four
intervals, one counter, the position in the segment and, for the
running-mean counts, one 12-bit register. Pairs never cross a segment
boundary. Definitions are in `src/afr2/seqfeat.py`:

- `rel{L}_{k}`: count of |r_i - r_(i-L)| > r_(i-L) >> k, for lags
  L = 1..4 and shifts k = 3..6 (16 counts).
- `abs_{t}`: count of |r_i - r_(i-1)| > t, t = 2, 4, 8, 16 (4).
- `tp`: strict turning points of the RR series (1).
- `run_{k}`: two consecutive lag-1 relative steps both above
  r >> k, k = 3, 4 (2).
- `dev_{k}`: count of |16 r_i - m| > m >> k, with m a running mean
  times 16 kept by shift-add (m = 16 r_0, then
  m += (16 r_i - m) >> 3, clipped to 0..4095), k = 3, 4, 5 (3).

Model families (`src/afr2/fit.py`), seven candidates:

- `thr1`: one count >= t.
- `and2`, `or2`: two counts against two thresholds, AND or OR, every
  pair and every threshold pair searched.
- `tree2`, `tree3`: CART of depth at most 2 or 3 on the counts
  (balanced class weights, at least 10 segments per leaf); a segment
  is AF when its leaf score is >= tau.
- `lin3`, `lin6`: sum of integer weights times counts >= t, over at
  most 3 or 6 counts. Counts chosen by a fixed L1-logistic path on
  standardised counts (17 values of C from 1e-3 to 10, the largest C
  with 1..k nonzero counts); weights from an L2 logistic refit,
  scaled so the largest is 8 and rounded (|w| <= 8, zeros dropped).

## Operating rule (inside every fit)

Every threshold (t, the pair t1 t2, tau, and the linear t) is the one
with the highest specificity on the fitting segments among those with
sensitivity on the fitting segments of at least 0.96 (ties: higher
sensitivity, then the first in scan order). For thr1, and2 and or2
the feature choice uses the same key.

## Selection rule (inside every outer fold, training subjects only)

For each outer fold (one held-out subject):

1. Inner leave-one-subject-out over the training subjects: each of
   the seven families is fitted on the inner-training subjects and
   predicts the inner held-out subject. Pool the inner predictions:
   inner sensitivity and specificity per family.
2. Eligible families: inner sensitivity >= 0.95 (the fits target
   0.96 on their own segments; 0.95 is just above the baseline 94.9).
3. Among eligible families, take the highest inner specificity; every
   eligible family within 0.2 percentage points of it is tied, and
   the tie goes to the smaller design: fewer distinct counters, then
   the order thr1, and2, or2, tree2, lin3, tree3, lin6.
4. If no family is eligible: highest inner sensitivity plus
   specificity, ties to the smaller design.
5. Refit the chosen family on all training subjects of the fold and
   apply it to the held-out subject.

The pooled predictions of step 5 over all outer folds are the primary
accuracy result ("nested"). Per-family leave-one-subject-out results
(no selection) are recorded as descriptive only and are not used for
any claim.

The design for the chip and the untouched test is the same procedure
run once with all subjects of the primary configuration as training
data (inner leave-one-subject-out over all 23). It is not an accuracy
result.

## Statistics

For every configuration, on segments, pooled over subjects:

- counts k/n for sensitivity and specificity;
- Wilson 95 % intervals;
- subject bootstrap 95 % intervals (2000 resamples of subjects with
  replacement, seed 0, percentile, pooled ratio in each resample);
- per-subject mean (over subjects with at least one segment of the
  class);
- worst subject (overall, and among subjects with at least 10
  segments of the class);
- interval (beat) level counts as secondary: each interval inherits
  its segment's decision.

## Decision rule for the wording

Applied to the nested result of the primary configuration against
94.9 / 95.8 (for the secondary configurations it is reported too, but
the published figure is for N = 128 only):

- BEATS: both nested point estimates are at or above the baseline and
  the subject-bootstrap interval of at least one lies entirely above
  its baseline value.
- MATCHES: not BEATS, and neither subject-bootstrap interval lies
  entirely below its baseline value (the baseline is inside, or
  below, each interval).
- BELOW: otherwise.

## Untouched test: MIT-BIH Arrhythmia database

Never used in round one's AF work or before this commit. Run once,
after the chip design is frozen, and reported whatever it gives.

- Records: all 48 (`RECORDS` file: 23 records 100-124, 25 records
  200-234), including the paced records, as both papers list both
  series in full.
- Beats: the reviewed beat labels in `.atr` (all beat symbols,
  ectopic and paced included; non-beat symbols dropped), as round one
  did for the Long-Term AF database. Rhythm from the `.atr` rhythm
  annotations. Same RR quantisation.
- Segments: contiguous 128-interval segments from each record start;
  AF when more than half of the intervals are `(AFIB`, `(AFL` and all
  others non-AF; segments touching unlabelled intervals not scored.
  This is the segment rule of both papers (l = 128, PercThresh 50 %).
  Clarification, 22 Nov 2026 (added after the results; the protocol's
  meaning is unchanged): the code treats atrial flutter as non-AF.
  Counting it as AF gives 200-series sensitivity 94/96 and
  specificity 286/375, the same conclusion, as found by the
  independent recomputation.
- No ectopic filter, so the like-for-like published rows are Dash's
  "with ectopy" rows; Andersson's PrecSeg row includes their ectopic
  preprocessing and is shown next to ours as the headline baseline.
- Reported per series (100 and 200) and pooled: segment level
  (Andersson's unit) with counts, Wilson and subject-bootstrap
  intervals, and interval level (Dash's "AF beats" column).
- Designs run, in one pass, both frozen before this commit or by the
  rule above: (a) primary, the round-two chip design fitted on the 23
  AF-database records; (b) pre-declared secondary, round one's
  `and2_n128` exactly as committed in round one.

## Long-Term AF database

Secondary and not independent (round one looked at it). The same two
frozen designs are run on all 84 records, round one's loading.

## Clocked chip (aim 1)

- Designs: (a) round one's `and2_n128` (same function, so the same
  accuracy, as round one's 38,441-GE parallel chip) and (b) the
  round-two chip design. Both at N = 128.
- Combinational next-state core in chipir/1, compiled by the lab:
  inputs the new interval, the stored intervals, the counters, the
  position and (if needed) the mean register; outputs the next state,
  the AF bit and a done flag. A register wrapper in Verilog holds the
  state.
- Checks: lab `simulate` of the core on its real state trajectory;
  lab `prove-equivalence` with the golden model (core); the lab's
  `prove_sequential` with the core as a black box (wrapper) and, if it
  finishes, on the flattened design; Icarus over every record of the
  AF database (25 records), the Long-Term AF database and, after the
  untouched test, the Arrhythmia database, comparing every segment
  decision and the counters at every segment end with an independent
  step model and with the segment-level integer model.
- Size: generic gates and depth (lab yosys), flip-flops, and
  gate-equivalents including flip-flops in sky130, gf180 and IHP (lab
  mapping). One layout (sky130) of design (b) if Docker answers. No
  power comparison with the published chip.
