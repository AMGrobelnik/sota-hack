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

## Case 2: Epilepsy wearable (adults at home)

### What and why

People with epilepsy undercount their own seizures, so treatment rests on unreliable
seizure diaries. A behind-the-ear wearable with two to four electrodes is discreet enough
to wear every day, but it needs a tiny, low-power chip that detects seizures on the
device. The question a wearable maker needs answered before building: **with only these
electrodes, how small can the chip be, and what does it cost in missed seizures?**

We design the chip; we do not build the wearable.

### Chip outputs

| Output | From |
|---|---|
| Seizure alarm | EEG from the wearable's channels |
| Signal quality (electrode off, movement) | Same channels |

### How it works end to end

1. **Data.** Siena Scalp EEG (PhysioNet, CC BY 4.0, 14 adults, expert seizure
   annotations).
2. **Wearable channels.** Keep only the electrodes a behind-the-ear device would
   approximate (temporal channels nearest the ear; exact choice to agree with Oran, and
   ideally with the wearable company's real electrode layout).
3. **Channel budget sweep.** Run the search at 1, 2, 4 channels and the full cap, so the
   result shows what the wearable gives up.
4. **Batched design search, compile, bit-exact check**, as in Case 1.
5. **Results.** Split by patient (14 patients, so leave-one-patient-out). Seizures caught
   per event and false alarms per day, against chip size, one curve per channel budget.

### On the slide

"With two behind-the-ear electrodes, the smallest chip that works is N gates and catches
X% of seizures, against Y% with the full cap." Caveat: hospital electrodes near the ear
approximate, but are not identical to, a wearable's electrodes.

---

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
