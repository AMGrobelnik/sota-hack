# Baseline AF: hard-wired AF detector from RR intervals

Status: in progress. Results are filled in from `results.json` at the end.

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
