# Demo use cases (final, Sat 21 Nov 2026)

Theme: **always-on monitoring, from the incubator to the home.** One design environment
designs the core chip for two very different continuous-monitoring devices. Two case
studies, locked:

1. **Incubator Watch** (premature babies; radar plus thermal infrared): contactless
   detection of apnoea and bradycardia (radar, fused with thermal nostril breathing) and
   temperature warning signs of cold stress and early sepsis (thermal). Real neonatal
   physiology, simulated sensors.
2. **Epilepsy wearable** (adults at home; EEG): the smallest chip that still catches
   seizures from the two to four electrodes a real wearable has. Real recordings with
   expert seizure labels.

Two populations, two sensor types, one case on simulated data and one on real data: this
shows the environment is general.

## What each sensor is for (Case 1)

- **Radar**: mounted on the incubator, it senses the tiny chest movements of breathing and
  the heartbeat without touching the baby. The chip turns that into breathing and heart
  rate and flags apnoea and bradycardia. It replaces wired chest leads, which irritate
  fragile skin and fall off.
- **Thermal infrared camera**: one camera, one chip, several outputs (see the thermal
  readouts table under Case 1). For the demo it gives two: the core against hands and
  feet gap (warm core, cold periphery is the warning pattern for cold stress and early
  sepsis; Oran's NeoTherm work), and breathing from nostril temperature, a second,
  independent breathing signal fused with the radar.
- **Not doing**: two-wavelength near-infrared for oxygen. Contactless camera oxygen in
  neonates is not reliable enough, and there is no open neonatal ground truth;
  desaturation stays with the existing pulse oximeter.

## Shared clinical framing

- Problem: alarm fatigue. In one neonatal unit, 82% of alarms nurses experienced were
  non-critical or non-actionable (Children's Hospital Association report, 2019). A NICU and
  PICU nurse study found 41.7% of recorded alarms non-actionable (PMC11353546). Adult ICUs
  report up to 45 alarms per patient per hour; that is an adult figure and must not be
  presented as neonatal.
- Clinical metric for every case: events detected (sensitivity per event) against false
  alarms per hour, compared with the baseline above. Report per baby, not pooled accuracy.

## Case 1: Incubator Watch

**Event definitions** (UK: NHS Greater Glasgow and Clyde neonatal guideline, apnoea of
prematurity; BAPM wording not yet found):

- Apnoea: a pause in breathing of 20 s or more, or a shorter pause with bradycardia,
  cyanosis or pallor.
- Bradycardia: heart rate below 100 beats per minute.
- Desaturation: threshold varies by source (85%, 88%, 90%); use the unit's or BAPM's figure
  and cite it. To decide.

**Sensors and data**

| Sensor | Measures | Data | Status |
|---|---|---|---|
| Radar on the incubator | Chest movement: breathing and heartbeat | Real neonatal physiology from PhysioNet PICS; radar signal simulated from it; front end checked against open radar data | Build first |
| Thermal camera | Core versus peripheral temperature; breathing from nostril temperature | Simulated: body heat and breathing airflow for thousands of babies and incubator settings on the GPU | Build second |

**Fusion: the alarm-fatigue story.** Radar and nostril temperature give two independent
breathing signals. The chip raises an apnoea alarm only when both agree (or when one
agrees together with bradycardia), which targets the non-actionable alarms directly.
Report false alarms per hour for radar alone, thermal alone and fused.

**Thermal readouts**

| Readout | Detects | Evidence | Demo |
|---|---|---|---|
| Core against hands and feet | Cold stress, early sepsis | Thermoregulation and peripheral perfusion are listed thermal uses in neonatal imaging reviews (PMC6481091; Topalidou et al. 2019 scoping review, 21 observational studies, cohorts of 4 to 29); Oran's NeoTherm work | Build |
| Breathing from nostril temperature | Breathing rate, apnoea | Abbas et al. 2011, BioMedical Engineering OnLine: 0.3 to 0.5 C difference between inspiration and expiration at the anterior nares in NICU newborns (PMC3258209) | Build, fused with radar |
| Overall temperature trend | Hypothermia, fever | Comes with the core readout | Build |
| Abdomen temperature pattern | Necrotising enterocolitis (NEC) | Pilot level only: Rice et al., 13 ELBW infants, 3 with radiographic NEC had lower abdominal skin temperature (PMC3775585); Herry, Frize and Bariciak 2011, slower abdominal temperature decrease in NEC; Ottawa cohort NCT03994341 completed, results not found | Roadmap slide |
| Local hot spots | Skin infection (umbilical stump, cellulitis), cannula sites | Principle only (inflammation raises local temperature); no human neonatal studies found; one newborn calf omphalitis study | Roadmap, exploratory |
| Jaundice | | Needs visible light, not thermal | Not thermal |

**Data sources**

- PhysioNet Preterm Infant Cardio-Respiratory Signals Database (picsdb, v1.0.0, open):
  10 preterm infants, 29 3/7 to 34 2/7 weeks post-conceptional age; ECG and respiration;
  `.atr` files hold reference bradycardia onsets (heart rate below 100 bpm for at least two
  beats); `.qrsc` reference R peaks; `.resp` respiration peaks are algorithmic and not
  manually vetted. https://physionet.org/content/picsdb/
- Radar front-end checks: neonatal thorax simulator radar dataset (Scientific Data 2024,
  5 to 80 breaths per minute, laser reference); small neonatal IR-UWB respiration CSV
  (Dryad doi:10.5061/dryad.f3bn03g); adult FAU clinical radar set with ECG (Sci Data 2020,
  figshare 10.6084/m9.figshare.12186516).
- Thermal: no open neonatal thermal dataset found after four searches. Leads needing a
  request: the Greek neonatal sepsis thermal repo (no licence), Selcuk University NICU set
  (34 neonates). Hence simulation.

**On the slide:** "real neonatal physiology, simulated radar and thermal".

## Case 2: Epilepsy wearable

**The claim (a design study, not a product):** "If a wearable only has these two
electrodes, here is the smallest chip that works, and what it costs in missed seizures."
We design the chip for whoever builds the wearable; we do not build the wearable.

- Clinical problem: people with epilepsy undercount their own seizures, so treatment
  decisions rest on unreliable seizure diaries. A discreet wearable needs a tiny,
  low-power chip that detects seizures on the device.
- Real wearables use two to four electrodes (behind or around the ear, under the scalp,
  patches, headbands), not a full cap. Company examples to check before naming on a slide.
- Method:
  1. Hospital EEG with expert seizure labels (Siena).
  2. Keep only the channels a wearable would have (for example those nearest the ear).
  3. The environment finds the smallest chip that still catches seizures from those
     channels.
  4. Show the trade-off: number of electrodes against chip size against seizures caught.
- Data: Siena Scalp EEG Database, PhysioNet v1.0.0, CC BY 4.0, 14 adults (ages 20 to 71),
  University of Siena, 20.3 GB, annotated seizures.
  https://physionet.org/content/siena-scalp-eeg/1.0.0/ . Scale-up options: CHB-MIT
  (PhysioNet, younger patients, licence to check), TUH EEG Seizure Corpus (large, free
  with registration).
- Metric: seizures caught (per event) against false alarms per day; split by patient.
- Caveat to state: hospital electrodes near the ear are not identical to a wearable's
  (contact quality, placement), so this is an approximation.
- Competition: home seizure wearables and Ceribell in the ICU exist. Our claim is the
  design environment and the electrode-against-chip-size map, verified bit for bit.

## Data model (how customers use it)

1. **Feasibility, on public or simulated data** (what we demo): before any hardware, is
   the device possible and how big must the chip be?
2. **Final design, on the customer's own device data**: their electrodes and noise differ
   from hospital data, so the chip is redesigned on their recordings. The platform runs
   in the customer's environment; their patient data never leaves their control.

The device maker remains responsible for clinical validation and regulatory approval.

## Dropped

- AF from ECG (served by existing devices).
- Neonatal EEG seizures and HIE grading (kept as backup; both datasets open CC BY 4.0:
  Helsinki, Zenodo 10.5281/zenodo.4940267, 79 neonates, three expert labellers; Cork,
  Zenodo 7477575, 53 neonates with HIE, 169 h, hourly background grades by two experts).

## Open decisions (Oran)

- Desaturation threshold and its UK source.
- The clinical line for each case, as events detected and false alarms per hour.
- Which channels count as "wearable" for the epilepsy case.

## Sources

- NHS GGC apnoea of prematurity:
  https://www.clinicalguidelines.scot.nhs.uk/nhsggc-guidelines/nhsggc-guidelines/neonatology/apnoea-of-prematurity/
- Alarm fatigue: https://www.childrenshospitals.org/news/childrens-hospitals-today/2019/04/patient-safety-project-aims-to-reduce-alarm-fatigue-in-the-nicu ;
  https://pmc.ncbi.nlm.nih.gov/articles/PMC11353546/ ; https://onlinelibrary.wiley.com/doi/10.1111/nicc.70322
- Siena Scalp EEG: https://physionet.org/content/siena-scalp-eeg/1.0.0/
- Backup neonatal EEG: https://zenodo.org/records/4940267 ; https://zenodo.org/record/7477575
- Neonatal radar simulator: https://doaj.org/article/6d2b87fb398d490d9916b5649b3aa08c
