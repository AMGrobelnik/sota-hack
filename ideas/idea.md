# The idea in full

## What the team said

Medical devices such as ultrasound machines have sensors that feed a
pattern-recognition model. The first version was: sensor, then AI
model, then finding patterns. It then became: design the chip for the
device instead.

An AI loop repeatedly produces and optimises a model for one task. The
model's weights are embedded in the chip. So the device is as efficient
as possible, works offline and keeps patient data on the device.
Hospital data rules were mentioned.

## The design environment

The team is not the chip supplier. We build the place where anyone who
makes a medical sensing device designs its core chip with AI
scientists.

- The device has sensors, a housing and a core chip.
- The chip takes the sensor inputs and does one job for one
  application. It may run an AI model, plain machine learning, or only
  combine the inputs.
- It is optimised for that one task as efficiently as possible, with
  privacy as a further constraint.

Adrian showed what such an environment can look like: write a prompt,
choose compute and agents, run it, and watch several views of the
design stages.

An environment alone is too generic, and the judging slide scores none
of its four criteria for a platform. So the demo is the environment
designing one real chip from start to finish, with numbers.

## The specific demo

The question: how many logic gates does a diagnosis need?

First device: atrial fibrillation (AF) detection from a single-lead
ECG. Oran has run an AF screening programme and can set the clinical
line.

The loop:

1. An AI scientist proposes tiny networks and input choices (sample
   rate, bits).
2. Thousands are trained at once on the GPU. That is the parallelism.
   The baseline is one at a time.
3. The winners are compiled to a gate circuit with fixed weights.
4. The circuit is checked bit for bit against the model.

The result: a curve of accuracy against gate count, with the clinical
line and the point where they cross.

The visual: the gate circuit lighting up on a heartbeat, plus the
curve.

The stages, views and first run are in `ideas/environment.md`. The
comparison target is a published AF design (arXiv 2605.29994) on the
same database. We plan to compare on patients the model never saw,
with a full curve of accuracy against size.

## Mapping to the judging slide

- **Correctness and assumptions**: the circuit matches the model bit
  for bit on unseen patients.
- **Fundamental reshaping**: thousands of designs trained as one GPU
  batch; agents propose in parallel.
- **Meaningful speedup**: designs per hour against one at a time. The
  circuit against a microcontroller is only a labelled estimate.
- **Scientific value**: the curve of accuracy against gate count.

## Optional second device

Only if time allows: an infrared oxygen calculation, the case where the
chip only combines the inputs. It would show that the environment is
not limited to ECG.

Ultrasound as a second device is less likely, since images need much
larger models.

## Also considered

- Infrared light for newborn brain-oxygen monitoring: what distorts the
  reading, and by how much, found by simulating light through a head
  model. Kept as the possible second device.
- ECG with the smallest chip that still gets the diagnosis right: now
  absorbed into this idea.

## Pitch cautions

- Say that data never leaves the device.
- Do not claim the law forbids cloud processing. That is unchecked.
- As stated, the idea is generic. The pitch must lead with the concrete
  AF demo and its numbers.
- The slide's parallelism and speed-up criteria need to be shown
  explicitly.

## Published work that already exists

From memory, not yet checked: Taalas, hls4ml, FINN, LogicNets and
differentiable logic gate networks. Hard-wiring a model into silicon
and compiling small networks into logic gates are existing work. So
the claim is not "first to compile a network to gates". The claim is
the automated, parallel design loop and the accuracy-against-gate-count
result for a clinical task. Checked evidence goes in `evidence.md`.

## What is still unknown

- Whether the whole chain works end to end. A feasibility test on
  Adrian's Mac is running.
- Which published work overlaps, and how closely (see `evidence.md`).
- Which data and tools are usable on the day.
- The clinical accuracy line, which Oran sets.
- The law on cloud processing of patient data. Unchecked.
