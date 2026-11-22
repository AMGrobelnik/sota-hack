# Apnea-ECG baseline comparison (key: apnea)

## Pre-registration (written before the test records were scored)

- Data: PhysioNet Apnea-ECG 1.0.0, 35 learning records (a01-a20, b01-b05,
  c01-c10) for every fit and choice, 35 test records (x01-x35) scored once.
- Labels: per-minute reference labels; test labels from the challenge file
  event-2-answers (identical to x??.apn, checked).
- Input: the database's machine beat annotations (.qrs) only.
- Per-recording reference: 12 x apnoea minutes >= minutes (AHI estimate
  of 5 or more), giving 23 OSA and 12 non-OSA test records; the challenge
  event-1 A versus C protocol (30 records) is reported too.
- Designs D1-D6 and the two float references are fixed in models.py.
- Headline per-minute design: best training-CV minute accuracy (D5).
- Headline per-recording design: best training-CV night accuracy, ties
  to the smallest design (D1; D2 and D6 tie with it at 33 of 35).
- Training-CV numbers at freeze: see logs (not tracked) and results.json.
