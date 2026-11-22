# Neonatal EEG: tiny seizure-detector chips measured on open recordings

A feasibility experiment for ChipIn's neonatal EEG case. It trains a family of tiny integer seizure detectors
on open neonatal EEG, compiles every design into logic gates with the chip lab, checks the frontier designs
bit for bit, and scores every design on babies it never saw. The result is the dashboard's data file
`dashboard/data/neonatal-eeg.json` on the `gh-pages` branch.

This is a feasibility result on one hospital's recordings, not clinical evidence.

## Data

Stevenson NJ, Tapani K, Lauronen L, Vanhatalo S. *A dataset of neonatal EEG recordings with seizure
annotations.* Scientific Data 6, 190039 (2019). Data: Zenodo, doi:10.5281/zenodo.4940267 (version 4),
licence CC BY 4.0. 79 term neonates, Helsinki University Hospital, 19 EEG electrodes at 256 Hz, seizures
annotated per second by three experts.

No recording, feature or excerpt is stored in this repository. `scripts/download.sh` fetches the files
(resumable, md5-checked) into a folder outside the repository.

## Method (fixed before results were read)

| Step | Choice |
| --- | --- |
| Labels | a second is seizure when 2 of 3 experts mark it |
| Split | by baby, seeded, stratified: 50% train, 20% validation, 30% held out |
| Signal | bipolar derivations, causal 0.5-30 Hz band-pass, 64 Hz |
| Channels | 1: C3-C4; 2: C3-P3, C4-P4; 4: adds T3-O1, T4-O2; 18: double banana |
| Windows | 8 s, decision every second at the window end |
| Features | 6 per channel, 6-bit, log scale (see below) |
| Model | one tiny network per channel (shared), max over channels, score > t |
| Threshold | on validation babies only, at most 1 false alarm per hour |

- Features: line length; zero crossings of the 0.5-4 Hz signal (16-sample moving average); and line
  length, 0.5-4 Hz line length, amplitude and high-frequency residual (signal minus a 4-sample moving
  average), each relative to a causal 15-minute background average. Scaling uses the training babies only.
- Networks: a single linear unit, or 1 to 32 hidden units with 4-bit activations; weights of 3, 7 or 15
  levels. They are trained with the integer arithmetic in the loop, and every figure is computed from the
  exact chipir/1 document the lab compiles.
- Event scoring: consensus runs closer than 10 s are merged, and events under 10 s are not scored. An event
  is caught when the alarm is on between its onset and its end plus 30 s. Alarm time outside every seizure
  (onset to end plus 30 s) is merged across gaps under 60 s and counts one false alarm per started 60 s, so
  an alarm that stays on keeps counting. Worst-baby sensitivity counts held-out babies with at least 2 events.
- Gates come from the lab's synthesis of the classifier only; the feature front end is not counted.

## Run

```bash
uv venv VENV --python=3.12 && uv pip install --python VENV/bin/python -e .
bash scripts/download.sh MANIFEST.tsv DATA_DIR 24            # or "all"
python -I -m neonatal_eeg.pipeline --data DATA_DIR --out OUT --babies 24 --stage 1
python -I -m neonatal_eeg.lab compile --designs OUT/stage1/designs.json --out OUT/stage1/lab.json \
  --chiplab CHIPLAB_BIN --cwd OUT/labwd                       # CHIPLAB_USER_DIR / CHIPLAB_CONFIG set
python -I -m neonatal_eeg.publish build --stage-dir OUT/stage1 --out neonatal-eeg.json --verify OUT/stage1/verify.json
python -I -m neonatal_eeg.publish validate neonatal-eeg.json
```
