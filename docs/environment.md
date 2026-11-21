# The design environment for medical-device chips

## What it is

This comes from the team's Granola note.

- The team builds the environment, not the chips.
- The user writes a prompt that describes the device and the task.
  The user chooses the compute and the agents, and runs it.
- An orchestration layer, not a chatbot, starts agents. They
  propose designs, run experiments and test them in rounds.
- The user can pause, step in or redirect at any point.
- It reuses Adrian's existing general environment, which was
  declared as written before the event.

## Stages for chip design

This is a proposal from Claude. The team still has to agree it.

1. **Spec.** The sensor and signal, the task, the clinical line
   (Oran sets it), the size budget, the data, and the constraints
   (offline, fixed weights).
2. **Reference.** A full-precision model on the same data is the
   accuracy ceiling. The split by patient is fixed here.
3. **Propose.** Agents propose candidates: input rate, bits and
   window, what is computed in hardware before the model, the
   circuit family and its size. The families are binary or ternary
   networks, lookup-table networks, logic-gate networks and decision
   trees.
4. **Train.** Many candidates are trained at once as one GPU batch.
5. **Compile.** The best become a gate circuit with the weights
   fixed. This gives a gate or lookup-table count and a logic depth.
6. **Verify.** The circuit is checked against the model, bit for
   bit, on patients it never saw. Noise tests are added.
7. **Report.** The curve of accuracy against size, the winning
   design, the published results, and what failed.

Stages 3 to 6 repeat.

## Views

The Granola note names four views:

- the current stage
- live agent commands and outputs
- cost
- the chip sketch, always visible

Proposed additions from Claude, not yet agreed:

- The sketch shows the gate count.
- A live curve where each candidate is a dot. The clinical line and
  the published result are marked on it.
- An ECG strip that shows the circuit's decision.

## What the GPUs do

From the Granola note: the GPUs simulate the chip, and they run the
small models that would sit on it. In stage 4 they also train the
batch of candidates.

## How one run answers the four judging criteria

1. **Correctness and assumptions**: the circuit matches the model bit
   for bit on unseen patients.
2. **Fundamental reshaping**: thousands of designs trained as one GPU
   batch; agents propose in parallel.
3. **Meaningful speedup**: designs per hour against one at a time.
   The circuit against a microcontroller is only a labelled
   estimate.
4. **Scientific value**: the curve of accuracy against gate count.

## First run, and the published result to compare against

The first run is AF against normal rhythm.

### The published result: arXiv 2605.29994

Source: [arXiv 2605.29994](https://arxiv.org/abs/2605.29994),
read in full and checked by a second reader.

- **Data.** The MIT-BIH atrial fibrillation database has 25
  records. The paper uses 16 of them, about 13,800 windows of about
  42 s, channel 1 only. It does not say which 16.
- **Input.** 12-bit samples, every second sample kept, so 125 Hz. No
  filtering and no peak detection.
- **Scores.** The large design (BIG) has accuracy 95.8 and F1 95.6.
  The small design (SMALL) has 88.4 and 87.4. The abstract says F1
  up to 95.6%. No sensitivity or specificity is given.
- **Size on the FPGA.** BIG uses 2,844 LUTs, no DSP and 871 FF, on an
  AMD Spartan-7 S15. The paper lists 51 us for both BIG and SMALL.
  The 50.88 us figure was measured on a depthwise-separable AF
  model, not stated to be BIG. Power is a Vivado estimate of 42 to
  65 mW, not a measurement.
- **Split.** The paper does not state how train and test were split.
  It has no train, validation or test statement and no
  patient-wise statement. The accuracies are "best model" figures on
  an unnamed set.
- **How the design was found.** 73 configurations with the first
  block fixed, 115 with it free. Each experiment is 6 runs of 400
  epochs. One run takes about 13 minutes on an NVIDIA RTX 8000. The
  paper states no search wall-clock beyond that.

### The team's intended claim (a plan, not a result)

- The same database.
- Tested on patients the model never saw.
- Designs searched automatically in one batch.
- A full curve of accuracy against size.

### Caveats

- The paper does not say which 16 records it used, so an exact
  repeat is not possible.
- The comparison must be in the same unit as the paper: LUTs, and
  the same score.
- Its abstract says no BRAM, but Section IV.C says the accelerator
  has a BRAM input buffer.

## The other two papers

**arXiv 2609.32854: heartbeat classes, not AF.** Source:
[arXiv 2609.32854](https://arxiv.org/abs/2609.32854).

- MIT-BIH Arrhythmia Database, 48 records, with 102, 104, 107 and
  217 removed. The task is four heartbeat classes: N, S, V and F.
- The split is by patient: DS1 to train, DS2 to test.
- Cost: the classifier uses 3,223 LUTs and 0.46 nJ. The
  preprocessing needs 17,064 LUTs and 8.25 uJ. Both are Vivado
  estimates, not measurements. R-peaks come from the dataset
  annotations, so no peak detection is included.
- Lesson: accuracy alone can mislead. For the 6-LUTN, the per-class
  sensitivity is 0.998 for N, 0.007 for S, 0.869 for V and 0.003
  for F. The overall accuracy is about 94%, yet the S and F
  sensitivities are near zero.

**arXiv 2508.13181: AF patch.** Source:
[arXiv 2508.13181](https://arxiv.org/abs/2508.13181).

- Its own dataset: 30 people wearing a patch, about 98K samples of
  120 s. Whether the data is public is not stated. The split is 70,
  15 and 15 percent. Whether it is by person is not stated.
- Cost: 7,328 parameters, 14.6 KByte, on a Lattice iCE40 UltraPlus.
  3.81 mW was measured for the whole platform, not the chip alone.
- Lesson: a hardware-aware search that runs 190 generations of 8
  offspring and keeps a Pareto set. Sensitivity 0.938 and
  specificity 0.981 for the chosen model.

## Open points

- **The clinical accuracy bar is not verified.** In the baseline
  note, one review (AAFP, on a handheld ECG) was confirmed: 92%
  sensitivity and 95% specificity for AF in 233 patients, against a
  12-lead read by a cardiologist. Two other cohorts on the same page
  were also confirmed. The ESC 2020 30 s rule and the NICE figures
  were seen only as search snippets. The pages were not opened. So
  Oran sets the line.
- **No microcontroller baseline was found.** Two candidates were
  checked. One is an FPGA with no inference time or energy figure.
  The other is an ESP32-S3 at 9 ms, but it is not a Cortex-M, the
  task is not AF, and it gives no energy figure.
- **Nothing is built yet.** A feasibility test on Adrian's Mac is
  running.
