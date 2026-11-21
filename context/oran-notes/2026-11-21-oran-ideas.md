# Oran's idea work, 20 to 21 Nov 2026

Research note from Oran's sessions with Claude, before and during the event. It covers
every candidate discussed, how each scores against the judging slide, the size of the
clinical problem behind the top ones, and possible case studies for the chip design
environment. Figures marked as checked were read from a primary source or its abstract;
everything else needs checking before a slide.

Supporting notes:

- [2026-11-21-figure-ledger.md](2026-11-21-figure-ledger.md): source-by-source check of
  every number in the dialysis graft brief.
- [2026-11-21-idealab-ranking.md](2026-11-21-idealab-ranking.md): seven idea-database
  searches and the resulting ranking.
- [2026-11-21-ideation-prompt.md](2026-11-21-ideation-prompt.md): a paste-in prompt for
  generating and stress-testing ideas against the judging slide.

## How the ideas were judged

- The four criteria on the organisers' slide: correctness and assumptions, fundamental
  reshaping, meaningful speedup against a credible baseline, scientific value. Negative
  results count.
- Judges are expected to be technical and AI-for-science people, not clinicians. Expect
  questions on baseline fairness, whether the work is reshaped or just many copies, how
  correctness is shown, where the bottleneck is, and why it matters in one sentence.
- "Fundamental reshaping" means changing the method so new parallelism appears. Running
  many independent copies of a slow program is parallel but is not reshaping on its own.
- Team fit: two strong ML and JAX engineers without a numerical-solver background, so
  build on JAX libraries (j-Wave for acoustics, XLB for lattice Boltzmann) rather than
  writing solvers from scratch.

## Ranking (as of Sat 21 Nov, before the chip pivot)

Scores 1 to 5 on the four criteria, finishability in about 24 h, and sponsor fit.

| Rank | Idea | Total /30 | One-line reason |
|---|---|---|---|
| 1 | Transcranial focused ultrasound under skull uncertainty | 24 | Published benchmark with known answers; clean k-Wave baseline; bandwidth-bound |
| 2 | Dialysis graft geometry search (XLB) | 21 | Strongest AI loop and an interventional radiologist contact; riskiest engineering |
| 3 | Cardiac tissue grid for ablation targets | 22 | Easiest build, very visual; clinical premise failed in trials |
| 4 | CiPA virtual population | 21 | Easy to validate; arithmetic-bound, weak Fractile fit; commercial overlap |
| 5 | Hyperthermia antenna planning | 20 | Neat field-superposition trick; nothing to validate against |
| 6 | Proton minibeam collimator design | 17 | No validation, too heavy to build |

Dropped earlier: pulse oximetry skin-tone simulation (the GPU code already exists, so the
speedup is not ours), deep brain stimulation programming and radiotherapy planning (very
crowded), inverse docking (scores not comparable across proteins), ablation target
search as originally framed (see the cardiac caveat below).

## 1. Transcranial focused ultrasound under skull uncertainty

- **What**: focused ultrasound treats conditions such as essential tremor through the
  skull. The skull bends and weakens the beam; planners correct using skull properties
  estimated from CT, which are uncertain, but plan on one best guess. Simulate thousands
  of plausible skulls in batched GPU passes and report how likely the beam is to hit and
  heat the target.
- **Validation (checked)**: Aubry et al. 2022, J Acoust Soc Am 152:1003, nine benchmark
  problems from a flat bone plate to a whole skull; eleven codes agreed within 10% on
  focal pressure and 1 mm on focal position; data on Zenodo (record 6020543).
- **Tooling (checked)**: j-Wave (Stanziola et al., SoftwareX 2023), a differentiable JAX
  acoustic simulator matching k-Wave's Fourier method.
- **Reshaping**: one batched pass over many uncertain skulls; time reversal gives every
  transducer element's settings from one simulation; gradients through j-Wave optimise
  settings robust across the ensemble.
- **Problem size (checked unless noted)**:
  - Essential tremor: about 1.3% of people worldwide, 5.8% of those 65 and over
    (meta-analysis).
  - Low skull density ratio (below 0.45) may be 30 to 40% of patients who could benefit,
    more in East Asian populations; low ratios have been a trial exclusion criterion.
  - Pivotal randomised trial (Elias, NEJM 2016): gait disturbance 36%, numbness or
    tingling 38%, persisting at 12 months in 9% and 14%. Benefit attenuates by 5 years.
  - Value for money borderline: about GBP 20,851 per QALY (England analysis), about CAD
    43,075 per QALY (Ontario, patients ineligible for surgery); Australia's MSAC declined
    to fund it. No reliable per-procedure cost found.
  - Caveat: no study attributes failures or side effects to skull-property uncertainty;
    claim better-quantified confidence, not fewer complications.
- **Discovery angle for an AI scientist**: "Is there a better predictor than the skull
  density ratio of who focused ultrasound will work for?" Use synthetic layered skulls
  (thickness, porosity, curvature) so the agent can explore a controlled space.
- **Risks**: 3D whole-skull may be slow; the raw solver speed is the library's; pressure
  waves only, no shear; crowded field (about 15 Idealab ventures); needs a neurosurgery
  contact.

## 2. Dialysis graft geometry search

Full brief and checked figures in [dialysis-graft.md](dialysis-graft.md) and
[2026-11-21-figure-ledger.md](2026-11-21-figure-ledger.md). Key corrections from the
check:

- Use 41% pooled 1-year primary patency for ePTFE grafts (Halbert 2020, Kidney360), not
  49%/62% (no primary source found).
- $2.8bn (Thamer 2018, AJKD) is total fee-for-service Medicare access spend in 2013, not
  the geometry-addressable slice. $48.9bn not found; drop it.
- Closest prior art: Williams et al. 2021, Sci Rep 11:12153, six graft-to-vein angles,
  about 30 degrees optimal, shear-rate thresholds of 50 and 1000 per second. Same group
  holds US patent 11,369,381 B2. Published studies test 6 to 27 hand-picked
  configurations; anastomosis shape optimisation dates to 1997 (Lei, Archie and
  Kleinstreuer, J Vasc Surg).

## 3. Cardiac tissue grid for ablation targets

- **What**: simulate spiral waves on a 2D grid of heart tissue (Fenton-Karma or
  Aliev-Panfilov) and test thousands of ablation patterns at once to see which stop
  them.
- **Problem size (checked)**: AF costs an estimated $6 to 26bn a year in the US and about
  EUR 13.5bn in the EU; repeat ablations drive cost after a first procedure; severe
  complications in about 2.4% of first ablations in trials, tamponade under 1%, stroke
  about 0.2%, death well under 0.1%.
- **Caveat (checked)**: ablating rotor sources did not beat standard ablation in
  randomised trials (REAFFIRM equivalent; REDO-FIRM no added benefit). Most first
  ablations fail because lesions do not last. Method demonstration only.

## 4. CiPA virtual population

Run the FDA's single-cell cardiac safety model across thousands of virtual patients.
Validates against the CiPA reference drugs, but single-cell ODEs are arithmetic-bound,
and Idealab lists Oxford and Certara selling close methods. Thorough QT study cost of $2
to 4m each is unverified (from an earlier chat citing Altasciences).

## Chip and hardware ideas from Oran's hunches

Shared thesis: medicine is moving from occasional measurement to continuous sensing on
the body and in small devices, which makes it a streaming and memory-bandwidth problem
on tiny chips. That is Fractile's thesis appearing in healthcare.

- **Atrial fibrillation detector chip** (now the team's demo): see `docs/idea.md`. Points
  raised: report sensitivity and specificity per patient at a screening operating point,
  not accuracy; split data by patient to avoid leakage; frame reshaping as turning
  one-at-a-time circuit synthesis into batched gradient training; hard-wired weights
  remove memory traffic entirely, the extreme end of Fractile's thesis.
- **Sperm-sorting microfluidic chip design (fertility)**: simulate thousands of sperm
  through thousands of channel geometries; ties to Oran's fertility work; hard physics
  near walls and no known benchmark.
- **Electronic-nose sensor-array design (olfaction)**: choose which sensors go on a breath
  chip to separate disease signatures; data availability is the blocker.
- **Always-on monitoring model for an edge chip**: show inference is bandwidth-bound,
  then fit it to a small chip's memory budget; strong Fractile fit, weaker scientific
  value.

## Case-study candidates for the chip design environment

Ordered by fit with "AI scientist designs the core chip of a sensing device":

1. AF from single-lead ECG (current demo; Oran sets the clinical line).
2. Neonatal infrared brain-oxygen monitoring (team notes already exist; the chip only
   combines inputs).
3. Breath or e-nose classifier (needs data).
4. Sperm motility classifier for a microfluidic or home test chip (data: VISEM-Tracking,
   to check).

## Pitch lessons

- A previous SoTA x ARIA winner (MineTrust, Trust Everything, March 2026) paired clear
  real-world stakes with a mechanism that made a claim verifiable. Lead with verification
  (here: bit-exact circuit check), then speed.
- Show generality, do not just claim it: one validated case study plus a crude second
  device beats "works for anything".
