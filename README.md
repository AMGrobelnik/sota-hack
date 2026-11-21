# Adrian's branch: the main idea and every idea so far

Hackathon project for the Scientific Parallelism hackathon, London,
21 to 22 Nov 2026. Code freeze is Sunday 14:45; demos start at 15:00.

This branch (`amg/context`) holds Adrian's material. `main` is kept empty
for now. Oran's and Antonio's material is on `oran/context` and
`ant/context`.

## Main idea: an AI-scientist environment that designs the core chip of a medical sensing device

**In one line:** you describe a medical sensing device and its task, and
AI scientists design, test and hand back the chip at its core.

- A medical sensing device has sensors, a housing and a core chip.
- The core chip takes the sensor input and does one specific job. It may
  run a small model, or only combine the inputs.
- The model's weights are wired into the chip. The device is small and
  low-power, works offline, and the patient's data stays on it.
- We do not make or sell chips. We build the environment where they are
  designed.
- The user writes a prompt. Agents propose designs, simulate and test
  them, repeat, and output the best one.
- The user sees the current stage, the live agent output, the cost and a
  sketch of the chip, and can pause or redirect at any point.
- It runs on Adrian's existing AI-scientist environment, which was
  written before the event and is declared as such.

### The demo: one real chip, end to end

"An environment" alone is generic and scores nothing on the judging
slide, so the demo is the environment designing one chip with numbers.

- **Prompt:** an atrial fibrillation (AF) detector from a single-lead
  ECG, with as few gates as possible, at the accuracy line Oran sets.
- **Search:** agents propose tiny models and input choices; thousands
  are trained at once as one GPU batch.
- **Compile:** the best become a gate circuit with the weights fixed.
- **Check:** the circuit must match the model bit for bit on patients it
  never saw.
- **Result:** a curve of accuracy against chip size, with the clinical
  line and the published designs marked on it.
- **Second device, only if time:** the newborn brain-oxygen calculation,
  as the case where the chip only combines inputs. It shows the
  environment is not ECG-only.

### How the demo answers the four judging criteria

1. **Correctness and assumptions:** the bit-for-bit check on unseen
   patients; every assumption stated (data, split, input, bits).
2. **Fundamental reshaping:** designing circuits one at a time becomes
   training thousands of candidates as one batch.
3. **Meaningful speedup:** designs per hour against the same search run
   one at a time on all CPU cores.
4. **Scientific value:** how much computation a diagnosis needs, shown
   as the curve, set honestly against published chips.

### What is measured so far (Mac test, Sat 21 Nov)

Code and rerun commands are in `spike/` (a quick feasibility test).

- The whole chain runs on Adrian's Mac: data, batch training, circuit
  export, gate synthesis, bit-for-bit check.
- 256 candidates train in one batch at 1,626 per minute. One at a time
  it is 27.6 per minute on the same GPU (about 59 times slower) and 56.0
  per minute on the CPU (about 29 times slower).
- One small model became 2,330 gates and matched the model on all 3,880
  test windows.
- Accuracy is not there yet: the circuit scores sensitivity 0.73,
  specificity 0.88, F1 0.68, against 0.97, 0.93 and 0.88 for the
  full-precision reference.
- The best larger model did not finish synthesis in 11 minutes.
- Limits: one seed, no tuning, beat intervals as input (not raw ECG),
  the CinC 2017 data (not the data the closest paper uses).

### Published work to compare against

- **Closest (arXiv 2605.29994):** AF against normal rhythm on the
  MIT-BIH AF database, raw ECG, accuracy 95.8 and F1 95.6 in 2,844
  lookup tables. It does not say how train and test were split, and its
  design was hand-built and scored over about 115 configurations.
- **Wearable AF patch (arXiv 2508.13181):** 3.81 mW measured on the
  whole platform, private data, found by an evolutionary search.
- **From Antonio's notes, not re-checked here:** an ECG chip at 98.29%
  on MIT-BIH with 31.39 nJ per inference (arXiv 2406.06543).
- So the claim is not "first". It is: tested on unseen patients, searched
  automatically in one batch, with the full curve.
- Details and sources: `ideas/evidence.md` and `ideas/environment.md`.

### Open points

- Whether teams may bring their own idea, and whether an engineering
  problem counts, are both unanswered on the event Discord.
- What GPUs or credits the event provides is not announced.
- The accuracy gap and the synthesis time for larger models.
- The clinical line: not verified from guidelines; Oran sets it, as
  sensitivity and specificity per patient, not accuracy.
- Privacy wording: say that keeping data on the device removes the
  transfer question. Do not say the law forbids cloud processing.

### Who does what

- **Adrian:** the environment and the GPU batch.
- **Antonio:** the views: stages, the live curve, the chip sketch.
- **Oran:** the clinical line, and which errors matter.

## Every idea so far

### Chosen

- **Chip design environment for medical sensing devices** (the team, Sat
  afternoon). Described above. Candidate devices, in order: AF from ECG,
  newborn brain oxygen, a breath or smell classifier (needs data), a
  sperm motility classifier (data to check).

### Fallbacks (Antonio's rule)

Own idea allowed and a strong GPU: ultrasound. Own idea allowed and a
limited GPU: thermal. Only the organisers' three examples allowed: flood.

- **Focused ultrasound through the skull under uncertainty** (Oran's top
  idea before the chip pivot). Simulate thousands of plausible skulls in
  one batch and report how likely the beam is to hit its target. A
  published benchmark with known answers exists. Risks: the simulator's
  authors already published skull-uncertainty estimation, and 3-D needs
  a big GPU.
- **Thermal detection limits.** Batched heat simulations of tissue with
  an infection: what depth and size can be detected from the surface.
  Textbook solutions as the answer key. The product space is crowded.
- **Flood uncertainty.** One of the organisers' examples: many rainfall
  scenarios in one kernel, with error bars on flood maps.

### Folded into the main idea

- **Infrared brain-oxygen monitoring for newborns** (Adrian). What
  distorts the reading, and by how much. On the Mac a photon simulation
  runs in about 0.3 s, and re-using its paths is about 1,700 times
  faster than a fresh run. Now the second-device candidate.
- **The smallest chip that still gets the diagnosis right** (ECG leads,
  bits and noise). Became the AF demo.
- **Where scarce biological or brain-inspired parts pay off in ordinary
  computers** (Antonio; dictated to Claude by Adrian). Most novel, weak
  on speedup and on the science. Now part of the motivation.

### Considered and set aside

- **Dialysis graft geometry search** (Oran's brief). Simulate blood flow
  through thousands of graft shapes. Strong story with a doctor to
  quote; too much solver risk for the time left.
- **Heart spiral waves and ablation targets.** Easiest build and very
  visual; the clinical premise failed in trials.
- **Drug heart-safety virtual population.** Easy to validate; barely a
  reshaping, and not new.
- **Smell and disease.** Fits an ARIA programme; no public breath data.
- **Multi-sensor early warning (sepsis data).** Modest reshaping.
- **Testing many hypotheses in parallel with error control.** Too
  generic alone; kept as the way hypotheses are kept honest.
- **Parallel AI scientist: depth or breadth.** Too generic alone; kept
  as one possible measurement (findings per hour against the number of
  parallel streams).

### Dropped

An AI scientist that enters the hackathon itself; scientists that learn
on fine-tuning credits; hyperthermia antenna planning; proton minibeam
design; pulse oximetry skin-tone simulation; deep brain stimulation
programming; radiotherapy planning; sperm-sorting channel design; the
first panel's ideas (light patterns to stop arrhythmias, a cell-sorting
chip designer, optogenetic implant design, neuron-culture wiring,
sound-shaped tissue, a through-skull focus designer).

Full detail on each: `context/adrian-notes/ideas.md`.

## Layout of this branch

- `README.md`: this page.
- `BUILT-TODAY.md`: what was brought in and what was built at the event.
- `ideas/`: the idea, the design environment, the event rules and the
  checked evidence.
- `context/`: raw context: transcripts, Granola notes, the judging
  slide, the team chat export and `adrian-notes/`.
- `spike/`: the feasibility test code and results.
