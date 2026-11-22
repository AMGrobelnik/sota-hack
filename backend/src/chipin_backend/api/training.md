**Training (reference and finetune).** `"$CHIPIN_TRAIN_PYTHON"` is a Python that can train (numpy, torch);
plain `python3` may not be. Run every training and data script with it: `"$CHIPIN_TRAIN_PYTHON" train.py`.

- **No recordings attached** and the user did not forbid simulation: generate synthetic recordings. First write
  `data/assumptions.md`: sampling rate, channels, what an event (a seizure) looks like in the signal, the
  artefacts, and how many synthetic patients and events.
- **Make the synthetic task hard enough to tell designs apart**: patients that differ from each other, artefacts
  that look like events, far fewer events than background. If the reference scores perfectly on validation, the
  data is too easy: make it harder (and say how) before proposing candidates.
- **Split by patient** into train, validation and held-out sets before any training, and write the split to
  `data/split.json`; hold out at least two patients. Held-out patients are never used for training or for
  choosing a model.
- **Train** the reference and the candidates, marking `reference` and `finetune` started and done as for the
  other stages. Choose the chip on validation figures, by the rule in "Choosing the chip". Training is a long
  step: write a status line before it starts and at least every couple of minutes while it runs (call
  `./progress status` from the training loop, for example once per epoch block), saying only what is really
  happening.
- **Score on the held-out patients only**: sensitivity (events caught of all events) and false alarms per hour,
  per patient and pooled, for every candidate. Report the chosen design's pooled figures as
  `./progress metric synthetic_sensitivity 0.925` (a fraction between 0 and 1, never a percentage) and
  `./progress metric synthetic_false_alarms_per_h 0.4 /h`, and the held-out patients meeting the target as
  `patients_pass` and `patients_total`.
- **As soon as a candidate is scored**, before anything is compiled, send its design record with `gates: null`
  and your `gates_est`, under your own name for it (see "Design records"); the compile and verify updates
  follow under the lab's `design_id` with `previous_id`.
- **Label every such figure "synthetic data"** in `report.md` and in status lines. Synthetic figures show the
  pipeline works; they are never clinical evidence.
- With the chip lab, hand the trained weights to it with `ingest-model`, and pass the held-out windows and
  your model's outputs to `simulate` so the chip is checked against the trained model.
