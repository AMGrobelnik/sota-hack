# Synthetic data assumptions (synthetic data, not patient data)
- 5 synthetic patients (p1–p5), 3 h each, 2 EEG channels behind the ear, 256 Hz.
- Background: 1/f noise ~20 µV RMS plus a weak alpha (8–12 Hz) component; per-patient amplitude scale 0.7–1.4.
- Seizure: 4 per patient, 30–90 s, rhythmic 3–7 Hz spike-wave whose amplitude ramps to 3–6× background,
  frequency slowing over the event, present on both channels (ch2 at 0.6–1.0× of ch1).
- Artefacts: chewing/EMG bursts (20–60 Hz, 5–20 s, ~12/h), motion (slow 0.3–2 Hz swings, large, ~6/h),
  electrode pops (step + decay, ~4/h).
- Split by patient: train p1,p2 · validation p3 · held-out test p4,p5.
