# Build brief for the demo (for Adrian), Sat 21 Nov 2026

What each case study does, why, and how it runs end to end in the design environment.
Clinical choices are Oran's; implementation choices are Adrian's. Background and sources:
[2026-11-21-demo-use-cases.md](2026-11-21-demo-use-cases.md).

Both cases use the same loop: **spec, data, batched design search, compile to gates,
bit-exact check, results.** What changes is the sensor, the data and the task.

---

## Case 1: Incubator Watch (premature babies)

### What and why

A contactless monitor for a premature baby in an incubator. Today breathing and heart rate
come from wired chest leads: they irritate fragile skin, fall off, and drive alarm
fatigue (in one neonatal unit, 82% of alarms needed no action). We replace the leads with
two contactless sensors whose signals are combined on one small chip inside the
incubator:

- **Radar** sees chest movement: breathing and heartbeat.
- **Thermal camera** sees temperature: breathing at the nostrils, and core against hands
  and feet.

Why both: they measure breathing in two independent ways. The chip only raises an apnoea
alarm when both agree, so a baby moving or the radar losing its lock does not trigger an
alarm on its own. The thermal camera also adds what radar cannot see: temperature
warning signs of cold stress and early sepsis.

### Chip outputs (what the nurse sees)

| Output | Rule (UK, NHS GGC guideline) | From |
|---|---|---|
| Apnoea alarm | Breathing pause of 20 s or more, or shorter with bradycardia | Radar and thermal breathing, fused |
| Bradycardia alarm | Heart rate below 100 bpm (PICS annotation: at least two beats) | Radar heartbeat |
| Temperature warning | Core against hands and feet gap widening (cold stress, early sepsis pattern) | Thermal |
| Signal quality | Sensor unreliable (movement, obstruction) | Both |

### How it works end to end

1. **Real physiology.** PhysioNet Preterm Infant Cardio-Respiratory Signals (picsdb):
   10 preterm babies, ECG and respiration, expert bradycardia annotations (`.atr`).
   Apnoea labels are not annotated: derive them from the respiration signal with the 20 s
   rule, or inject apnoeas in simulation (state which).
2. **Simulate the sensors from that physiology, in parallel on the GPU.** Thousands of
   variations per baby, each a different "incubator":
   - Radar: chest displacement from the respiration signal plus a small cardiac
     component timed to the ECG R peaks; vary distance, angle, noise and baby movement.
   - Thermal nostril breathing: a temperature oscillation of about 0.3 to 0.5 C in step
     with breathing (Abbas et al. 2011); vary camera noise, head position and occlusion.
   - Thermal core and periphery: temperature trajectories for normal, cold stress and
     early sepsis (warm core, cooling periphery); vary incubator temperature and baby
     size.
   - Tier 1 (do first): signal-level simulation as above. Tier 2 (only if time): a
     physics body-heat simulation on a grid, which is the stronger parallelism story.
3. **Batched design search.** Thousands of tiny candidate chips trained at once; the AI
   scientist varies inputs used, window length, bits, size and the fusion rule.
4. **Compile and verify.** Best designs to gates; bit-exact check on unseen babies.
5. **Results.** Per baby (split by baby, never by window): apnoeas and bradycardias
   caught, false alarms per hour for radar alone, thermal alone and fused, against chip
   size.

### On the slide

"Real neonatal physiology, simulated radar and thermal." Roadmap from the same camera:
necrotising enterocolitis (abdominal temperature pattern, pilot evidence) and skin
infection (local hot spots, exploratory).

---

## Case 2: Neonatal EEG brain monitor

### What and why

Babies in neonatal intensive care, especially those with brain injury from lack of oxygen
around birth (hypoxic-ischaemic encephalopathy, HIE), need their brain activity watched
continuously. Full EEG needs an expert to read it, and experts are not there around the
clock. Units fall back on aEEG, a simplified one- or two-channel bedside trend that misses
many seizures (Cochrane: sensitivity for individual seizures 0 to 86% across 13 studies,
low certainty). Many neonatal seizures have no visible signs and are only seen on EEG.

The chip reads the EEG continuously at the cot side, from as few electrodes and gates as
possible, and gives expert-level outputs without an expert in the room.

### Chip outputs

| Output | Meaning | Labels from |
|---|---|---|
| Seizure alarm | A seizure is happening now | Helsinki dataset, three experts |
| Brain-injury severity grade | Normal or mild, moderate, severe, inactive background | Cork dataset, two experts with consensus |
| Signal quality | Electrode off, movement | Derived from the signal |

### How it works end to end

1. **Data** (both open, CC BY 4.0):
   - Helsinki neonatal EEG: 79 term babies from a neonatal unit, seizures annotated
     independently by three experts (Zenodo 10.5281/zenodo.4940267; take the latest
     version).
   - Cork neonatal EEG: 53 babies with HIE, 169 hours, each hour graded for background
     severity by two experts (Zenodo 7477575, about 4.4 GB, EDF or CSV).
2. **Channel budget.** Run the search at 1, 2 and 4 channels and the full montage. The
   bedside two-channel layout (Oran to confirm the standard positions) is the key point:
   can two electrodes plus a tiny chip match the expert reading the full EEG?
3. **Batched design search.** Thousands of candidate chips trained at once across
   channels, window length, bits and size; seizure and grade outputs share one front end.
4. **Compile and verify.** Best designs to gates; bit-exact check on unseen babies.
5. **Results.** Split by baby. Seizures caught (per event, against expert consensus) and
   false alarms per hour; grade agreement with the experts; all against chip size, one
   curve per channel budget.

### On the slide

"With two electrodes and N gates, the chip catches X% of the seizures three experts
marked, at Y false alarms per hour, and agrees with expert brain-injury grading Z% of the
time."

---

## Benchmark: our environment against a general AI model

Real data is what makes this comparison fair, which is why both demo cases use it.

- **Task:** the same design brief (data, constraints, clinical line) given to (a) our
  environment and (b) a general frontier model (Claude or ChatGPT) asked to design the
  chip, with the same time budget.
- **Measure on the same held-out real patients:** events caught, false alarms per hour,
  chip size in gates, and whether the design passes the bit-exact check.
- **Other baselines:** random search at the same budget; one design at a time instead of
  batched (the speedup); full-precision models (the accuracy ceiling).
- **Fairness:** same data access, same compute time, same verification; report the
  setup on the slide.

---

## Other use cases (roadmap slide)

"We demoed these two today because open data exists to show you exactly how it works.
The same environment covers:"

- Adult behind-the-ear epilepsy wearable: seizures and sleep from two to four
  electrodes (Siena Scalp EEG, Sleep-EDF); seizure-risk forecasting from sleep is a
  research direction.
- Necrotising enterocolitis and skin infection from the incubator thermal camera.
- Camera vital signs where raw video never leaves the chip.
- Breath and olfaction sensor arrays.

## What the dashboard should show (Oran)

1. **Spec**: sensor(s), task, constraints (gates or power, latency), clinical line, and
   data source labelled "public", "simulated" or "your device data".
2. **Data card**: source, number of patients, channels, who labelled it, real against
   simulated.
3. **Live search**: designs trained, designs per minute, what the AI scientist tries next.
4. **Results curve**: events caught and false alarms against chip size, clinical line
   marked, smallest passing design highlighted. Case 2: one curve per channel budget.
5. **Incubator view (Case 1)**: timeline per baby with radar breathing, thermal
   breathing, heart rate and temperature tracks, the fused alarm, and alarms avoided.
6. **Verification**: bit-exact on unseen patients.
7. **Circuit view and export**: gates lighting up on a breath or seizure; Verilog and a
   one-page design report.
