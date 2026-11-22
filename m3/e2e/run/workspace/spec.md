# Spec: two-channel EEG seizure flag chip

Source: `brief.md`. The brief fixes the task (flag seizures), the input (two EEG
channels), the model type (small neural network) and the size (a few thousand logic
gates). Every other value below was **chosen by ChipIn** because the brief does not
give it; each is marked *(chosen)*.

| Item | Value |
|---|---|
| Signal | 2 scalp EEG channels, bipolar montage, e.g. F7-T7 and F8-T8 (temporal pair, covers the most common seizure onset zones) *(chosen)* |
| Sampling rate | 256 Hz per channel, 12-bit ADC samples (the CHB-MIT rate, so public data can be used unchanged) *(chosen)* |
| Window / decision rate | one decision per second over the last 2 s (design A and C) or 4 s (design B) of signal *(chosen)* |
| Decision | 1 bit: seizure / no seizure for the current window. The device raises an alarm after 3 consecutive positive windows (a 2-bit counter outside the classifier) *(chosen)* |
| Who wears it | not stated; assumed an ambulatory adult or child with epilepsy at home *(chosen)* |
| Accuracy target | event sensitivity ≥ 90 % (seizures with ≥ 1 alarm), worst-subject sensitivity ≥ 75 %, ≤ 1 false alarm per 24 h, median detection latency ≤ 10 s after electrographic onset *(chosen; in line with what published wearable detectors report)* |
| Size budget | classifier ≤ 3,000 generic gates; classifier + feature front-end ≤ 5,000 gates ("a few thousand", brief) |
| Power budget | logic ≤ 10 µW at 1 decision per second, so it is negligible next to the analogue front-end and radio *(chosen)* |
| Numerics | integer only: weights ≤ 4 bits (or ternary), activations ≤ 4 bits, features ≤ 6 bits *(chosen)* |

## What is not available in this run

- **No recordings.** The brief attaches no EEG data, so nothing can be trained or
  scored on patients here.
- **No ML libraries.** This machine has plain Python 3 only (no numpy, no torch).
- Therefore the reference model and training are skipped. The designs are compiled
  with fixed placeholder weights so that the size of each architecture can be measured.
  These circuits do not detect seizures.
