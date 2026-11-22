# Apnea-ECG baseline comparison (key: apnea)

## Verdict

Partly reached. Per minute, the pre-registered design D5 (16 features,
linear, 2282 gates) scores 14627 of 17268 test minutes (84.71 percent)
against the database's reference rule apdet at 14591 of 17268 (84.49);
the margin is 36 minutes and well inside the intervals. Per recording, the
pre-registered design D1 gets 32 of 35 (91.4 percent) and the best design
33 of 35, below the hand-crafted 34 of 35 (97.1). Not reached there.

## Pre-registration (written before the test records were scored)

Committed in d8a612d before the single test run.

- Data: PhysioNet Apnea-ECG 1.0.0, 35 learning records (a01-a20, b01-b05,
  c01-c10) for every fit and choice, 35 test records (x01-x35) scored once.
- Labels: per-minute reference labels; test labels from the challenge file
  event-2-answers (identical to x??.apn, checked).
- Input: the database's machine beat annotations (.qrs) only.
- Per-recording reference: 12 x apnoea minutes >= minutes (AHI estimate
  of 5 or more), giving 23 OSA and 12 non-OSA test records; the challenge
  event-1 A versus C protocol (30 records) is reported too.
- Designs D1-D6 and the two float references are fixed in models.py.
- Headline per-minute design: best training-CV minute accuracy (D5).
- Headline per-recording design: best training-CV night accuracy, ties
  to the smallest design (D1; D2 and D6 tie with it at 33 of 35).

## Baselines, confirmed at the source

| Baseline | Test per minute | Test per recording |
|---|---|---|
| apdet (Mietus et al. 2000) | 14591/17268, 84.5 | 28/30 (A vs C) |
| de Chazal et al. (CinC 2000) | 15432/17268, 89.36 | 30/30 (A vs C) |
| McNames et al. (CinC 2000) | 15994/17268, 92.62 | 30/30 (A vs C) |
| Song et al. 2016 HMM-SVM | 86.2 | 97.1 (AHI 5) |
| Sharma and Sharma 2016 | about 84 (83.8) | 97.14 (AHI 5) |
| Chang et al. 2020 1D CNN | 87.9 | 97.1 (AHI 5) |

Sources and what they cover:

- apdet: <https://archive.physionet.org/physiotools/apdet/>. Hand-set
  thresholds on the NN series from a beat annotation file, no learning.
  Learning set 26 of 30, 13895 of 17045 minutes (82.1). The page swaps the
  two set names once in its closing note.
- Challenge table: <https://physionet.org/content/challenge-2000/1.0.0/>
  (top-scores.html). Event 1 counts 20 A and 10 C test records (class B
  excluded); event 2 counts all 17268 test minutes. Teams could submit
  several entries and see their scores (de Chazal 15, McNames 4).
- Song et al., IEEE TBME 63(7):1532-42, doi 10.1109/TBME.2015.2498199
  (PubMed abstract read; full text paywalled): ECG and EDR features.
- Sharma and Sharma, Comput Biol Med 77:116-24, doi
  10.1016/j.compbiomed.2016.08.012 (abstract read): Hermite QRS-shape
  coefficients plus RR mean and SD.
- Chang et al., Sensors 20(15):4157, doi 10.3390/s20154157, Tables 5-6:
  train on the 35 released, test on the 35 withheld; AHI = 60 N / L >= 5;
  23 OSA + 12 non-OSA test records; 17234 test minutes.
- None of the baselines is hardware: all run as software on a computer.
  There is no published chip, gate count or area to compare against.

## What runs where

Before the chip (software front end, not measured by the lab):
beat times from the database's .qrs file; RR series with outlier removal
(300-2000 ms, within 20 percent of an 11-beat median); per minute and over
centred 3, 5 and 9 minute windows: SDs, RMSSD, pNN50, 1 Hz resampling and
a Hann-windowed periodogram for band powers (0.01-0.05 Hz cyclic
variation, 0.15-0.4 Hz, as ms and as fractions of 0.01-0.5 Hz); the
features of minutes i-2 .. i+2 join minute i (up to 4 minutes of
look-ahead); affine 8-bit quantisation with offsets and steps fixed on the
learning records.

On the chip (hard-wired, weights as constants, no weight memory):
the minute classifier (integer dot product, compare with a constant), and
the night logic: a saturating 10-bit counter of positive minutes, a 10-bit
minute counter, and the decision k x positives >= minutes (k fixed on the
learning records: 6 for D1, 8 for D5), with the minute and night outputs
registered. 22 flip-flops in every design.

## Size against accuracy (test records, scored once)

Gates: the lab's generic two-input gates; GE: sky130 gate equivalents of
the clocked night design (classifier + counters + registers).

| Design | Gates (min / night) | GE | Minutes | AHI5 | A/C |
|---|---|---|---|---|---|
| D1 1 feature | 3 / 197 | 465 | 12879 (74.58) | 32/35 | 27/30 |
| D2 2 feat w4 | 109 / 305 | 665 | 13151 (76.16) | 31/35 | 27/30 |
| D3 4 feat w6 | 256 / 367 | 791 | 13307 (77.06) | 33/35 | 28/30 |
| D4 8 feat w8 | 1059 / 1242 | 2634 | 14156 (81.98) | 29/35 | 25/30 |
| D5 16 feat w8 | 2282 / 2402 | 5205 | 14627 (84.71) | 32/35 | 28/30 |
| D6 MLP 16-8-1 | 10065 / 10262 | 20310 | 14723 (85.26) | 32/35 | 28/30 |
| float LR | - | - | 14725 (85.27) | 32/35 | 28/30 |
| float boosting | - | - | 14950 (86.58) | 32/35 | 29/30 |

Minute counts are out of 17268. Intervals (results.json has all):

- D5 minutes: Wilson 84.16-85.23, subject bootstrap 79.94-88.74;
  sensitivity 4943/6550, specificity 9684/10718; worst subject x14
  (45.9 percent of 490 minutes).
- D6 minutes: Wilson 84.73-85.78, subject bootstrap 81.49-88.60; worst
  subject x01 (62.0 percent of 523).
- D1 nights: 32/35, Wilson 77.6-97.0; sensitivity 23/23, specificity 9/12;
  errors x06, x17, x18 (non-OSA called OSA). Worst minute subject x31.
- D3 nights: 33/35, Wilson 81.4-98.4; errors x17, x18.
- With the fixed AHI rule (k = 12) instead of the trained k: D1 27/35,
  D3 32/35, D5 31/35, D6 32/35.

## Chip lab checks

For all six designs, minute classifier and night core (chiplab, sky130,
gf180 and ihp mapping):

- Level 1: bit-exact simulation on all 17268 test-minute input vectors
  (night core: with the real counter states of every night), 0 mismatches.
- Level 2: prove-equivalence with the independent golden model: proved.
- Clocked night design (core + 22 registers), with the lab's own
  functions: generic synthesis, mapping, and prove_sequential with the
  core as a black box (compositional): proved for all six. The flattened
  whole-design eqy proof failed on internal core partitions for D1 and D2
  (every output and register partition proved), timed out for D3 and was
  not run above 300 gates.
- Icarus (the lab's oss-cad-suite) ran the clocked design over all 35
  test nights: every minute output, counter value and night decision
  matched the Python integer model.

Area of the clocked night design (synthesis, before layout):

| Design | sky130 um2 | gf180 um2 | ihp um2 |
|---|---|---|---|
| D1 | 1745 | 5064 | 3023 |
| D5 | 19536 | 64899 | 34045 |
| D6 | 76236 | 249467 | 134164 |

## Like for like

- Same database, same fixed learning/test split, same per-minute labels
  and the same 17268-minute denominator as the challenge and apdet.
- Per-recording AHI rule reproduces Chang's 23/12 test counts; Song's
  and Sharma's exact truth rule was not read (paywalled full text).
- Inputs differ: ours and apdet use RR only; Song uses ECG and EDR,
  Sharma QRS shape, Chang the raw ECG.
- Challenge figures had test-set feedback (several entries); ours is one
  scoring of a fixed list of designs.
- Not paired: apdet's per-minute outputs were not rerun here.

## Weak points

- Per-recording result misses 34/35; with 35 records one error moves the
  accuracy by 2.9 points and every interval overlaps 97.1.
- The per-minute win over apdet is 36 minutes and unpaired; it does not
  beat Song, Chang, de Chazal or McNames.
- The costly part (band powers over 9-minute windows) runs before the
  chip; the gate counts exclude it.
- The night constant k was trained (6 or 8); the plain AHI rule (k = 12)
  scores lower, so the minute classifier over-calls minutes.
- Feature ranking used liblinear L1 without a fixed seed; a training-only
  rerun swapped two near-tied features. designs.json is the exact model.
- Training CV used 7 grouped folds (c05 and c06 as one subject).
- QRS annotations are machine-made and unaudited.

## Data, licence, credit

Apnea-ECG Database (ODC-By 1.0): T Penzel, GB Moody, RG Mark,
AL Goldberger, JH Peter, The Apnea-ECG Database, Computers in Cardiology
2000;27:255-258, doi 10.13026/C23W2R. PhysioNet, as the database page
asks: Pollard et al. (2026), PhysioNet as a global platform for biomedical
research, Nature Health. Only .qrs, .apn and .hea files and the
challenge answer files were downloaded (SHA-256 checked), outside the
repository; no recording is stored here.

## Reproduce

features.py, then models.py (cv, then test), chip.py, summarize.py; each
script's docstring gives its arguments. Python 3.12, numpy, scipy,
scikit-learn, wfdb. Run Python that reads data with -I.
