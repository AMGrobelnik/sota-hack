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
