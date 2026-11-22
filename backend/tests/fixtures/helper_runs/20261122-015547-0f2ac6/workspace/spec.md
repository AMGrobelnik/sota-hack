# Spec: two-electrode seizure flag

Items marked (chosen) are not in the brief; I picked them.

- Signal: 2 EEG channels from a band (chosen: 128 Hz per channel, 2 s windows, no overlap).
- Decision: one bit per window, seizure / not seizure. Chosen rate: 0.5 decisions per second.
- Chip input (chosen): 6 unsigned 4-bit numbers per window, 3 per channel: line length, amplitude
  (standard deviation) and zero-crossing count. The front end that makes them is NOT on this chip.
- Data: synthetic only, as the brief asks. No patient recordings. Chosen: 60 simulated subjects,
  split by subject 36 train / 12 validation / 12 test.
- Accuracy target (chosen): window sensitivity >= 0.90 and specificity >= 0.90 on the synthetic test
  subjects. This says nothing about real patients.
- Budget (chosen): under 2,000 gates; power is not measurable here (no layout, Docker off).
- Choice rule (brief): of two candidates, the smaller one that is bit-exact.
