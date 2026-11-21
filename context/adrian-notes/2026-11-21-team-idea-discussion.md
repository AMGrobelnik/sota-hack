# Team idea discussion: chip design for medical devices

A Granola note Adrian shared at 14:56 on Sat 21 Nov 2026.

- The project concept is AI-assisted chip design for medical devices.
- The core idea is an environment where AI scientists can design chips
  for medical sensing devices.
- A chip is the core of a medical device: it takes sensor input and
  performs very specific tasks.
- A chip may run an embedded AI or ML model, or may simply combine
  sensor inputs.
- Chips are optimised for efficiency and for the specific application.
- Privacy is a key constraint: medical data cannot go to external
  servers, because of GDPR and hospital policy.
- Hosting the model on the chip keeps data local and secure.
- The domain is any medical device that includes sensors.
- Scope was debated as too broad or too narrow at the extremes; the
  group agreed on sensors in medical devices.
- Examples in scope include ultrasound, biosensors and diagnostics.
- The team would not be a chip supplier; it would build the design
  environment that lets others create chips.
- The potential market is US healthcare, and NHS-scale funding was
  noted as a signal of demand.
- The design environment is an agentic orchestration layer, not just a
  chatbot interface.
- The user writes a prompt describing the chip or task.
- The system starts agents, runs experiments, and proposes and tests
  chip designs iteratively.
- The user gets several views: the current design stage (ideation,
  testing, reporting), live agent commands and outputs, cost tracking,
  and an always-visible sketch or image of the chip design.
- The user can intervene, pause or redirect at any point.
- The chip-design workflow is to generate several candidate designs,
  simulate and validate each, repeat iteratively, and output the best
  design.
- The GPUs serve two purposes: simulating the chip hardware, and running
  small models locally that mirror what would be embedded on the chip.
- The small-model focus matches what some hackathon sponsors are looking
  for.
- The concept is similar in spirit to Idea Labs AI (idea breakdown,
  go-to-market, team planning), but goes further.
- Idea Labs validates ideas; this environment runs real experiments and
  produces research-grade output.
- Pre-written code and existing repos are permitted.
- The transcript and code were already recorded and shared within the
  group.
- Next step: refine the prompt and pitch deck for the concept.
- Next step: flesh out the idea, make it presentable, and prepare to
  pitch it.
- Next step: define domain-specific environment features for chip design.
- Next step: identify the visualisations, stages and tooling specific to
  medical chip design, compared with the general agentic framework shown.
- Next step: share the transcript and codebase with the group.
- Everything was recorded together, so the materials should be circulated
  for all members to build on.

## Use-case discussion, about 15:30 to 15:50

- About 15:31 the team said atrial fibrillation is only one possible use case and not the idea itself. The product is the design environment.
- EEG was proposed as a better use case because it can cover a wider range of conditions, though it is harder.
- A teammate asked whether one chip can report more than one condition from the same sensor.
- Claude's answer: a fixed chip can give several answers at once. It has a shared front part and one small output per condition.
- A fixed chip cannot learn a new condition after it is made, unless the design is loaded on a reloadable chip (an FPGA).
- The user's prompt should list the conditions, and the environment should report what each extra one costs in gates.
- Adrian asked for a fertility-medicine use case. He said EEG is attractive because brain-wave data is extremely sensitive.
- Adrian's concern: the use cases mostly amount to putting an AI model on top of a sensor.
- Claude's answer, part (a): the finished device holds no AI model. It holds only a small gate circuit that AI was used to find.
- Part (b): the result is a measurement, namely how many logic gates a diagnosis needs. Each use case is one point on that scale.
- Part (c): privacy becomes a hardware property. The chip outputs only the answer and has no software that could be changed to send raw data.
- Fertility candidate proposed by Claude (facts still being checked): a fertile-window chip inside a ring, patch or vaginal sensor. It outputs only "fertile today" and "ovulation confirmed".
- Stated weakness: the signal is slow, so the battery saving is negligible. The claim rests on privacy and on how few gates it takes.

## About 16:10

- The team validated the idea with a person at the event (no details recorded yet). It is now choosing application domains and a project name.
