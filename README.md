# Chip design environment for medical devices (working title)

Hackathon project for the Scientific Parallelism hackathon, London,
21 to 22 Nov 2026.

## The idea

- A medical sensing device has sensors, a housing and a core chip.
- The core chip does one job: it may run an AI model, plain machine
  learning, or only combine the sensor inputs.
- We build an environment where an AI scientist designs that core chip
  for one task, as efficiently as possible, with privacy as a constraint.
- The model is wired into the chip, so the device works offline and
  patient data stays on the device.
- We build the environment, not the chips.

## The demo

The prompt: "an atrial fibrillation (AF) detector from a single-lead
ECG, with as few logic gates as possible, at the clinical accuracy
line."

An automated search proposes many tiny models and input choices. They
are trained thousands at a time on the GPU. The winners are compiled to a
gate circuit with fixed weights. The circuit is checked bit for bit
against the model. The result is a curve of accuracy against gate count,
with the clinical line marked.

## How the demo answers the four judging criteria

1. **Correctness and assumptions**: the circuit matches the model bit
   for bit on unseen patients.
2. **Fundamental reshaping**: thousands of candidate designs are
   trained as one GPU batch, and agents propose in parallel.
3. **Meaningful speedup**: designs per hour against one at a time. The
   circuit against a microcontroller is shown only as a labelled
   estimate.
4. **Scientific value**: the curve of accuracy against gate count.

## Who does what

- **Adrian**: the environment and the GPU batch.
- **Antonio**: the views: the design stages, the accuracy curve, the
  circuit lighting up on a heartbeat.
- **Oran**: the clinical accuracy line, and which errors matter.

## Status

Feasibility test done on Adrian's Mac (Sat 21 Nov): the whole chain runs. 256 tiny candidates train in one batch at about 1,600 per minute, about 59 times the one-at-a-time rate on the same GPU and about 29 times the one-at-a-time rate on the CPU. One small model was compiled to 2,330 gates and gives the same answer as the model on all 3,880 test windows. Its accuracy is still poor (F1 0.68 against 0.88 for the full-precision reference), and the best larger model did not finish synthesis in 11 minutes. Details and rerun commands: `spike/README.md`.

The checked evidence will be in `docs/evidence.md`.

## Layout

- `README.md`: this page.
- `BUILT-TODAY.md`: what was brought in and what was built at the event.
- `docs/event.md`: dates, venue, rules, judging, prizes.
- `docs/idea.md`: the idea in full, with cautions and open questions.
- `docs/environment.md`: the design environment: stages, views, first run.
- `docs/evidence.md`: checked evidence on prior work, data and tools.
- `context/` is not on `main`. Adrian's raw context (transcripts, Granola notes, the judging slide, research notes) is on the branch `amg/context`.
