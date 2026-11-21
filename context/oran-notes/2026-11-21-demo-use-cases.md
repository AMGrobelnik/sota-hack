# Demo use cases (locked, Sat 21 Nov 2026)

Theme: **NICU on a chip.** The design environment designs the core chip for neonatal
monitoring devices. Two case studies:

1. **Incubator Watch** (radar plus thermal infrared): contactless detection of apnoea and
   bradycardia (radar) and temperature warning signs of cold stress and early sepsis
   (thermal). Real neonatal physiology, simulated sensors.
2. **Neonatal seizure detection from EEG**: real open expert-labelled data, a richer chip
   design problem.

AF from ECG is dropped completely (decision, 21 Nov). AF screening is already served by
existing devices, so it is not a case study.

## What each sensor is for

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

## Case 2: Neonatal seizure detection

- Data: Helsinki neonatal EEG dataset, Stevenson et al., Scientific Data 2019
  (doi:10.1038/sdata.2019.39), CC BY 4.0, Zenodo 10.5281/zenodo.4940267 (several versions;
  use the latest, which corrected annotations and headers). 79 term neonates from the
  Helsinki University Hospital NICU; seizures annotated independently by three experts;
  39 with seizures and 22 seizure-free by consensus.
- Clinical problem: many neonatal seizures have no visible signs and are only seen on EEG;
  expert EEG reading is not available around the clock.
- Chip: bedside or wearable EEG seizure detector, on the device.
- Why the design search matters: many channels, so the AI scientist chooses channels,
  window length and bits; a richer design space than single-lead ECG, and more data per
  second, so gate count matters more.
- Metric: seizures detected (per event, using expert consensus) against false detections
  per hour; split by baby.

## Open decisions (Oran)

- Desaturation threshold and its UK source.
- The clinical line for each case, as events detected and false alarms per hour.
- Whether to use consensus or any-expert seizure labels.

## Sources

- NHS GGC apnoea of prematurity:
  https://www.clinicalguidelines.scot.nhs.uk/nhsggc-guidelines/nhsggc-guidelines/neonatology/apnoea-of-prematurity/
- Alarm fatigue: https://www.childrenshospitals.org/news/childrens-hospitals-today/2019/04/patient-safety-project-aims-to-reduce-alarm-fatigue-in-the-nicu ;
  https://pmc.ncbi.nlm.nih.gov/articles/PMC11353546/ ; https://onlinelibrary.wiley.com/doi/10.1111/nicc.70322
- Helsinki EEG: https://pmc.ncbi.nlm.nih.gov/articles/PMC6400100/ ; https://zenodo.org/records/4940267
- Neonatal radar simulator: https://doaj.org/article/6d2b87fb398d490d9916b5649b3aa08c
