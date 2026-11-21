# Ideas considered

Every idea so far, grouped by where it came from. Panels scored each
idea out of 35 on seven criteria (hardware, AI-for-science loop,
biology, visual, parallelism or sponsor fit, feasibility, honesty;
the technical-judges panel swapped biology for judge appeal).
Headline numbers are what the project would report; none exists yet.
Full text, sources and build plans are in [data/](data/).

Common terms:

- **GPU batching**: running thousands of independent simulations in
  one call on a graphics processor.
- **CMA-ES**: an evolutionary optimiser for continuous parameters.
- **Lattice Boltzmann (LBM)**: a fluid-flow solver on a grid where
  each point updates from its neighbours, a good fit for GPUs.

## Team call, 20 Nov (before any panel)

From [the team-call notes](notes/2026-11-20-team-call.md):

- **Dialysis graft geometry simulation**: the lead idea that night;
  see [dialysis-graft.md](dialysis-graft.md).
- **Embryo selection simulation**: simulate many embryo development
  paths for IVF. Dropped: data availability unclear.
- **Colorectal anastomosis geometry**: same flow principle, aimed at
  leaks after bowel surgery. Not taken further.
- **Brain-computer interface or neurochip simulation**. Dropped: no
  hardware access for the weekend.
- **Low-energy defibrillator**: simulate current paths through cells
  to target precisely. Speed concern in urgent clinical use; later
  reborn as Light Switch.
- **Cell colony simulation**. Dropped: single-cell simulation is an
  unsolved multi-year problem; an agent per cell is intractable.
- **AI-designed biochips**: strong overlap with sponsor interests;
  became the biochip panel.

## Panel 1 (heart-chip light patterns ranked first)

Source: [data/idea-panel-1.json](data/idea-panel-1.json). 12 ideas.

1. **Light Switch**, 30/35. Thousands of simulated 2-D heart-cell
   layers run together on a GPU; an AI agent writes light-pattern
   policies for a real micro-LED grid (Deng et al. 2026) to stop
   spiral-wave arrhythmias, tuned by CMA-ES.
   - Headline: light dose needed for at least 90% termination on
     1,000 held-out states, best agent policy against Deng's
     core-to-border line rule and a whole-field pulse; plus a check
     that simulation reproduces Deng's 0.8-0.9 mm optimal line pitch.
   - Main risk: the heart model is simplified, and spirals can stop on
     their own in small domains; report results net of no-light
     controls and claim only relative rankings.
2. **Sound-Sculpted Tissue**, 26/35. Optimise printable acoustic
   plates by where simulated cells end up, not by the pressure image.
   - Headline: mean overlap (Dice) between simulated cell density and
     target shapes, against standard plates.
   - Main risk: acoustic streaming is not modelled; the GPU load is
     modest and the agent loop thin.
3. **DLD chip designer**, 27/35. GPU lattice Boltzmann search for
   pillar shapes in a cell-sorting chip (deterministic lateral
   displacement) that keep the size cut-off with wider gaps.
   - Headline: gap-widening factor at equal cut-off, circle posts
     validated against the published Davis fit.
   - Main risk: crowded prior art; rigid 2-D particles ignore cell
     softness.
4. **OptoFit**, 27/35. Co-design optogenetic brain implants with GPU
   Monte Carlo light and heat simulation in a mouse brain atlas.
   - Headline: percent of target brain region lit above threshold at
     no more than 1 °C heating, against a single standard fibre.
   - Main risk: tissue optical properties uncertain several-fold;
     needs an NVIDIA GPU and heavy setup.
5. **Wire the Dish**, 26/35. Design channel layouts for neuron
   cultures on chips that keep network activity rich.
   - Headline: richness score of the best layout against the published
     Yamamoto layout.
   - Main risk: the score is noisy; layout-to-wiring link is assumed.

Killed or merged:

- Drug cardiotoxicity screen: simple heart models have no ion
  channels, and population-of-models work already owns the space.
- Programmable living display: no real device, and inverse design of
  gene networks for cell shapes already exists.
- Self-driving lab on a droplet chip: an old chip-design problem with
  weak GPU parallelism and a weak visual.
- Low-energy defibrillation with electrodes: merged into Light Switch,
  where the light version has a real device and lab baselines.
- AI-designed microfluidic sorter, PillarForge, Bump-array designer:
  merged into the DLD chip designer.
- SonoForm: merged into Sound-Sculpted Tissue.
- Spiral-wave breaker: merged into Light Switch.
- Through-skull focus designer: hardest build (25 GB data, 3-D runs
  that failed in prior benchmarks), and gains are thin.
- Bionic-eye layout lab: very close prior art, and so little GPU load
  that judges would see the GPU as optional.
- SpikeSteer: the core stimulation physics would be written from
  scratch, and prior work found no efficiency gain.
- Sperm Slalom: its validation baseline needs a flow the idea made
  optional, and its wall rules are not established.

## Biochip panel

Source: [data/idea-panel-biochip.json](data/idea-panel-biochip.json).
8 ideas. Verdict: none clearly beats Light Switch; DEP-Agent is an
equal alternative.

1. **DEP-Agent**, 30/35. Agent-written electrode patterns and
   frequency schedules for a chip that pulls tumour cells out of blood
   by their electrical properties (dielectrophoresis), checked against
   the commercial ApoStream device.
   - Headline: blood draws processed per hour at at least 70% tumour
     cell recovery and 99.33% white-cell removal, against simulated
     ApoStream (1 draw per hour); plus GPU against CPU throughput.
   - Main risk: an empirical lift term must be calibrated; close
     method prior art, so novelty rests on the agent and scale.
2. **ReadUntil Agent**, 30/35. Agent-written keep-or-eject policies
   for a nanopore DNA sequencing chip, to call antibiotic-resistance
   genes faster.
   - Headline: median simulated hours to a confident resistance-gene
     call, against static and published dynamic policies.
   - Main risk: gains rest on assumed read-error rates; a published
     method (BOSS-RUNS) already does dynamic policies; weak visual.
3. **Zonation-by-design**, 28/35. Agent-designed gas-channel layouts
   that set a realistic oxygen gradient in a liver chip.
   - Headline: error between achieved and target oxygen profile,
     against the published ZoC layout.
   - Main risk: one diffusion solve takes seconds on a CPU, so the GPU
     looks optional.
4. **Field Sculptor**, 28/35. Agent-designed electrode layouts for
   counting blood cells by impedance without focusing hardware.
   - Headline: sizing spread of 6 µm beads against three published
     layouts, after reproducing their measured ranking.
   - Main risk: only rankings can be claimed; diffuse money story.
5. **Drift-Proof Pulse**, 25/35. Agent-designed readout for a
   continuous drug-level sensor (vancomycin) that resists drift.
   - Headline: share of 24-hour readings within ±10% of true level.
   - Main risk: drift model is assumed; GPU close to optional.

Killed:

- Perfusion network designer: a 2025 Science paper already does
  fast vascular-tree design with flow and a 230-fold speedup.
- Gut-chip oxygen gradient on its own: thin design space; folded
  into Zonation-by-design.
- Multi-organ drug-kinetics chip: the model is tiny (GPU optional),
  weak visual, and the needed parameters are hard to extract.
- ITP-Agent urine infection chip: sharp moving fronts are a high
  build risk, and the 10x detection gain is extrapolated.
- Protocol Pilot (heart-drug screening on electrode arrays): crowded,
  overlaps Light Switch, and the models disagree on drug responses.

## Compute-hardware panel

Source: [data/sponsors-and-compute-ideas.json](data/sponsors-and-compute-ideas.json).
8 ideas, judged for fit with the sponsors' hardware.

1. **Bits per Verdict**, 29/35. One general engine, shown on the
   heart-tissue workload: the AI scientist proposes light patterns,
   then finds the fewest bits of precision (and most noise) each
   simulated quantity tolerates before its own conclusion changes.
   - Headline: minimum bits per state variable at which the verdict
     agrees with full precision in at least 95% of runs; measured
     speed and bandwidth use at 64, 32 and 16-bit storage; bytes per
     cell.
   - Main risk: 16-bit storage for flow solvers is known work; the
     defence is that the tolerance is the scientific conclusion.
     Formats below 16 bits are emulated, accuracy only. Never present
     noise as Fractile's chip.
2. **Roofline-Gated Kernel Scientist**, 24/35. An agent rewrites a
   blood-flow LBM kernel for a dialysis graft; a physics check rejects
   any version that changes the answer.
   - Headline: percent of measured memory bandwidth reached, baseline
     against final kernel; cheats caught by the physics gate.
   - Main risk: textbook optimisations; FluidX3D already reaches
     80-85% by hand.
3. **Compute-Routing AI Scientist**, 24/35. For each question about
   graft designs, the agent chooses a learned surrogate, a coarse run
   or a full run, and which device.
   - Headline: confirmed better designs per GPU-hour and per kJ.
   - Main risk: three subsystems in 28 hours; one-node mixing is thin
     evidence for Callosum.
4. **Where an AI Scientist's Seconds and Joules Go**, 23/35. Measure
   how a full AI-scientist loop splits time and energy between model
   output, simulation and analysis.
   - Headline: share of time and energy per discovery in each stage.
   - Main risk: the result is Amdahl's law; thin biology. Better as a
     side panel in rank 1.
5. **Split the Heart**, 24/35. Route the heart model's two kernels
   to different chips.
   - Headline: per-kernel arithmetic intensity and the break-even
     transfer cost.
   - Main risk: only GPUs available, so the measured gain is likely
     zero; the key chip number is from Burchard et al., not ours.

Killed:

- Designing living compute hardware: neuron chips are not the
  sponsors' silicon, so no compute-hardware finding.
- Diverge Less (photon transport): needs GPU features data-centre
  cards probably lack, and rewriting the kernels is too much.
- Bytes per Discovery alone: 16-bit LBM storage is already shown;
  folded into rank 1.
- Bit Budget for the Heart and H2 separately: duplicates, merged into
  rank 1.
- Solver or Surrogate alone: training a usable surrogate on the day
  is high risk; merged into rank 3.
- Two nested loops (kernel plus graft design): doubles integration
  for no extra hardware insight.
- Any projection of Fractile speed, precision or analogue behaviour:
  nothing public supports it.

## Panel 2 (ECG lead lattice ranked first)

Source: [data/idea-panel-2.json](data/idea-panel-2.json). Only four
ideas came in; all survive. Excluded angles from earlier rounds: no
precision study, no roofline kernel tuning, no compute-budget tiers.

1. **Lead Lattice**, 30/35. A general hypothesis engine: an AI
   planner writes experiments, a compiler packs compatible ones into
   one batch of tiny 1-D networks trained together on one GPU. Shown
   on the open PTB-XL heart-rhythm (ECG) data, training a model for
   each of the 4,095 subsets of the 12 leads.
   - Headline: models trained per GPU-hour, packed against
     sequential; how well a cheap one-model shortcut ranks lead
     subsets against per-subset ground truth; 12-lead accuracy
     against the published 0.930 AUC.
   - Main risk: a judge says it is just batching and one masked model
     scores every subset in seconds; the answer is the measured
     shortcut-against-ground-truth agreement.
2. **Starving Tensor Cores**, 28/35. An AI scientist on breast-cancer
   lymph-node slides (CAMELYON16), where image decoding, not
   arithmetic, is the bottleneck.
   - Headline: tiles per second, CPU decode against GPU hardware
     decode.
   - Main risk: three unchecked preconditions (JPEG slides, GPU decode
     engine, a 900 GB download in time). Fallback only after an
     hour-one check.
3. **Which chip should score this mutation?**, 27/35. Route protein
   mutation scoring across model sizes and devices (ProteinGym).
   - Headline: GPU-seconds to get within 0.01 of the best score.
   - Main risk: overlaps the rejected compute-tier angle; needs two or
     more chip types.
4. **Six Million Forward Passes**, 24/35. Genome-wide simulated gene
   knockouts with Geneformer, checked against real Perturb-seq data.
   - Headline: perturbations per GPU-second; agreement with real
     knockdowns.
   - Main risk: heavy data preparation, and simple baselines already
     win in published work.

Framings dropped:

- "Two leads are nearly enough": already shown (CinC 2021; Li and Tao
  2026).
- Citing a 9.2x batching speedup: unverified; the checkable figure is
  "up to 10x" from HiveMind.
- CAMELYON with the full download as main path: too risky without an
  hour-one go or no-go.
- Geneformer screen as the science claim: linear baselines already
  match it.
- "Medium protein model beats large" as headline: already visible in
  the public table.
- ProteinGym on one GPU type: loses the Callosum and Fractile angle.

## Technical-judges panel (21 Nov, biology optional)

Source:
[data/idea-panel-technical-judges.json](data/idea-panel-technical-judges.json).
8 ideas from three lenses (the hardware itself, the AI scientist as
a workload, the event's listed challenges), then a judge. Written for
judges who are technical and know little biology, with biology
optional.

This panel's judge did NOT have the organisers' judging slide. It
scored on its own seven criteria (compute hardware, AI-scientist loop
and generality, technical-judge appeal, visual, sponsor relevance,
weekend feasibility, honesty), each out of 5.

1. **Tokens per second to discoveries per hour**, 31/35. An
   OpenEvolve loop (a model proposes a program, a sandbox scores it,
   the best feed the next prompt) on circle packing with n=26, using
   local models of three sizes. Throttled runs of the same model
   change speed without changing quality, which separates the two.
   A replay simulator fitted on the logs projects discovery time to
   about 1,200 tokens/s.
   - Headline: how much faster discovery gets per token-rate
     speed-up over an 8x throttle range; small-fast against
     large-slow time and energy to a target score; simulator error on
     a held-out setup; scores against AlphaEvolve 2.63586276 and
     ThetaEvolve 2.6359857.
   - Main risk: high run-to-run variance; small models may not reach
     2.63, so use lower targets and medians over 3 seeds. If the
     scorer dominates wall-clock, faster tokens barely help.
2. **How many bits does an Ising machine need?**, 29/35. Thousands of
   batched simulated-bifurcation solvers on Max-Cut with quantised
   couplings and injected analogue noise; an agent maps bits against
   noise and tests hypotheses about how they interact.
   - Main risk: reads as "just quantisation"; the state-precision
     sweep is already published; weak Fractile link.
3. **Agent tunes a lattice Boltzmann blood-flow kernel**, 27/35. An
   existing idea: a physics check gates each kernel version and a
   live roofline plot shows bandwidth reached.
   - Main risk: a kernel optimiser, not a general hypothesis engine;
     LLM kernel tuning is crowded.
4. **How much analogue noise can an LLM take?**, 26/35. Simulated
   noisy in-memory inference of Llama-3.2-1B; an agent ranks the
   hardware imperfections and tries training-free fixes.
   - Main risk: training-free fixes were published this month
     (Karfakis and Gupta), so the best case is rediscovery.
5. **Speculative experiments**, 26/35. A small model guesses the AI
   scientist's next shift-and-stack search for faint asteroids (a
   listed challenge) and the GPU runs it while the large model
   thinks; kept only if the large model picks the same experiment.
   - Main risk: exact matches may be rare; hardest build (2/5).
6. **When does a thermodynamic computer beat a GPU?**, 24/35. A
   batched simulation of noisy analogue Langevin hardware; an agent
   finds which imperfection moves the crossover with a GPU solve.
   - Main risk: validation mostly qualitative; judges may not know
     thermodynamic computing.

Killed:

- Existing heart-tissue bits and noise (Bits per Verdict) and the
  ECG lead subsets (Lead Lattice): dropped as too biological for
  technical judges; the ECG idea was also called batch packing with
  no real hypothesis loop.
- Existing compute routing (surrogate, coarse or full run): generic,
  no measured chip result.
- Existing time and energy breakdown of one AI-scientist loop:
  superseded by rank 1.
- Memory-first chip design search (LLMCompass): least visual, crowded.
- Cache-shared hypothesis swarm: prefix caching is a stock feature;
  folded into rank 1 as an optional knob.
- Co-scheduling an LLM and a Gray-Scott simulation on one GPU (23/35):
  no control of memory-bandwidth sharing; overlaps the ECG packing.

The panel recommended rank 1, with rank 2 as backup if model serving
fails by hour 4. Its 26-hour plan is in the JSON file.

## Claude's re-scoring against the judging slide (21 Nov)

This is Claude's own scoring after the panels, not a panel result. It
rates the leading ideas on the four criteria from the organisers'
slide (see [README.md](README.md#judging)): correctness, fundamental
reshaping, meaningful speed-up, scientific value.

- **Faster AI, faster discovery** (tokens per second idea):
  correctness good; fundamental reshaping only if the loop itself is
  made parallel; speed-up good; scientific value good for AI for
  science.
- **ECG leads packed into one GPU job** (Lead Lattice: one model per
  each of the 4,095 PTB-XL lead subsets): strong on all four.
- **Agent that tunes blood-flow code** (kernel tuning): correctness
  strong, reshaping good, speed-up good, scientific value moderate.
- **How many bits an optimiser chip needs** (Ising bits): correctness
  good, reshaping weak, speed-up moderate, scientific value moderate.

Recommendation: build **the parallel AI scientist**. Run the
OpenEvolve circle-packing loop on local models, and turn its
one-proposal-at-a-time loop into 16 or 64 proposals in parallel.

- Report time to a target score against the sequential loop as the
  baseline, and show solution quality is preserved.
- Also measure how discovery speed depends on token rate. This tests
  Fractile's public claim that going from about 40 to about 1,200
  tokens/s compresses a month of work into a day.
- Main risk: run-to-run variance, and small models not reaching
  record scores. Use lower target scores and three repeats per
  setting.
- Fallback: if model serving is not working within two hours of
  getting GPUs, switch to the ECG leads idea.
- First two hours with compute: find the GPU type and count; serve
  one small open model locally and run the OpenEvolve circle-packing
  example against it; go or no-go on one full loop logged end to end
  (tokens, time per call, score).

## Ideas from Saturday afternoon (21 Nov 2026)

These were worked out by Claude directly, not by an idea panel, after
the judging slide, the team profiles, the Discord digest and the Tinker
information were known. Prior-art checks were single web searches, not
exhaustive.

- Adrian's feedback (21 Nov, about 14:45): the two method ideas,
  parallel falsification with error control (idea 1 below) and depth
  or breadth (idea 2 below), are too generic and not specific enough
  to be projects.
- Decision that follows: neither is a project on its own. Parallel
  falsification stays only as the way the AI scientist's hypotheses
  are kept honest inside a concrete project (one slide at most). Depth
  or breadth becomes one measurement inside the chosen project: run
  that project's hypothesis loop with 1, 4, 16 and 64 parallel streams
  and at slowed model speeds, and report validated findings per hour.
- Claude applied the same test to ideas 3 and 4 below (the agent that
  enters the hackathon, and learning scientists on Tinker): both are
  methods without a concrete scientific question and are dropped.
- Lead project as of this point: idea 6 (infrared monitoring of
  newborns), stated as a concrete question: what distorts a newborn's
  brain-oxygen reading, and by how much. Build: a layered model newborn
  head for ages 29 to 44 weeks; two or three virtual sensor spacings
  with the standard calculation that turns detected light into an
  oxygen number; the error is the reported value minus the true value
  set in the simulation. Example hypotheses: a thicker fluid layer
  biases the reading, more at wider spacing; skin pigment lowers the
  reading, most at low oxygen; the error grows as age falls; two sensor
  designs disagree on the same head. Outputs: an error map by age,
  pigment and sensor design, the causes ranked by size, and the
  speed-up against one simulation per setting.
- Adrian's feedback (21 Nov, about 14:50): the ECG leads idea is not
  bad, but the team wants a chip component in every idea.
- Claude's answer for ECG: merge ECG leads with the low-precision idea
  into one question, the smallest chip that still gets the diagnosis
  right. For every subset of the 12 leads and every number of bits and
  noise level, train or evaluate a small model, all packed into one GPU
  job. The output is a chip specification for an always-on heart
  monitor (how many leads, how many bits) with the accuracy lost at
  each step, and a comparison with published low-power ECG chips. The
  medical teammate sets the accuracy loss that is clinically acceptable.
- The same chip component for the infrared idea: add detector noise
  and limited converter bits to the simulated sensor signals, and find
  the cheapest sensor electronics that keep the oxygen error within the
  clinical limit; also report where the simulation's time goes on the
  GPU.
- For any project: the measurement of validated findings per hour
  against model speed and number of parallel streams is the
  inference-chip slide.

1. **Parallel falsification with error control** (Claude's top pick at
   14:00). An AI scientist tests many hypotheses at once. Baseline:
   POPPER (Huang et al., ICML 2025, arXiv 2502.09858, open source), which
   tests one hypothesis through sequential falsification experiments and
   keeps the false-positive rate at or below 0.1 using e-values.
   Reshaping: run hypotheses and tests in parallel and control errors
   with the e-BH procedure (Wang and Ramdas, arXiv 2009.02824), which
   holds the false-discovery rate under any dependence.
   - Correctness evidence: the theorem, plus a shuffled-label copy of the
     data where every discovery is false.
   - Speed-up: validated discoveries per hour against the sequential loop
     at the same error level. Also report discoveries per token, since
     parallel runs adapt less.
   - Hardware result: discoveries per hour against tokens per second and
     number of streams.
   - Medical angle: ECG data (PTB-XL feature tables, to be verified). The
     medical teammate writes an answer key of known true and false facts
     about atrial fibrillation.
   - Risks: a participant on Discord lists massively parallel scientific
     falsification. No parallel version of POPPER was found in one search.
     The nearest result is a NeurIPS 2026 paper on LLM priors in multiple
     testing with e-values.
2. **Depth or breadth: what hardware does an AI scientist need.** The same
   discovery loop at equal total tokens per second, as one fast stream
   against many slow ones. The ShinkaEvolve authors (arXiv 2509.19349) call
   the trade-off between throughput and sample efficiency an open question.
   Speculative execution for agents is already published (Speculative
   Actions, arXiv 2510.04371, ICLR 2026 oral), so the novelty is the
   measurement. Best used as the hardware slide of idea 1.
3. **The AI scientist that enters the hackathon.** An agent takes the
   official challenge codes plus one medical pipeline, proposes parallel
   rewrites, checks that outputs match the original, and reports speed-ups.
   Depends on challenge code the organisers had not posted. Other teams
   have GPU-kernel specialists.
4. **A population of learning scientists on Tinker.** Many adapters
   fine-tuned in parallel. Highest novelty and risk; not recommended with
   24 hours left.
5. **Where scarce biological or bio-inspired computing parts pay off inside
   ordinary computers** (Adrian's idea, 21 Nov). Living-cell and
   bio-inspired chip designs are power-efficient but will stay expensive for
   years, so they cannot go everywhere. Take existing hardware (CPUs, GPUs,
   whole computers, data centres) on one side and those designs on the
   other, and find where adding a limited number of them gives the highest
   return. It is a constrained optimisation: few costly units, many possible
   slots. The aim is to motivate and guide, not to design the devices.
   - Fit: ARIA's Scaling Compute programme sits in its "Nature Computes
     Better" opportunity space, and its first pillar is software simulators
     that map expected performance, power and cost. This idea is that kind
     of map.
   - Evidence, corrected after a literature check (21 Nov, five web searches
     read as summaries, papers not read in full): the first version of this
     line overstated the gap.
   - Peer-reviewed performance numbers do exist, from the groups that built
     the systems: DishBrain (Kagan et al., Neuron 2022), cultured neurons
     learning a simplified Pong; a time-matched comparison in which the
     cultures beat the DQN, A2C and PPO reinforcement-learning agents on sample
     efficiency (Khajehnejad et al., arXiv 2405.16946, journal version 2025);
     Brainoware (Cai et al., Nature Electronics 2023), organoid reservoir
     computing with speech-task accuracy rising from 51% to 78% after two days
     of training; FinalSpark's Neuroplatform paper (Jordan et al., Frontiers in
     Artificial Intelligence 2024), over 1,000 organoids in three years and
     lifetimes above 100 days.
   - Still not found: any measured power per organoid, per neuron or per
     operation; any head-to-head energy benchmark against silicon; any
     independent replication of DishBrain (a 2025 reanalysis reuses the same
     data). The efficiency figures of a million times or more come from
     comparing a 20 W brain with a supercomputer, or from assumed energy per
     synaptic event.
   - System-level figures remain press-level: Cortical Labs' CL1 at about USD
     35,000 per unit, a rack of 30 drawing about 850 to 1,000 W including life
     support, cells lasting up to six months.
   - Consequence for the idea: the advantage on record for living neurons is
     learning from few samples, not energy, so the return model should use
     sample efficiency as the measured benefit and treat energy as an open
     parameter. Bio-inspired silicon (neuromorphic, analogue in-memory) has
     measured energy numbers.
   - Prior art: design-space tools exist (ATHENA from Sandia, NeuroSim). An
     analogue in-memory study shows an Amdahl-style limit and an interface
     bottleneck. No explicit break-even analysis was found in one search.
   - Claude's reframing: turn "where to put them" into "what a device must
     deliver to be worth putting in each slot" (a break-even map). Measure
     real workload profiles; emulate device imperfections (noise, low
     precision, slowness) on the offloaded part and check the result is
     preserved; evaluate thousands of placements in parallel; then solve the
     budgeted placement. Published devices are overlaid at the end;
     living-cell devices are a labelled what-if.
   - Against the judging slide: strong on assumptions and scientific value if
     every parameter is sourced or measured; weak on speed-up unless the
     placement search and emulation are the parallel part.
   - Link to idea 1: it can be the domain that idea 1's engine works on.
     Hypotheses of the form "this component tolerates this imperfection
     within this loss" are tested in parallel with error control.
6. **Infrared light for newborn monitoring** (Adrian's idea, 21 Nov).
   Infrared light for continuous, non-invasive monitoring of newborns,
   an area that may grow and where new science could be opened up.
   - Claude's shaping: an AI scientist proposes hypotheses about what
     distorts a newborn brain-oxygen reading (skull and fluid thickness,
     skin tone, hair, age, sensor design), tests each by simulating
     photons through a head model, thousands at once, with the
     false-discovery control of idea 1.
   - Why it fits the event: the experiments are physics simulations. One
     simulation's saved photon paths can be re-weighted for many
     absorption values, which is the reshaping; the tool documentation
     confirms saved partial paths and photon replay, while the exactness
     of re-weighting was not confirmed from a source and must be shown by
     a numerical test.
   - Verified: SafeBoosC-III (NEJM 2023) found no benefit of
     oximetry-guided care in extremely preterm infants, 35.2% against
     34.0% for death or severe brain injury; the two-year follow-up
     (JAMA Pediatrics 2026) was also null, 47.1% against 48.0%. A phantom
     study (Afshari, Biomedical Optics Express 2022) found readings change
     by up to 15% with simulated melanin, most in a neonatal sensor. A
     null trial does not show the sensors are wrong; it only makes the
     question worth asking.
   - Tools, verified: MCX needs an NVIDIA or AMD GPU and does not run on a
     Mac. MCX-CL runs on Apple silicon, with a documented fault where about
     one run in 20 to 60 returns an empty result. Validation values for a
     slab test case are published (reflectance 0.09734, transmittance
     0.66096).
   - Feasibility on Adrian's Mac (tested 21 Nov, about 14:25):
     - The OpenCL simulator (pmcxcl 0.8.1) installed and ran on the Apple
       M3 Max GPU.
     - Speed, warm: 10 million photons in about 0.3 seconds on a 60-cubed
       slab.
     - Reliability: 0 empty results in 30 runs of 1 million photons (too
       few runs to rule out the documented fault).
     - Published slab test case at 10 million photons: reflectance 0.09674
       against 0.09734, transmittance 0.66041 against 0.66096, both within
       about 0.6%; about 0.3% of the weight was unaccounted for and not
       traced.
     - Path re-use on a two-layer slab: re-weighting saved photon paths for
       a new absorption setting took 0.73 milliseconds, against about 1.3
       to 1.5 seconds for a fresh simulation. The two agreed to 0.22% (0.23%
       on a second run). The fresh run used a different random seed, so
       that gap is sampling noise plus any real error.
     - Verdict: a sweep of thousands of absorption settings is one
       simulation plus thousands of cheap re-weights. Scripts are in the
       session scratch folder `mcx-spike`, not in the repo.
   - Models and data: a UCL database holds 215 newborn head models for 29
     to 44 weeks, with scalp and skull as one label; whether it can be
     downloaded today without a sign-up was not verified. No public
     newborn dataset with near-infrared signals and a ground-truth oxygen
     value was found.
   - Prior work: simulation studies of single error sources exist. No
     newborn sweep of thousands of configurations and no AI
     hypothesis-testing system for tissue optics was found (one search
     pass, not exhaustive).
   - Team fit: the medical teammate owns the clinical question and the size
     of error that matters; the visualisation is photons moving through a
     3-D newborn head.
   - Risks: simulation-only evidence, so conclusions are about models;
     compute on a Mac was tested and is not a blocker (see the feasibility
     result above); five parts to build in a day.
   - Notes: [clinical](notes/2026-11-21-neonatal-ir-clinical.md),
     [computation](notes/2026-11-21-neonatal-ir-computation.md),
     [data and prior work](notes/2026-11-21-neonatal-ir-data.md).

### Team idea: a chip with the model wired in, for medical devices

- **Source**: the team dictated this at about 15:15 on Sat 21 Nov 2026.
  The dictation was cut off mid-sentence.
- **What the team said**: medical devices such as ultrasound machines have
  sensors that feed a pattern-recognition model. The first version ran
  sensor, then AI model, then finding patterns. It then became: design the
  chip for the device instead. An AI loop repeatedly produces and optimises
  a model for one task, and the model's weights are embedded in the chip, so
  the device is as efficient as possible, works offline and keeps patient
  data on the device. Hospital data rules were mentioned.
- **Relation to other ideas**: this is the idea Adrian meant by the
  ultrasound idea, and it is separate from the infrared idea. It is not the
  "Through-skull focus designer" from the first panel (beam steering through
  the skull), which stays dropped. Fact checks on beam steering were started
  by mistake and stopped at about 15:20; nothing from them was kept.
- **Claude's assessment (its own view, 21 Nov)**: the best fit so far for the
  chip steer and for sponsors who build inference chips, and it absorbs the
  earlier "smallest chip that still gets the diagnosis right" idea. Two
  catches. As stated it is generic. Hard-wiring a model into silicon and
  compiling small networks into logic gates are existing work (from memory,
  to be checked: Taalas, hls4ml, FINN, LogicNets, differentiable logic gate
  networks). The judging slide's parallelism and speed-up-against-a-baseline
  criteria are not yet addressed by the pitch.
- **Specific version Claude proposed**: the question "how many logic gates
  does a diagnosis need?". First device: atrial fibrillation detection from a
  single-lead ECG, because Oran ran an AF screening programme and can set the
  clinical line. Loop: an AI scientist proposes tiny networks and input
  choices (sample rate, bits); thousands are trained at once on the GPU (the
  parallelism; the baseline is one at a time); winners are compiled to a gate
  circuit with fixed weights and checked bit for bit against the model.
  Result: a curve of accuracy against gate count, with the clinical line and
  the point where they cross. Visual: the gate circuit lighting up on a
  heartbeat, plus the curve. Ultrasound as a second device only if time
  allows, since images need much larger models.
- **Pitch caution**: say that data never leaves the device. Do not claim the
  law forbids cloud processing; that is unchecked and being checked.
- **Status at about 15:30**: a fact check (prior art, medical chips and data,
  tools on the Mac; notes will be under
  `[local path removed]`) and a test of the
  whole chain on Adrian's Mac (under
  `[local path removed]`) are running. No
  results yet. Adrian has not yet responded to the specific version.
- **Team clarification (about 15:35, Sat 21 Nov 2026)**: the team is not the
  chip supplier. They build the design environment: a place where anyone who
  makes a medical sensing device designs its core chip with AI scientists. The
  device has sensors, a housing and a core chip. The chip takes the sensor
  inputs and does one application-specific job: it may run an AI model, plain
  machine learning, or only combine the inputs. It is optimised for that one
  task as efficiently as possible, with privacy as a further constraint.
- **Team decision**: the team agreed to keep this idea, as heard in the
  dictation.
- **Adrian's demo of the environment**: Adrian then showed what such an
  environment can look like, framed generally rather than for one domain: write
  a prompt, choose compute and agents, run it, and watch several views of the
  design stages. The dictation was cut off there.
- **Claude's view on the framing (21 Nov)**: keep this direction. An
  environment alone is the generic version again, the same problem as ideas 2
  and 4, and the judging slide scores none of its four criteria for a platform.
  The demo should be the environment designing one real chip end to end, with
  numbers.
- **Demo proposed by Claude, mapped to the judging slide**: the prompt is an
  atrial fibrillation detector from a single-lead ECG, with as few logic gates
  as possible at Oran's clinical line. Correctness is the circuit matching the
  model bit for bit on unseen patients. Parallelism is thousands of candidate
  designs trained as one GPU batch, with agents proposing in parallel. Speed-up
  is designs per hour against one at a time, with the circuit against a
  microcontroller given only as a labelled estimate. Scientific value is the
  curve of accuracy against gate count.
- **Second device, only if time allows**: an infrared oxygen calculation, as
  the case where the chip only combines the inputs. It would show that the
  environment is not limited to ECG.
- **Proposed split**: Adrian builds the environment and the GPU batch; Antonio
  builds the views (the design stages, the accuracy curve, the circuit lighting
  up on a heartbeat); Oran owns the clinical line and which errors matter.
- **Declaration**: if the environment is code written before the event, declare
  it, because the event Discord allows pre-written code when it is declared.
- **Housekeeping**: the hackathon folder landed on master as 29227e5dd at about
  15:35 (land log `.worktrees/_logs/land-sota-hackathon-6.log`). This section
  was committed afterwards and still needs a land.
- **Evidence result (about 15:45)**: the concept and even the AF example already exist.
  Closest published work: a LUT-based 1-D CNN for AF on MIT-BIH with F1 up to 95% in
  2,844 LUTs (arXiv 2605.29994, May 2026); logic-gate and LUT networks on ECG at 94.41%
  (arXiv 2609.32854, Sep 2026); a hardware-aware-search wearable AF patch on an FPGA at
  95% accuracy and 3.8 mW. Details in
  `notes/2026-11-21-medical-chip-evidence.md`.
- **What that means (Claude's reading)**: no "first" claim. These become the published
  baselines to match or beat, in the same unit, on the same data. In one search pass,
  no published system was found where a language-model agent generates both the model
  and the circuit in one loop. Not found is not proof of absence.
- **Tools**: the pip build of Yosys runs on macOS arm64 at about half native speed.
  difflogic's fast path needs CUDA, hls4ml targets vendor tools and FINN is Docker-only,
  so the team writes its own small version. Open ECG data (CinC 2017, PTB-XL, MIT-BIH
  AF) needs no account.
- **Privacy wording**: health data is specially protected under GDPR Article 9, with
  exceptions under conditions. Say that keeping data on the device removes the transfer
  question, not that the law forbids cloud processing.
- **Still missing (follow-up running)**: the exact protocol of the closest papers (how
  they split patients), the clinical accuracy bar, a microcontroller baseline, and
  ultrasound facts.
- **Adrian, about 15:50**: the environment he showed the team is all his own code, and
  any part of it may be used. Pre-written code is allowed; the team only has to say what
  was made new during the event. The team wants one shared GitHub repo holding
  everything. Claude offered to create a private one and is waiting for his go; it is
  not created yet.

## Not explored

Three ideation lenses were stopped by model safeguards and never ran:

- Living biochips.
- AI scientists as an inference workload (the biology-framed round).
- The event's official challenges (the biology-framed round).
