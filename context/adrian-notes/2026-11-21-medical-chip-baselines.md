# Medical chip baselines, 21 Nov 2026

On Sat 21 Nov 2026, mid-afternoon, one search and full-text reading pass was
run by two researchers, with one checker. Where the checker disagrees with a
researcher, the checker's version is used. A claim the checker marked as
overstated appears only in its corrected form, and a claim the checker did not
confirm is left out. An item marked not found was not found in this pass; that
does not show it is absent.

## arXiv 2605.29994 (Einhaus et al.)

- Task and data: detection of atrial fibrillation against sinus rhythm in ECG.
  The paper uses 16 of the 25 records of the MIT-BIH atrial fibrillation
  dataset, cut into about 13,800 windows of about 42 s, on channel 1 only.
- Train and test split: not stated. The paper names no train, validation or
  test split and does not say whether the split is patient-wise.
- Input: 12-bit ECG, with every second sample kept, giving 125 Hz. No filtering
  or peak detection. The first layer is a conv1d followed by binarization.
- Model: a 1D CNN with split convolutional blocks, binary activations and
  full-resolution weights. Table I gives the layers. No parameter count.
- Reported scores: Table IV gives accuracy 95.8 and F1 95.6 for BIG, and
  accuracy 88.4 and F1 87.4 for SMALL. The abstract gives F1 up to 95.6%. No
  sensitivity or specificity is reported. The accuracies are for the best
  model, on a set the paper does not name.
- Hardware cost: BIG uses 2,844 LUTs, 0 DSP and 871 FF on an AMD Spartan-7 S15,
  with Vivado 2023.1 (Table IV). Table IV lists 51 us latency for both BIG and
  SMALL. The 50.88 us figure is a measurement on an atrial fibrillation model
  described as depthwise-separable, which the paper does not name as BIG.
  Vivado estimates a total power of 42 mW to 65 mW, with 20 mW static; this is
  an estimate, not a measurement. The abstract says there is no BRAM, but
  Section IV.C describes a BRAM input buffer.
- How the design was found: a search over 73 configurations with the first
  block fixed and 115 with it free, with a plateau at 7 and 12. Each experiment
  was six training runs of 400 epochs, and one run takes about 13 minutes on an
  NVIDIA RTX 8000. The paper lists the CHB-MIT database as future work.
- Code availability: the generator tool, es-ude/elasticai.creator, is open
  source on GitHub (footnote 1 of the paper). Whether the AF model is in it is
  not stated.

## arXiv 2609.32854 (Mommen et al.)

- Task and data: four-class heartbeat classification into the AAMI classes N,
  S, V and F. This is not AF. The MIT-BIH Arrhythmia Database has 48 records;
  paced records 102, 104, 107 and 217 are removed, and class Q is ignored.
- Train and test split: by patient. Train set DS1 and test set DS2, under the
  inter-patient scheme of de Chazal, with 22 records each.
- Input: one 138-bit precomputed feature vector per heartbeat. The R-peak
  positions come from the database annotations, so no peak detector is used.
  Features include 8-bit RR intervals and 8-bit crest factors. The raw signal
  is 360 Hz at 11 bits.
- Model: the LGN has 8000 gates per layer. The LUTN is built from 6-input LUTs;
  the hardware design has 2000 of them, in one layer, with outputs popcounted
  in groups of 500 per class. Depths 1 to 4 were tested (Table B.14). No
  parameter count.
- Reported scores: Table 4 gives accuracy and jk per model for the inter-patient
  split. Each accuracy and jk value in Table 4 is the best across depths, so a
  row need not be one model: 6-LUTN has accuracy 94.24 at 2 layers (Table B.14)
  and jk 0.651 at 1 layer (Table B.15). The abstract gives up to 94.41%
  accuracy and a jk index of 0.683; these maxima come from different models.
  The 1-layer 6-LUTN built in hardware scores accuracy 94.04 and jk 0.651.
  Table 5 gives per-class precision, sensitivity, specificity and F1 for N, S,
  V and F. Depth and temperature appear to have been chosen on the test set
  DS2, and no validation set is mentioned.
- Hardware cost: Vivado 2025.1 estimates on a Zynq-7000 ZedBoard
  (xc7z020clg484-1), using vectorless analysis at an assumed 1 MHz.
  Preprocessing IP: 17,064 LUTs, 2,811 FF, 53 DSP and 8.25 uJ. Classifier IP:
  3,223 LUTs, 267 FF, 5 cycles, 0.092 mW and 0.46 nJ, of which the LUTN itself
  is 2,000 LUTs.
- How the design was found: the topology was chosen as a hyperparameter in
  PyTorch. Peak detection is the part still missing for an end-to-end
  classifier (Table 10).
- Code availability: no code link found. The paper has only reference URLs.

## arXiv 2508.13181 (Loroch et al.)

- Task and data: AF detection on the authors' own dataset, not MIT-BIH: 30
  probands and about 98K samples of 120 s, recorded with a GE SEER 1000 device.
  The abstract also mentions three weeks. Table II checks the model on other
  datasets, including MIT-BIH.
- Train and test split: 70% training, 15% validation and 15% final testing.
  Whether the split is by proband: not stated.
- Input: 120 s ECG windows. The sample rate of the authors' own data is not
  stated.
- Model: a depthwise-separable 1D CNN trained with quantization-aware training.
  The final model is a 2-layer model with 14.6 KByte of memory. Model 3 has
  7,328 parameters. The text does not state outright that Model 3 is the
  deployed model.
- Reported scores: Table I, Model 3: sensitivity 0.938, specificity 0.981 and
  noise specificity 0.985. Table III, "Ours": 95.8% sensitivity and 95.8%
  specificity, with no accuracy value. These 95.8 figures match the Model 3
  MIT-BIH column of Table II, not the authors' own-dataset figures. The
  abstract's 95% accuracy is not supported by a number in any table.
- Hardware cost: Lattice iCE40 UltraPlus (iCE40UP5K). Power was measured with an
  NGU201 at 1.03 mA and 3.81 mW for the whole platform, which acquires and
  analyses the ECG. The FPGA takes 15.9% and the neural network 6.3% of the
  total. The abstract gives 3.8 mW. The measurement excludes Bluetooth
  transmission and eMMC storage. Absolute LUT count, latency and energy per
  inference are not stated; Fig. 3 shows resource use only as percentages.
- How the design was found: hardware-aware evolutionary neural architecture
  search, run for 190 generations with 8 offspring per generation, 30 epochs per
  candidate and 220 Pareto individuals. The search wall-clock time is not
  stated. The paper says the model may be overfitted to its topology.
- Code availability: no code or circuit link found in the text.

## Clinical bar and microcontroller baseline

- Clinical bar, n=233: sensitivity 92% and specificity 95% for AF, in a single
  outpatient cardiology clinic, against a 12-lead ECG read by a cardiologist
  (AAFP review of KardiaMobile).
- Clinical bar, other cohorts: n=55 gives sensitivity 100% and specificity 97%
  for AF or flutter. n=42 gives sensitivity 94.6% and specificity 92.9%. The
  device gives a reading within 30 seconds.
- The same page also cites a 381-person study at 94%, which was not checked
  further.
- Only this one review, for one device, is confirmed as a clinical bar.
- Microcontroller baseline: ESP32-S3 (arXiv 2606.02256, ArrythML), with about
  180 KB of memory and 9 ms on-device inference latency. The task is binary
  normal versus abnormal arrhythmia, not AF. It is not a Cortex-M device, and no
  energy figure is given.
- The nearest AF hardware figures are the FPGA patch above (arXiv 2508.13181).
  That is not a microcontroller.

## Not found

- arXiv 2605.29994: the 16 records used; a train, validation and test split, and
  whether it is patient-wise; a parameter count; sensitivity and specificity;
  energy per inference; whether the AF model is in the code tool.
- arXiv 2609.32854: a parameter count; static power; a code link.
- arXiv 2508.13181: whether the split is by proband; the sample rate of the own
  data; final bit widths; absolute LUT count; latency; energy per inference;
  search wall-clock time; a code or circuit link; public availability of the
  dataset.
- Clinical bar, ESC 2020 30-second rule: only a search snippet; the page was not
  opened.
- Clinical bar, NICE MTG64: page fetch blocked; search snippet only.
- Clinical bar, PubMed 37417386: page fetch blocked; search snippet only.
- Microcontroller baseline, Sensors 2025 energy and time figures: page refused
  (403); search snippet only.
- Microcontroller baseline for AF: none found.
- Fourth question in the bar and baseline file (Q4): not attempted.
