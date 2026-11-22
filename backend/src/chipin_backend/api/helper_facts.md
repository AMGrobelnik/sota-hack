# ChipIn fact sheet for Chippy

Drawn from the backend README and the how-it-works page. Each section is one
topic for the product_facts tool.

## product

ChipIn is an AI-scientist environment that designs the small chip at the core
of a medical sensing device. The user describes the device; agents propose
small models, train many at once, compile them into logic gates with the
weights wired in as constants, check the gates bit for bit against the model,
and return the smallest chip that clears the user's clinical bar. Each run is
a folder on disk: its events, its record, the spec, the designs, the report
and the files the agent wrote. ChipIn is a feasibility tool; its results are
not clinical evidence.

## stages

A run goes through seven stages, in order; each is started, done or skipped
(a skipped stage carries a short reason). An orchestrator agent briefs each
stage, and subagents can work on one stage in parallel.
1. Spec: pins down the device, signal, targets and constraints, and the data
   split by patient.
2. Reference: trains a full-precision model with no chip limits. It sets the
   accuracy to beat and never goes on a chip.
3. Propose: proposes candidate small designs, with estimated sizes.
4. Finetune: trains the candidates, many at once, and scores them on patients
   not seen in training.
5. Compile: turns each design into logic gates with the weights wired in, and
   gives its gate count, logic depth and netlist.
6. Verify: runs the gates on test vectors and compares them bit for bit with
   the model, then proves formally that they agree. A design with a mismatch
   is dropped.
7. Report: lays out and costs the chosen chip where the tools are available,
   and writes the report. The run names one chosen chip.

## marks

How numbers are marked on the page:
- Measured: shown plain. Gate count, logic depth, mismatches, verification
  level, and scores on unseen patients.
- Estimate: marked "estimate", with its assumption. Power, area and cost come
  from layout tools in one open 130 nm process; sizes before synthesis in the
  propose stage are estimates too.
- Simulated: marked "simulated". Simulated data chosen at intake, and demo
  runs on the dashboard. A score measured on simulated data is a measurement
  of the design on that simulated data, not on patients.
Every number on the dashboard comes from a tool's answer, not from a model's
text.

## tabs

A run page has six tabs:
- Overview: the run's targets, the trade-off chart of chip size against one
  metric, the designs, the selected design, the stages and the run clock.
- Where it fails: the selected design's results per patient (or per
  recording), worst first, judged against the targets.
- Signal: an illustration of the signals named in the brief and the event the
  chip must detect.
- Chip: the chip of the selected design, once the first designs are checked.
  Power figures are not estimated in this version.
- Chat: the run's messages; on a live run the user can write to the running
  agent here.
- Sources: where the run's data and figures come from.

## flow

A brief on the start page opens a guided flow of five steps, one question
group each, every question with a default:
1. The device: what it is and what it must detect.
2. Who and where: the patient group, where it is used and who responds; this
   sets the false-alarm unit (per hour on a ward, per night or per day at
   home).
3. Targets: the bar the chip must clear, a metric and a threshold defaulted
   by task type (event monitoring: sensitivity and false alarms per hour or
   per day; screening: sensitivity and specificity; grading: agreement with
   experts).
4. Constraints: how many electrodes or sensors, battery life, disposable or
   reusable.
5. Data: the user's own recordings, an open dataset with a card of what it
   holds, or simulated data, labelled as simulated.
Then the Your spec card shows the spec, the run size and the agent, and Run
starts it. Patients are split so that none is in both training and test, and
every design is judged on the worst unseen patient.

## presets

The run size is a preset: Lite, Pro, Max or Ultra. On the page a preset sets
how many rounds and designs a new run tries (Lite 3 rounds, Pro 4, Max 5,
Ultra 5, with more candidates per round at each step up). On the local
backend the preset sets the agent's effort: Lite low, Pro high, Max xhigh,
Ultra max. The agent and model are chosen separately: Claude by default, or a
model through OpenRouter such as Inkling 2.

## checks

Each design carries a verification level, the highest it has passed:
level 1 bit-exact simulation, level 2 formal proof of equivalence, level 3
streaming RTL simulation and lint, level 4 gate-level test after layout,
level 5 real hardware (never set automatically). After a run the backend can
compute its evidence from the run folder alone: a number check that puts each
number of the report in "no source", "value found, unit or meaning unclear"
or "source found"; the weight bytes software would read per decision for one
chip (none when the weights are constants in the logic); and the wall time of
each stage.

## limits

ChipIn is a feasibility tool and its results are not clinical evidence. The
device maker keeps clinical validation and regulatory responsibility. Power,
area and cost are estimates from layout tools in one open process. Demo runs
are simulated unless marked as measured.

## chippy

Chippy is the dashboard's guide. It reads runs and the product's own
explanations, answers questions, and moves the page (route, run, tab, design,
playback time, file, new spec, highlight). It never starts, messages or stops
a run itself: it offers a button and the user decides. It does not design
chips; the design agent is reached through the run's Chat tab.
