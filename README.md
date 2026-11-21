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

Nothing is built yet. A feasibility test of the whole chain is running
on Adrian's Mac. The checked evidence will be in `docs/evidence.md`.

## Layout

- `README.md`: this page.
- `BUILT-TODAY.md`: what was brought in and what was built at the event.
- `docs/event.md`: dates, venue, rules, judging, prizes.
- `docs/idea.md`: the idea in full, with cautions and open questions.
- `docs/environment.md`: the design environment: stages, views, first run.
- `docs/evidence.md`: checked evidence on prior work, data and tools.
- `context/`: raw context: transcripts, Granola notes, the judging slide, research notes.
