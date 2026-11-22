# Spec (restated from the user's spec; not changed)

| Item | Value |
|---|---|
| Device | behind-the-ear EEG patch |
| Signal | EEG, 2 electrodes (channel budget: 2 at most, every candidate) |
| Detect | seizure onset (task: monitoring) |
| Patients | adults with epilepsy |
| Place | home |
| Target 1 | sensitivity ≥ 0.8 (primary metric) |
| Target 2 | false alarms ≤ 1 per hour |
| Data | SYNTHETIC (the user asked for simulated data) |

## Values I chose (the spec is silent)
- Sampling rate 256 Hz, 12-bit-ish ADC; decision every 2 s on a 2 s window → 0.5 decisions/s.
- Chip input: per-window features (line length, mean |x|) per channel, quantised to 8 bits; the chip makes
  the seizure/no-seizure decision. An alarm needs 2 consecutive positive windows; alarms within 60 s merge.
  (The feature front-end and the 2-window rule are modelled in software, not compiled — stated in the report.)
- Event caught: an alarm between seizure onset and seizure end + 10 s. False alarm: an alarm outside that.
- Power/size budget: "cheap enough for a tiny chip" → aim under ~2,000 gates; no power figure set.

## Can each target be measured?
Yes, both, but only on **synthetic data**: sensitivity and false alarms/h on held-out synthetic patients.
They are not clinical evidence. With ~6 test seizures, sensitivity is coarse (steps of ~0.17).
